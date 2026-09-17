import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance, AttendanceStatus
from app.schemas.attendance import AttendanceCorrection


async def check_in(db: AsyncSession, employee_id: uuid.UUID) -> Attendance:
    today = datetime.date.today()
    existing = await db.execute(
        select(Attendance).where(Attendance.employee_id == employee_id, Attendance.date == today)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already checked in today")

    record = Attendance(employee_id=employee_id, date=today, check_in=datetime.datetime.now())
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