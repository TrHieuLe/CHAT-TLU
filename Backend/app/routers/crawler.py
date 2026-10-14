import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, get_db
from app.crawler.tlu_crawler import WEB_DOC_PREFIX, crawl_and_ingest_tlu

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["crawler"])

# Trạng thái phiên quét hiện tại (1 tiến trình backend chỉ chạy 1 phiên một lúc)
_job: dict[str, Any] = {
    "running": False,
    "max_articles": 0,
    "started_at": None,
    "finished_at": None,
    "total": 0,
    "done": 0,
    "current": None,
    "new": 0,
    "updated": 0,
    "skipped": 0,
    "failed": 0,
    "errors": [],
    "articles": [],
}
_task: asyncio.Task | None = None


class CrawlRequest(BaseModel):
    max_articles: int = Field(default=5, ge=1, le=20)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _run_job(max_articles: int) -> None:
    try:
        await crawl_and_ingest_tlu(max_articles=max_articles, progress=_job)
    except Exception as e:
        logger.error("Phiên quét thông báo lỗi: %s", e, exc_info=True)
        _job["errors"].append(str(e))
    finally:
        _job["running"] = False
        _job["current"] = None
        _job["finished_at"] = _now()


@router.post("/run")
async def trigger_tlu_crawler(req: CrawlRequest):
    """
    Kích hoạt (chạy nền) trình thu thập thông báo mới từ website Đại học Thủy Lợi.
    Theo dõi tiến độ qua GET /api/crawler/status (trường `job`).
    """
    global _task
    if _job["running"]:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "message": "Đang có một phiên quét thông báo chạy, vui lòng chờ hoàn tất.", "job": _job},
        )

    _job.update(
        running=True, max_articles=req.max_articles, started_at=_now(), finished_at=None,
        total=0, done=0, current=None, new=0, updated=0, skipped=0, failed=0, errors=[], articles=[],
    )
    _task = asyncio.create_task(_run_job(req.max_articles))
    return {
        "ok": True,
        "message": f"Đã bắt đầu quét tối đa {req.max_articles} thông báo từ website trường.",
        "job": _job,
    }


@router.get("/status")
async def get_crawler_status(db: AsyncSession = Depends(get_db)):
    """Lấy thống kê thông báo đã cào từ web trường và tiến độ phiên quét hiện tại."""
    res = await db.execute(
        select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.chunk_count), 0),
        ).where(Document.original_name.like(f"{WEB_DOC_PREFIX}%"))
    )
    crawled_count, chunk_count = res.first() or (0, 0)

    # Lấy 5 bài cào gần nhất
    latest_res = await db.execute(
        select(Document)
        .where(Document.original_name.like(f"{WEB_DOC_PREFIX}%"))
        .order_by(Document.created_at.desc())
        .limit(5)
    )
    latest_docs = [
        {
            "id": d.id,
            "title": d.original_name.replace(WEB_DOC_PREFIX, "", 1),
            "chunks": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in latest_res.scalars().all()
    ]

    return {
        "total_crawled_articles": crawled_count,
        "total_crawled_chunks": chunk_count,
        "latest_announcements": latest_docs,
        "job": _job,
    }
