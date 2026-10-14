import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

from main import app
from app.crawler import tlu_crawler
from app.crawler.tlu_crawler import (
    build_article_filename,
    build_article_markdown,
    clean_text,
    extract_article_links,
    html_to_markdown,
    parse_article_detail,
    read_modified_marker,
)
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


def test_parse_article_detail_wordpress_layout():
    sample_html = """
    <div class="site-content"><nav>Menu Học phí Tầm nhìn sứ mạng</nav>
      <h1 class="entry-title">Thông báo tổ chức cuộc thi hùng biện</h1>
      <time class="entry-date published" datetime="2026-10-09T09:35:58+07:00">09/10/2026</time>
      <div class="entry-content single-page"><p>Nội dung chính của thông báo.</p></div>
    </div>
    """
    article = parse_article_detail(sample_html, base_url="https://tlu.edu.vn/x-1/")
    assert article["title"] == "Thông báo tổ chức cuộc thi hùng biện"
    assert article["publish_date"] == "2026-10-09T09:35:58+07:00"
    assert article["content"] == "Nội dung chính của thông báo."


def test_html_to_markdown_keeps_inline_text_tables_and_attachments():
    html = """
    <div class="fancybox">
      <p>Lời dạy <b>Dân vận khéo</b> thì việc gì cũng thành công.</p>
      <h2>Thời gian</h2>
      <ul><li>Đợt 1: 10/10</li><li>Đợt 2: 20/10</li></ul>
      <table><tr><th>STT</th><th>Lớp</th></tr><tr><td>1</td><td>64CNTT|1</td></tr></table>
      <p>Đăng ký tại <a href="https://forms.gle/abc">đây</a>, liên hệ <a href="mailto:a@tlu.edu.vn">a@tlu.edu.vn</a>.</p>
      <p><a href="/wp-content/uploads/2026/10/TB.docx?ver=2">Tải thông báo</a></p>
      <script>alert(1)</script><img src="x.png">
    </div>
    """
    md, attachments = html_to_markdown(html, "https://tlu.edu.vn/bai-viet-1/")

    assert "Lời dạy Dân vận khéo thì việc gì cũng thành công." in md
    assert "### Thời gian" in md
    assert "- Đợt 1: 10/10" in md
    assert "| STT | Lớp |" in md
    assert "| 1 | 64CNTT\\|1 |" in md
    assert "[đây](https://forms.gle/abc)" in md
    assert "alert" not in md
    assert attachments == [{
        "name": "Tải thông báo",
        "url": "https://tlu.edu.vn/wp-content/uploads/2026/10/TB.docx?ver=2",
    }]


def test_extract_article_links_filters_menu_and_external():
    html = """
    <a href="https://tlu.edu.vn/sinh-vien/hoc-phi/">Học phí cho sinh viên chính quy năm học</a>
    <a href="https://tlu.edu.vn/thong-bao-to-chuc-cuoc-thi-hung-bien-57290/">Thông báo thi</a>
    <a href="https://www.tlu.edu.vn/ke-hoach-thang-10-57368/#comments">Kế hoạch</a>
    <a href="https://facebook.com/post-12345/">FB</a>
    <a href="https://tlu.edu.vn/category/thong-bao-123/">Danh mục</a>
    """
    links = extract_article_links(html, "https://tlu.edu.vn/tin-tuc-thong-bao/thong-bao/")
    assert links == [
        "https://tlu.edu.vn/thong-bao-to-chuc-cuoc-thi-hung-bien-57290/",
        "https://www.tlu.edu.vn/ke-hoach-thang-10-57368/",
    ]


def test_build_article_filename_is_stable():
    assert build_article_filename(57290, "thong-bao-thi-hung-bien-57290") == "TLU_57290_thong-bao-thi-hung-bien.md"
    assert build_article_filename(1, "") == "TLU_1_thong-bao.md"


def _article(**overrides):
    article = {
        "post_id": 57290,
        "slug": "thong-bao-thi-57290",
        "title": "Thông báo thi hùng biện",
        "url": "https://tlu.edu.vn/thong-bao-thi-57290/",
        "date": "2026-10-09T09:35:58",
        "modified": "2026-10-09T09:36:40",
        "content": "Nội dung thông báo tổ chức cuộc thi hùng biện tiếng Trung năm 2026 dành cho sinh viên.",
        "attachments": [{"name": "TB.docx", "url": "https://tlu.edu.vn/TB.docx"}],
    }
    article.update(overrides)
    return article


def test_build_article_markdown_roundtrips_modified_marker(tmp_path):
    path = tmp_path / "a.md"
    path.write_text(build_article_markdown(_article()), encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Thông báo thi hùng biện")
    assert "## Tệp đính kèm văn bản" in text
    assert read_modified_marker(path) == "2026-10-09T09:36:40"


class _FakeSessionCtx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def crawler_env(tmp_path, monkeypatch):
    session = MagicMock()
    session.commit = AsyncMock()
    monkeypatch.setattr(tlu_crawler, "CRAWLED_DIR", tmp_path)
    monkeypatch.setattr(tlu_crawler, "AsyncSessionLocal", lambda: _FakeSessionCtx(session))
    ingest = MagicMock(return_value=4)
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(tlu_crawler, "ingest_file", ingest)
    monkeypatch.setattr(tlu_crawler, "delete_doc_by_name", delete)
    find = AsyncMock(return_value=None)
    monkeypatch.setattr(tlu_crawler, "_find_document", find)
    return {"dir": tmp_path, "session": session, "ingest": ingest, "delete": delete, "find": find}


@pytest.mark.asyncio
async def test_process_article_new_then_skip_then_update(crawler_env):
    # Lần 1: bài mới → ghi file, ingest, thêm Document
    result = await tlu_crawler.process_article(_article())
    assert result["status"] == "new"
    assert result["chunk_count"] == 4
    file_path = crawler_env["dir"] / "TLU_57290_thong-bao-thi.md"
    assert file_path.is_file()
    added_doc = crawler_env["session"].add.call_args[0][0]
    assert added_doc.filename == "TLU_57290_thong-bao-thi"
    assert added_doc.original_name == "[Thông báo Web] Thông báo thi hùng biện"
    assert added_doc.status == "ok"

    # Lần 2: không đổi trên web → bỏ qua, không gọi ingest
    crawler_env["find"].return_value = added_doc
    crawler_env["ingest"].reset_mock()
    result = await tlu_crawler.process_article(_article())
    assert result["status"] == "skipped"
    crawler_env["ingest"].assert_not_called()

    # Lần 3: bài được sửa trên web → cập nhật, giữ nguyên dòng Document
    crawler_env["session"].add.reset_mock()
    result = await tlu_crawler.process_article(_article(modified="2026-10-10T08:00:00"))
    assert result["status"] == "updated"
    crawler_env["ingest"].assert_called_once()
    crawler_env["session"].add.assert_not_called()
    assert read_modified_marker(file_path) == "2026-10-10T08:00:00"


@pytest.mark.asyncio
async def test_process_article_zero_chunks_marks_failed(crawler_env):
    crawler_env["ingest"].return_value = 0
    result = await tlu_crawler.process_article(_article())
    assert result["status"] == "failed"
    added_doc = crawler_env["session"].add.call_args[0][0]
    assert added_doc.status == "error"


@pytest.mark.asyncio
async def test_process_article_removes_old_file_when_slug_changes(crawler_env):
    old = crawler_env["dir"] / "TLU_57290_ten-cu.md"
    old.write_text("cũ", encoding="utf-8")
    result = await tlu_crawler.process_article(_article())
    assert result["status"] == "updated"
    assert not old.exists()
    crawler_env["delete"].assert_any_call("TLU_57290_ten-cu.md")


@pytest.mark.asyncio
async def test_crawl_uses_wp_api_and_reports_progress(monkeypatch):
    posts = [{
        "id": 57290,
        "slug": "thong-bao-thi-57290",
        "link": "https://tlu.edu.vn/thong-bao-thi-57290/",
        "title": {"rendered": "Th&ocirc;ng b&aacute;o thi"},
        "date": "2026-10-09T09:35:58",
        "modified": "2026-10-09T09:36:40",
        "content": {"rendered": "<p>Nội dung</p>"},
    }]

    def handler(request):
        assert request.url.path == "/wp-json/wp/v2/posts"
        assert request.url.params["categories"] == "2010"
        return httpx.Response(200, json=posts)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        tlu_crawler.httpx, "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    processed = []

    async def fake_process(article):
        processed.append(article)
        return {"title": article["title"], "status": "new", "chunk_count": 2, "error": None}

    monkeypatch.setattr(tlu_crawler, "process_article", fake_process)
    progress = {}
    results = await tlu_crawler.crawl_and_ingest_tlu(max_articles=3, progress=progress)

    assert len(results) == 1
    assert processed[0]["title"] == "Thông báo thi"
    assert processed[0]["content"] == "Nội dung"
    assert progress["total"] == 1 and progress["done"] == 1 and progress["new"] == 1


@pytest.mark.asyncio
async def test_trigger_crawler_endpoint_runs_in_background():
    from app.routers import crawler as crawler_router

    transport = ASGITransport(app=app)
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_crawl(max_articles, progress):
        progress.update(total=1, done=0, new=0, updated=0, skipped=0, failed=0, errors=[], articles=[])
        started.set()
        await release.wait()
        progress.update(done=1, new=1)
        return []

    with patch("app.routers.crawler.crawl_and_ingest_tlu", side_effect=fake_crawl):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawler/run", json={"max_articles": 2})
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["job"]["running"] is True
            assert data["job"]["max_articles"] == 2

            await asyncio.wait_for(started.wait(), 2)
            # Phiên thứ 2 trong lúc phiên đầu đang chạy bị từ chối
            resp2 = await client.post("/api/crawler/run", json={"max_articles": 2})
            assert resp2.status_code == 409

            release.set()
            await asyncio.wait_for(crawler_router._task, 2)
            assert crawler_router._job["running"] is False
            assert crawler_router._job["new"] == 1
            assert crawler_router._job["finished_at"] is not None


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
            assert "job" in data
    finally:
        app.dependency_overrides.clear()
