from fastapi import APIRouter, Depends

from app.core.deps import require_permission
from app.models.user import User

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/_permission_test")
async def permission_test(current_user: User = Depends(require_permission("demo:hr_only"))):
    return {"message": f"Hello {current_user.email}, you have HR-level access."}