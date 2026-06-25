from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.entities import ConversationStatus, TicketPriority, TicketStatus, UserRole


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str = Field(min_length=6)
    role: UserRole = UserRole.agent


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserPatch(BaseModel):
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class ConversationCreate(BaseModel):
    visitor_name: str = "访客"
    visitor_contact: str = ""


class ConversationOut(BaseModel):
    id: int
    visitor_name: str
    visitor_contact: str
    channel: str
    status: ConversationStatus
    assigned_agent_id: Optional[int]
    intent: str
    priority: TicketPriority
    satisfaction: Optional[int]
    summary: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender: str
    content: str
    confidence: float
    intent: str
    sources: list[dict]
    created_at: datetime


class HandoffOut(BaseModel):
    conversation_id: int
    status: ConversationStatus
    reason: str


class TicketCreate(BaseModel):
    title: str
    description: str
    conversation_id: Optional[int] = None
    priority: TicketPriority = TicketPriority.normal


class TicketPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assignee_id: Optional[int] = None


class TicketOut(BaseModel):
    id: int
    conversation_id: Optional[int]
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    assignee_id: Optional[int]
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    title: str
    category: str = "通用"
    content: str
    source: str = "manual"
    license: str = "internal"


class KnowledgeDocumentOut(BaseModel):
    id: int
    title: str
    category: str
    source: str
    license: str
    is_active: bool
    created_at: datetime


class OpenDatasetImportIn(BaseModel):
    dataset: str
    purpose: str = "evaluation"
    notes: str = ""


class AnalyticsOverview(BaseModel):
    conversations: int
    waiting_agent: int
    tickets_open: int
    knowledge_documents: int
    ai_resolution_rate: float
