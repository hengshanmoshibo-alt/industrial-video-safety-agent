from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlmodel import Session, select

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.entities import AuditLog, KnowledgeDocument, User, UserRole
from app.schemas.api import KnowledgeDocumentCreate, KnowledgeDocumentOut, OpenDatasetImportIn
from app.services.knowledge import index_document, seed_ecommerce_kb
from app.services.seed_data import OPEN_DATASETS

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles([UserRole.admin, UserRole.supervisor, UserRole.kb_manager])),
):
    return session.exec(select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())).all()


@router.post("/documents", response_model=KnowledgeDocumentOut)
def create_document(
    payload: KnowledgeDocumentCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    doc = KnowledgeDocument(**payload.model_dump())
    session.add(doc)
    session.flush()
    chunks = index_document(session, doc)
    session.add(AuditLog(actor_id=actor.id, action="kb.document.create", target_type="document", target_id=str(doc.id), detail={"chunks": chunks}))
    session.commit()
    session.refresh(doc)
    return doc


@router.post("/documents/upload", response_model=KnowledgeDocumentOut)
async def upload_document(
    file: UploadFile,
    category: str = "上传文档",
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("gb18030", errors="ignore")
    doc = KnowledgeDocument(title=file.filename or "未命名文档", category=category, source="upload", license="user_provided", content=content)
    session.add(doc)
    session.flush()
    chunks = index_document(session, doc)
    session.add(AuditLog(actor_id=actor.id, action="kb.document.upload", target_type="document", target_id=str(doc.id), detail={"chunks": chunks}))
    session.commit()
    session.refresh(doc)
    return doc


@router.post("/documents/{document_id}/reindex")
def reindex_document(
    document_id: int,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    doc = session.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = index_document(session, doc)
    session.add(AuditLog(actor_id=actor.id, action="kb.document.reindex", target_type="document", target_id=str(doc.id), detail={"chunks": chunks}))
    session.commit()
    return {"document_id": document_id, "chunks": chunks}


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    doc = session.get(KnowledgeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_active = False
    session.add(doc)
    session.add(AuditLog(actor_id=actor.id, action="kb.document.disable", target_type="document", target_id=str(doc.id)))
    session.commit()
    return {"ok": True}


@router.post("/seed/ecommerce")
def seed_ecommerce(
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    result = seed_ecommerce_kb(session)
    session.add(AuditLog(actor_id=actor.id, action="kb.seed.ecommerce", detail=result))
    session.commit()
    return result


@router.post("/import/open-dataset")
def import_open_dataset(
    payload: OpenDatasetImportIn,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles([UserRole.admin, UserRole.kb_manager])),
):
    match = next((item for item in OPEN_DATASETS if item["name"].lower() == payload.dataset.lower()), None)
    if match is None:
        raise HTTPException(status_code=400, detail="Dataset is not in allowlist")
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="kb.import.open_dataset.requested",
            target_type="dataset",
            target_id=match["name"],
            detail={"dataset": match, "purpose": payload.purpose, "notes": payload.notes},
        )
    )
    session.commit()
    return {"status": "recorded", "dataset": match, "next_step": "Download manually and transform into evaluation data only."}
