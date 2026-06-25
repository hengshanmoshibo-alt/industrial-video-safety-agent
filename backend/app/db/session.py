from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def _connect_args() -> dict[str, bool]:
    if get_settings().database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(get_settings().database_url, echo=False, connect_args=_connect_args())


def init_db() -> None:
    from app.models.entities import (  # noqa: F401
        AuditLog,
        BotConfig,
        Conversation,
        KnowledgeChunk,
        KnowledgeDocument,
        Message,
        Role,
        Ticket,
        TicketComment,
        User,
    )

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
