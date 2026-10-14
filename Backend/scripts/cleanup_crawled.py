"""
cleanup_crawled.py — Xóa toàn bộ thông báo đã cào từ web trường (file data/crawled/, vector Qdrant, dòng Document).

Dùng để dọn dữ liệu cào cũ trước khi cào lại bằng crawler mới.

Cách dùng (chạy trong thư mục Backend/):
    python scripts/cleanup_crawled.py --dry-run
    python scripts/cleanup_crawled.py
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.crawler.tlu_crawler import CRAWLED_DIR, WEB_DOC_PREFIX  # noqa: E402
from app.models.database import AsyncSessionLocal, Document  # noqa: E402
from ingest import delete_doc_by_name  # noqa: E402


async def main(dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Document).where(Document.original_name.like(f"{WEB_DOC_PREFIX}%")))
        docs = res.scalars().all()

        doc_names = {f"{d.filename}.md" for d in docs}
        files = sorted(CRAWLED_DIR.glob("*.md")) if CRAWLED_DIR.exists() else []
        doc_names |= {f.name for f in files}

        print(f"Dòng Document: {len(docs)}")
        for d in docs:
            print(f"  - {d.original_name}  ({d.filename}.md, {d.chunk_count} chunks)")
        print(f"File trong {CRAWLED_DIR}: {len(files)}")
        for f in files:
            print(f"  - {f.name}")

        if dry_run:
            print("\n--dry-run: không xóa gì.")
            return

        for name in sorted(doc_names):
            delete_doc_by_name(name)
        for f in files:
            f.unlink(missing_ok=True)
        for d in docs:
            await db.delete(d)
        await db.commit()
        print(f"\nĐã xóa {len(docs)} dòng Document, {len(files)} file và vector của {len(doc_names)} doc_name.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không xóa")
    asyncio.run(main(parser.parse_args().dry_run))
