import asyncio
import html as html_lib
import logging
import re
import ssl
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import certifi
import httpx
from bs4 import BeautifulSoup, Comment, Declaration, Doctype, NavigableString, ProcessingInstruction, Tag
from sqlalchemy import select

from app.core.config import settings
from app.models.database import AsyncSessionLocal, Document
from ingest import delete_doc_by_name, ingest_file

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

WEB_DOC_PREFIX = "[Thông báo Web] "
CERTS_DIR = Path(__file__).resolve().parent / "certs"
CRAWLED_DIR = Path(__file__).resolve().parents[2] / "data" / "crawled"

# Trang danh sách thông báo (dùng khi WP REST API không truy cập được)
TLU_NOTICE_LIST_PATH = "/tin-tuc-thong-bao/thong-bao/"
# Link bài viết WordPress của TLU luôn kết thúc bằng "-<post id>/"
ARTICLE_URL_RE = re.compile(r"-(\d+)/?$")
ATTACHMENT_RE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar)$", re.I)
MODIFIED_RE = re.compile(r"^- \*\*Cập nhật lần cuối\*\*: (.*)$", re.M)

_SKIP_TAGS = {"script", "style", "noscript", "iframe", "img", "svg", "form", "button", "nav", "footer"}
_BLOCK_TAGS = {
    "p", "div", "section", "article", "ul", "ol", "blockquote", "figure", "figcaption",
    "header", "main", "aside", "dl", "dt", "dd", "pre", "hr", "center",
}
_NON_TEXT = (Comment, Doctype, Declaration, ProcessingInstruction)


def build_ssl_context() -> ssl.SSLContext:
    """
    tlu.edu.vn không gửi kèm chứng chỉ trung gian (Sectigo RSA DV CA) nên certifi không xác thực được.
    Bổ sung các chứng chỉ trung gian trong certs/ vào bộ CA, vẫn giữ xác thực SSL đầy đủ.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    for pem in sorted(CERTS_DIR.glob("*.pem")):
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


def clean_text(text: str) -> str:
    """Làm sạch các khoảng trắng thừa và ký tự rác."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\t+", " ", text)
    lines = [re.sub(r" +", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _is_attachment(url: str) -> bool:
    return bool(ATTACHMENT_RE.search(urlparse(url).path))


def _table_to_markdown(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [
            re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).replace("|", "\\|")
            for cell in tr.find_all(["td", "th"])
        ]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def html_to_markdown(html: str, base_url: str) -> tuple[str, list[dict]]:
    """
    Chuyển HTML nội dung bài viết sang Markdown (giữ đoạn, tiêu đề, danh sách, bảng, link)
    và gom danh sách tệp đính kèm (.pdf, .docx, .xlsx...).
    """
    soup = BeautifulSoup(html or "", "html.parser")
    attachments: list[dict] = []
    seen_urls: set[str] = set()
    parts: list[str] = []

    def render(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, _NON_TEXT):
                continue
            if isinstance(child, NavigableString):
                parts.append(re.sub(r"\s+", " ", str(child)))
                continue
            if not isinstance(child, Tag):
                continue

            name = child.name.lower()
            if name in _SKIP_TAGS:
                continue
            if name == "br":
                parts.append("\n")
            elif name == "table":
                table_md = _table_to_markdown(child)
                if table_md:
                    parts.append(f"\n\n{table_md}\n\n")
            elif name == "a":
                text = re.sub(r"\s+", " ", child.get_text(" ", strip=True))
                href = (child.get("href") or "").strip()
                if not href or href.startswith(("#", "javascript:")):
                    parts.append(text)
                    continue
                if href.startswith("mailto:"):
                    parts.append(text or href[len("mailto:"):])
                    continue
                abs_url = urljoin(base_url, href)
                if _is_attachment(abs_url) and abs_url not in seen_urls:
                    seen_urls.add(abs_url)
                    attachments.append({
                        "name": text or unquote(Path(urlparse(abs_url).path).name),
                        "url": abs_url,
                    })
                parts.append(f"[{text}]({abs_url})" if text and text != abs_url else abs_url)
            elif re.fullmatch(r"h[1-6]", name):
                text = re.sub(r"\s+", " ", child.get_text(" ", strip=True))
                if text:
                    # "#" dành cho tiêu đề bài, "##" cho các mục của file → heading trong bài bắt đầu từ "###"
                    parts.append(f"\n\n{'#' * max(3, int(name[1]))} {text}\n\n")
            elif name == "li":
                parts.append("\n- ")
                render(child)
                parts.append("\n")
            elif name in _BLOCK_TAGS:
                parts.append("\n\n")
                render(child)
                parts.append("\n\n")
            else:
                render(child)

    render(soup)
    return clean_text("".join(parts)), attachments


def _find_content_element(soup: BeautifulSoup) -> Tag | None:
    return (
        soup.select_one(".entry-content")
        or soup.select_one(".fancybox")
        or soup.find(class_=re.compile(r"post-content|post-body|article-body|content|detail", re.I))
        or soup.find("article")
        or soup.find("div", id=re.compile(r"content", re.I))
    )


def parse_article_detail(html: str, base_url: str) -> dict:
    """Trích xuất tiêu đề, ngày đăng, nội dung (Markdown) và tệp đính kèm từ trang chi tiết bài viết."""
    soup = BeautifulSoup(html, "html.parser")

    title_el = (
        soup.find("h1", class_=re.compile(r"entry-title|title|detail|post", re.I))
        or soup.find("h1")
        or soup.find("h2", class_=re.compile(r"title", re.I))
    )
    title = title_el.get_text(strip=True) if title_el else "Thông báo Đại học Thủy Lợi"

    date_el = soup.find("time") or soup.find(class_=re.compile(r"entry-date|published|post-date|date", re.I))
    publish_date = ""
    if date_el:
        publish_date = date_el.get("datetime") or date_el.get_text(strip=True)

    content_el = _find_content_element(soup)
    content, attachments = html_to_markdown(str(content_el) if content_el else str(soup), base_url)

    return {
        "title": title,
        "publish_date": publish_date,
        "content": content,
        "attachments": attachments,
    }


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\-]+", "-", text, flags=re.UNICODE).strip("-_").lower()
    return slug[:max_len].strip("-_") or "thong-bao"


def build_article_filename(post_id: int | str, slug: str) -> str:
    slug = re.sub(rf"-{post_id}$", "", slug or "")
    return f"TLU_{post_id}_{_slugify(slug)}.md"


def build_article_markdown(article: dict) -> str:
    lines = [
        f"# {article['title']}",
        f"- **Mã bài viết**: {article['post_id']}",
        f"- **Nguồn trích xuất**: {article['url']}",
        f"- **Ngày đăng**: {article.get('date') or 'Không rõ'}",
        f"- **Cập nhật lần cuối**: {article.get('modified') or article.get('date') or 'Không rõ'}",
        "- **Đơn vị ban hành**: Trường Đại học Thủy lợi",
        "",
        "## Nội dung thông báo",
        "",
        article["content"],
    ]
    if article.get("attachments"):
        lines += ["", "## Tệp đính kèm văn bản"]
        lines += [f"- [{att['name']}]({att['url']})" for att in article["attachments"]]
    return "\n".join(lines) + "\n"


def read_modified_marker(file_path: Path) -> str | None:
    try:
        match = MODIFIED_RE.search(file_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return match.group(1).strip() if match else None


def _article_from_wp_post(post: dict) -> dict:
    link = post.get("link") or ""
    content, attachments = html_to_markdown((post.get("content") or {}).get("rendered", ""), link)
    return {
        "post_id": post["id"],
        "slug": post.get("slug") or "",
        "title": html_lib.unescape((post.get("title") or {}).get("rendered", "")).strip() or "Thông báo",
        "url": link,
        "date": post.get("date") or "",
        "modified": post.get("modified") or post.get("date") or "",
        "content": content,
        "attachments": attachments,
    }


async def fetch_articles_via_api(client: httpx.AsyncClient, max_articles: int) -> list[dict]:
    """Lấy thông báo mới nhất qua WordPress REST API của tlu.edu.vn."""
    base = settings.TLU_CRAWL_BASE_URL.rstrip("/")
    resp = await client.get(
        f"{base}/wp-json/wp/v2/posts",
        params={
            "categories": ",".join(str(c) for c in settings.TLU_CRAWL_CATEGORY_IDS),
            "per_page": min(max_articles, 100),
            "orderby": "date",
            "order": "desc",
            "_fields": "id,slug,link,title,date,modified,content",
        },
    )
    resp.raise_for_status()
    posts = resp.json()
    if not isinstance(posts, list):
        raise ValueError("WP REST API trả về dữ liệu không hợp lệ")
    return [_article_from_wp_post(p) for p in posts if p.get("id")]


def extract_article_links(html: str, page_url: str) -> list[str]:
    """Lấy link bài viết từ trang danh sách: cùng domain, dạng ".../<slug>-<id>/" (bỏ link menu, danh mục)."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(settings.TLU_CRAWL_BASE_URL).netloc.removeprefix("www.")
    links: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        url = urljoin(page_url, a_tag["href"].strip()).split("#")[0]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc.removeprefix("www.") != host:
            continue
        path = parsed.path
        if path.count("/") > 2 or "/category/" in path or "/tag/" in path:
            continue
        if ARTICLE_URL_RE.search(path) and url not in links:
            links.append(url)
    return links


async def fetch_articles_via_html(client: httpx.AsyncClient, max_articles: int) -> list[dict]:
    """Fallback: cào trang danh sách thông báo rồi từng trang chi tiết."""
    list_url = settings.TLU_CRAWL_BASE_URL.rstrip("/") + TLU_NOTICE_LIST_PATH
    resp = await client.get(list_url)
    resp.raise_for_status()

    articles = []
    for url in extract_article_links(resp.text, list_url)[:max_articles]:
        try:
            detail = await client.get(url)
            detail.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Lỗi tải bài %s: %s", url, e)
            continue
        parsed = parse_article_detail(detail.text, url)
        path = urlparse(url).path.strip("/")
        articles.append({
            "post_id": ARTICLE_URL_RE.search(urlparse(url).path).group(1),
            "slug": path,
            "title": parsed["title"],
            "url": url,
            "date": parsed["publish_date"],
            "modified": parsed["publish_date"],
            "content": parsed["content"],
            "attachments": parsed["attachments"],
        })
    return articles


async def _find_document(db, post_id: int | str, filename_stem: str) -> Document | None:
    res = await db.execute(
        select(Document)
        .where(
            (Document.filename == filename_stem)
            | Document.filename.like(f"TLU\\_{post_id}\\_%", escape="\\")
        )
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    return res.scalars().first()


async def process_article(article: dict) -> dict:
    """Ghi file Markdown, ingest vào Qdrant và upsert dòng Document cho 1 bài. Trả về kết quả xử lý."""
    post_id = article["post_id"]
    filename = build_article_filename(post_id, article["slug"])
    file_path = CRAWLED_DIR / filename
    result = {
        "post_id": post_id,
        "title": article["title"],
        "url": article["url"],
        "date": article.get("date", ""),
        "filename": filename,
        "chunk_count": 0,
        "status": "failed",
        "error": None,
    }

    if len(article["content"]) < 50 and not article.get("attachments"):
        result.update(status="skipped", error="Nội dung bài viết quá ngắn")
        return result

    async with AsyncSessionLocal() as db:
        doc = await _find_document(db, post_id, file_path.stem)

        # Bài đã có, chưa đổi trên web và đã ingest thành công → bỏ qua (không gọi lại Gemini)
        if (
            doc is not None
            and doc.status == "ok"
            and file_path.is_file()
            and read_modified_marker(file_path) == (article.get("modified") or article.get("date") or "Không rõ")
        ):
            result.update(status="skipped", chunk_count=doc.chunk_count or 0)
            return result

        is_new = doc is None and not any(CRAWLED_DIR.glob(f"TLU_{post_id}_*.md"))

        # Bản cũ của cùng bài (khác tên file do đổi slug) → xóa file và vector cũ
        for old in CRAWLED_DIR.glob(f"TLU_{post_id}_*.md"):
            if old.name != filename:
                await asyncio.to_thread(delete_doc_by_name, old.name)
                old.unlink(missing_ok=True)

        file_path.write_text(build_article_markdown(article), encoding="utf-8")

        if doc is None or doc.status != "ok":
            # Chưa có bản ghi hợp lệ → xóa chunk sót lại để ingest lại từ đầu, tránh trùng
            await asyncio.to_thread(delete_doc_by_name, filename)

        doc_id = doc.id if doc else str(uuid.uuid4())
        try:
            chunk_count = await asyncio.to_thread(ingest_file, file_path, doc_id, False, True)
            error = None if chunk_count > 0 else "Không tạo được chunk nào từ nội dung bài viết"
        except Exception as e:
            logger.warning("Lỗi ingest bài %s: %s", article["url"], e, exc_info=True)
            chunk_count, error = 0, str(e)

        if doc is None:
            doc = Document(id=doc_id)
            db.add(doc)
        doc.filename = file_path.stem
        doc.original_name = f"{WEB_DOC_PREFIX}{article['title']}"[:255]
        doc.file_type = "md"
        doc.file_size = file_path.stat().st_size
        doc.chunk_count = chunk_count
        doc.status = "ok" if error is None else "error"
        doc.error_msg = error
        await db.commit()

    result.update(
        chunk_count=chunk_count,
        status=("new" if is_new else "updated") if error is None else "failed",
        error=error,
    )
    return result


async def crawl_and_ingest_tlu(max_articles: int = 5, progress: dict[str, Any] | None = None) -> list[dict]:
    """
    Cào các thông báo mới nhất từ website TLU, lưu thành file Markdown và
    ingest vào Qdrant để Chatbot có thể tra cứu ngay.
    `progress` (tùy chọn) được cập nhật trực tiếp để router theo dõi tiến độ.
    """
    progress = progress if progress is not None else {}
    progress.update(total=0, done=0, current=None, new=0, updated=0, skipped=0, failed=0, errors=[], articles=[])
    CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Bắt đầu quét thông báo từ website Đại học Thủy Lợi (tối đa %d bài)", max_articles)

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=settings.TLU_CRAWL_TIMEOUT_SECONDS, follow_redirects=True,
        verify=build_ssl_context(),
    ) as client:
        try:
            articles = await fetch_articles_via_api(client, max_articles)
        except Exception as e:
            logger.warning("WP REST API lỗi (%s), chuyển sang cào HTML", e)
            try:
                articles = await fetch_articles_via_html(client, max_articles)
            except Exception as e_html:
                logger.error("Không cào được trang danh sách thông báo: %s", e_html)
                progress["errors"].append(f"Không truy cập được website trường: {e_html}")
                return []

    articles = articles[:max_articles]
    progress["total"] = len(articles)
    results = []

    for article in articles:
        progress["current"] = article["title"]
        try:
            result = await process_article(article)
        except Exception as e:
            logger.warning("Lỗi xử lý bài %s: %s", article.get("url"), e, exc_info=True)
            result = {
                "post_id": article.get("post_id"),
                "title": article.get("title"),
                "url": article.get("url"),
                "chunk_count": 0,
                "status": "failed",
                "error": str(e),
            }

        results.append(result)
        progress[result["status"]] += 1
        if result["status"] == "failed":
            progress["errors"].append(f"{result['title']}: {result['error']}")
        progress["articles"].append(result)
        progress["done"] += 1
        logger.info("  [%s] %s (%s chunks)", result["status"], (result["title"] or "")[:60], result["chunk_count"])

    progress["current"] = None
    logger.info(
        "Hoàn tất cào thông báo: mới %d, cập nhật %d, bỏ qua %d, lỗi %d",
        progress["new"], progress["updated"], progress["skipped"], progress["failed"],
    )
    return results
