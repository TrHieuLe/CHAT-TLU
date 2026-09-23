import logging
import mimetypes
import uuid
from pathlib import Path

import google.generativeai as genai
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import ChatMessage, get_db, Document
from app.rag.retriever import Retriever
from app.storage.helper import StorageHelper
from ingest import ingest_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/document", tags=["document"])

_kw = {"url": settings.QDRANT_URL, "api_key": settings.QDRANT_API_KEY}
_sync = QdrantClient(**_kw, prefer_grpc=False)
_async = AsyncQdrantClient(**_kw, prefer_grpc=False)
_retriever = Retriever(client=_sync, async_client=_async)

genai.configure(api_key=settings.EFFECTIVE_GEMINI_API_KEY)

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "data" / "images" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DOC_DIR = BASE_DIR / "data"

storage_helper = StorageHelper()


@router.post("/upload", tags=["document"])
async def upload_document(
        db: AsyncSession = Depends(get_db),
        *,
        file: UploadFile = File(...),
        filename: str = Form(None),
        auto: bool = Form(True)
):
    logger.info("Start uploading document")
    if not filename:
        filename = Path(file.filename).stem.strip()

    filename += Path(file.filename).suffix

    full_path = storage_helper.upload_v2(filename, file)
    if not full_path:
        raise HTTPException(500, "Đã có lỗi xảy ra khi lưu file, vui lòng thử lại sau")

    logger.info("Start ingest document")
    file_size = full_path.stat().st_size if full_path.exists() else 0
    file_type = full_path.suffix.lower().replace(".", "")

    doc = Document(
        id=str(uuid.uuid4()),
        filename=full_path.stem.strip(),
        original_name=full_path.name,
        file_type=file_type,
        file_size=file_size,
        status="processing",
    )

    try:
        doc.chunk_count = ingest_file(file_path=full_path, doc_id=doc.id, auto=auto)
        doc.status = "ok"
    except Exception as e:
        logger.error(f"Lỗi khi ingest file {filename}: {e}", exc_info=True)
        doc.status = "error"
        doc.error_msg = str(e)

    logger.info("Ingest document finished with status %s", doc.status)

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "original_name": doc.original_name,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
    }


@router.get("/list", tags=["document"])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """Lấy danh sách tất cả tài liệu đã được tải lên và index."""
    res = await db.execute(
        select(Document).order_by(Document.created_at.desc())
    )
    documents = res.scalars().all()
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "original_name": doc.original_name,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "chunk_count": doc.chunk_count or 0,
            "status": doc.status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in documents
    ]


@router.delete("/{doc_id}", tags=["document"])
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Xóa tài liệu khỏi cơ sở dữ liệu, vector store Qdrant và bộ lưu trữ file."""
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    # Xóa khỏi Qdrant theo doc_name
    from ingest import delete_doc_by_name
    try:
        delete_doc_by_name(doc.original_name)
        if doc.filename != doc.original_name:
            delete_doc_by_name(doc.filename)
    except Exception as e:
        logger.warning("Không thể xóa vector Qdrant cho %s: %s", doc.original_name, e)

    # Xóa file vật lý khỏi storage
    try:
        storage_helper.delete_v2(doc.original_name)
    except Exception as e:
        logger.warning("Không thể xóa file vật lý %s: %s", doc.original_name, e)

    await db.delete(doc)
    await db.commit()

    return {"ok": True, "message": f"Đã xóa tài liệu {doc.original_name} thành công"}


@router.get("/stats", tags=["document"])
async def get_document_stats(db: AsyncSession = Depends(get_db)):
    """Lấy thống kê tổng quan về tài liệu và chunks."""
    from sqlalchemy import func
    res = await db.execute(
        select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.chunk_count), 0),
        )
    )
    total_docs, total_chunks = res.first() or (0, 0)

    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "collection_name": settings.COLLECTION_NAME,
    }


@router.get("/reference/{filename}")
async def get_reference(db: AsyncSession = Depends(get_db), *, filename: str):
    if not filename:
        raise HTTPException(400, "Tên nguồn tham khảo không được để trống")

    res = await db.execute(
        select(Document)
        .where(Document.filename == filename)
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    document = res.scalars().first()
    if not document or not document.original_name:
        raise HTTPException(404, "Nguồn tham khảo hiện không thể xem")

    try:
        content = storage_helper.download_v2(document.original_name)
        if content is None:
            raise HTTPException(404, "Nguồn tham khảo hiện không thể xem")

        content_type, _ = mimetypes.guess_type(document.original_name)
        if not content_type:
            content_type = "application/octet-stream"

        return StreamingResponse(
            content,
            media_type=content_type,
        )

    except Exception as e:
        raise HTTPException(500, "Đã có lỗi xảy ra, vui lòng thử lại sau")
    finally:
        await db.close()
