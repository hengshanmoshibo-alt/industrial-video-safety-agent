from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("industrial-safety-agent")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _image_data_url(path: str) -> str:
    image_path = Path(path)
    data = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def _feishu_sign(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@mcp.tool()
async def inspect_safety_frame(image_path: str, instruction: str = "") -> dict[str, Any]:
    """Inspect one industrial safety frame and return JSON-like risk findings."""
    base_url = _env("VISION_BASE_URL") or _env("LLM_BASE_URL")
    api_key = _env("VISION_API_KEY") or _env("LLM_API_KEY")
    model = _env("VISION_MODEL") or _env("LLM_MODEL", "qwen3-vl-plus")
    if not (base_url and api_key and model):
        return {"status": "not_configured", "message": "VISION_BASE_URL / VISION_API_KEY / VISION_MODEL is required"}
    prompt = (
        "你是工业安全巡检视觉工具。只依据图片判断安全风险，输出简体中文 JSON。"
        "如果发现风险，请返回 findings 数组，每项包含 label、risk_level、confidence、bbox、reason、recommendation。"
        "bbox 使用 [x_min,y_min,x_max,y_max]，坐标归一化到 0-1000。"
    )
    if instruction:
        prompt += f"\n补充要求：{instruction}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请检查这张工业/仓储巡检画面。"},
                            {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                        ],
                    },
                ],
                "temperature": 0,
                "max_tokens": 1024,
            },
        )
        response.raise_for_status()
    return {"status": "ok", "model": model, "content": response.json()["choices"][0]["message"]["content"]}


@mcp.tool()
async def query_video_memory(audit_id: int, label: str = "", review_status: str = "", has_bbox: bool | None = None) -> dict[str, Any]:
    """Query video memory segments from the safety platform API."""
    base = _env("SAFETY_AGENT_API_BASE", "http://localhost:8000/api")
    token = _env("SAFETY_AGENT_TOKEN")
    if not token:
        return {"status": "not_configured", "message": "SAFETY_AGENT_TOKEN is required"}
    params: dict[str, Any] = {}
    if label:
        params["label"] = label
    if review_status:
        params["review_status"] = review_status
    if has_bbox is not None:
        params["has_bbox"] = has_bbox
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{base.rstrip('/')}/video-audits/{audit_id}/memory",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        response.raise_for_status()
    return {"status": "ok", "audit_id": audit_id, "segments": response.json()}


@mcp.tool()
async def send_feishu_alert(text: str) -> dict[str, Any]:
    """Send a Feishu text alert for a safety inspection event."""
    webhook = _env("FEISHU_WEBHOOK_URL")
    secret = _env("FEISHU_WEBHOOK_SECRET")
    if not webhook:
        return {"status": "not_configured", "message": "FEISHU_WEBHOOK_URL is required"}
    payload: dict[str, Any] = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _feishu_sign(secret, timestamp)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook, json=payload)
        response.raise_for_status()
    return {"status": "sent"}


if __name__ == "__main__":
    mcp.run()
