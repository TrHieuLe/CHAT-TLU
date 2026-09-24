"""
chat.py — RAG + Gemini streaming + hỗ trợ ảnh người dùng upload.

FIXES:
  1. history không còn bị cắt cứng 20 tin nhắn — thay vào đó cắt theo token budget
  2. prompt gửi Gemini chỉ dùng effective_question (đã rewrite), KHÔNG gửi câu gốc song song
  3. history truyền vào _rewrite_followup_question lấy từ DB trước khi lưu tin hiện tại
     → _last_meaningful_model_answer() luôn trả đúng câu trả lời bot gần nhất
  4. System prompt hợp nhất, không nhân đôi
  5. Nếu retrieve trúng chunk bảng (is_table=True) thì ưu tiên ép model trả bảng Markdown
"""
import json
import logging
import uuid
from io import BytesIO
from pathlib import Path
from typing import AsyncGenerator

import google.generativeai as genai
from PIL import Image
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import AsyncSessionLocal, ChatMessage, ChatMessageFeedback, Session, get_db
from app.rag.retriever import Retriever
from app.rag.query_enhancer import enhance_query
from app.rag.semantic_cache import get_semantic_cache

# ─── Import từ các module đã tách ────────────────────────────────────────────
from app.routers.chat_formatters import (
    normalize_text,
    wants_table_answer,
    postprocess_answer,
)
from app.routers.chat_followup import (
    is_reference_followup,
    last_meaningful_model_answer,
    extract_referenced_item,
    rewrite_followup_question,
    trim_history_by_token_budget,
    HISTORY_TOKEN_BUDGET,
)
from app.routers.chat_vision import (
    is_image_followup,
    is_text_focused_image_request,
    build_upload_image_prompt,
    find_last_uploaded_image,
    open_local_image_from_url,
    vision_answer_for_uploaded_image,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

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

SYSTEM_INSTRUCTION = """Bạn là StudyBot — trợ lý học vụ và quy chế đào tạo AI dành cho sinh viên Trường Đại học Thủy Lợi (TLU).

Quy tắc nghiệp vụ:
- CĂN CỨ VÀO TÀI LIỆU: Ưu tiên tối đa thông tin từ phần [CONTEXT] hoặc [BẢNG] được cung cấp. Nêu rõ nguồn tài liệu, số Điều, Khoản nếu có trong ngữ cảnh.
- TRUNG THỰC & CHỐNG BỊA ĐẶT: Nếu ngữ cảnh không chứa câu trả lời hoặc không đủ thông tin, hãy trả lời trung thực rằng: "Tài liệu quy chế hiện tại chưa có thông tin cụ thể về vấn đề này. Bạn vui lòng liên hệ Phòng Đào tạo (ĐT: 024.38522201) hoặc Văn phòng Khoa để được giải đáp chính thức." Tuyệt đối không tự suy đoán thông tin học vụ quan trọng.
- ĐỊNH DẠNG:
  - Nếu ngữ cảnh có bảng số liệu, điểm chuẩn, biểu phí hoặc đối chiếu ngắn, hãy dùng bảng Markdown chuẩn.
  - Nếu nội dung có nhiều điều kiện hoặc bước thực hiện, dùng bullet list rõ ràng, rành mạch.
  - Công thức tính điểm (CPA, GPA, tín chỉ) nếu có hãy trình bày bằng cú pháp LaTeX Markdown `$ ... $`.
  - Không bao giờ in ra đường dẫn file nội bộ hoặc URL ảnh hệ thống (/images/...).
- ĐỐI VỚI ẢNH TÀI LIỆU: Đọc và tóm tắt thông tin chữ, quy định hoặc thông báo trong ảnh; bỏ qua mô tả phong cảnh/màu sắc không liên quan.
- Tác phong: Thân thiện, lịch sự, chính xác, chuẩn phong cách sư phạm. Trả lời bằng tiếng Việt.
"""


class ChatRequest(BaseModel):
    session_id: str
    question: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _pack_meta(
    *,
    sources: list[str] | None = None,
    images: list[str] | None = None,
    kind: str | None = None,
) -> str | None:
    data: dict = {}
    if sources:
        data["sources"] = sources
    if images:
        data["images"] = images
    if kind:
        data["kind"] = kind
    return json.dumps(data, ensure_ascii=False) if data else None


def _is_reference_source_name(name: str) -> bool:
    source_name = (name or "").strip().lower()
    if not source_name:
        return False
    return Path(source_name).suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _safe_chunk_text(chunk) -> str:
    try:
        candidates = getattr(chunk, "candidates", None) or []
        texts: list[str] = []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                txt = getattr(part, "text", None)
                if txt:
                    texts.append(txt)
        if texts:
            return "".join(texts)
        txt = getattr(chunk, "text", None)
        return txt or ""
    except Exception:
        return ""


async def _maybe_set_title(db: AsyncSession, session_id: str, title_seed: str):
    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.role == "user")
    )
    user_msgs = res.scalars().all()
    if len(user_msgs) == 1:
        from app.llm.llm_service import llm_service
        try:
            title = await llm_service.generate_title(title_seed)
        except Exception:
            title = title_seed[:60] + ("..." if len(title_seed) > 60 else "")
        await db.execute(
            update(Session).where(Session.id == session_id).values(title=title)
        )
        await db.commit()


# ─── RAG Streaming ───────────────────────────────────────────────────────────

async def _stream_text_answer(
    *,
    session_id: str,
    question: str,
    history: list[dict],
    user_id: str = "default_user",
) -> AsyncGenerator[str, None]:
    async with AsyncSessionLocal() as db:
        try:
            # ─── 0. Semantic Cache Check (< 30ms) ────────────────────────────────
            # Tăng tốc phản hồi tức thì cho các câu hỏi phổ biến độc lập
            if len(history) <= 1:
                cached = get_semantic_cache().get(question)
                if cached:
                    cached_answer, cached_sources, match_type = cached
                    db.add(ChatMessage(session_id=session_id, role="user", content=question))
                    db.add(ChatMessage(
                        session_id=session_id,
                        role="model",
                        content=cached_answer,
                        source_docs=_pack_meta(sources=cached_sources, kind="rag_cached"),
                    ))
                    await db.commit()
                    await _maybe_set_title(db, session_id, question)

                    if cached_sources:
                        yield f"data: [SOURCES]{json.dumps(cached_sources, ensure_ascii=False)}\n\n"

                    # Fast streaming animation (< 50ms)
                    import asyncio
                    words = cached_answer.split(" ")
                    for i in range(0, len(words), 3):
                        chunk_str = " ".join(words[i:i+3]) + " "
                        yield f"data: {json.dumps(chunk_str, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.005)

                    yield "data: [DONE]\n\n"
                    return

            effective_question = rewrite_followup_question(question, history)
            # Mở rộng từ viết tắt học vụ ĐH Thủy Lợi (TLU Abbreviation Expansion)
            enhanced_question = enhance_query(effective_question)

            is_self_contained_followup = (
                is_reference_followup(question)
                and effective_question != question
                and extract_referenced_item(question, last_meaningful_model_answer(history)) != ""
            )

            if is_self_contained_followup:
                chunks = []
                source_names = []
                ctx_parts = []
                has_table_context = False
                logger.info("Follow-up self-contained — skipping RAG retrieval")
            else:
                try:
                    chunks = await _retriever.retrieve_v3(enhanced_question, bot_id=0)
                    if not isinstance(chunks, list):
                        chunks = list(chunks)
                except Exception as e:
                    logger.error("Qdrant error: %s", e)
                    chunks = []

                # Lọc bỏ các chunk có điểm rerank quá thấp nếu có
                min_threshold = getattr(settings, "MIN_RELEVANCE_SCORE", 0.15)
                valid_chunks = [
                    c for c in chunks
                    if not (c.payload and "rerank_score" in c.payload and c.payload["rerank_score"] < min_threshold)
                ]
                if valid_chunks:
                    chunks = valid_chunks

                source_names = list({
                    c.payload.get("doc_name", "")
                    for c in chunks
                    if c.payload
                    and c.payload.get("doc_name")
                    and _is_reference_source_name(c.payload.get("doc_name", ""))
                })

                has_table_context = any(
                    bool((c.payload or {}).get("is_table", False))
                    for c in chunks
                )

                ctx_parts = []
                for i, c in enumerate(chunks, 1):
                    payload = c.payload or {}
                    content = payload.get("content", "")
                    doc_name = payload.get("doc_name", "")
                    updated = payload.get("created_at", "")
                    img_descs = payload.get("image_descs", []) or []
                    is_table = bool(payload.get("is_table", False))

                    label = "BẢNG" if is_table else "CONTEXT"
                    ctx_text = f"[{label} {i}] Nguồn: {doc_name} | Cập nhật: {updated}\n{content}"

                    if img_descs:
                        desc_lines = [f"[HÌNH ẢNH] {desc}" for desc in img_descs if desc]
                        if desc_lines:
                            ctx_text += "\n" + "\n".join(desc_lines)

                    ctx_parts.append(ctx_text)

            if ctx_parts:
                src_str = ", ".join(f"**{n}**" for n in source_names if n)

                if has_table_context or wants_table_answer(effective_question):
                    extra_instruction = (
                        "\n\nYÊU CẦU ĐỊNH DẠNG:\n"
                        "- Nếu trong ngữ cảnh có bảng, hãy ưu tiên giữ nguyên thông tin dưới dạng bảng Markdown chuẩn.\n"
                        "- Nếu dữ liệu ngắn, đồng đều, dễ đối chiếu, hãy ưu tiên bảng Markdown.\n"
                        "- Nếu số ý ít và mỗi ý ngắn, có thể trình bày thành bảng 2 hoặc 3 cột.\n"
                        "- Không gộp cả đoạn văn dài vào một ô.\n"
                        "- Nếu có cột STT thì giữ cột STT.\n"
                        "- Nếu bảng trong ngữ cảnh đã rõ cột/hàng, hãy bám sát cấu trúc đó để trả lời.\n"
                        "- Chỉ khi nội dung quá dài, ô quá dài hoặc bảng bị vỡ thì mới chuyển sang bullet list.\n"
                        "- Không in đường dẫn ảnh, tên file ảnh hoặc URL nội bộ.\n"
                        "- Nêu rõ căn cứ Điều/Khoản trong quy chế nếu có trong ngữ cảnh.\n"
                    )
                else:
                    extra_instruction = (
                        "\n\nYÊU CẦU ĐỊNH DẠNG:\n"
                        "- Ưu tiên bullet list ngắn gọn, rõ ràng, dễ đối chiếu.\n"
                        "- Nếu các ý ngắn, đồng đều, dưới 10 dòng thì có thể dùng bảng Markdown.\n"
                        "- Nêu rõ căn cứ Điều/Khoản trong quy chế nếu có trong ngữ cảnh.\n"
                        "- Nếu thông tin không có trong tài liệu, trả lời trung thực rằng tài liệu hiện chưa đề cập.\n"
                    )

                prompt = (
                    f"Tài liệu tham khảo: {src_str}\n\n"
                    f"{'---'.join(ctx_parts)}\n\n"
                    f"Câu hỏi: {effective_question}"
                    f"{extra_instruction}"
                )
            else:
                prompt = effective_question

            db.add(ChatMessage(session_id=session_id, role="user", content=question))
            await db.commit()

            if source_names:
                yield f"data: [SOURCES]{json.dumps(source_names, ensure_ascii=False)}\n\n"

            from app.llm.llm_service import llm_service
            from app.memory.memory_service import get_user_cell_state_prompt, update_user_memories

            trimmed_history = trim_history_by_token_budget(history, HISTORY_TOKEN_BUDGET)
            user_context = await get_user_cell_state_prompt(user_id, db)
            instruction = f"{SYSTEM_INSTRUCTION}\n\n{user_context}" if user_context else SYSTEM_INSTRUCTION

            full = ""
            try:
                async for delta in llm_service.stream_chat_response(
                    history=trimmed_history,
                    prompt=prompt,
                    system_instruction=instruction,
                ):
                    if delta:
                        full += delta
                        yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"
            except Exception as e:
                err = str(e)
                msg = (
                    "Hệ thống quá tải, thử lại sau."
                    if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err
                    else f"Lỗi: {err[:160]}"
                )
                logger.exception("Gemini stream error: %s", err)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                full = msg

            full = postprocess_answer(full, effective_question)

            db.add(ChatMessage(
                session_id=session_id,
                role="model",
                content=full,
                source_docs=_pack_meta(sources=source_names, kind="rag"),
            ))
            await db.commit()
            await _maybe_set_title(db, session_id, question)

            # Cập nhật tế bào nhớ dài hạn (Input Gate)
            try:
                await update_user_memories(user_id, f"{question} {full}", db)
            except Exception as e:
                logger.warning("Cập nhật memory thất bại: %s", e)

            # Lưu vào Semantic Cache nếu câu trả lời hợp lệ & câu hỏi độc lập
            if len(history) <= 1 and full and not full.startswith("Lỗi:"):
                try:
                    get_semantic_cache().put(question, full, source_names=source_names)
                except Exception as e:
                    logger.warning("Lưu Semantic Cache thất bại: %s", e)

            yield "data: [DONE]\n\n"
        finally:
            await db.close()


# ─── Vision Follow-up Streaming ──────────────────────────────────────────────

async def _stream_followup_about_last_image(
    *,
    session_id: str,
    question: str,
) -> AsyncGenerator[str, None]:
    async with AsyncSessionLocal() as db:
        try:
            image_url = await find_last_uploaded_image(session_id, db)
            if not image_url:
                yield "data: Mình chưa thấy ảnh nào được gửi trong phiên chat này.\n\n"
                yield "data: [DONE]\n\n"
                return

            db.add(ChatMessage(session_id=session_id, role="user", content=question))
            await db.commit()

            yield f"data: [IMAGES]{json.dumps([image_url], ensure_ascii=False)}\n\n"

            try:
                full = await vision_answer_for_uploaded_image(
                    question=question,
                    image_url=image_url,
                    system_instruction=SYSTEM_INSTRUCTION,
                )
            except Exception as e:
                logger.exception("Vision follow-up error: %s", e)
                full = "Mình chưa phân tích tiếp được ảnh này. Hãy thử lại."

            yield f"data: {json.dumps(full, ensure_ascii=False)}\n\n"

            db.add(ChatMessage(
                session_id=session_id,
                role="model",
                content=full,
                source_docs=_pack_meta(images=[image_url], kind="vision_followup"),
            ))
            await db.commit()
            await _maybe_set_title(db, session_id, question)

            yield "data: [DONE]\n\n"
        finally:
            await db.close()


# ─── API Endpoints ───────────────────────────────────────────────────────────

from app.core.auth import get_current_user_id

@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if not req.question.strip():
        raise HTTPException(400, "Câu hỏi không được rỗng")

    # Kiểm tra hoặc tự tạo session gắn với user_id
    res_sess = await db.execute(select(Session).where(Session.id == req.session_id))
    sess = res_sess.scalar_one_or_none()
    if sess:
        if sess.user_id == "default_user" and user_id != "default_user":
            sess.user_id = user_id
            await db.commit()
        elif user_id != "default_user" and sess.user_id != user_id:
            raise HTTPException(403, "Bạn không có quyền truy cập phiên trò chuyện này")
    else:
        # Tự động tạo session cho user nếu chưa tồn tại
        sess = Session(id=req.session_id, user_id=user_id)
        db.add(sess)
        await db.commit()

    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == req.session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = [{"role": m.role, "content": m.content} for m in res.scalars().all()]

    await db.close()

    if is_image_followup(req.question):
        stream = _stream_followup_about_last_image(
            session_id=req.session_id,
            question=req.question,
        )
    else:
        stream = _stream_text_answer(
            session_id=req.session_id,
            question=req.question,
            history=history,
            user_id=user_id,
        )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/image")
async def analyze_uploaded_image(
    session_id: str = Form(...),
    question: str = Form(""),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Kiểm tra hoặc tạo session
    res_sess = await db.execute(select(Session).where(Session.id == session_id))
    sess = res_sess.scalar_one_or_none()
    if sess:
        if sess.user_id == "default_user" and user_id != "default_user":
            sess.user_id = user_id
            await db.commit()
        elif user_id != "default_user" and sess.user_id != user_id:
            raise HTTPException(403, "Bạn không có quyền truy cập phiên trò chuyện này")
    else:
        sess = Session(id=session_id, user_id=user_id)
        db.add(sess)
        await db.commit()

    if image.content_type not in {"image/png", "image/jpeg", "image/jpg", "image/webp"}:
        raise HTTPException(400, "Chỉ hỗ trợ PNG, JPG, JPEG, WEBP")

    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Ảnh rỗng")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "Ảnh vượt quá 5MB")

    ext = Path(image.filename or "upload.jpg").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    save_path.write_bytes(raw)

    image_url = f"/images/uploads/{filename}"
    user_prompt = question.strip() or "Hãy đọc và tóm tắt nội dung trong ảnh này."

    db.add(ChatMessage(
        session_id=session_id,
        role="user",
        content=user_prompt,
        source_docs=_pack_meta(images=[image_url], kind="user_image"),
    ))
    await db.commit()

    try:
        from app.llm.llm_service import llm_service
        prompt = build_upload_image_prompt(user_prompt)
        mime = image.content_type or "image/jpeg"
        answer = await llm_service.generate_image_answer(
            image_bytes=raw,
            mime_type=mime,
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        answer = answer or "Mình chưa phân tích được ảnh này."
        answer = postprocess_answer(answer, user_prompt)
    except Exception as e:
        logger.exception("Analyze uploaded image error: %s", e)
        answer = "Mình chưa phân tích được ảnh này. Hãy thử lại."

    db.add(ChatMessage(
        session_id=session_id,
        role="model",
        content=answer,
        source_docs=_pack_meta(images=[image_url], kind="vision_upload"),
    ))
    await db.commit()
    await _maybe_set_title(db, session_id, user_prompt)

    return {
        "ok": True,
        "answer": answer,
        "image_url": image_url,
    }


class ChatFeedbackRequest(BaseModel):
    session_id: str
    message_id: int | None = None
    rating: str  # "like" | "dislike"
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(req: ChatFeedbackRequest, db: AsyncSession = Depends(get_db)):
    if req.rating not in {"like", "dislike"}:
        raise HTTPException(400, "Rating phải là 'like' hoặc 'dislike'")

    fb = ChatMessageFeedback(
        session_id=req.session_id,
        message_id=req.message_id,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return {"ok": True, "id": fb.id}


@router.get("/cache/stats")
async def get_cache_statistics():
    """Lấy số liệu thống kê hiệu năng của Semantic Cache."""
    return {
        "ok": True,
        "stats": get_semantic_cache().get_stats(),
    }


@router.delete("/cache/clear")
async def clear_cache_data():
    """Xóa toàn bộ dữ liệu trong Semantic Cache."""
    get_semantic_cache().clear()
    return {"ok": True, "message": "Semantic Cache cleared successfully."}

