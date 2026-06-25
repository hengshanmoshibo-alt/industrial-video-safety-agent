from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    admin = "admin"
    supervisor = "supervisor"
    agent = "agent"
    kb_manager = "kb_manager"
    auditor = "auditor"


class ChannelType(str, Enum):
    web = "web"
    wecom = "wecom"
    wechat = "wechat"
    feishu = "feishu"
    dingtalk = "dingtalk"


class ConversationStatus(str, Enum):
    ai = "ai"
    waiting_agent = "waiting_agent"
    human = "human"
    closed = "closed"


class MessageSender(str, Enum):
    visitor = "visitor"
    ai = "ai"
    agent = "agent"
    system = "system"


class TicketStatus(str, Enum):
    open = "open"
    pending = "pending"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class VideoAuditStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"


class VideoRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
    needs_review = "needs_review"


class AgentRunStatus(str, Enum):
    running = "running"
    waiting_review = "waiting_review"
    waiting_remediation = "waiting_remediation"
    completed = "completed"
    failed = "failed"


class AgentStepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class VideoAuditReviewDecision(str, Enum):
    confirmed_violation = "confirmed_violation"
    false_positive = "false_positive"
    needs_more_evidence = "needs_more_evidence"


class TicketVerificationStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    needs_review = "needs_review"


class ApprovalStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    published = "published"


class Tenant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    plan: str = "enterprise"
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="department.id")


class Role(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    department_id: Optional[int] = Field(default=None, foreign_key="department.id")
    username: str = Field(index=True)
    display_name: str
    role: UserRole = Field(default=UserRole.agent)
    password_hash: str
    data_scope: str = "tenant"
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class Channel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    type: ChannelType = ChannelType.web
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class SlaPolicy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    first_response_seconds: int = 60
    resolution_seconds: int = 86400
    enabled: bool = True


class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    channel_id: Optional[int] = Field(default=None, foreign_key="channel.id")
    visitor_name: str = "访客"
    visitor_contact: str = ""
    external_id: str = ""
    status: ConversationStatus = Field(default=ConversationStatus.ai, index=True)
    assigned_agent_id: Optional[int] = Field(default=None, foreign_key="user.id")
    intent: str = ""
    priority: TicketPriority = TicketPriority.normal
    satisfaction: Optional[int] = None
    summary: str = ""
    sla_deadline_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    sender: MessageSender
    content: str = Field(sa_column=Column(Text))
    confidence: float = 0
    intent: str = ""
    sources: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    risk_tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc, index=True)


class HandoffEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    conversation_id: int = Field(index=True, foreign_key="conversation.id")
    reason: str
    created_at: datetime = Field(default_factory=now_utc)


class KnowledgeBase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    description: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class KnowledgeDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    knowledge_base_id: Optional[int] = Field(default=None, foreign_key="knowledgebase.id")
    title: str
    category: str = "通用"
    source: str = "seed"
    license: str = "internal"
    content: str = Field(sa_column=Column(Text))
    status: ApprovalStatus = ApprovalStatus.published
    version: int = 1
    is_active: bool = True
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class KnowledgeVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    document_id: int = Field(index=True, foreign_key="knowledgedocument.id")
    version: int
    content: str = Field(sa_column=Column(Text))
    status: ApprovalStatus = ApprovalStatus.draft
    reviewer_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=now_utc)


class KnowledgeChunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    document_id: int = Field(index=True, foreign_key="knowledgedocument.id")
    title: str
    category: str = "通用"
    content: str = Field(sa_column=Column(Text))
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "seed"
    vector_id: str = Field(default="", index=True)
    score_hint: float = 1


class ModelProvider(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    provider_type: str = "openai-compatible"
    base_url: str = ""
    model: str = "mock-local"
    enabled: bool = True


class ModelRoute(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    intent: str = "default"
    provider_id: Optional[int] = Field(default=None, foreign_key="modelprovider.id")
    priority: int = 100
    enabled: bool = True


class PromptTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    description: str = ""
    active_version: int = 1


class PromptVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    template_id: int = Field(index=True, foreign_key="prompttemplate.id")
    version: int
    content: str = Field(sa_column=Column(Text))
    is_active: bool = True


class ModelCallLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    provider: str = "mock-local"
    model: str = "mock-local"
    prompt_version: str = ""
    input_summary: str = ""
    output_summary: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0
    error: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    conversation_id: Optional[int] = Field(default=None, foreign_key="conversation.id")
    title: str
    description: str = Field(sa_column=Column(Text))
    status: TicketStatus = Field(default=TicketStatus.open, index=True)
    priority: TicketPriority = Field(default=TicketPriority.normal, index=True)
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    sla_deadline_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TicketFlowLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    ticket_id: int = Field(index=True, foreign_key="ticket.id")
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class QualityRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    name: str
    rule_type: str = "keyword"
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    enabled: bool = True


class QualityReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    conversation_id: Optional[int] = Field(default=None, foreign_key="conversation.id")
    ticket_id: Optional[int] = Field(default=None, foreign_key="ticket.id")
    score: float = 100
    risk_tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class VideoAudit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    uploader_id: Optional[int] = Field(default=None, foreign_key="user.id")
    assigned_agent_id: Optional[int] = Field(default=None, foreign_key="user.id")
    file_name: str
    content_type: str = "video/mp4"
    object_key: str = Field(index=True)
    status: VideoAuditStatus = Field(default=VideoAuditStatus.queued, index=True)
    risk_level: VideoRiskLevel = Field(default=VideoRiskLevel.needs_review, index=True)
    summary: str = ""
    error: str = ""
    duration_ms: int = 0
    created_ticket_id: Optional[int] = Field(default=None, foreign_key="ticket.id")
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc)
    completed_at: Optional[datetime] = None


class VideoAuditFinding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    category: str = "unsafe_behavior"
    label: str = Field(index=True)
    risk_level: VideoRiskLevel = Field(default=VideoRiskLevel.high, index=True)
    confidence: float = 0
    start_ms: int = 0
    end_ms: int = 0
    bbox: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    reason: str = Field(default="", sa_column=Column(Text))
    recommendation: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditEvidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    finding_id: Optional[int] = Field(default=None, index=True, foreign_key="videoauditfinding.id")
    timestamp_ms: int = 0
    frame_object_key: str = ""
    caption: str = ""
    model_score: float = 0
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    report: dict = Field(default_factory=dict, sa_column=Column(JSON))
    model_version: str = "rule-fallback"
    processing_ms: int = 0
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditAgentRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    status: AgentRunStatus = Field(default=AgentRunStatus.running, index=True)
    goal: str = "完成工业安全巡检、风险决策和闭环建议"
    current_step: str = ""
    current_stage: str = ""
    paused_reason: str = Field(default="", sa_column=Column(Text))
    decision: dict = Field(default_factory=dict, sa_column=Column(JSON))
    final_decision: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error: str = Field(default="", sa_column=Column(Text))
    started_at: datetime = Field(default_factory=now_utc)
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditAgentStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    run_id: int = Field(index=True, foreign_key="videoauditagentrun.id")
    step_order: int = Field(index=True)
    tool_name: str = Field(index=True)
    status: AgentStepStatus = Field(default=AgentStepStatus.completed, index=True)
    input_summary: str = Field(default="", sa_column=Column(Text))
    output_summary: str = Field(default="", sa_column=Column(Text))
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    artifact_refs: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    latency_ms: int = 0
    error: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc)


class VideoMemorySegment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    start_ms: int = 0
    end_ms: int = 0
    frame_index: int = 0
    frame_object_key: str = ""
    visible_objects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    risk_subject: str = ""
    bbox: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    evidence: str = Field(default="", sa_column=Column(Text))
    raw_finding: dict = Field(default_factory=dict, sa_column=Column(JSON))
    vlm_raw_output: dict = Field(default_factory=dict, sa_column=Column(JSON))
    review_status: str = Field(default="unreviewed", index=True)
    created_at: datetime = Field(default_factory=now_utc)


class SafetyPolicy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    code: str = Field(index=True)
    label: str = Field(index=True)
    title: str
    description: str = Field(default="", sa_column=Column(Text))
    severity: VideoRiskLevel = Field(default=VideoRiskLevel.high, index=True)
    auto_alert: bool = True
    requires_review: bool = False
    recommend_ticket: bool = True
    requires_verification: bool = True
    due_hours: int = 24
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    reviewer_id: Optional[int] = Field(default=None, foreign_key="user.id")
    decision: VideoAuditReviewDecision = Field(index=True)
    comment: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc)


class VideoAuditAlertEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    audit_id: int = Field(index=True, foreign_key="videoaudit.id")
    channel: str = "feishu"
    status: str = Field(default="sent", index=True)
    risk_level: VideoRiskLevel = Field(default=VideoRiskLevel.high, index=True)
    message: str = Field(default="", sa_column=Column(Text))
    error: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc)


class TicketVerification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(index=True, foreign_key="tenant.id")
    ticket_id: int = Field(index=True, foreign_key="ticket.id")
    audit_id: Optional[int] = Field(default=None, index=True, foreign_key="videoaudit.id")
    object_key: str = Field(index=True)
    content_type: str = "application/octet-stream"
    status: TicketVerificationStatus = Field(default=TicketVerificationStatus.needs_review, index=True)
    summary: str = Field(default="", sa_column=Column(Text))
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=now_utc)
    completed_at: Optional[datetime] = None


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[int] = Field(default=None, index=True, foreign_key="tenant.id")
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str
    target_type: str = ""
    target_id: str = ""
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc, index=True)
