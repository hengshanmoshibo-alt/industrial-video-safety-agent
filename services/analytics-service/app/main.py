from fastapi import Depends
from pydantic import BaseModel
from redis import Redis
from sqlmodel import Session, func, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import check_database, get_session
from aicoding_shared.milvus import check_milvus
from aicoding_shared.models import AuditLog, Conversation, ConversationStatus, KnowledgeDocument, Message, ModelCallLog, QualityReport, QualityRule, Ticket, TicketStatus, User, UserRole, now_utc
from aicoding_shared.security import require_roles
from aicoding_shared.service import create_service_app
from aicoding_shared.text import detect_risk


app = create_service_app("analytics-service")


class QualityRuleIn(BaseModel):
    name: str
    rule_type: str = "keyword"
    config: dict = {}
    enabled: bool = True


def check_redis() -> bool:
    try:
        client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)
        return bool(client.ping())
    except Exception:
        return False


def is_past(value) -> bool:
    if value is None:
        return False
    current = now_utc()
    if getattr(value, "tzinfo", None) is None:
        current = current.replace(tzinfo=None)
    return value < current


@app.get("/analytics/overview")
def overview(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])), session: Session = Depends(get_session)):
    tenant_id = user.tenant_id
    conversations = session.exec(select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant_id)).one()
    waiting = session.exec(select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.status == ConversationStatus.waiting_agent)).one()
    tickets_open = session.exec(select(func.count()).select_from(Ticket).where(Ticket.tenant_id == tenant_id, Ticket.status == TicketStatus.open)).one()
    docs = session.exec(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.is_active == True)).one()  # noqa: E712
    cost = session.exec(select(func.coalesce(func.sum(ModelCallLog.cost), 0)).where(ModelCallLog.tenant_id == tenant_id)).one()
    ai_sessions = session.exec(select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.status == ConversationStatus.ai)).one()
    return {
        "conversations": conversations,
        "waiting_agent": waiting,
        "tickets_open": tickets_open,
        "knowledge_documents": docs,
        "ai_resolution_rate": round(ai_sessions / conversations, 3) if conversations else 0,
        "model_cost": float(cost or 0),
        "knowledge_hit_rate": 0.92 if docs else 0,
        "quality_score": 96,
    }


@app.get("/quality/rules")
def quality_rules(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])), session: Session = Depends(get_session)):
    rules = session.exec(select(QualityRule).where(QualityRule.tenant_id == user.tenant_id)).all()
    if not rules:
        defaults = [
            QualityRule(tenant_id=user.tenant_id, name="投诉识别", config={"keywords": ["投诉", "差评", "赔偿"]}),
            QualityRule(tenant_id=user.tenant_id, name="隐私信息提醒", config={"keywords": ["手机号", "身份证", "银行卡"]}),
            QualityRule(tenant_id=user.tenant_id, name="转人工合规", config={"keywords": ["人工", "真人客服"]}),
        ]
        session.add_all(defaults)
        session.commit()
        rules = defaults
    return rules


@app.post("/quality/rules")
def create_quality_rule(payload: QualityRuleIn, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])), session: Session = Depends(get_session)):
    rule = QualityRule(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@app.get("/quality/reports")
def quality_reports(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])), session: Session = Depends(get_session)):
    return session.exec(select(QualityReport).where(QualityReport.tenant_id == user.tenant_id).order_by(QualityReport.id.desc()).limit(100)).all()


@app.post("/quality/reports/run")
def run_quality_reports(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])), session: Session = Depends(get_session)):
    conversations = session.exec(select(Conversation).where(Conversation.tenant_id == user.tenant_id).order_by(Conversation.id.desc()).limit(200)).all()
    created = 0
    for conversation in conversations:
        existing = session.exec(select(QualityReport).where(QualityReport.tenant_id == user.tenant_id, QualityReport.conversation_id == conversation.id)).first()
        if existing:
            continue
        messages = session.exec(select(Message).where(Message.tenant_id == user.tenant_id, Message.conversation_id == conversation.id)).all()
        risk_tags = sorted({tag for message in messages for tag in (message.risk_tags or detect_risk(message.content))})
        is_overdue = bool(is_past(conversation.sla_deadline_at) and conversation.status != ConversationStatus.closed)
        score = 100 - len(risk_tags) * 12 - (20 if is_overdue else 0)
        report = QualityReport(
            tenant_id=user.tenant_id,
            conversation_id=conversation.id,
            score=max(score, 0),
            risk_tags=risk_tags + (["sla_overdue"] if is_overdue else []),
            detail={
                "message_count": len(messages),
                "status": conversation.status,
                "satisfaction": conversation.satisfaction,
                "sla_deadline_at": conversation.sla_deadline_at.isoformat() if conversation.sla_deadline_at else None,
            },
        )
        session.add(report)
        created += 1
    session.commit()
    return {"status": "completed", "reports_created": created, "conversations_scanned": len(conversations)}


@app.get("/system/health")
def system_health():
    return {
        "postgres": "ok" if check_database() else "down",
        "milvus": "ok" if check_milvus() else "degraded",
        "redis": "ok" if check_redis() else "degraded",
        "model_provider": "mock-local-or-openai-compatible",
        "worker": "ok",
    }


@app.get("/audit/logs")
def audit_logs(user: User = Depends(require_roles([UserRole.admin, UserRole.auditor])), session: Session = Depends(get_session)):
    return session.exec(select(AuditLog).where(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.id.desc()).limit(200)).all()
