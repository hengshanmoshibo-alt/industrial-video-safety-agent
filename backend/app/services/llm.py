import httpx

from app.core.config import get_settings


class LLMProvider:
    async def complete(self, question: str, contexts: list[dict]) -> str:
        settings = get_settings()
        if settings.llm_base_url and settings.llm_api_key:
            return await self._openai_compatible(question, contexts)
        return self._local_answer(question, contexts)

    async def _openai_compatible(self, question: str, contexts: list[dict]) -> str:
        settings = get_settings()
        context_text = "\n".join([f"- {item['title']}：{item['content']}" for item in contexts])
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是电商智能客服。只基于给定知识回答，不确定时建议转人工，语气简洁专业。",
                        },
                        {"role": "user", "content": f"知识：\n{context_text}\n\n用户问题：{question}"},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _local_answer(self, question: str, contexts: list[dict]) -> str:
        if not contexts:
            return "抱歉，我暂时没有找到可确认的知识。建议为您转接人工客服进一步处理。"
        top = contexts[0]
        return f"关于“{top['title']}”：{top['content']} 如需进一步核实订单信息，我可以继续为您转接人工客服。"
