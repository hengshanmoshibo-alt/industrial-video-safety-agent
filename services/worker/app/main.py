import uuid

import httpx
from fastapi import Depends
from sqlmodel import Session, select

from aicoding_shared.config import get_settings
from aicoding_shared.db import get_session
from aicoding_shared.milvus import VectorStore
from aicoding_shared.models import ApprovalStatus, KnowledgeChunk, KnowledgeDocument
from aicoding_shared.security import tenant_from_token
from aicoding_shared.seed import ECOMMERCE_KB
from aicoding_shared.service import create_service_app
from aicoding_shared.text import chunk_text, deterministic_embedding, keywords


app = create_service_app("worker")
SEED_KEYWORDS = {title: kws for title, _, kws, _ in ECOMMERCE_KB}


def _reindex_document(session: Session, doc: KnowledgeDocument) -> int:
    old = session.exec(select(KnowledgeChunk).where(KnowledgeChunk.tenant_id == doc.tenant_id, KnowledgeChunk.document_id == doc.id)).all()
    VectorStore().delete_chunks([int(item.id) for item in old if item.id is not None])
    for item in old:
        session.delete(item)
    session.flush()

    rows = []
    count = 0
    explicit_keywords = SEED_KEYWORDS.get(doc.title)
    for part in chunk_text(doc.content):
        chunk = KnowledgeChunk(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            title=doc.title,
            category=doc.category,
            content=part,
            keywords=keywords(part, explicit_keywords),
            source=doc.source,
            vector_id=str(uuid.uuid4()),
        )
        session.add(chunk)
        session.flush()
        rows.append(
            {
                "id": int(chunk.id),
                "vector": deterministic_embedding(part),
                "tenant_id": doc.tenant_id,
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "content": part,
                "source": doc.source,
            }
        )
        count += 1
    VectorStore().upsert(rows)
    return count


@app.post("/tasks/reindex")
def reindex_all(tenant=Depends(tenant_from_token), session: Session = Depends(get_session)):
    documents = session.exec(
        select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == tenant.id,
            KnowledgeDocument.status == ApprovalStatus.published,
            KnowledgeDocument.is_active == True,  # noqa: E712
        )
    ).all()
    chunks = sum(_reindex_document(session, doc) for doc in documents)
    session.commit()
    return {"status": "completed", "documents": len(documents), "chunks": chunks}


@app.post("/tasks/evaluate")
async def evaluate(tenant=Depends(tenant_from_token)):
    cases = [
        ("我想退款多久到账？", "退款规则"),
        ("发票怎么开？", "发票开具"),
        ("快递在哪里查？", "物流查询"),
        ("优惠券不能用怎么办？", "优惠券使用"),
    ]
    passed = 0
    details = []
    async with httpx.AsyncClient(timeout=20) as client:
        for question, expected in cases:
            resp = await client.get(
                f"{get_settings().knowledge_service_url}/kb/search",
                params={"q": question, "include_trace": "true"},
                headers={"X-Tenant-Id": str(tenant.id)},
            )
            data = resp.json() if resp.status_code == 200 else {"sources": []}
            top = data["sources"][0]["title"] if data.get("sources") else ""
            ok = top == expected
            passed += int(ok)
            details.append({"question": question, "expected": expected, "top": top, "passed": ok})
    return {"status": "completed", "tenant_id": tenant.id, "score": round(passed / len(cases), 3), "cases": len(cases), "details": details}
