from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.api import agent, analytics, audit, auth, chat, kb, tickets, users
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import engine, init_db
from app.models.entities import BotConfig, User, UserRole
from app.services.knowledge import seed_ecommerce_kb


def bootstrap_defaults() -> None:
    with Session(engine) as session:
        if session.exec(select(User).where(User.username == "admin")).first() is None:
            session.add(
                User(
                    username="admin",
                    display_name="系统管理员",
                    role=UserRole.admin,
                    password_hash=hash_password("Admin123!"),
                )
            )
        if session.exec(select(BotConfig)).first() is None:
            session.add(BotConfig())
        session.commit()
        seed_ecommerce_kb(session)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    bootstrap_defaults()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(kb.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}
