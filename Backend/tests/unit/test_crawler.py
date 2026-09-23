import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

from main import app
from app.crawler.tlu_crawler import clean_text, parse_article_detail
from app.models.database import get_db, Document


def test_clean_text():
    raw = "  Thông báo    đăng ký   tín chỉ \r\n\r\n\n  Học kỳ 1 \t năm 2026   "
    cleaned = clean_text(raw)
    assert cleaned == "Thông báo đăng ký tín chỉ\n\nHọc kỳ 1 năm 2026"


def test_parse_article_detail():
    sample_html = """
    <html>
      <body>
        <h1 class="post-title">Thông báo lịch thi chuẩn đầu ra Tiếng Anh đợt 2 năm 2026</h1>
        <span class="post-date">05/09/2026</span>
        <div class="post-content">
          <p>Nhà trường thông báo tới toàn thể sinh viên lịch thi chuẩn đầu ra...</p>
          <p>Thời gian đăng ký từ ngày 10/09/2026 đến hết ngày 20/09/2026.</p>
          <a href="/uploads/lich_thi_tieng_anh.pdf">Danh sách ca thi chi tiết.pdf</a>
          <a href="https://tlu.edu.vn">Trang chủ</a>
        </div>
      </body>
    </html>
    """
    article = parse_article_detail(sample_html, base_url="https://www.tlu.edu.vn/thong-bao")

    assert "chuẩn đầu ra Tiếng Anh" in article["title"]
    assert "05/09/2026" in article["publish_date"]
    assert "Thời gian đăng ký" in article["content"]
    assert len(article["attachments"]) == 1
    assert article["attachments"][0]["name"] == "Danh sách ca thi chi tiết.pdf"
    assert "lich_thi_tieng_anh.pdf" in article["attachments"][0]["url"]


@pytest.mark.asyncio
async def test_trigger_crawler_endpoint():
    transport = ASGITransport(app=app)
    mock_results = [
        {
            "title": "Thông báo học bổng khuyến khích kỳ 2",
            "url": "https://tlu.edu.vn/hb",
            "date": "05/09/2026",
            "chunk_count": 3,
            "filename": "TLU_hb.md",
        }
    ]

    with patch("app.routers.crawler.crawl_and_ingest_tlu", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_results

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawler/run", json={"max_articles": 2})
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert len(data["articles"]) == 1
            assert data["articles"][0]["title"] == "Thông báo học bổng khuyến khích kỳ 2"


@pytest.mark.asyncio
async def test_crawler_status_endpoint():
    transport = ASGITransport(app=app)
    mock_session = AsyncMock()

    # Mock count & sum
    count_res = MagicMock()
    count_res.first.return_value = (4, 25)

    # Mock latest docs
    fake_doc = Document(
        id="crawled-1",
        original_name="[Thông báo Web] Lịch thi tốt nghiệp",
        chunk_count=5,
    )
    latest_res = MagicMock()
    latest_res.scalars.return_value.all.return_value = [fake_doc]

    mock_session.execute.side_effect = [count_res, latest_res]
    app.dependency_overrides[get_db] = lambda: mock_session

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/crawler/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_crawled_articles"] == 4
            assert data["total_crawled_chunks"] == 25
            assert len(data["latest_announcements"]) == 1
            assert data["latest_announcements"][0]["title"] == "Lịch thi tốt nghiệp"
    finally:
        app.dependency_overrides.clear()
