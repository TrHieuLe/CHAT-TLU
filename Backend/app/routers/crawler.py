import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.models.database import AsyncSessionLocal, CrawlRun, Document, get_db
from app.crawler.tlu_crawler import WEB_DOC_PREFIX, crawl_and_ingest_tlu

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["crawler"], dependencies=[Depends(require_admin)])

# Trạng thái phiên quét hiện tại (1 tiến trình backend chỉ chạy 1 phiên một lúc)
_job: dict[str, Any] = {
    "running": False,
    "trigger": None,
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


async def _save_run(trigger: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            db.add(CrawlRun(
                trigger=trigger,
                max_articles=_job["max_articles"],
                started_at=datetime.fromisoformat(_job["started_at"]),
                finished_at=datetime.fromisoformat(_job["finished_at"]),
                total=_job["total"], new=_job["new"], updated=_job["updated"],
                skipped=_job["skipped"], failed=_job["failed"],
                errors=json.dumps(_job["errors"][:20], ensure_ascii=False) if _job["errors"] else None,
            ))
            await db.commit()
    except Exception as e:
        logger.warning("Không lưu được lịch sử phiên quét: %s", e)


async def _run_job(max_articles: int, trigger: str) -> None:
    try:
        await crawl_and_ingest_tlu(max_articles=max_articles, progress=_job)
    except Exception as e:
        logger.error("Phiên quét thông báo lỗi: %s", e, exc_info=True)
        _job["errors"].append(str(e))
    finally:
        _job["running"] = False
        _job["current"] = None
        _job["finished_at"] = _now()
        await _save_run(trigger)


def start_crawl(max_articles: int, trigger: str = "manual") -> bool:
    """Bắt đầu một phiên quét chạy nền. Trả về False nếu đang có phiên khác chạy."""
    global _task
    if _job["running"]:
        return False
    _job.update(
        running=True, trigger=trigger, max_articles=max_articles, started_at=_now(), finished_at=None,
        total=0, done=0, current=None, new=0, updated=0, skipped=0, failed=0, errors=[], articles=[],
    )
    _task = asyncio.create_task(_run_job(max_articles, trigger))
    return True


async def crawl_scheduler(interval_hours: float, max_articles: int, initial_delay: float = 300.0) -> None:
    """Quét định kỳ (chạy trong lifespan). Bỏ qua lượt nếu đang có phiên thủ công."""
    await asyncio.sleep(initial_delay)
    while True:
        if start_crawl(max_articles, trigger="schedule"):
            logger.info("Bắt đầu quét thông báo theo lịch (tối đa %d bài)", max_articles)
        else:
            logger.info("Bỏ qua lượt quét theo lịch: đang có phiên khác chạy")
        await asyncio.sleep(interval_hours * 3600)


@router.post("/run")
async def trigger_tlu_crawler(req: CrawlRequest):
    """
    Kích hoạt (chạy nền) trình thu thập thông báo mới từ website Đại học Thủy Lợi.
    Theo dõi tiến độ qua GET /api/crawler/status (trường `job`).
    """
    if not start_crawl(req.max_articles, trigger="manual"):
        return JSONResponse(
            status_code=409,
            content={"ok": False, "message": "Đang có một phiên quét thông báo chạy, vui lòng chờ hoàn tất.", "job": _job},
        )
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


@router.get("/runs")
async def list_crawl_runs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Lịch sử các phiên quét gần nhất (thủ công + theo lịch)."""
    from app.core.config import settings
    from app.routers.admin import iso_utc

    res = await db.execute(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(min(max(limit, 1), 100)))
    return {
        "schedule_interval_hours": settings.CRAWL_INTERVAL_HOURS,
        "runs": [
            {
                "id": r.id,
                "trigger": r.trigger,
                "max_articles": r.max_articles,
                "started_at": iso_utc(r.started_at),
                "finished_at": iso_utc(r.finished_at),
                "total": r.total, "new": r.new, "updated": r.updated,
                "skipped": r.skipped, "failed": r.failed,
                "errors": json.loads(r.errors) if r.errors else [],
            }
            for r in res.scalars().all()
        ],
    }
