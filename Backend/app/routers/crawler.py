import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, get_db
from app.crawler.tlu_crawler import crawl_and_ingest_tlu

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["crawler"])


class CrawlRequest(BaseModel):
    max_articles: int = Field(default=5, ge=1, le=20)


@router.post("/run")
async def trigger_tlu_crawler(req: CrawlRequest):
    """
    Kích hoạt trình thu thập thông báo mới từ website Đại học Thủy Lợi,
    tự động làm sạch, cắt chunk và lập chỉ mục vào Qdrant.
    """
    results = await crawl_and_ingest_tlu(max_articles=req.max_articles)
    return {
        "ok": True,
        "message": f"Đã quét và nạp thành công {len(results)} thông báo từ website trường.",
        "articles": results,
    }


@router.get("/status")
async def get_crawler_status(db: AsyncSession = Depends(get_db)):
    """Lấy thống kê số lượng thông báo đã cào được từ web trường."""
    res = await db.execute(
        select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.chunk_count), 0),
        ).where(Document.original_name.like("[Thông báo Web]%"))
    )
    crawled_count, chunk_count = res.first() or (0, 0)

    # Lấy 5 bài cào gần nhất
    latest_res = await db.execute(
        select(Document)
        .where(Document.original_name.like("[Thông báo Web]%"))
        .order_by(Document.created_at.desc())
        .limit(5)
    )
    latest_docs = [
        {
            "id": d.id,
            "title": d.original_name.replace("[Thông báo Web] ", ""),
            "chunks": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in latest_res.scalars().all()
    ]

    return {
        "total_crawled_articles": crawled_count,
        "total_crawled_chunks": chunk_count,
        "latest_announcements": latest_docs,
    }
