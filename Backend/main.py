import asyncio
from contextlib import asynccontextmanager
import logging, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.models.database import init_db
from app.rag.qdrant_client_custom import qdrant_client
from app.routers import admin, chat, sessions, document, memory, crawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

# SỬA Ở ĐÂY: ảnh thật đang nằm trong app/data/images
BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / "app" / "data" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    try:
        from app.models.database import AsyncSessionLocal
        from app.routers.document import sync_local_data_documents
        async with AsyncSessionLocal() as session:
            await sync_local_data_documents(session)
    except Exception as e:
        logger.warning(f"Không thể tự động đồng bộ tài liệu data/: {e}")

    try:
        qdrant_client.create_collection(vector_size=settings.EMBEDDING_VECTOR_SIZE)
        logger.info("✅ Qdrant collection checked/created")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Qdrant: {e}")

    try:
        import torch
        torch.set_num_threads(settings.TORCH_NUM_THREADS or os.cpu_count() or 1)
        logger.info(f"Torch dùng {torch.get_num_threads()} CPU threads")
    except Exception as e:
        logger.warning(f"Không thể cấu hình torch threads: {e}")

    if settings.WARMUP_MODELS:
        # Nạp sẵn embedder + reranker để câu hỏi đầu tiên không phải chờ load model
        from app.rag import embedder, reranker
        for name, fn in (("embedder", embedder.warmup), ("reranker", reranker.warmup)):
            try:
                await asyncio.to_thread(fn)
            except Exception as e:
                logger.warning(f"Warmup {name} thất bại: {e}")

    # Khởi tạo sẵn Gemini client: import google.genai lần đầu mất vài giây và chạy đồng bộ,
    # nếu để tới request đầu sẽ chặn cả event loop
    try:
        from app.llm.llm_service import llm_service
        await asyncio.to_thread(llm_service._get_client)
    except Exception as e:
        logger.warning(f"Không thể khởi tạo sẵn Gemini client: {e}")

    # Mở sẵn kết nối HTTPS tới Qdrant (bắt tay TLS ~1s) để câu hỏi đầu không phải chờ
    try:
        await chat._async.get_collection(settings.QDRANT_COLLECTION)
    except Exception as e:
        logger.warning(f"Không thể mở sẵn kết nối Qdrant: {e}")

    # Semantic cache: nạp từ SQLite, xóa nếu kho tài liệu đã đổi, rồi theo dõi định kỳ
    from app.rag.semantic_cache import get_semantic_cache, watch_kb_changes
    logger.info(f"Semantic cache: {get_semantic_cache().get_stats()['cached_entries']} entry")
    kb_watch = asyncio.create_task(watch_kb_changes(chat._async, settings.QDRANT_COLLECTION))

    # Quét thông báo web trường định kỳ
    crawl_task = None
    if settings.CRAWL_INTERVAL_HOURS > 0:
        crawl_task = asyncio.create_task(
            crawler.crawl_scheduler(settings.CRAWL_INTERVAL_HOURS, settings.CRAWL_SCHEDULE_MAX_ARTICLES)
        )
        logger.info(f"Lịch quét thông báo: mỗi {settings.CRAWL_INTERVAL_HOURS}h")

    yield

    kb_watch.cancel()
    if crawl_task is not None:
        crawl_task.cancel()


app = FastAPI(title="NCKH StudyBot API v3.1", version="3.1.0", lifespan=lifespan)

# Chỉ cho phép origin khai báo rõ ràng; regex chỉ bật khi đặt CORS_ORIGIN_REGEX
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=False,  # API dùng header (X-User-ID, X-Admin-Key), không dùng cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve ảnh tại /images/*
app.mount("/images", StaticFiles(directory=str(IMG_DIR)), name="images")

app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(document.router)
app.include_router(memory.router)
app.include_router(crawler.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {"status": "ok", "version": "3.1.0"}


@app.get("/health")
async def health():
    from app.rag.qdrant_client_custom import qdrant_client
    from app.core.config import settings
    try:
        n = qdrant_client.client.get_collection(settings.COLLECTION_NAME).points_count
    except Exception:
        n = 0
    return {"status": "healthy", "qdrant_chunks": n}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)