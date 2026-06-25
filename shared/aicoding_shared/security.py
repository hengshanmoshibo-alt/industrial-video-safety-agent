from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.models import Tenant, User, UserRole


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(username: str, tenant_id: int, role: str, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "sub": username,
        "tenant_id": tenant_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    tenant_id = x_tenant_id or int(payload["tenant_id"])
    user = session.exec(
        select(User).where(User.username == payload["sub"], User.tenant_id == tenant_id, User.is_active == True)  # noqa: E712
    ).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def tenant_from_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
    session: Session = Depends(get_session),
) -> Tenant:
    if x_tenant_id is not None:
        tenant = session.get(Tenant, x_tenant_id)
        if tenant is None:
            raise HTTPException(status_code=401, detail="Tenant not found")
        return tenant
    if credentials is None:
        tenant = session.exec(select(Tenant).where(Tenant.slug == get_settings().default_tenant_slug)).first()
        if tenant is None:
            tenant = Tenant(slug=get_settings().default_tenant_slug, name="默认企业")
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
        return tenant
    payload = decode_token(credentials.credentials)
    tenant = session.get(Tenant, int(payload["tenant_id"]))
    if tenant is None:
        raise HTTPException(status_code=401, detail="Tenant not found")
    return tenant


def require_roles(roles: list[UserRole]):
    allowed = set(roles)

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dep
