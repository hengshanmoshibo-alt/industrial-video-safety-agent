import time

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.models import ModelCallLog, ModelProvider, ModelRoute, PromptTemplate, PromptVersion, TicketPriority
from aicoding_shared.security import tenant_from_token
from aicoding_shared.service import create_service_app
from aicoding_shared.text import detect_risk


class AnswerIn(BaseModel):
    question: str


class ModelProviderIn(BaseModel):
    name: str
    provider_type: str = "openai-compatible"
    base_url: str = ""
    model: str = "mock-local"
    enabled: bool = True


class ModelRouteIn(BaseModel):
    name: str
    intent: str = "default"
    provider_id: int | None = None
    priority: int = 100
    enabled: bool = True


class PromptVersionIn(BaseModel):
    template_id: int | None = None
    template_name: str = "客服RAG提示词"
    content: str
    is_active: bool = True


def classify_intent(text: str) -> tuple[str, TicketPriority]:
    if any(word in text for word in ["投诉", "差评", "举报", "赔偿"]):
        return "投诉升级", TicketPriority.high
    if any(word in text for word in ["退款", "退货", "换货", "退钱"]):
        return "退款售后", TicketPriority.normal
    if any(word in text for word in ["物流", "快递", "发货", "地址"]):
        return "物流配送", TicketPriority.normal
    if any(word in text for word in ["支付", "付款", "扣款", "发票"]):
        return "支付发票", TicketPriority.normal
    if any(word in text for word in ["人工", "真人", "客服"]):
        return "人工服务", TicketPriority.high
    return "通用咨询", TicketPriority.normal


async def _mock_or_real_answer(question: str, sources: list[dict]) -> tuple[str, str, str]:
    settings = get_settings()
    if settings.llm_base_url and settings.llm_api_key:
        context = "\n".join([f"- {s['title']}：{s['content']}" for s in sources])
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": "你是企业级电商智能客服，只根据知识库回答，不确定时建议转人工。"},
                        {"role": "user", "content": f"知识：\n{context}\n\n问题：{question}"},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"], "openai-compatible", settings.llm_model
    if not sources:
        return "抱歉，我暂时无法确认这个问题，建议为您转接人工客服。", "mock-local", "mock-local"
    top = sources[0]
    return f"关于“{top['title']}”：{top['content']} 如需进一步核实订单信息，我可以继续为您转接人工客服。", "mock-local", "mock-local"


def bootstrap() -> None:
    from aicoding_shared.db import engine
    from aicoding_shared.models import Tenant

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == "default")).first()
        if tenant is None:
            tenant = Tenant(slug="default", name="默认企业")
            session.add(tenant)
            session.flush()
        provider = session.exec(select(ModelProvider).where(ModelProvider.tenant_id == tenant.id, ModelProvider.name == "Mock Local")).first()
        if provider is None:
            provider = ModelProvider(tenant_id=tenant.id, name="Mock Local", provider_type="mock", model="mock-local")
            session.add(provider)
            session.flush()
        if session.exec(select(ModelRoute).where(ModelRoute.tenant_id == tenant.id, ModelRoute.name == "默认路由")).first() is None:
            session.add(ModelRoute(tenant_id=tenant.id, name="默认路由", provider_id=provider.id))
        template = session.exec(select(PromptTemplate).where(PromptTemplate.tenant_id == tenant.id, PromptTemplate.name == "客服RAG提示词")).first()
        if template is None:
            template = PromptTemplate(tenant_id=tenant.id, name="客服RAG提示词", description="默认企业客服回答提示词")
            session.add(template)
            session.flush()
            session.add(PromptVersion(tenant_id=tenant.id, template_id=template.id, version=1, content="只根据知识库回答，不确定时转人工。"))
        session.commit()


app = create_service_app("ai-orchestrator", bootstrap=bootstrap)


@app.post("/ai/answer")
async def answer(payload: AnswerIn, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{get_settings().knowledge_service_url}/kb/search",
            params={"q": payload.question, "include_trace": "true"},
            headers={"X-Tenant-Id": str(tenant.id)},
        )
        retrieval = resp.json() if resp.status_code == 200 else {"sources": [], "confidence": 0, "retrieval_trace": {"error": resp.text}}
        sources = retrieval.get("sources", [])
    intent, priority = classify_intent(payload.question)
    confidence = float(retrieval.get("confidence", 0) or 0)
    risk_tags = detect_risk(payload.question)
    should_handoff = confidence < 0.35 or "complaint" in risk_tags or "handoff" in risk_tags
    content, provider, model = await _mock_or_real_answer(payload.question, sources)
    if confidence < 0.35:
        content = "抱歉，我暂时无法确认这个问题，建议为您转接人工客服。"
    session.add(
        ModelCallLog(
            tenant_id=tenant.id,
            provider=provider,
            model=model,
            prompt_version="客服RAG提示词:v1",
            input_summary=payload.question[:200],
            output_summary=content[:200],
            latency_ms=int((time.perf_counter() - start) * 1000),
            prompt_tokens=len(payload.question),
            completion_tokens=len(content),
        )
    )
    session.commit()
    return {
        "answer": content,
        "confidence": round(confidence, 3),
        "intent": intent,
        "priority": priority,
        "sources": sources,
        "retrieval_trace": retrieval.get("retrieval_trace", {}),
        "risk_tags": risk_tags,
        "should_handoff": should_handoff,
    }


@app.get("/models/providers")
def list_providers(tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    return session.exec(select(ModelProvider).where(ModelProvider.tenant_id == tenant.id)).all()


@app.post("/models/providers")
def create_provider(payload: ModelProviderIn, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    provider = ModelProvider(tenant_id=tenant.id, **payload.model_dump())
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


@app.get("/models/routes")
def list_routes(tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    return session.exec(select(ModelRoute).where(ModelRoute.tenant_id == tenant.id)).all()


@app.post("/models/routes")
def create_route(payload: ModelRouteIn, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    route = ModelRoute(tenant_id=tenant.id, **payload.model_dump())
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


@app.get("/prompts/versions")
def list_prompt_versions(tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    return session.exec(select(PromptVersion).where(PromptVersion.tenant_id == tenant.id).order_by(PromptVersion.id.desc())).all()


@app.post("/prompts/versions")
def create_prompt_version(payload: PromptVersionIn, tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    template_id = payload.template_id
    if template_id is None:
        template = session.exec(select(PromptTemplate).where(PromptTemplate.tenant_id == tenant.id, PromptTemplate.name == payload.template_name)).first()
        if template is None:
            template = PromptTemplate(tenant_id=tenant.id, name=payload.template_name)
            session.add(template)
            session.flush()
        template_id = template.id
    else:
        template = session.get(PromptTemplate, template_id)
        if template is None or template.tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Prompt template not found")
    if template_id is None:
        raise HTTPException(status_code=400, detail="Prompt template is required")
    latest = session.exec(
        select(PromptVersion).where(PromptVersion.tenant_id == tenant.id, PromptVersion.template_id == template_id).order_by(PromptVersion.version.desc())
    ).first()
    version = (latest.version if latest else 0) + 1
    prompt = PromptVersion(tenant_id=tenant.id, template_id=template_id, version=version, content=payload.content, is_active=payload.is_active)
    if template is not None and payload.is_active:
        template.active_version = version
        session.add(template)
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt


@app.get("/model-call-logs")
def list_model_call_logs(tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    return session.exec(select(ModelCallLog).where(ModelCallLog.tenant_id == tenant.id).order_by(ModelCallLog.id.desc()).limit(200)).all()
