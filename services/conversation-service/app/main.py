from datetime import timedelta

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.models import Conversation, ConversationStatus, HandoffEvent, Message, MessageSender, User, UserRole, now_utc
from aicoding_shared.security import current_user, require_roles, tenant_from_token
from aicoding_shared.service import create_service_app


class ConversationCreate(BaseModel):
    visitor_name: str = "访客"
    visitor_contact: str = ""
    channel_id: int | None = None
    external_id: str = ""


class MessageCreate(BaseModel):
    content: str


class SatisfactionIn(BaseModel):
    score: int


app = create_service_app("conversation-service")


@app.post("/chat/sessions")
def create_session(payload: ConversationCreate, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    conversation = Conversation(
        tenant_id=tenant.id,
        channel_id=payload.channel_id,
        visitor_name=payload.visitor_name,
        visitor_contact=payload.visitor_contact,
        external_id=payload.external_id,
        sla_deadline_at=now_utc() + timedelta(seconds=60),
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


@app.get("/chat/sessions/{conversation_id}/messages")
def list_messages(conversation_id: int, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    return session.exec(select(Message).where(Message.tenant_id == tenant.id, Message.conversation_id == conversation_id).order_by(Message.id)).all()


@app.post("/chat/sessions/{conversation_id}/messages")
async def send_message(conversation_id: int, payload: MessageCreate, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_message = Message(tenant_id=tenant.id, conversation_id=conversation_id, sender=MessageSender.visitor, content=payload.content)
    session.add(user_message)
    session.flush()

    if conversation.status in [ConversationStatus.human, ConversationStatus.waiting_agent]:
        conversation.status = ConversationStatus.waiting_agent
        conversation.updated_at = now_utc()
        session.add(conversation)
        session.commit()
        session.refresh(user_message)
        return [user_message]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{get_settings().ai_orchestrator_url}/ai/answer",
            json={"question": payload.content},
            headers={"X-Tenant-Id": str(tenant.id)},
        )
    result = resp.json() if resp.status_code == 200 else {
        "answer": "抱歉，智能客服暂时不可用，建议转人工。",
        "confidence": 0,
        "intent": "系统异常",
        "priority": "high",
        "sources": [],
        "risk_tags": ["ai_error"],
        "should_handoff": True,
    }
    conversation.intent = result["intent"]
    conversation.priority = result["priority"]
    if result["should_handoff"]:
        conversation.status = ConversationStatus.waiting_agent
        conversation.sla_deadline_at = now_utc() + timedelta(minutes=15)
        session.add(HandoffEvent(tenant_id=tenant.id, conversation_id=conversation_id, reason="ai_policy"))
    conversation.updated_at = now_utc()
    ai_message = Message(
        tenant_id=tenant.id,
        conversation_id=conversation_id,
        sender=MessageSender.ai,
        content=result["answer"],
        confidence=result["confidence"],
        intent=result["intent"],
        sources=result["sources"],
        risk_tags=result["risk_tags"],
    )
    session.add(conversation)
    session.add(ai_message)
    session.commit()
    session.refresh(user_message)
    session.refresh(ai_message)
    return [user_message, ai_message]


@app.post("/chat/sessions/{conversation_id}/handoff")
def handoff(conversation_id: int, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.waiting_agent
    conversation.sla_deadline_at = now_utc() + timedelta(minutes=15)
    conversation.updated_at = now_utc()
    session.add(HandoffEvent(tenant_id=tenant.id, conversation_id=conversation_id, reason="visitor_requested"))
    session.add(Message(tenant_id=tenant.id, conversation_id=conversation_id, sender=MessageSender.system, content="访客请求转人工"))
    session.add(conversation)
    session.commit()
    return {"conversation_id": conversation_id, "status": conversation.status, "reason": "visitor_requested"}


@app.post("/chat/sessions/{conversation_id}/satisfaction")
def rate_satisfaction(conversation_id: int, payload: SatisfactionIn, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    if payload.score < 1 or payload.score > 5:
        raise HTTPException(status_code=400, detail="Satisfaction score must be between 1 and 5")
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.satisfaction = payload.score
    conversation.updated_at = now_utc()
    session.add(conversation)
    session.add(Message(tenant_id=tenant.id, conversation_id=conversation_id, sender=MessageSender.system, content=f"satisfaction:{payload.score}"))
    session.commit()
    session.refresh(conversation)
    return {"conversation_id": conversation_id, "satisfaction": conversation.satisfaction}


@app.get("/agent/conversations")
def list_conversations(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    return session.exec(select(Conversation).where(Conversation.tenant_id == user.tenant_id).order_by(Conversation.updated_at.desc())).all()


@app.post("/agent/conversations/{conversation_id}/accept")
def accept(conversation_id: int, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.human
    conversation.assigned_agent_id = user.id
    conversation.updated_at = now_utc()
    session.add(conversation)
    session.add(Message(tenant_id=user.tenant_id, conversation_id=conversation_id, sender=MessageSender.system, content=f"{user.display_name} 已接入会话"))
    session.commit()
    session.refresh(conversation)
    return conversation


@app.post("/agent/conversations/{conversation_id}/reply")
def reply(conversation_id: int, payload: MessageCreate, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.human
    conversation.assigned_agent_id = user.id
    conversation.updated_at = now_utc()
    message = Message(tenant_id=user.tenant_id, conversation_id=conversation_id, sender=MessageSender.agent, content=payload.content)
    session.add(conversation)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@app.post("/agent/conversations/{conversation_id}/close")
def close(conversation_id: int, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.closed
    conversation.updated_at = now_utc()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation
