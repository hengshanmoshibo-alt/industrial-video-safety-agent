from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.entities import Conversation, ConversationStatus, Message, MessageSender, User, UserRole
from app.schemas.api import ConversationOut, MessageCreate, MessageOut

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    return session.exec(select(Conversation).order_by(Conversation.updated_at.desc())).all()


@router.post("/conversations/{conversation_id}/accept", response_model=ConversationOut)
def accept_conversation(
    conversation_id: int,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.human
    conversation.assigned_agent_id = actor.id
    session.add(conversation)
    session.add(Message(conversation_id=conversation_id, sender=MessageSender.system, content=f"{actor.display_name} 已接入会话"))
    session.commit()
    session.refresh(conversation)
    return conversation


@router.post("/conversations/{conversation_id}/reply", response_model=MessageOut)
def reply_conversation(
    conversation_id: int,
    payload: MessageCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.human
    conversation.assigned_agent_id = actor.id
    message = Message(conversation_id=conversation_id, sender=MessageSender.agent, content=payload.content)
    session.add(conversation)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@router.post("/conversations/{conversation_id}/close", response_model=ConversationOut)
def close_conversation(
    conversation_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.closed
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation
