import re
from collections import Counter

from sqlmodel import Session, select

from app.models.entities import KnowledgeChunk, KnowledgeDocument
from app.services.seed_data import ECOMMERCE_KB


def extract_keywords(text: str, explicit: list[str] | None = None) -> list[str]:
    keywords = list(explicit or [])
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", text)
    for token, _ in Counter(tokens).most_common(12):
        if token not in keywords:
            keywords.append(token)
    return keywords[:20]


def chunk_text(content: str, max_len: int = 420) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"[\n。；;]+", content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) > max_len and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}。{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks or [content[:max_len]]


def index_document(session: Session, document: KnowledgeDocument, keywords: list[str] | None = None) -> int:
    existing = session.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)).all()
    for item in existing:
        session.delete(item)
    session.flush()

    count = 0
    for part in chunk_text(document.content):
        session.add(
            KnowledgeChunk(
                document_id=document.id,
                title=document.title,
                category=document.category,
                content=part,
                source=document.source,
                keywords=extract_keywords(part, keywords),
            )
        )
        count += 1
    return count


def seed_ecommerce_kb(session: Session) -> dict[str, int]:
    created = 0
    chunks = 0
    for item in ECOMMERCE_KB:
        exists = session.exec(
            select(KnowledgeDocument).where(
                KnowledgeDocument.title == item["title"],
                KnowledgeDocument.source == "seed:ecommerce",
            )
        ).first()
        if exists:
            continue
        doc = KnowledgeDocument(
            title=item["title"],
            category=item["category"],
            source="seed:ecommerce",
            license="internal_seed",
            content=item["content"],
        )
        session.add(doc)
        session.flush()
        chunks += index_document(session, doc, item["keywords"])
        created += 1
    session.commit()
    return {"documents": created, "chunks": chunks}


def search_knowledge(session: Session, query: str, limit: int = 4) -> list[dict]:
    chunks = session.exec(select(KnowledgeChunk)).all()
    query_lower = query.lower()
    query_chars = set(query_lower)
    ranked: list[tuple[float, KnowledgeChunk]] = []
    for chunk in chunks:
        score = 0.0
        text = f"{chunk.title} {chunk.category} {chunk.content}".lower()
        for keyword in chunk.keywords:
            if keyword and keyword.lower() in query_lower:
                score += 1.8
        overlap = len(query_chars & set(text)) / max(len(query_chars), 1)
        score += overlap
        if any(word in text for word in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", query)):
            score += 0.8
        if score > 0.12:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "title": chunk.title,
            "category": chunk.category,
            "content": chunk.content,
            "score": round(score, 3),
            "source": chunk.source,
        }
        for score, chunk in ranked[:limit]
    ]
