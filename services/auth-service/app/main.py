from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from aicoding_shared.db import engine
from aicoding_shared.db import get_session
from aicoding_shared.models import Channel, ChannelType, Department, Role, Tenant, User, UserRole
from aicoding_shared.security import create_access_token, hash_password, require_roles, verify_password
from aicoding_shared.service import create_service_app


class LoginIn(BaseModel):
    username: str
    password: str
    tenant: str = "default"


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    role: UserRole = UserRole.agent
    department_id: int | None = None


class UserPatch(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: UserRole | None = None
    department_id: int | None = None
    data_scope: str | None = None
    is_active: bool | None = None


class TenantCreate(BaseModel):
    slug: str
    name: str
    plan: str = "enterprise"


class DepartmentCreate(BaseModel):
    name: str
    parent_id: int | None = None


class RoleCreate(BaseModel):
    name: str
    description: str = ""
    permissions: list[str] = []


def bootstrap() -> None:
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == "default")).first()
        if tenant is None:
            tenant = Tenant(slug="default", name="默认企业")
            session.add(tenant)
            session.flush()
        if session.exec(select(Department).where(Department.tenant_id == tenant.id)).first() is None:
            session.add(Department(tenant_id=tenant.id, name="客服中心"))
        if session.exec(select(Role).where(Role.tenant_id == tenant.id, Role.name == "admin")).first() is None:
            session.add(Role(tenant_id=tenant.id, name="admin", description="系统管理员", permissions=["*"]))
        if session.exec(select(User).where(User.tenant_id == tenant.id, User.username == "admin")).first() is None:
            session.add(
                User(
                    tenant_id=tenant.id,
                    username="admin",
                    display_name="系统管理员",
                    role=UserRole.admin,
                    password_hash=hash_password("Admin123!"),
                )
            )
        if session.exec(select(Channel).where(Channel.tenant_id == tenant.id, Channel.type == ChannelType.web)).first() is None:
            session.add(Channel(tenant_id=tenant.id, name="官网网页客服", type=ChannelType.web))
        session.commit()


app = create_service_app("auth-service", bootstrap=bootstrap)


@app.post("/auth/login")
def login(payload: LoginIn, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == payload.tenant, Tenant.is_active == True)).first()  # noqa: E712
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid tenant")
    user = session.exec(select(User).where(User.tenant_id == tenant.id, User.username == payload.username)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "access_token": create_access_token(user.username, tenant.id, user.role.value, {"user_id": user.id}),
        "token_type": "bearer",
        "tenant_id": tenant.id,
        "role": user.role,
        "display_name": user.display_name,
    }


@app.get("/tenants")
def list_tenants(_: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    return session.exec(select(Tenant).order_by(Tenant.id)).all()


@app.post("/tenants")
def create_tenant(payload: TenantCreate, _: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    tenant = Tenant(**payload.model_dump())
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@app.get("/departments")
def list_departments(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    return session.exec(select(Department).where(Department.tenant_id == user.tenant_id)).all()


@app.post("/departments")
def create_department(payload: DepartmentCreate, user: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    if payload.parent_id is not None:
        parent = session.get(Department, payload.parent_id)
        if parent is None or parent.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="Parent department not found")
    department = Department(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


@app.get("/roles")
def list_roles(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    return session.exec(select(Role).where(Role.tenant_id == user.tenant_id)).all()


@app.post("/roles")
def create_role(payload: RoleCreate, user: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    role = Role(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@app.get("/users")
def list_users(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    return session.exec(select(User).where(User.tenant_id == user.tenant_id).order_by(User.id)).all()


@app.post("/users")
def create_user(payload: UserCreate, user: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    created = User(
        tenant_id=user.tenant_id,
        department_id=payload.department_id,
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    session.add(created)
    session.commit()
    session.refresh(created)
    return created


@app.patch("/users/{user_id}")
def patch_user(user_id: int, payload: UserPatch, user: User = Depends(require_roles([UserRole.admin])), session: Session = Depends(get_session)):
    target = session.get(User, user_id)
    if target is None or target.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    if password:
        target.password_hash = hash_password(password)
    for key, value in changes.items():
        setattr(target, key, value)
    session.add(target)
    session.commit()
    session.refresh(target)
    return target
