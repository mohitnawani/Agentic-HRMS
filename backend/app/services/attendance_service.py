import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance, AttendanceStatus
from app.models.leave import LeaveRequest, LeaveRequestStatus, LeaveType
from app.schemas.attendance import AttendanceCorrection

# office policy: 9 AM – 6 PM, Saturday/Sunday off
WORK_START = datetime.time(9, 0)
WORK_END = datetime.time(18, 0)
EXPECTED_WORK_MINUTES = 9 * 60


def _is_weekend(day: datetime.date) -> bool:
    return day.weekday() >= 5


async def check_in(db: AsyncSession, employee_id: uuid.UUID) -> Attendance:
    today = datetime.date.today()
    existing = await db.execute(
        select(Attendance).where(Attendance.employee_id == employee_id, Attendance.date == today)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already checked in today")

    record = Attendance(
        employee_id=employee_id,
        date=today,
        check_in=datetime.datetime.now(),
        status=(
            AttendanceStatus.LATE
            if datetime.datetime.now().time() > WORK_START
            else AttendanceStatus.PRESENT
        ),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def check_out(db: AsyncSession, employee_id: uuid.UUID) -> Attendance:
    today = datetime.date.today()
    result = await db.execute(
        select(Attendance).where(Attendance.employee_id == employee_id, Attendance.date == today)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No check-in found for today")
    if record.check_out is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already checked out today")

    record.check_out = datetime.datetime.now()
    if record.check_out.time() < WORK_END:
        record.status = AttendanceStatus.HALF_DAY  # left before 6 PM
    await db.commit()
    await db.refresh(record)
    return record


async def get_history(
    db: AsyncSession, employee_id: uuid.UUID, start: datetime.date | None = None, end: datetime.date | None = None
) -> list[Attendance]:
    query = select(Attendance).where(Attendance.employee_id == employee_id)
    if start:
        query = query.where(Attendance.date >= start)
    if end:
        query = query.where(Attendance.date <= end)
    result = await db.execute(query.order_by(Attendance.date.desc()))
    return list(result.scalars().all())


async def get_monthly_summary(db: AsyncSession, employee_id: uuid.UUID, year: int, month: int) -> dict:
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month + 1, 1) if month < 12 else datetime.date(year + 1, 1, 1)
    result = await db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee_id,
            Attendance.date >= start,
            Attendance.date < end,
        )
    )
    records = list(result.scalars().all())
    counts = {s: 0 for s in AttendanceStatus}
    for r in records:
        counts[r.status] += 1
    return {
        "total_days": len(records),
        "present": counts[AttendanceStatus.PRESENT],
        "absent": counts[AttendanceStatus.ABSENT],
        "late": counts[AttendanceStatus.LATE],
        "half_day": counts[AttendanceStatus.HALF_DAY],
    }


async def correct_attendance(
    db: AsyncSession, attendance_id: uuid.UUID, corrected_by: uuid.UUID, data: AttendanceCorrection
) -> Attendance:
    result = await db.execute(select(Attendance).where(Attendance.id == attendance_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")

    if data.check_in is not None:
        record.check_in = data.check_in
    if data.check_out is not None:
        record.check_out = data.check_out
    if data.status is not None:
        record.status = data.status
    record.corrected_by = corrected_by
    record.correction_reason = data.correction_reason

    await db.commit()
    await db.refresh(record)
    return record


def _month_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month + 1, 1) if month < 12 else datetime.date(year + 1, 1, 1)
    return start, end


async def get_month_calendar(
    db: AsyncSession, employee_id: uuid.UUID, date_of_joining: datetime.date, year: int, month: int
) -> list[dict]:
    """One cell per calendar day: stored punches + weekend/leave/absence overlay.

    Resolution per day: before_joining > punch record > approved leave >
    pending leave > weekend > absent (past) > upcoming (today/future).
    """
    start, end = _month_bounds(year, month)
    today = datetime.date.today()

    result = await db.execute(
        select(Attendance).where(
            Attendance.employee_id == employee_id,
            Attendance.date >= start,
            Attendance.date < end,
        )
    )
    by_date = {r.date: r for r in result.scalars().all()}

    leave_result = await db.execute(
        select(LeaveRequest, LeaveType.name).join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_([LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING]),
            LeaveRequest.start_date < end,
            LeaveRequest.end_date >= start,
        )
    )
    leave_by_date: dict[datetime.date, dict] = {}
    for req, type_name in leave_result.all():
        day = max(req.start_date, start)
        last = min(req.end_date, end - datetime.timedelta(days=1))
        while day <= last:
            # approved wins over pending on overlap
            existing = leave_by_date.get(day)
            if existing is None or req.status == LeaveRequestStatus.APPROVED:
                leave_by_date[day] = {"leave_name": type_name, "leave_status": req.status.value}
            day += datetime.timedelta(days=1)

    days: list[dict] = []
    day = start
    while day < end:
        cell: dict = {"date": day, "is_weekend": _is_weekend(day), "before_joining": day < date_of_joining}
        record = by_date.get(day)
        leave = leave_by_date.get(day)
        if cell["before_joining"]:
            cell["state"] = "before_joining"
        elif record is not None:
            worked = None
            if record.check_in and record.check_out:
                worked = int((record.check_out - record.check_in).total_seconds() // 60)
            cell.update({
                "state": record.status.value,
                "attendance_id": record.id,
                "check_in": record.check_in,
                "check_out": record.check_out,
                "worked_minutes": worked,
                "overtime_minutes": (worked - EXPECTED_WORK_MINUTES) if worked is not None else None,
                "missing_punch": record.check_in is not None and record.check_out is None,
            })
        elif leave is not None:
            cell["state"] = "on_leave" if leave["leave_status"] == "approved" else "leave_pending"
            cell.update(leave)
        elif cell["is_weekend"]:
            cell["state"] = "weekend"
        elif day < today:
            cell["state"] = "absent"
        else:
            cell["state"] = "upcoming"
        days.append(cell)
        day += datetime.timedelta(days=1)
    return days