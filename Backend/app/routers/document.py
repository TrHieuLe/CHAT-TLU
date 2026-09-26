import logging
import mimetypes
import urllib.parse
import uuid
from pathlib import Path

import google.generativeai as genai
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse
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

try:
    if settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY:
        genai.configure(api_key=settings.EFFECTIVE_GEMINI_API_KEY)
except Exception as e:
    logger.warning("Chưa cấu hình API Key Gemini hợp lệ khi khởi động: %s", e)

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


@router.get("/reference/{filename:path}")
async def get_reference(db: AsyncSession = Depends(get_db), *, filename: str):
    """
    Phục vụ xem hoặc tải tài liệu tham khảo:
    1. Tìm trong DB Document table (theo filename hoặc original_name).
    2. Nếu không thấy hoặc file chưa đăng ký trong DB, quét đệ quy ổ đĩa trong Backend/data.
    3. Phục vụ với header Content-Disposition: inline và đúng MIME type (PDF, DOCX, TXT, MD...).
    """
    if not filename:
        raise HTTPException(400, "Tên nguồn tham khảo không được để trống")

    decoded_filename = urllib.parse.unquote(filename).strip()
    target_path: Path | None = None
    original_display_name: str = decoded_filename

    # 1. Tra cứu trong SQLite DB trước
    res = await db.execute(
        select(Document)
        .where(
            (Document.filename == decoded_filename)
            | (Document.original_name == decoded_filename)
            | (Document.filename == Path(decoded_filename).stem)
        )
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    document = res.scalars().first()

    if document and document.original_name:
        original_display_name = document.original_name
        target_path = storage_helper.find_file(document.original_name)

    # 2. Nếu DB chưa có hoặc file không ở vị trí cũ, tìm trực tiếp trên ổ đĩa
    if not target_path or not target_path.is_file():
        target_path = storage_helper.find_file(decoded_filename)
        if target_path and target_path.is_file():
            original_display_name = target_path.name

    if not target_path or not target_path.is_file():
        logger.warning("Không tìm thấy file nguồn tham khảo: %s", decoded_filename)
        raise HTTPException(404, f"Nguồn tham khảo '{decoded_filename}' hiện không tồn tại trên hệ thống")

    try:
        content_type, _ = mimetypes.guess_type(target_path.name)
        if not content_type:
            ext = target_path.suffix.lower()
            if ext == ".docx":
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext == ".doc":
                content_type = "application/msword"
            elif ext in [".txt", ".md"]:
                content_type = "text/plain; charset=utf-8"
            elif ext == ".pdf":
                content_type = "application/pdf"
            else:
                content_type = "application/octet-stream"

        encoded_name = urllib.parse.quote(original_display_name)
        headers = {
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
            "Access-Control-Allow-Origin": "*",
        }

        return FileResponse(
            path=target_path,
            media_type=content_type,
            headers=headers,
        )

    except Exception as e:
        logger.error("Lỗi khi phục vụ file %s: %s", decoded_filename, e, exc_info=True)
        raise HTTPException(500, "Đã có lỗi xảy ra khi đọc tệp tin")


@router.get("/preview-text/{filename:path}")
async def get_preview_text(*, filename: str):
    """
    Trích xuất và trả về nội dung text của tài liệu để xem nhanh trên giao diện modal.
    Hỗ trợ .txt, .md, .docx, .pdf.
    """
    if not filename:
        raise HTTPException(400, "Tên tài liệu không được để trống")

    decoded_filename = urllib.parse.unquote(filename).strip()
    target_path = storage_helper.find_file(decoded_filename)

    if not target_path or not target_path.is_file():
        raise HTTPException(404, f"Không tìm thấy tài liệu '{decoded_filename}'")

    ext = target_path.suffix.lower()
    file_size = target_path.stat().st_size
    text_content = ""

    try:
        if ext in [".txt", ".md", ".json", ".csv"]:
            try:
                text_content = target_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text_content = target_path.read_text(encoding="cp1258", errors="ignore")

        elif ext in [".docx", ".doc"]:
            try:
                import docx2txt
                text_content = docx2txt.process(str(target_path)) or ""
            except Exception:
                text_content = ""

            if not text_content.strip():
                try:
                    import docx
                    doc = docx.Document(target_path)
                    paras = [p.text for p in doc.paragraphs if p.text.strip()]
                    text_content = "\n\n".join(paras)
                except Exception as e_docx:
                    logger.warning("python-docx extraction failed: %s", e_docx)

        elif ext == ".pdf":
            try:
                import pdfplumber
                pages_text = []
                with pdfplumber.open(target_path) as pdf:
                    for idx, page in enumerate(pdf.pages[:15], 1):  # Giới hạn 15 trang đầu cho preview nhanh
                        p_text = page.extract_text() or ""
                        if p_text.strip():
                            pages_text.append(f"--- Trang {idx} ---\n{p_text}")
                text_content = "\n\n".join(pages_text)
            except Exception as e_pdf:
                logger.warning("pdfplumber preview extraction failed: %s", e_pdf)

        else:
            text_content = f"Tệp tin định dạng {ext.upper()} ({file_size} bytes). Vui lòng nhấn 'Tải về' để mở trên máy tính."

        return {
            "ok": True,
            "filename": target_path.name,
            "file_type": ext.replace(".", ""),
            "file_size": file_size,
            "content": text_content.strip(),
        }

    except Exception as e:
        logger.error("Lỗi khi trích xuất text preview cho %s: %s", target_path.name, e)
        return {
            "ok": False,
            "filename": target_path.name,
            "file_type": ext.replace(".", ""),
            "file_size": file_size,
            "content": f"Không thể trích xuất nội dung văn bản tự động: {e}",
        }


async def sync_local_data_documents(db: AsyncSession) -> int:
    """
    Quét đệ quy thư mục Backend/data/ và tự động thêm các tài liệu chưa có vào bảng Document.
    """
    data_dir = BASE_DIR / "data"
    if not data_dir.exists():
        return 0

    added_count = 0
    supported_exts = {".pdf", ".docx", ".doc", ".txt", ".md"}

    for file_path in data_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in supported_exts:
            continue
        # Bỏ qua thư mục images/uploads
        if "uploads" in file_path.parts or "images" in file_path.parts:
            continue

        filename_stem = file_path.stem.strip()
        original_name = file_path.name

        # Kiểm tra xem đã có trong DB chưa
        res = await db.execute(
            select(Document).where(
                (Document.original_name == original_name) | (Document.filename == filename_stem)
            )
        )
        existing = res.scalars().first()

        if not existing:
            doc = Document(
                id=str(uuid.uuid4()),
                filename=filename_stem,
                original_name=original_name,
                file_type=file_path.suffix.lower().replace(".", ""),
                file_size=file_path.stat().st_size,
                chunk_count=0,
                status="ok",
            )
            db.add(doc)
            added_count += 1

    if added_count > 0:
        await db.commit()
        logger.info("✅ Đã tự động đồng bộ %d tài liệu từ data/ vào cơ sở dữ liệu", added_count)

    return added_count
