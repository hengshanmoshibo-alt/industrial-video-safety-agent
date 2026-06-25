from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.entities import AuditLog, User, UserRole

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def list_logs(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.auditor])),
):
    return session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()
