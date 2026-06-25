import hashlib
import math
import re
from collections import Counter


def keywords(text: str, explicit: list[str] | None = None) -> list[str]:
    result = list(explicit or [])
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", text)
    for token, _ in Counter(tokens).most_common(16):
        if token not in result:
            result.append(token)
    return result[:24]


def chunk_text(content: str, max_len: int = 420) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"[\n。；;]+", content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > max_len:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}。{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks or [content[:max_len]]


def deterministic_embedding(text: str, dim: int = 128) -> list[float]:
    vector = [0.0] * dim
    for token in re.findall(r"[\u4e00-\u9fff]{1,}|[A-Za-z0-9]{2,}", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1 if digest[4] % 2 else -1
        vector[idx] += sign * (1 + min(len(token), 8) / 8)
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [round(item / norm, 6) for item in vector]


def detect_risk(text: str) -> list[str]:
    rules = {
        "complaint": ["投诉", "差评", "举报", "赔偿", "生气"],
        "refund": ["退款", "退货", "退钱"],
        "handoff": ["人工", "真人", "客服"],
        "pii": ["手机号", "身份证", "地址", "银行卡"],
    }
    return [tag for tag, words in rules.items() if any(word in text for word in words)]

