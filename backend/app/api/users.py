from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_session
from app.models.entities import AuditLog, User, UserRole
from app.schemas.api import UserCreate, UserOut, UserPatch

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])),
):
    return session.exec(select(User).order_by(User.id)).all()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin])),
):
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.flush()
    session.add(AuditLog(actor_id=actor.id, action="user.create", target_type="user", target_id=str(user.id)))
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    user_id: int,
    payload: UserPatch,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin])),
):
    user = session.get(User, user_id)
    if user is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="User not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "password":
            user.password_hash = hash_password(value)
        else:
            setattr(user, key, value)
    session.add(AuditLog(actor_id=actor.id, action="user.patch", target_type="user", target_id=str(user.id)))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
