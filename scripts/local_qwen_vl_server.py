"""OpenAI-compatible local Qwen2.5-VL server for video safety inspection.

This server implements the minimal `/v1/chat/completions` endpoint used by
`video-worker`. It accepts text plus base64 image_url messages, runs a local
Qwen2.5-VL model, and returns an OpenAI-style response.
"""

from __future__ import annotations

import argparse
import base64
import io
import time
import uuid
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]]
    temperature: float | None = 0.0
    max_tokens: int | None = 768
    max_new_tokens: int | None = None


app = FastAPI(title="Local Qwen2.5-VL OpenAI-compatible Server")
MODEL = None
PROCESSOR = None
MODEL_PATH = ""
MAX_IMAGE_SIDE = 768


def _decode_image_url(url: str) -> Image.Image:
    if not url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Only base64 data:image URLs are supported")
    try:
        _, encoded = url.split(",", 1)
        image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
        if MAX_IMAGE_SIDE > 0:
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        return image
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image_url payload: {exc}") from exc


def _convert_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content", "")
        if isinstance(content, str):
            converted.append({"role": role, "content": [{"type": "text", "text": content}]})
            continue
        if not isinstance(content, list):
            converted.append({"role": role, "content": [{"type": "text", "text": str(content)}]})
            continue
        parts: list[dict[str, Any]] = []
        for item in content:
            item_type = item.get("type")
            if item_type == "text":
                parts.append({"type": "text", "text": str(item.get("text") or "")})
            elif item_type == "image_url":
                image_url = item.get("image_url") or {}
                parts.append({"type": "image", "image": _decode_image_url(str(image_url.get("url") or ""))})
        converted.append({"role": role, "content": parts})
    return converted


def load_model(model_path: str, gpu_memory: str, offload_folder: str) -> None:
    global MODEL, PROCESSOR, MODEL_PATH
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    MODEL_PATH = model_path
    PROCESSOR = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    max_memory = {0: gpu_memory, "cpu": "32GiB"} if torch.cuda.is_available() else None
    MODEL = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_path,
        torch_dtype="auto",
        device_map="auto",
        max_memory=max_memory,
        offload_folder=offload_folder,
        trust_remote_code=True,
    )
    MODEL.eval()


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": MODEL_PATH, "object": "model"}]}


@app.post("/v1/chat/completions")
def chat_completions(payload: ChatCompletionRequest) -> dict[str, Any]:
    if MODEL is None or PROCESSOR is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    messages = _convert_messages(payload.messages)
    text = PROCESSOR.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs = []
    for message in messages:
        for part in message.get("content", []):
            if part.get("type") == "image":
                image_inputs.append(part["image"])
    inputs = PROCESSOR(
        text=[text],
        images=image_inputs or None,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(MODEL.device)
    max_new_tokens = int(payload.max_new_tokens or payload.max_tokens or 768)
    with torch.inference_mode():
        generated_ids = MODEL.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    generated_ids = generated_ids[:, inputs.input_ids.shape[1] :]
    output = PROCESSOR.batch_decode(generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.model or MODEL_PATH,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": output}, "finish_reason": "stop"}],
    }


def main() -> None:
    global MAX_IMAGE_SIDE
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default=r"D:\home\software\huggingface\models\Qwen2.5-VL-3B-Instruct-ms")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--gpu-memory", default="7GiB")
    parser.add_argument("--offload-folder", default=r"D:\home\software\huggingface\offload\qwen-vl-3b")
    parser.add_argument("--max-image-side", type=int, default=768)
    args = parser.parse_args()
    MAX_IMAGE_SIDE = args.max_image_side
    load_model(args.model_path, args.gpu_memory, args.offload_folder)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
