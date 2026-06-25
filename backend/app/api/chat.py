from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.entities import BotConfig, Conversation, ConversationStatus, Message, MessageSender
from app.schemas.api import ConversationCreate, ConversationOut, HandoffOut, MessageCreate, MessageOut
from app.services.rag import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ConversationOut)
def create_session(payload: ConversationCreate, session: Session = Depends(get_session)):
    conversation = Conversation(visitor_name=payload.visitor_name, visitor_contact=payload.visitor_contact)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


@router.get("/sessions/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)).all()


@router.post("/sessions/{conversation_id}/messages", response_model=list[MessageOut])
async def send_message(conversation_id: int, payload: MessageCreate, session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_message = Message(conversation_id=conversation_id, sender=MessageSender.visitor, content=payload.content)
    session.add(user_message)
    session.flush()

    if conversation.status in [ConversationStatus.human, ConversationStatus.waiting_agent]:
        conversation.status = ConversationStatus.waiting_agent
        session.add(conversation)
        session.commit()
        return [user_message]

    bot_config = session.exec(select(BotConfig).order_by(BotConfig.id)).first()
    result = await answer_question(session, payload.content, bot_config)
    conversation.intent = result.intent
    conversation.priority = result.priority
    if result.should_handoff:
        conversation.status = ConversationStatus.waiting_agent
    ai_message = Message(
        conversation_id=conversation_id,
        sender=MessageSender.ai,
        content=result.answer,
        confidence=result.confidence,
        intent=result.intent,
        sources=result.sources,
    )
    session.add(ai_message)
    session.add(conversation)
    session.commit()
    session.refresh(user_message)
    session.refresh(ai_message)
    return [user_message, ai_message]


@router.post("/sessions/{conversation_id}/handoff", response_model=HandoffOut)
def handoff(conversation_id: int, session: Session = Depends(get_session)):
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.status = ConversationStatus.waiting_agent
    session.add(Message(conversation_id=conversation_id, sender=MessageSender.system, content="访客请求转人工"))
    session.add(conversation)
    session.commit()
    return HandoffOut(conversation_id=conversation_id, status=conversation.status, reason="visitor_requested")
