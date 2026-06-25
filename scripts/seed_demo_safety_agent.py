"""Seed a deterministic demo run for the industrial safety Agent.

This script is intentionally database-level, not API-level. It creates one
complete inspection with video memory, bbox evidence, Agent steps, policy
decision, alert record, and report without calling any external VLM provider.
Run it inside the video-audit-service container for the most reliable MinIO and
PostgreSQL connectivity.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from sqlmodel import Session, select  # noqa: E402

from aicoding_shared.db import engine, init_db  # noqa: E402
from aicoding_shared.models import (  # noqa: E402
    AgentRunStatus,
    AgentStepStatus,
    AuditLog,
    Department,
    SafetyPolicy,
    Tenant,
    Ticket,
    TicketFlowLog,
    TicketPriority,
    TicketStatus,
    TicketVerification,
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
    VideoAuditStatus,
    VideoMemorySegment,
    VideoRiskLevel,
    now_utc,
)
from aicoding_shared.security import hash_password  # noqa: E402
from aicoding_shared.storage import ObjectStorage  # noqa: E402


DEMO_FILE_NAME = "demo_walkway_violation.mp4"
DEMO_VIDEO_KEY = "tenant-{tenant_id}/demo/demo_walkway_violation.mp4"
DEMO_EVIDENCE_KEY = "tenant-{tenant_id}/demo/evidence/walkway_violation_bbox.svg"
DEMO_BBOX = [600, 360, 790, 500]


def evidence_svg() -> bytes:
    """Return a lightweight deterministic evidence image with one red bbox."""
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#d9dde1"/>
  <rect x="0" y="0" width="1280" height="720" fill="#c8ced5"/>
  <path d="M790 0 L1070 0 L1185 720 L860 720 Z" fill="#1f8f55" opacity="0.95"/>
  <path d="M755 0 L785 0 L855 720 L825 720 Z" fill="#f6d44a"/>
  <path d="M1075 0 L1105 0 L1225 720 L1195 720 Z" fill="#f6d44a"/>
  <rect x="60" y="180" width="280" height="260" rx="8" fill="#2d6fb3"/>
  <rect x="92" y="220" width="210" height="82" rx="4" fill="#f3f4f6"/>
  <rect x="380" y="120" width="190" height="160" rx="8" fill="#f97316"/>
  <rect x="415" y="300" width="150" height="18" fill="#8b949e"/>
  <g transform="translate(695 430)">
    <ellipse cx="0" cy="0" rx="86" ry="42" fill="#737373"/>
    <ellipse cx="0" cy="-4" rx="60" ry="26" fill="#bdbdbd"/>
    <ellipse cx="0" cy="-8" rx="30" ry="12" fill="#efefef"/>
    <path d="M-80 -5 C-35 45 40 48 86 -2" fill="none" stroke="#4b5563" stroke-width="16"/>
  </g>
  <rect x="600" y="360" width="190" height="140" fill="none" stroke="#e11d48" stroke-width="8"/>
  <text x="36" y="54" font-family="Arial, sans-serif" font-size="28" fill="#111827">Demo evidence: walkway obstruction</text>
  <text x="36" y="92" font-family="Arial, sans-serif" font-size="20" fill="#374151">Single bbox highlights the metal coil blocking the marked pedestrian path.</text>
</svg>
""".encode("utf-8")


def video_placeholder() -> bytes:
    return b"demo placeholder: original video bytes are not required for seeded UI evidence\n"


def bootstrap_identity(session: Session) -> tuple[Tenant, User]:
    tenant = session.exec(select(Tenant).where(Tenant.slug == "default")).first()
    if tenant is None:
        tenant = Tenant(slug="default", name="Demo Factory", plan="enterprise")
        session.add(tenant)
        session.flush()
    if tenant.id is None:
        session.flush()

    department = session.exec(select(Department).where(Department.tenant_id == tenant.id)).first()
    if department is None:
        department = Department(tenant_id=tenant.id, name="Safety Office")
        session.add(department)
        session.flush()

    user = session.exec(select(User).where(User.tenant_id == tenant.id, User.username == "admin")).first()
    if user is None:
        user = User(
            tenant_id=tenant.id,
            department_id=department.id,
            username="admin",
            display_name="Demo Admin",
            role=UserRole.admin,
            password_hash=hash_password("Admin123!"),
        )
        session.add(user)
        session.flush()
    return tenant, user


def ensure_policy(session: Session, tenant_id: int) -> SafetyPolicy:
    policy = session.exec(
        select(SafetyPolicy).where(
            SafetyPolicy.tenant_id == tenant_id,
            SafetyPolicy.code == "policy.walkway_violation",
        )
    ).first()
    if policy is not None:
        return policy
    policy = SafetyPolicy(
        tenant_id=tenant_id,
        code="policy.walkway_violation",
        label="walkway_violation",
        title="安全通道占用处置策略",
        description="安全通道、消防通道和逃生路径不得堆放物料。发现占用时应立即清理并恢复通行。",
        severity=VideoRiskLevel.high,
        auto_alert=True,
        requires_review=False,
        recommend_ticket=True,
        requires_verification=True,
        due_hours=2,
        keywords=["安全通道", "黄色线", "物料占用", "逃生路径"],
    )
    session.add(policy)
    session.flush()
    return policy


def delete_rows(session: Session, model, *conditions) -> int:
    rows = session.exec(select(model).where(*conditions)).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def reset_existing_demo(session: Session, tenant_id: int) -> int:
    audits = session.exec(
        select(VideoAudit).where(
            VideoAudit.tenant_id == tenant_id,
            VideoAudit.file_name == DEMO_FILE_NAME,
        )
    ).all()
    removed = 0
    for audit in audits:
        if audit.id is None:
            continue
        ticket_id = audit.created_ticket_id
        run_ids = [
            item.id
            for item in session.exec(
                select(VideoAuditAgentRun).where(
                    VideoAuditAgentRun.tenant_id == tenant_id,
                    VideoAuditAgentRun.audit_id == audit.id,
                )
            ).all()
            if item.id is not None
        ]
        if run_ids:
            for run_id in run_ids:
                removed += delete_rows(session, VideoAuditAgentStep, VideoAuditAgentStep.tenant_id == tenant_id, VideoAuditAgentStep.run_id == run_id)
        removed += delete_rows(session, VideoAuditAgentRun, VideoAuditAgentRun.tenant_id == tenant_id, VideoAuditAgentRun.audit_id == audit.id)
        removed += delete_rows(session, VideoMemorySegment, VideoMemorySegment.tenant_id == tenant_id, VideoMemorySegment.audit_id == audit.id)
        removed += delete_rows(session, VideoAuditReview, VideoAuditReview.tenant_id == tenant_id, VideoAuditReview.audit_id == audit.id)
        removed += delete_rows(session, VideoAuditAlertEvent, VideoAuditAlertEvent.tenant_id == tenant_id, VideoAuditAlertEvent.audit_id == audit.id)
        removed += delete_rows(session, VideoAuditEvidence, VideoAuditEvidence.tenant_id == tenant_id, VideoAuditEvidence.audit_id == audit.id)
        removed += delete_rows(session, VideoAuditFinding, VideoAuditFinding.tenant_id == tenant_id, VideoAuditFinding.audit_id == audit.id)
        removed += delete_rows(session, VideoAuditReport, VideoAuditReport.tenant_id == tenant_id, VideoAuditReport.audit_id == audit.id)
        removed += delete_rows(session, TicketVerification, TicketVerification.tenant_id == tenant_id, TicketVerification.audit_id == audit.id)
        removed += delete_rows(
            session,
            AuditLog,
            AuditLog.tenant_id == tenant_id,
            AuditLog.target_type == "video_audit",
            AuditLog.target_id == str(audit.id),
        )
        if ticket_id is not None:
            removed += delete_rows(session, TicketVerification, TicketVerification.tenant_id == tenant_id, TicketVerification.ticket_id == ticket_id)
            removed += delete_rows(session, TicketFlowLog, TicketFlowLog.tenant_id == tenant_id, TicketFlowLog.ticket_id == ticket_id)
            removed += delete_rows(session, Ticket, Ticket.tenant_id == tenant_id, Ticket.id == ticket_id)
        session.delete(audit)
        removed += 1
    session.flush()
    return removed


def seed_demo(with_ticket: bool = False) -> dict:
    init_db()
    storage = ObjectStorage()
    now = now_utc()

    with Session(engine) as session:
        tenant, user = bootstrap_identity(session)
        if tenant.id is None or user.id is None:
            raise RuntimeError("Failed to bootstrap demo tenant/user")
        removed = reset_existing_demo(session, tenant.id)
        policy = ensure_policy(session, tenant.id)

        video_key = DEMO_VIDEO_KEY.format(tenant_id=tenant.id)
        evidence_key = DEMO_EVIDENCE_KEY.format(tenant_id=tenant.id)
        storage.put_bytes(video_key, video_placeholder(), "video/mp4")
        storage.put_bytes(evidence_key, evidence_svg(), "image/svg+xml")

        audit = VideoAudit(
            tenant_id=tenant.id,
            uploader_id=user.id,
            file_name=DEMO_FILE_NAME,
            content_type="video/mp4",
            object_key=video_key,
            status=VideoAuditStatus.completed,
            risk_level=VideoRiskLevel.high,
            summary="发现 1 个高风险片段：圆形金属卷材占用黄色安全通道，影响人员通行和应急疏散。",
            duration_ms=10_000,
            completed_at=now,
            updated_at=now,
        )
        session.add(audit)
        session.flush()
        if audit.id is None:
            raise RuntimeError("Failed to create demo audit")

        finding = VideoAuditFinding(
            tenant_id=tenant.id,
            audit_id=audit.id,
            category="unsafe_behavior",
            label="walkway_violation",
            risk_level=VideoRiskLevel.high,
            confidence=0.92,
            start_ms=4_000,
            end_ms=8_000,
            bbox=DEMO_BBOX,
            reason="画面中圆形金属卷材放置在黄色安全通道标线内，占用人员通行路径，存在绊倒、碰撞和应急疏散受阻风险。",
            recommendation="立即将卷材移至指定物料暂存区，恢复黄色安全通道畅通；补充通道巡检和物料暂存责任人记录。",
        )
        session.add(finding)
        session.flush()
        if finding.id is None:
            raise RuntimeError("Failed to create demo finding")

        session.add(
            VideoAuditEvidence(
                tenant_id=tenant.id,
                audit_id=audit.id,
                finding_id=finding.id,
                timestamp_ms=6_000,
                frame_object_key=evidence_key,
                caption="6s · 圆形金属卷材占用黄色安全通道，红框为风险主体。",
                model_score=0.92,
            )
        )

        memory_rows = [
            (0, 2_000, 0, [], "", "画面可见冲压设备、黄色标线和绿色安全通道，通道主体保持畅通。", "none", 0.0),
            (4_000, 6_000, 2, DEMO_BBOX, "圆形金属卷材", "圆形金属卷材开始进入黄色安全通道范围，已影响通行路径。", "walkway_violation", 0.88),
            (6_000, 8_000, 3, DEMO_BBOX, "圆形金属卷材", "卷材位于安全通道标线内，构成明确通道占用风险。", "walkway_violation", 0.92),
        ]
        for start_ms, end_ms, frame_index, bbox, subject, evidence, label, confidence in memory_rows:
            raw = {
                "label": label,
                "risk_level": "high" if label != "none" else "low",
                "confidence": confidence,
                "bbox": bbox,
                "reason": evidence,
            }
            session.add(
                VideoMemorySegment(
                    tenant_id=tenant.id,
                    audit_id=audit.id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    frame_index=frame_index,
                    frame_object_key=evidence_key,
                    visible_objects=["press machine", "yellow safety line", "green walkway", "metal coil"],
                    risk_subject=subject,
                    bbox=bbox or None,
                    evidence=evidence,
                    raw_finding=raw,
                    vlm_raw_output={
                        "provider": "seeded-demo",
                        "model": "qwen3-vl-plus",
                        "output_language": "zh-CN",
                        "raw_json": raw,
                    },
                    review_status="unreviewed",
                )
            )

        decision = {
            "overall_risk": "high",
            "send_feishu_alert": True,
            "needs_human_review": False,
            "recommend_ticket": True,
            "requires_verification": True,
            "recommended_due_hours": 2,
            "decision_reason": "检测到安全通道被卷材占用，影响人员通行和应急疏散，按安全策略触发高风险告警并建议创建整改工单。",
            "matched_policy": policy.code,
        }
        run = VideoAuditAgentRun(
            tenant_id=tenant.id,
            audit_id=audit.id,
            status=AgentRunStatus.waiting_remediation,
            goal="完成工业安全巡检、风险决策和整改闭环建议",
            current_step="recommend_remediation_ticket",
            current_stage="waiting_supervisor_ticket",
            paused_reason="等待主管确认创建整改工单，并在整改完成后上传复检证据。",
            decision=decision,
            final_decision=decision,
            started_at=now - timedelta(seconds=34),
            completed_at=now,
        )
        session.add(run)
        session.flush()
        if run.id is None:
            raise RuntimeError("Failed to create demo AgentRun")

        steps = [
            ("receive_task", "audit_id=demo", "已接收安全巡检视频并创建可追踪 AgentRun。", 0, []),
            ("load_video", DEMO_FILE_NAME, "视频已加载，时长 10s。", 420, [{"type": "video", "object_key": video_key}]),
            ("sample_video_frames", "interval=2s", "抽取 5 张关键帧并写入视频记忆。", 360, [{"type": "frame", "object_key": evidence_key}]),
            ("inspect_safety_frame", "qwen3-vl-plus frame grounding", "视觉模型识别到安全通道占用，并返回风险主体 bbox。", 24_500, [{"type": "bbox", "bbox": DEMO_BBOX}]),
            ("validate_bbox", "bbox sanity check", "bbox 位于画面有效区域，面积和宽高比通过校验。", 2, [{"type": "evidence", "object_key": evidence_key}]),
            ("merge_risk_events", "merge adjacent frame findings", "相邻通道占用片段已合并为 1 个风险事件。", 1, []),
            ("build_video_memory", "persist frame-level memory", "写入 3 个视频记忆片段，其中 2 个包含风险主体 bbox。", 3, [{"type": "memory", "count": 3}]),
            ("decide_safety_action", "apply SafetyPolicy", "命中安全通道占用策略：自动告警、建议工单、要求复检。", 1, [{"type": "policy", "code": policy.code}]),
            ("write_audit_report", "structured Chinese report", "已生成中文结构化审核报告。", 820, []),
            ("send_feishu_alert", "high risk alert", "已记录飞书高风险告警事件。", 120, [{"type": "alert", "channel": "feishu"}]),
            ("recommend_remediation_ticket", "ticket recommendation", "已生成整改工单建议，等待主管确认创建。", 0, []),
        ]
        for index, (tool, input_summary, output_summary, latency, artifacts) in enumerate(steps, start=1):
            session.add(
                VideoAuditAgentStep(
                    tenant_id=tenant.id,
                    audit_id=audit.id,
                    run_id=run.id,
                    step_order=index,
                    tool_name=tool,
                    status=AgentStepStatus.completed,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    detail={"why": output_summary},
                    artifact_refs=artifacts,
                    latency_ms=latency,
                )
            )

        session.add(
            VideoAuditAlertEvent(
                tenant_id=tenant.id,
                audit_id=audit.id,
                channel="feishu",
                status="sent",
                risk_level=VideoRiskLevel.high,
                message="【演示告警】检测到安全通道占用风险，请安全主管查看证据并派发整改。",
            )
        )
        session.add(
            VideoAuditReport(
                tenant_id=tenant.id,
                audit_id=audit.id,
                model_version="qwen3-vl-plus",
                processing_ms=26_226,
                report={
                    "analysis_provider": "dashscope-vlm",
                    "analysis_model": "qwen3-vl-plus",
                    "agent_decision": decision,
                    "llm_report": (
                        "本次巡检发现圆形金属卷材占用黄色安全通道。该行为会阻碍人员通行和应急疏散，"
                        "判定为高风险。建议立即清理通道、核查物料暂存流程，并在整改后上传复检证据。"
                    ),
                    "timeline": [
                        {
                            "start_ms": finding.start_ms,
                            "end_ms": finding.end_ms,
                            "label": finding.label,
                            "risk_level": finding.risk_level.value,
                            "confidence": finding.confidence,
                            "bbox": finding.bbox,
                        }
                    ],
                },
            )
        )
        if with_ticket:
            ticket = Ticket(
                tenant_id=tenant.id,
                title=f"安全巡检整改：{DEMO_FILE_NAME}",
                description=(
                    "来源：安全巡检演示任务\n"
                    "问题：圆形金属卷材占用黄色安全通道。\n"
                    "要求：2 小时内移除卷材，恢复通道畅通，并上传整改后证据。"
                ),
                status=TicketStatus.open,
                priority=TicketPriority.high,
                created_by_id=user.id,
            )
            session.add(ticket)
            session.flush()
            audit.created_ticket_id = ticket.id
            session.add(TicketFlowLog(tenant_id=tenant.id, ticket_id=ticket.id or 0, actor_id=user.id, action="ticket.seed_demo", detail={"audit_id": audit.id}))

        session.add(
            AuditLog(
                tenant_id=tenant.id,
                actor_id=user.id,
                action="demo.seed_safety_agent",
                target_type="video_audit",
                target_id=str(audit.id),
                detail={"file_name": DEMO_FILE_NAME, "removed_rows": removed, "with_ticket": with_ticket},
            )
        )
        session.add(audit)
        session.commit()
        return {
            "audit_id": audit.id,
            "tenant_id": tenant.id,
            "user": user.username,
            "removed_rows": removed,
            "with_ticket": with_ticket,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a deterministic industrial safety Agent demo.")
    parser.add_argument("--with-ticket", action="store_true", help="Also create a remediation ticket. By default the UI can demonstrate the Create Ticket button.")
    args = parser.parse_args()

    result = seed_demo(with_ticket=args.with_ticket)
    print("Seeded industrial safety Agent demo:")
    print(f"  audit_id: {result['audit_id']}")
    print(f"  tenant_id: {result['tenant_id']}")
    print(f"  login: {result['user']} / Admin123!")
    print(f"  removed_previous_demo_rows: {result['removed_rows']}")
    print(f"  with_ticket: {result['with_ticket']}")
    print("  open: http://localhost:5173")


if __name__ == "__main__":
    main()
