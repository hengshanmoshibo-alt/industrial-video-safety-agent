from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.entities import Conversation, ConversationStatus, KnowledgeDocument, Ticket, TicketStatus, User, UserRole
from app.schemas.api import AnalyticsOverview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])),
):
    conversations = session.exec(select(func.count()).select_from(Conversation)).one()
    waiting = session.exec(select(func.count()).select_from(Conversation).where(Conversation.status == ConversationStatus.waiting_agent)).one()
    tickets_open = session.exec(select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.open)).one()
    docs = session.exec(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.is_active == True)).one()  # noqa: E712
    ai_sessions = session.exec(select(func.count()).select_from(Conversation).where(Conversation.status == ConversationStatus.ai)).one()
    rate = round(ai_sessions / conversations, 3) if conversations else 0
    return AnalyticsOverview(
        conversations=conversations,
        waiting_agent=waiting,
        tickets_open=tickets_open,
        knowledge_documents=docs,
        ai_resolution_rate=rate,
    )
