import base64
import json
import uuid
from typing import Any

import httpx
from fastapi import Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.models import (
    Ticket,
    TicketFlowLog,
    TicketPriority,
    TicketStatus,
    TicketVerification,
    TicketVerificationStatus,
    User,
    UserRole,
    AgentRunStatus,
    AgentStepStatus,
    VideoAuditAgentRun,
    VideoAuditAgentStep,
    now_utc,
)
from aicoding_shared.security import require_roles
from aicoding_shared.service import create_service_app
from aicoding_shared.storage import ObjectStorage


class TicketCreate(BaseModel):
    title: str
    description: str
    conversation_id: int | None = None
    priority: TicketPriority = TicketPriority.normal


class TicketPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: int | None = None


class TicketComment(BaseModel):
    content: str
    internal: bool = True


app = create_service_app("ticket-service")


def _audit_id_for_ticket(session: Session, ticket: Ticket) -> int | None:
    logs = session.exec(
        select(TicketFlowLog)
        .where(TicketFlowLog.tenant_id == ticket.tenant_id, TicketFlowLog.ticket_id == ticket.id)
        .order_by(TicketFlowLog.id.desc())
    ).all()
    for item in logs:
        audit_id = item.detail.get("audit_id")
        if audit_id is not None:
            return int(audit_id)
    return None


def _latest_agent_run(session: Session, tenant_id: int, audit_id: int | None) -> VideoAuditAgentRun | None:
    if audit_id is None:
        return None
    return session.exec(
        select(VideoAuditAgentRun)
        .where(VideoAuditAgentRun.tenant_id == tenant_id, VideoAuditAgentRun.audit_id == audit_id)
        .order_by(VideoAuditAgentRun.id.desc())
    ).first()


def _append_agent_verification_step(
    session: Session,
    run: VideoAuditAgentRun | None,
    status: TicketVerificationStatus,
    summary: str,
    result: dict[str, Any],
) -> None:
    if run is None or run.id is None:
        return
    steps = session.exec(
        select(VideoAuditAgentStep)
        .where(VideoAuditAgentStep.tenant_id == run.tenant_id, VideoAuditAgentStep.run_id == run.id)
        .order_by(VideoAuditAgentStep.step_order.desc())
    ).all()
    next_order = (steps[0].step_order + 1) if steps else 1
    run.current_step = "verify_remediation"
    run.current_stage = "verify_remediation"
    run.final_decision = {
        **(run.final_decision or run.decision or {}),
        "verification_status": status.value,
        "verification_summary": summary,
    }
    if status == TicketVerificationStatus.passed:
        run.status = AgentRunStatus.completed
        run.paused_reason = ""
        run.completed_at = now_utc()
    elif status == TicketVerificationStatus.failed:
        run.status = AgentRunStatus.waiting_remediation
        run.paused_reason = "复检未通过，等待继续整改并再次上传证据。"
    else:
        run.status = AgentRunStatus.waiting_review
        run.paused_reason = "复检证据无法自动确认，等待安全主管复核。"
    session.add(run)
    session.add(
        VideoAuditAgentStep(
            tenant_id=run.tenant_id,
            audit_id=run.audit_id,
            run_id=run.id,
            step_order=next_order,
            tool_name="verify_remediation",
            status=AgentStepStatus.completed,
            input_summary="上传整改后证据",
            output_summary=summary,
            detail=result,
        )
    )


def _evaluate_verification_file(filename: str) -> tuple[TicketVerificationStatus, str]:
    lower = filename.lower()
    if any(token in lower for token in ["pass", "passed", "clear", "resolved", "ok"]):
        return TicketVerificationStatus.passed, "复检证据命名显示隐患已清除，Agent 初判整改通过；建议安全主管抽查确认。"
    if any(token in lower for token in ["fail", "failed", "blocked", "unsafe", "ng"]):
        return TicketVerificationStatus.failed, "复检证据命名显示隐患仍存在，Agent 初判整改未通过，需要继续整改。"
    return TicketVerificationStatus.needs_review, "复检证据已归档，当前证据未能自动确认整改结果，建议安全主管结合原风险截图人工复核。"


def _parse_verification_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(text[start : end + 1])


async def _evaluate_verification_with_agent(ticket: Ticket, filename: str, data: bytes, content_type: str) -> tuple[TicketVerificationStatus, str, dict[str, Any]]:
    settings = get_settings()
    base_url = settings.vision_base_url or settings.llm_base_url
    api_key = settings.vision_api_key or settings.llm_api_key
    model = settings.vision_model or settings.llm_model
    if not (settings.vision_enabled and base_url and api_key and model and content_type.startswith("image/")):
        status, summary = _evaluate_verification_file(filename)
        return status, summary, {
            "agent_tool": "verify_remediation",
            "strategy": "filename-signal-fallback",
            "file_name": filename,
            "content_type": content_type,
        }
    encoded = base64.b64encode(data).decode("ascii")
    prompt = (
        "你是工业安全整改复检 Agent。请对照整改工单说明和复检图片，判断原安全隐患是否已经消除。\n"
        "只输出 JSON：{\"status\":\"passed|failed|needs_review\",\"summary\":\"中文结论\"}。\n"
        "判断原则：证据清楚显示隐患已消除则 passed；仍存在通道占用、防护打开、超载或危险干预则 failed；"
        "看不清、缺少原始对照或无法确认时 needs_review。\n\n"
        f"整改工单标题：{ticket.title}\n"
        f"整改工单说明：{ticket.description[:1600]}"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.vision_timeout_seconds) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是企业安全巡检整改复检 Agent，必须输出简体中文 JSON。"},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}},
                            ],
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            payload = _parse_verification_json(str(resp.json()["choices"][0]["message"].get("content") or ""))
        raw_status = str(payload.get("status") or "needs_review")
        status = TicketVerificationStatus(raw_status) if raw_status in {item.value for item in TicketVerificationStatus} else TicketVerificationStatus.needs_review
        summary = str(payload.get("summary") or "复检 Agent 未返回明确说明，建议人工复核。")
        return status, summary, {
            "agent_tool": "verify_remediation",
            "strategy": "vision-llm",
            "model": model,
            "file_name": filename,
            "content_type": content_type,
            "raw": payload,
        }
    except Exception as exc:
        status, summary = _evaluate_verification_file(filename)
        return status, summary, {
            "agent_tool": "verify_remediation",
            "strategy": "vision-llm-failed-fallback",
            "file_name": filename,
            "content_type": content_type,
            "error": str(exc)[:500],
        }


@app.get("/tickets")
def list_tickets(user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    return session.exec(select(Ticket).where(Ticket.tenant_id == user.tenant_id).order_by(Ticket.id.desc())).all()


@app.post("/tickets")
def create_ticket(payload: TicketCreate, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    ticket = Ticket(tenant_id=user.tenant_id, created_by_id=user.id, **payload.model_dump())
    session.add(ticket)
    session.flush()
    session.add(TicketFlowLog(tenant_id=user.tenant_id, ticket_id=ticket.id, actor_id=user.id, action="ticket.create"))
    session.commit()
    session.refresh(ticket)
    return ticket


@app.patch("/tickets/{ticket_id}")
def patch_ticket(ticket_id: int, payload: TicketPatch, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(ticket, key, value)
    ticket.updated_at = now_utc()
    session.add(TicketFlowLog(tenant_id=user.tenant_id, ticket_id=ticket.id, actor_id=user.id, action="ticket.patch", detail=changes))
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/comments")
def add_comment(ticket_id: int, payload: TicketComment, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.updated_at = now_utc()
    log = TicketFlowLog(
        tenant_id=user.tenant_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="ticket.comment",
        detail={"content": payload.content, "internal": payload.internal},
    )
    session.add(ticket)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@app.get("/tickets/{ticket_id}/flow-logs")
def list_flow_logs(ticket_id: int, user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])), session: Session = Depends(get_session)):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return session.exec(select(TicketFlowLog).where(TicketFlowLog.tenant_id == user.tenant_id, TicketFlowLog.ticket_id == ticket_id).order_by(TicketFlowLog.id)).all()


@app.get("/tickets/{ticket_id}/verification")
def list_ticket_verifications(
    ticket_id: int,
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent, UserRole.auditor])),
    session: Session = Depends(get_session),
):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return session.exec(
        select(TicketVerification)
        .where(TicketVerification.tenant_id == user.tenant_id, TicketVerification.ticket_id == ticket_id)
        .order_by(TicketVerification.id.desc())
    ).all()


@app.post("/tickets/{ticket_id}/verification")
async def create_ticket_verification(
    ticket_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.agent])),
    session: Session = Depends(get_session),
):
    ticket = session.get(Ticket, ticket_id)
    if ticket is None or ticket.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Verification file is empty")
    extension = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ".bin"
    object_key = f"tenant-{user.tenant_id}/tickets/{ticket.id}/verification/{uuid.uuid4()}{extension}"
    content_type = file.content_type or "application/octet-stream"
    ObjectStorage().put_bytes(object_key, data, content_type)
    audit_id = _audit_id_for_ticket(session, ticket)
    status, summary, result = await _evaluate_verification_with_agent(ticket, file.filename, data, content_type)
    verification = TicketVerification(
        tenant_id=user.tenant_id,
        ticket_id=ticket.id,
        audit_id=audit_id,
        object_key=object_key,
        content_type=content_type,
        status=status,
        summary=summary,
        result=result,
        created_by_id=user.id,
        completed_at=now_utc(),
    )
    ticket.updated_at = now_utc()
    if status == TicketVerificationStatus.passed:
        ticket.status = TicketStatus.closed
    elif status == TicketVerificationStatus.failed:
        ticket.status = TicketStatus.open
    _append_agent_verification_step(session, _latest_agent_run(session, user.tenant_id, audit_id), status, summary, result)
    session.add(verification)
    session.add(ticket)
    session.add(TicketFlowLog(
        tenant_id=user.tenant_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="ticket.verification",
        detail={"verification_status": status.value, "summary": summary, "object_key": object_key},
    ))
    session.commit()
    session.refresh(verification)
    return verification
