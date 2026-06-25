import json
import uuid
from datetime import datetime

from fastapi import Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from redis import Redis
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import engine, get_session
from aicoding_shared.models import (
    AgentRunStatus,
    AgentStepStatus,
    AuditLog,
    SafetyPolicy,
    Ticket,
    TicketFlowLog,
    TicketPriority,
    TicketVerification,
    Tenant,
    User,
    UserRole,
    VideoAudit,
    VideoAuditAgentRun,
    VideoAuditAgentStep,
    VideoAuditAlertEvent,
    VideoAuditEvidence,
    VideoAuditFinding,
    VideoAuditReport,
    VideoAuditReview,
    VideoAuditReviewDecision,
    VideoAuditStatus,
    VideoRiskLevel,
    VideoMemorySegment,
    now_utc,
)
from aicoding_shared.security import require_roles
from aicoding_shared.service import create_service_app
from aicoding_shared.storage import ObjectStorage


ALLOWED_ROLES = [UserRole.admin, UserRole.supervisor, UserRole.auditor, UserRole.agent]

RISK_TEXT = {
    VideoRiskLevel.low: "低风险",
    VideoRiskLevel.medium: "中风险",
    VideoRiskLevel.high: "高风险",
    VideoRiskLevel.critical: "严重风险",
    VideoRiskLevel.needs_review: "需人工复核",
}

LABEL_TEXT = {
    "safe_walkway": "安全通道通行",
    "authorized_intervention": "授权设备干预",
    "closed_panel_cover": "设备防护关闭",
    "safe_carrying": "安全搬运",
    "walkway_violation": "安全通道占用/越界",
    "unauthorized_intervention": "疑似未授权设备干预",
    "opened_panel_cover": "设备护罩/柜门打开",
    "forklift_overload": "叉车或搬运超载",
}


def _risk_text(risk: VideoRiskLevel | str) -> str:
    try:
        risk = VideoRiskLevel(risk)
    except ValueError:
        return str(risk)
    return RISK_TEXT.get(risk, risk.value)


def _build_ticket_description(
    audit: VideoAudit,
    findings: list[VideoAuditFinding],
    policies: list[SafetyPolicy] | None = None,
) -> str:
    policy_by_label = {item.label: item for item in policies or []}
    lines = [
        f"来源：安全巡检任务 #{audit.id}",
        f"视频：{audit.file_name}",
        f"总体风险：{_risk_text(audit.risk_level)}",
        f"摘要：{audit.summary or '暂无摘要'}",
        "",
        "风险明细：",
    ]
    if not findings:
        lines.append("1. 未发现明确高风险项，建议安全主管结合原视频复核。")
    for index, item in enumerate(findings, start=1):
        label = LABEL_TEXT.get(item.label, item.label)
        lines.append(
            f"{index}. {label}｜{_risk_text(item.risk_level)}｜"
            f"{item.start_ms // 1000}s-{item.end_ms // 1000}s｜置信度 {round(item.confidence * 100)}%"
        )
        if item.reason:
            lines.append(f"   证据：{item.reason}")
        if item.recommendation:
            lines.append(f"   整改：{item.recommendation}")
        policy = policy_by_label.get(item.label)
        if policy:
            lines.append(
                f"   处置策略：{policy.title}；整改期限 {policy.due_hours} 小时；"
                f"{'需要复检' if policy.requires_verification else '无需复检'}。"
            )
    lines.extend(
        [
            "",
            "处理要求：",
            "1. 安全主管先核验证据截图和原视频。",
            "2. 现场责任人完成通道清理、隔离标识或设备作业复核。",
            "3. 整改完成后补充复拍照片或复检结论，并关闭工单。",
        ]
    )
    return "\n".join(lines)
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "application/octet-stream"}

DEFAULT_POLICY_DEFINITIONS = [
    {
        "code": "policy.walkway_violation",
        "label": "walkway_violation",
        "title": "安全通道占用处置策略",
        "description": "安全通道、消防通道、逃生路径不得堆放物料或设备；发现占用时应立即清理并恢复通行。",
        "severity": VideoRiskLevel.high,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
        "due_hours": 2,
        "keywords": ["安全通道", "黄色线", "物料占用", "逃生路径"],
    },
    {
        "code": "policy.unauthorized_intervention",
        "label": "unauthorized_intervention",
        "title": "未授权设备干预处置策略",
        "description": "人员接触、调整或进入设备危险部位时，应核验作业许可、停机挂牌和授权记录；证据不足时进入人工复核。",
        "severity": VideoRiskLevel.high,
        "auto_alert": True,
        "requires_review": True,
        "recommend_ticket": True,
        "requires_verification": True,
        "due_hours": 4,
        "keywords": ["设备干预", "授权", "挂牌", "PPE", "操作区"],
    },
    {
        "code": "policy.opened_panel_cover",
        "label": "opened_panel_cover",
        "title": "设备防护打开处置策略",
        "description": "设备护罩、柜门或面板打开时，应确认停机、隔离和防护措施；运行状态下防护缺失应立即整改。",
        "severity": VideoRiskLevel.high,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
        "due_hours": 4,
        "keywords": ["护罩", "柜门", "面板", "防护缺失"],
    },
    {
        "code": "policy.forklift_overload",
        "label": "forklift_overload",
        "title": "叉车和搬运超载处置策略",
        "description": "叉车或搬运设备载荷过高、遮挡视线或堆叠不稳定时，应立即停止搬运并重新分载固定。",
        "severity": VideoRiskLevel.critical,
        "auto_alert": True,
        "requires_review": False,
        "recommend_ticket": True,
        "requires_verification": True,
        "due_hours": 1,
        "keywords": ["叉车", "超载", "遮挡视线", "载荷不稳"],
    },
]


class ReviewCreate(BaseModel):
    decision: VideoAuditReviewDecision
    comment: str = ""


class SafetyPolicyUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: VideoRiskLevel | None = None
    auto_alert: bool | None = None
    requires_review: bool | None = None
    recommend_ticket: bool | None = None
    requires_verification: bool | None = None
    due_hours: int | None = None
    enabled: bool | None = None


def _policies_for_findings(session: Session, tenant_id: int, findings: list[VideoAuditFinding]) -> list[SafetyPolicy]:
    _ensure_tenant_policies(session, tenant_id)
    labels = sorted({item.label for item in findings})
    if not labels:
        return []
    return session.exec(
        select(SafetyPolicy).where(
            SafetyPolicy.tenant_id == tenant_id,
            SafetyPolicy.enabled == True,  # noqa: E712
            SafetyPolicy.label.in_(labels),
        )
    ).all()


def _ensure_tenant_policies(session: Session, tenant_id: int) -> None:
    changed = False
    for item in DEFAULT_POLICY_DEFINITIONS:
        exists = session.exec(
            select(SafetyPolicy).where(SafetyPolicy.tenant_id == tenant_id, SafetyPolicy.code == item["code"])
        ).first()
        if exists is None:
            session.add(SafetyPolicy(tenant_id=tenant_id, **item))
            changed = True
    if changed:
        session.commit()


def _latest_agent_run(session: Session, tenant_id: int, audit_id: int) -> VideoAuditAgentRun | None:
    return session.exec(
        select(VideoAuditAgentRun)
        .where(VideoAuditAgentRun.tenant_id == tenant_id, VideoAuditAgentRun.audit_id == audit_id)
        .order_by(VideoAuditAgentRun.id.desc())
    ).first()


def _next_step_order(session: Session, run: VideoAuditAgentRun) -> int:
    if run.id is None:
        return 1
    steps = session.exec(
        select(VideoAuditAgentStep)
        .where(VideoAuditAgentStep.tenant_id == run.tenant_id, VideoAuditAgentStep.run_id == run.id)
        .order_by(VideoAuditAgentStep.step_order.desc())
    ).all()
    return (steps[0].step_order + 1) if steps else 1


def _append_agent_step(
    session: Session,
    run: VideoAuditAgentRun,
    tool_name: str,
    input_summary: str,
    output_summary: str,
    detail: dict | None = None,
) -> None:
    run.current_step = tool_name
    run.current_stage = tool_name
    session.add(run)
    session.flush()
    session.add(
        VideoAuditAgentStep(
            tenant_id=run.tenant_id,
            audit_id=run.audit_id,
            run_id=run.id or 0,
            step_order=_next_step_order(session, run),
            tool_name=tool_name,
            status=AgentStepStatus.completed,
            input_summary=input_summary,
            output_summary=output_summary,
            detail=detail or {},
        )
    )


def _build_agent_explanation(
    audit: VideoAudit,
    findings: list[VideoAuditFinding],
    memory_segments: list[VideoMemorySegment],
    agent_run: VideoAuditAgentRun | None,
    steps: list[VideoAuditAgentStep],
    policies: list[SafetyPolicy],
    alerts: list[VideoAuditAlertEvent],
) -> dict:
    decision = (agent_run.final_decision or agent_run.decision) if agent_run else {}
    risk_frames = [item for item in memory_segments if item.bbox or item.risk_subject]
    return {
        "summary": audit.summary or "本次巡检暂无摘要。",
        "what_agent_saw": [
            {
                "time_range": f"{item.start_ms // 1000}s-{item.end_ms // 1000}s",
                "objects": item.visible_objects,
                "risk_subject": item.risk_subject,
                "evidence": item.evidence,
                "bbox": item.bbox,
            }
            for item in risk_frames[:8]
        ],
        "why_this_risk": [
            f"{LABEL_TEXT.get(item.label, item.label)}：{item.reason}"
            for item in findings[:8]
        ],
        "why_this_action": decision.get("decision_reason", "Agent 已根据视觉证据和安全策略生成处置建议。"),
        "tools_used": [
            {
                "tool": item.tool_name,
                "reason": item.detail.get("why", item.input_summary),
                "result": item.output_summary,
                "latency_ms": item.latency_ms,
            }
            for item in steps
        ],
        "matched_policies": [item.title for item in policies],
        "alert_status": alerts[0].status if alerts else "none",
        "final_decision": decision,
    }


def _bootstrap_safety_policies() -> None:
    with Session(engine) as session:
        tenants = session.exec(select(Tenant)).all()
        for tenant in tenants:
            if tenant.id is not None:
                _ensure_tenant_policies(session, tenant.id)


app = create_service_app("video-audit-service", bootstrap=_bootstrap_safety_policies)


class TicketCreateOut(BaseModel):
    ticket_id: int
    audit_id: int


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _enqueue(audit: VideoAudit) -> None:
    _redis().rpush(get_settings().video_audit_queue, json.dumps({"audit_id": audit.id, "tenant_id": audit.tenant_id}))


def _can_access_audit(user: User, audit: VideoAudit) -> bool:
    if audit.tenant_id != user.tenant_id:
        return False
    if user.role in {UserRole.admin, UserRole.supervisor, UserRole.auditor}:
        return True
    return audit.uploader_id == user.id or audit.assigned_agent_id == user.id


def _audit_owned(session: Session, audit_id: int, user: User) -> VideoAudit:
    audit = session.get(VideoAudit, audit_id)
    if audit is None or not _can_access_audit(user, audit):
        raise HTTPException(status_code=404, detail="Video audit not found")
    return audit


def _scoped_audit_statement(user: User):
    statement = select(VideoAudit).where(VideoAudit.tenant_id == user.tenant_id)
    if user.role == UserRole.agent:
        statement = statement.where((VideoAudit.uploader_id == user.id) | (VideoAudit.assigned_agent_id == user.id))
    return statement


@app.post("/video-audits")
async def create_video_audit(
    file: UploadFile = File(...),
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Only video uploads are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > 1024 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Video file is too large")

    extension = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".mp4"
    object_key = f"tenant-{user.tenant_id}/audits/{uuid.uuid4()}{extension}"
    ObjectStorage().put_bytes(object_key, data, file.content_type)

    audit = VideoAudit(
        tenant_id=user.tenant_id,
        uploader_id=user.id,
        file_name=file.filename,
        content_type=file.content_type or "video/mp4",
        object_key=object_key,
        status=VideoAuditStatus.queued,
    )
    session.add(audit)
    session.flush()
    session.add(
        AuditLog(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="video_audit.create",
            target_type="video_audit",
            target_id=str(audit.id),
            detail={"file_name": file.filename, "object_key": object_key},
        )
    )
    session.commit()
    session.refresh(audit)
    _enqueue(audit)
    return audit


@app.get("/video-audits")
def list_video_audits(
    status: VideoAuditStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    statement = _scoped_audit_statement(user)
    if status is not None:
        statement = statement.where(VideoAudit.status == status)
    return session.exec(statement.order_by(VideoAudit.id.desc()).limit(limit)).all()


@app.get("/video-audits/metrics/overview")
def video_audit_metrics(
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    audits = session.exec(_scoped_audit_statement(user)).all()
    audit_ids = [item.id for item in audits if item.id is not None]
    review_audit_ids: set[int] = {
        item.id
        for item in audits
        if item.id is not None and (item.status == VideoAuditStatus.needs_review or item.risk_level == VideoRiskLevel.needs_review)
    }
    if audit_ids:
        review_findings = session.exec(
            select(VideoAuditFinding.audit_id).where(
                VideoAuditFinding.tenant_id == user.tenant_id,
                VideoAuditFinding.audit_id.in_(audit_ids),
                VideoAuditFinding.risk_level == VideoRiskLevel.needs_review,
            )
        ).all()
        review_audit_ids.update(int(item) for item in review_findings)
    return {
        "total": len(audits),
        "completed": sum(1 for item in audits if item.status == VideoAuditStatus.completed),
        "high_risk": sum(1 for item in audits if item.risk_level in {VideoRiskLevel.high, VideoRiskLevel.critical}),
        "needs_review": len(review_audit_ids),
        "tickets_created": sum(1 for item in audits if item.created_ticket_id is not None),
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/video-audits/metrics/agent-overview")
def video_audit_agent_metrics(
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    audits = session.exec(_scoped_audit_statement(user)).all()
    audit_ids = [item.id for item in audits if item.id is not None]
    runs = []
    alerts = []
    reviews = []
    if audit_ids:
        runs = session.exec(
            select(VideoAuditAgentRun).where(
                VideoAuditAgentRun.tenant_id == user.tenant_id,
                VideoAuditAgentRun.audit_id.in_(audit_ids),
            )
        ).all()
        alerts = session.exec(
            select(VideoAuditAlertEvent).where(
                VideoAuditAlertEvent.tenant_id == user.tenant_id,
                VideoAuditAlertEvent.audit_id.in_(audit_ids),
            )
        ).all()
        reviews = session.exec(
            select(VideoAuditReview).where(
                VideoAuditReview.tenant_id == user.tenant_id,
                VideoAuditReview.audit_id.in_(audit_ids),
            )
        ).all()
    completed_runs = [
        item for item in runs
        if item.status in {AgentRunStatus.completed, AgentRunStatus.waiting_review, AgentRunStatus.waiting_remediation}
    ]
    return {
        "agent_runs": len(runs),
        "completed_runs": len(completed_runs),
        "failed_runs": sum(1 for item in runs if item.status == "failed"),
        "waiting_review_runs": sum(1 for item in runs if item.status == AgentRunStatus.waiting_review),
        "waiting_remediation_runs": sum(1 for item in runs if item.status == AgentRunStatus.waiting_remediation),
        "alert_events": len(alerts),
        "sent_alerts": sum(1 for item in alerts if item.status == "sent"),
        "human_reviews": len(reviews),
        "avg_processing_ms": int(
            sum(item.final_decision.get("processing_ms", item.decision.get("processing_ms", 0)) for item in completed_runs) / len(completed_runs)
        ) if completed_runs else 0,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/video-audits/metrics/evaluation")
def video_audit_evaluation_metrics(
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    audits = session.exec(_scoped_audit_statement(user)).all()
    audit_ids = [item.id for item in audits if item.id is not None]
    findings: list[VideoAuditFinding] = []
    runs: list[VideoAuditAgentRun] = []
    alerts: list[VideoAuditAlertEvent] = []
    reviews: list[VideoAuditReview] = []
    verifications: list[TicketVerification] = []
    if audit_ids:
        findings = session.exec(
            select(VideoAuditFinding).where(
                VideoAuditFinding.tenant_id == user.tenant_id,
                VideoAuditFinding.audit_id.in_(audit_ids),
            )
        ).all()
        runs = session.exec(
            select(VideoAuditAgentRun).where(
                VideoAuditAgentRun.tenant_id == user.tenant_id,
                VideoAuditAgentRun.audit_id.in_(audit_ids),
            )
        ).all()
        alerts = session.exec(
            select(VideoAuditAlertEvent).where(
                VideoAuditAlertEvent.tenant_id == user.tenant_id,
                VideoAuditAlertEvent.audit_id.in_(audit_ids),
            )
        ).all()
        reviews = session.exec(
            select(VideoAuditReview).where(
                VideoAuditReview.tenant_id == user.tenant_id,
                VideoAuditReview.audit_id.in_(audit_ids),
            )
        ).all()
        verifications = session.exec(
            select(TicketVerification).where(
                TicketVerification.tenant_id == user.tenant_id,
                TicketVerification.audit_id.in_(audit_ids),
            )
        ).all()
    completed = [item for item in audits if item.status in {VideoAuditStatus.completed, VideoAuditStatus.needs_review}]
    findings_with_bbox = [item for item in findings if item.bbox]
    high_alert_audits = {item.audit_id for item in alerts if item.risk_level in {VideoRiskLevel.high, VideoRiskLevel.critical}}
    sent_alerts = [item for item in alerts if item.status == "sent"]
    confirmed = [item for item in reviews if item.decision == VideoAuditReviewDecision.confirmed_violation]
    false_positive = [item for item in reviews if item.decision == VideoAuditReviewDecision.false_positive]
    completed_runs = [item for item in runs if item.status in {AgentRunStatus.completed, AgentRunStatus.waiting_review, AgentRunStatus.waiting_remediation}]
    avg_ms = int(sum(item.final_decision.get("processing_ms", item.decision.get("processing_ms", 0)) for item in completed_runs) / len(completed_runs)) if completed_runs else 0
    return {
        "total_videos": len(audits),
        "processed_videos": len(completed),
        "processing_success_rate": round(len(completed) / len(audits), 4) if audits else 0,
        "total_findings": len(findings),
        "bbox_valid_findings": len(findings_with_bbox),
        "bbox_valid_rate": round(len(findings_with_bbox) / len(findings), 4) if findings else 0,
        "high_risk_alerts": len(high_alert_audits),
        "feishu_alert_success_rate": round(len(sent_alerts) / len(alerts), 4) if alerts else 0,
        "human_review_count": len(reviews),
        "human_review_confirm_rate": round(len(confirmed) / len(reviews), 4) if reviews else 0,
        "false_positive_rate": round(len(false_positive) / len(reviews), 4) if reviews else 0,
        "verification_count": len(verifications),
        "verification_passed": sum(1 for item in verifications if item.status == "passed"),
        "avg_processing_ms": avg_ms,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/safety-tools")
def list_safety_tools(user: User = Depends(require_roles(ALLOWED_ROLES))):
    return [
        {"name": "sample_video_frames", "description": "抽取巡检视频关键帧，生成可追溯帧时间戳。"},
        {"name": "inspect_safety_frame", "description": "调用 Qwen3-VL 对关键帧做风险识别和 bbox grounding。"},
        {"name": "query_video_memory", "description": "按时间、风险、对象查询视频结构化记忆。"},
        {"name": "validate_bbox", "description": "校验风险框是否过大、过小或缺失。"},
        {"name": "merge_risk_events", "description": "把相邻同类帧级风险合并为事件。"},
        {"name": "decide_safety_action", "description": "结合安全策略决定告警、复核、工单和复检要求。"},
        {"name": "send_feishu_alert", "description": "向飞书群发送高风险告警或复核提醒。"},
        {"name": "recommend_remediation_ticket", "description": "生成整改工单建议，等待主管确认。"},
        {"name": "verify_remediation", "description": "识别整改后证据，判断是否通过复检。"},
    ]


@app.get("/safety-policies")
def list_safety_policies(
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    _ensure_tenant_policies(session, user.tenant_id)
    return session.exec(
        select(SafetyPolicy)
        .where(SafetyPolicy.tenant_id == user.tenant_id, SafetyPolicy.enabled == True)  # noqa: E712
        .order_by(SafetyPolicy.id)
    ).all()


@app.patch("/safety-policies/{policy_id}")
def update_safety_policy(
    policy_id: int,
    payload: SafetyPolicyUpdate,
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor])),
    session: Session = Depends(get_session),
):
    policy = session.get(SafetyPolicy, policy_id)
    if policy is None or policy.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Safety policy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "due_hours" and value is not None and value < 1:
            raise HTTPException(status_code=400, detail="due_hours must be positive")
        setattr(policy, field, value)
    session.add(policy)
    session.add(AuditLog(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="safety_policy.update",
        target_type="safety_policy",
        target_id=str(policy.id),
        detail=payload.model_dump(exclude_unset=True),
    ))
    session.commit()
    session.refresh(policy)
    return policy


@app.get("/video-audits/{audit_id}")
def get_video_audit(
    audit_id: int,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    audit = _audit_owned(session, audit_id, user)
    findings = session.exec(select(VideoAuditFinding).where(VideoAuditFinding.tenant_id == user.tenant_id, VideoAuditFinding.audit_id == audit_id)).all()
    evidences = session.exec(select(VideoAuditEvidence).where(VideoAuditEvidence.tenant_id == user.tenant_id, VideoAuditEvidence.audit_id == audit_id)).all()
    report = session.exec(select(VideoAuditReport).where(VideoAuditReport.tenant_id == user.tenant_id, VideoAuditReport.audit_id == audit_id).order_by(VideoAuditReport.id.desc())).first()
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    agent_steps = []
    if agent_run is not None and agent_run.id is not None:
        agent_steps = session.exec(
            select(VideoAuditAgentStep)
            .where(VideoAuditAgentStep.tenant_id == user.tenant_id, VideoAuditAgentStep.run_id == agent_run.id)
            .order_by(VideoAuditAgentStep.step_order)
        ).all()
    memory_segments = session.exec(
        select(VideoMemorySegment)
        .where(VideoMemorySegment.tenant_id == user.tenant_id, VideoMemorySegment.audit_id == audit_id)
        .order_by(VideoMemorySegment.start_ms, VideoMemorySegment.id)
    ).all()
    matched_rules = _policies_for_findings(session, user.tenant_id, findings)
    reviews = session.exec(
        select(VideoAuditReview)
        .where(VideoAuditReview.tenant_id == user.tenant_id, VideoAuditReview.audit_id == audit_id)
        .order_by(VideoAuditReview.id.desc())
    ).all()
    alert_events = session.exec(
        select(VideoAuditAlertEvent)
        .where(VideoAuditAlertEvent.tenant_id == user.tenant_id, VideoAuditAlertEvent.audit_id == audit_id)
        .order_by(VideoAuditAlertEvent.id.desc())
    ).all()
    report_payload = report.report if report is not None else {}
    return {
        "audit": audit,
        "findings": findings,
        "evidences": evidences,
        "report": report,
        "agent_run": agent_run,
        "agent_steps": agent_steps,
        "memory_segments": memory_segments,
        "matched_rules": matched_rules,
        "agent_decision": report_payload.get("agent_decision") or ((agent_run.final_decision or agent_run.decision) if agent_run else {}),
        "reviews": reviews,
        "alert_events": alert_events,
    }


@app.get("/video-audits/{audit_id}/memory")
def get_video_audit_memory(
    audit_id: int,
    label: str | None = None,
    review_status: str | None = None,
    has_bbox: bool | None = None,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    _audit_owned(session, audit_id, user)
    statement = select(VideoMemorySegment).where(
        VideoMemorySegment.tenant_id == user.tenant_id,
        VideoMemorySegment.audit_id == audit_id,
    )
    if review_status:
        statement = statement.where(VideoMemorySegment.review_status == review_status)
    segments = session.exec(statement.order_by(VideoMemorySegment.start_ms, VideoMemorySegment.id)).all()
    if label:
        segments = [
            item for item in segments
            if item.raw_finding.get("label") == label or item.vlm_raw_output.get("label") == label or label in item.visible_objects
        ]
    if has_bbox is not None:
        segments = [item for item in segments if bool(item.bbox) == has_bbox]
    return segments


@app.get("/video-audits/{audit_id}/agent-run")
def get_video_audit_agent_run(
    audit_id: int,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    _audit_owned(session, audit_id, user)
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    if agent_run is None or agent_run.id is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    agent_steps = session.exec(
        select(VideoAuditAgentStep)
        .where(VideoAuditAgentStep.tenant_id == user.tenant_id, VideoAuditAgentStep.run_id == agent_run.id)
        .order_by(VideoAuditAgentStep.step_order)
    ).all()
    return {"agent_run": agent_run, "agent_steps": agent_steps}


@app.get("/video-audits/{audit_id}/agent-explanation")
def get_video_audit_agent_explanation(
    audit_id: int,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    audit = _audit_owned(session, audit_id, user)
    findings = session.exec(select(VideoAuditFinding).where(VideoAuditFinding.tenant_id == user.tenant_id, VideoAuditFinding.audit_id == audit_id)).all()
    memory_segments = session.exec(
        select(VideoMemorySegment)
        .where(VideoMemorySegment.tenant_id == user.tenant_id, VideoMemorySegment.audit_id == audit_id)
        .order_by(VideoMemorySegment.start_ms, VideoMemorySegment.id)
    ).all()
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    steps: list[VideoAuditAgentStep] = []
    if agent_run is not None and agent_run.id is not None:
        steps = session.exec(
            select(VideoAuditAgentStep)
            .where(VideoAuditAgentStep.tenant_id == user.tenant_id, VideoAuditAgentStep.run_id == agent_run.id)
            .order_by(VideoAuditAgentStep.step_order)
        ).all()
    policies = _policies_for_findings(session, user.tenant_id, findings)
    alerts = session.exec(
        select(VideoAuditAlertEvent)
        .where(VideoAuditAlertEvent.tenant_id == user.tenant_id, VideoAuditAlertEvent.audit_id == audit_id)
        .order_by(VideoAuditAlertEvent.id.desc())
    ).all()
    return _build_agent_explanation(audit, findings, memory_segments, agent_run, steps, policies, alerts)


@app.post("/video-audits/{audit_id}/review")
def review_video_audit(
    audit_id: int,
    payload: ReviewCreate,
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])),
    session: Session = Depends(get_session),
):
    audit = _audit_owned(session, audit_id, user)
    review = VideoAuditReview(
        tenant_id=user.tenant_id,
        audit_id=audit.id,
        reviewer_id=user.id,
        decision=payload.decision,
        comment=payload.comment,
    )
    session.add(review)
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    if agent_run is not None:
        if payload.decision == VideoAuditReviewDecision.needs_more_evidence:
            agent_run.status = AgentRunStatus.waiting_review
            agent_run.paused_reason = "安全主管要求补充证据后继续复核。"
        else:
            agent_run.paused_reason = ""
        agent_run.final_decision = {
            **(agent_run.final_decision or agent_run.decision or {}),
            "human_review_decision": payload.decision.value,
            "human_review_comment": payload.comment,
        }
        _append_agent_step(
            session,
            agent_run,
            "human_review",
            payload.decision.value,
            "人工复核结论已写入 Agent 会话。",
            {"decision": payload.decision.value, "comment": payload.comment},
        )
    session.add(AuditLog(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="video_audit.review",
        target_type="video_audit",
        target_id=str(audit.id),
        detail={"decision": payload.decision.value, "comment": payload.comment},
    ))
    session.commit()
    session.refresh(review)
    return review


@app.post("/video-audits/{audit_id}/resume")
def resume_video_audit_agent(
    audit_id: int,
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.auditor])),
    session: Session = Depends(get_session),
):
    audit = _audit_owned(session, audit_id, user)
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    if agent_run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    review = session.exec(
        select(VideoAuditReview)
        .where(VideoAuditReview.tenant_id == user.tenant_id, VideoAuditReview.audit_id == audit_id)
        .order_by(VideoAuditReview.id.desc())
    ).first()
    if review is None:
        raise HTTPException(status_code=400, detail="No human review decision to resume from")
    decision = dict(agent_run.final_decision or agent_run.decision or {})
    decision["human_review_decision"] = review.decision.value
    if review.decision == VideoAuditReviewDecision.false_positive:
        audit.status = VideoAuditStatus.completed
        audit.risk_level = VideoRiskLevel.low
        audit.summary = "人工复核判定为误报，Agent 已归档本次巡检。"
        decision.update({
            "send_feishu_alert": False,
            "needs_human_review": False,
            "recommend_ticket": False,
            "requires_verification": False,
            "decision_reason": "人工复核判定为误报，不再创建整改工单。",
        })
        agent_run.status = AgentRunStatus.completed
        agent_run.completed_at = now_utc()
        output = "复核结果为误报，Agent 已完成归档。"
    elif review.decision == VideoAuditReviewDecision.confirmed_violation:
        audit.status = VideoAuditStatus.completed
        if audit.risk_level == VideoRiskLevel.needs_review:
            audit.risk_level = VideoRiskLevel.high
        audit.summary = audit.summary or "人工复核确认存在安全违规，建议创建整改工单。"
        decision.update({
            "send_feishu_alert": True,
            "needs_human_review": False,
            "recommend_ticket": True,
            "requires_verification": True,
            "decision_reason": "人工复核确认违规，Agent 进入整改工单建议阶段。",
        })
        agent_run.status = AgentRunStatus.waiting_remediation
        agent_run.paused_reason = "等待主管创建整改工单并上传整改后证据。"
        output = "复核确认违规，Agent 等待整改工单和复检证据。"
    else:
        audit.status = VideoAuditStatus.needs_review
        decision.update({
            "needs_human_review": True,
            "recommend_ticket": False,
            "decision_reason": "人工复核要求补充证据，Agent 暂停等待更多证据。",
        })
        agent_run.status = AgentRunStatus.waiting_review
        agent_run.paused_reason = "等待补充证据。"
        output = "复核要求补充证据，Agent 保持等待复核状态。"
    audit.updated_at = now_utc()
    agent_run.final_decision = decision
    agent_run.decision = decision
    _append_agent_step(
        session,
        agent_run,
        "resume_after_review",
        review.decision.value,
        output,
        decision,
    )
    session.add(audit)
    session.add(agent_run)
    session.add(AuditLog(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="video_audit.resume",
        target_type="video_audit",
        target_id=str(audit.id),
        detail={"decision": review.decision.value, "agent_status": agent_run.status.value},
    ))
    session.commit()
    session.refresh(agent_run)
    return {"audit": audit, "agent_run": agent_run, "agent_decision": decision}


@app.get("/video-audits/{audit_id}/report")
def get_video_audit_report(
    audit_id: int,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    _audit_owned(session, audit_id, user)
    report = session.exec(select(VideoAuditReport).where(VideoAuditReport.tenant_id == user.tenant_id, VideoAuditReport.audit_id == audit_id).order_by(VideoAuditReport.id.desc())).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/video-audits/{audit_id}/evidence/{evidence_id}/image")
def get_evidence_image(
    audit_id: int,
    evidence_id: int,
    user: User = Depends(require_roles(ALLOWED_ROLES)),
    session: Session = Depends(get_session),
):
    _audit_owned(session, audit_id, user)
    evidence = session.get(VideoAuditEvidence, evidence_id)
    if evidence is None or evidence.tenant_id != user.tenant_id or evidence.audit_id != audit_id:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not evidence.frame_object_key:
        raise HTTPException(status_code=404, detail="Evidence frame is missing")
    data = ObjectStorage().get_bytes(evidence.frame_object_key)
    return Response(content=data, media_type=ObjectStorage().content_type(evidence.frame_object_key))


@app.post("/video-audits/{audit_id}/tickets", response_model=TicketCreateOut)
def create_ticket_from_audit(
    audit_id: int,
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
    session: Session = Depends(get_session),
):
    audit = _audit_owned(session, audit_id, user)
    if audit.created_ticket_id is not None:
        return TicketCreateOut(ticket_id=audit.created_ticket_id, audit_id=audit.id)

    findings = session.exec(select(VideoAuditFinding).where(VideoAuditFinding.tenant_id == user.tenant_id, VideoAuditFinding.audit_id == audit_id)).all()
    latest_review = session.exec(
        select(VideoAuditReview)
        .where(VideoAuditReview.tenant_id == user.tenant_id, VideoAuditReview.audit_id == audit_id)
        .order_by(VideoAuditReview.id.desc())
    ).first()
    if audit.risk_level == VideoRiskLevel.needs_review and (
        latest_review is None or latest_review.decision != VideoAuditReviewDecision.confirmed_violation
    ):
        raise HTTPException(status_code=400, detail="需人工复核确认违规后才能创建整改工单")
    if latest_review is not None and latest_review.decision == VideoAuditReviewDecision.false_positive:
        raise HTTPException(status_code=400, detail="人工复核已判定为误报，不能创建整改工单")
    policies = _policies_for_findings(session, user.tenant_id, findings)
    critical = any(item.risk_level == VideoRiskLevel.critical for item in findings)
    high = any(item.risk_level == VideoRiskLevel.high for item in findings)
    priority = TicketPriority.urgent if critical else TicketPriority.high if high else TicketPriority.normal
    ticket = Ticket(
        tenant_id=user.tenant_id,
        created_by_id=user.id,
        title=f"安全巡检整改：{audit.file_name}",
        description=_build_ticket_description(audit, findings, policies),
        priority=priority,
    )
    session.add(ticket)
    session.flush()
    audit.created_ticket_id = ticket.id
    audit.updated_at = now_utc()
    session.add(audit)
    agent_run = _latest_agent_run(session, user.tenant_id, audit_id)
    if agent_run is not None:
        agent_run.status = AgentRunStatus.waiting_remediation
        agent_run.paused_reason = "整改工单已创建，等待上传整改后证据并执行复检。"
        agent_run.final_decision = {
            **(agent_run.final_decision or agent_run.decision or {}),
            "created_ticket_id": ticket.id,
            "current_business_state": "waiting_remediation_evidence",
        }
        _append_agent_step(
            session,
            agent_run,
            "create_remediation_ticket",
            f"audit_id={audit.id}",
            f"整改工单 #{ticket.id} 已创建，等待整改后证据。",
            {"ticket_id": ticket.id},
        )
    session.add(TicketFlowLog(tenant_id=user.tenant_id, ticket_id=ticket.id, actor_id=user.id, action="ticket.create_from_video_audit", detail={"audit_id": audit.id}))
    session.add(
        AuditLog(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="video_audit.create_ticket",
            target_type="video_audit",
            target_id=str(audit.id),
            detail={"ticket_id": ticket.id},
        )
    )
    session.commit()
    return TicketCreateOut(ticket_id=ticket.id, audit_id=audit.id)
