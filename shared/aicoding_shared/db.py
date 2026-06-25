import time
from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from aicoding_shared.config import get_settings


def _connect_args() -> dict[str, bool]:
    if get_settings().database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(get_settings().database_url, echo=False, pool_pre_ping=True, connect_args=_connect_args())


def _json_type_sql(dialect_name: str) -> str:
    if dialect_name == "postgresql":
        return "JSONB"
    return "JSON"


def _default_sql(dialect_name: str, value: str) -> str:
    if dialect_name == "postgresql" and value == "{}":
        return "DEFAULT '{}'::jsonb"
    if dialect_name == "postgresql" and value == "[]":
        return "DEFAULT '[]'::jsonb"
    return f"DEFAULT '{value}'"


def _ensure_compat_columns() -> None:
    """Keep SQLModel create_all viable for the demo database without Alembic."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    json_type = _json_type_sql(dialect)
    desired: dict[str, list[tuple[str, str, str | None]]] = {
        "videoauditagentrun": [
            ("current_stage", "VARCHAR", "''"),
            ("paused_reason", "TEXT", "''"),
            ("final_decision", json_type, "{}"),
        ],
        "videoauditagentstep": [
            ("artifact_refs", json_type, "[]"),
        ],
        "videomemorysegment": [
            ("vlm_raw_output", json_type, "{}"),
            ("review_status", "VARCHAR", "'unreviewed'"),
        ],
    }
    with engine.begin() as connection:
        for table, columns in desired.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, type_sql, default_value in columns:
                if name in existing:
                    continue
                default_clause = ""
                if default_value is not None:
                    if default_value in {"{}", "[]"}:
                        default_clause = " " + _default_sql(dialect, default_value)
                    else:
                        default_clause = f" DEFAULT {default_value}"
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {type_sql}{default_clause}"))


def _ensure_compat_enums() -> None:
    """Add enum values introduced after the original demo schema was created."""
    if engine.dialect.name != "postgresql":
        return
    enum_values: dict[str, list[str]] = {
        "agentrunstatus": ["running", "waiting_review", "waiting_remediation", "completed", "failed"],
        "videorisklevel": ["low", "medium", "high", "critical", "needs_review"],
        "videoauditstatus": ["queued", "processing", "completed", "needs_review", "failed"],
        "ticketverificationstatus": ["passed", "failed", "needs_review"],
        "videoauditreviewdecision": ["confirmed_violation", "false_positive", "needs_more_evidence"],
    }
    with engine.begin() as connection:
        for enum_name, values in enum_values.items():
            exists = connection.execute(
                text("SELECT 1 FROM pg_type WHERE typname = :enum_name"),
                {"enum_name": enum_name},
            ).first()
            if exists is None:
                continue
            for value in values:
                connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def init_db() -> None:
    from aicoding_shared import models  # noqa: F401

    last_error: Exception | None = None
    for _ in range(30):
        try:
            SQLModel.metadata.create_all(engine)
            _ensure_compat_enums()
            _ensure_compat_columns()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError("Database is not ready") from last_error


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def check_database() -> bool:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return True
    except Exception:
        return False
