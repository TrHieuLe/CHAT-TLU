import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.database import AsyncSessionLocal, Document
from ingest import ingest_file

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Các trang thông báo chính thống của Đại học Thủy Lợi
TLU_ANNOUNCEMENT_URLS = [
    "https://www.tlu.edu.vn/thong-bao",
    "https://www.tlu.edu.vn/tin-tuc-thong-bao",
]


def clean_text(text: str) -> str:
    """Làm sạch các khoảng trắng thừa và ký tự rác."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\t+", " ", text)
    lines = [re.sub(r" +", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_article_detail(html: str, base_url: str) -> dict:
    """Trích xuất tiêu đề, nội dung và file đính kèm từ trang chi tiết bài viết."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Tiêu đề
    title_el = (
        soup.find("h1", class_=re.compile(r"title|detail|post", re.I))
        or soup.find("h1")
        or soup.find("h2", class_=re.compile(r"title", re.I))
    )
    title = title_el.get_text(strip=True) if title_el else "Thông báo Đại học Thủy Lợi"

    # 2. Ngày đăng
    date_el = (
        soup.find(class_=re.compile(r"date|time|published|created", re.I))
        or soup.find("time")
    )
    publish_date = date_el.get_text(strip=True) if date_el else ""

    # 3. Khối nội dung chính
    content_el = (
        soup.find(class_=re.compile(r"content|detail|post-body|article-body", re.I))
        or soup.find("article")
        or soup.find("div", id=re.compile(r"content", re.I))
    )

    # Loại bỏ các thành phần rác (script, style, banner quảng cáo, chia sẻ)
    if content_el:
        for unwanted in content_el(["script", "style", "nav", "footer", "iframe"]):
            unwanted.decompose()
        content = clean_text(content_el.get_text(separator="\n"))
    else:
        content = clean_text(soup.get_text(separator="\n"))

    # 4. Tìm các tệp đính kèm (.pdf, .docx, .doc, .xlsx)
    attachments = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if re.search(r"\.(pdf|docx|doc|xlsx)$", href, re.I):
            abs_url = urljoin(base_url, href)
            attachments.append({
                "name": link.get_text(strip=True) or Path(href).name,
                "url": abs_url,
            })

    return {
        "title": title,
        "publish_date": publish_date,
        "content": content,
        "attachments": attachments,
    }


async def crawl_and_ingest_tlu(max_articles: int = 5) -> list[dict]:
    """
    Cào các thông báo mới nhất từ website TLU, lưu thành file Markdown và
    tự động ingest vào Qdrant để Chatbot có thể tra cứu ngay lập tức.
    """
    logger.info("🚀 Bắt đầu quét thông báo từ website Đại học Thủy Lợi...")
    results = []

    crawled_dir = Path(__file__).resolve().parents[2] / "data" / "crawled"
    crawled_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        article_links: list[dict] = []

        # 1. Quét danh sách bài viết từ các trang thông báo
        for url in TLU_ANNOUNCEMENT_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                # Tìm các liên kết bài viết
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    title = a_tag.get_text(strip=True)
                    # Lọc các link bài viết tin tức / thông báo
                    if len(title) > 20 and not href.startswith("#") and not href.startswith("javascript:"):
                        full_url = urljoin(url, href)
                        if full_url not in [item["url"] for item in article_links]:
                            article_links.append({"title": title, "url": full_url})

                    if len(article_links) >= max_articles * 2:
                        break
            except Exception as e:
                logger.warning(f"Lỗi truy cập danh mục {url}: {e}")

        # 2. Thu thập chi tiết từng bài viết và tiến hành nạp vào RAG
        processed = 0
        for item in article_links:
            if processed >= max_articles:
                break

            detail_url = item["url"]
            try:
                resp = await client.get(detail_url)
                if resp.status_code != 200:
                    continue

                article = parse_article_detail(resp.text, detail_url)
                if len(article["content"]) < 100:
                    continue  # Bỏ qua nếu nội dung quá ngắn hoặc rỗng

                # Đặt tên file an toàn
                safe_slug = re.sub(r"[^\w\-_]", "_", article["title"][:50]).strip("_")
                filename = f"TLU_{safe_slug}_{uuid.uuid4().hex[:6]}.md"
                file_path = crawled_dir / filename

                # Tạo nội dung Markdown có cấu trúc
                md_content = [
                    f"# {article['title']}",
                    f"- **Nguồn trích xuất**: {detail_url}",
                    f"- **Thời gian ban hành**: {article['publish_date'] or 'Gần đây'}",
                    f"- **Đơn vị ban hành**: Đại học Thủy Lợi",
                    "",
                    "## Nội dung thông báo",
                    "",
                    article["content"],
                ]

                if article["attachments"]:
                    md_content.append("\n## Tệp đính kèm văn bản")
                    for att in article["attachments"]:
                        md_content.append(f"- [{att['name']}]({att['url']})")

                file_path.write_text("\n".join(md_content), encoding="utf-8")

                # Ingest tự động vào Qdrant & Database
                doc_id = str(uuid.uuid4())
                chunk_count = ingest_file(file_path=file_path, doc_id=doc_id, auto=True)

                # Lưu vào database Document
                async with AsyncSessionLocal() as db:
                    doc = Document(
                        id=doc_id,
                        filename=file_path.stem,
                        original_name=f"[Thông báo Web] {article['title']}",
                        file_type="md",
                        file_size=file_path.stat().st_size,
                        chunk_count=chunk_count,
                        status="ok",
                    )
                    db.add(doc)
                    await db.commit()

                results.append({
                    "title": article["title"],
                    "url": detail_url,
                    "date": article["publish_date"],
                    "chunk_count": chunk_count,
                    "filename": filename,
                })
                processed += 1
                logger.info(f"  ✓ Đã cào & ingest: {article['title'][:60]} ({chunk_count} chunks)")

            except Exception as e:
                logger.warning(f"Lỗi cào chi tiết bài {detail_url}: {e}")

    logger.info(f"✅ Hoàn tất cào thông báo. Đã nạp thành công {len(results)} bài viết vào cơ sở tri thức.")
    return results
