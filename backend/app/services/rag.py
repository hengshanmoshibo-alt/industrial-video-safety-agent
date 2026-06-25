from dataclasses import dataclass

from sqlmodel import Session

from app.models.entities import BotConfig, TicketPriority
from app.services.knowledge import search_knowledge
from app.services.llm import LLMProvider


@dataclass
class RagResult:
    answer: str
    confidence: float
    intent: str
    sources: list[dict]
    should_handoff: bool
    priority: TicketPriority
    fallback_reason: str = ""


def classify_intent(text: str) -> tuple[str, TicketPriority]:
    rules = [
        ("投诉升级", TicketPriority.high, ["投诉", "差评", "举报", "赔偿", "生气"]),
        ("退款售后", TicketPriority.normal, ["退款", "退货", "换货", "退钱"]),
        ("物流配送", TicketPriority.normal, ["物流", "快递", "发货", "地址", "配送"]),
        ("支付发票", TicketPriority.normal, ["支付", "付款", "扣款", "发票"]),
        ("人工服务", TicketPriority.high, ["人工", "真人", "客服"]),
    ]
    for intent, priority, keywords in rules:
        if any(word in text for word in keywords):
            return intent, priority
    return "通用咨询", TicketPriority.normal


async def answer_question(session: Session, question: str, bot_config: BotConfig | None) -> RagResult:
    config = bot_config or BotConfig()
    intent, priority = classify_intent(question)
    sources = search_knowledge(session, question)
    confidence = min(0.98, sources[0]["score"] / 3 if sources else 0)
    keyword_handoff = any(word in question for word in config.handoff_keywords)
    should_handoff = keyword_handoff or confidence < config.confidence_threshold
    answer = await LLMProvider().complete(question, sources)
    fallback_reason = ""
    if confidence < config.confidence_threshold:
        fallback_reason = "low_confidence"
        answer = config.fallback_message
    return RagResult(
        answer=answer,
        confidence=round(confidence, 3),
        intent=intent,
        sources=sources,
        should_handoff=should_handoff,
        priority=priority,
        fallback_reason=fallback_reason,
    )
