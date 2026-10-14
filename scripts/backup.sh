#!/usr/bin/env bash
# Sao lưu hằng ngày cho bản triển khai docker compose (chạy trên host, trong thư mục gốc repo).
#   - SQLite app.db + semantic_cache.db: dùng sqlite3 backup API trong container backend (an toàn khi đang ghi)
#   - Qdrant: tạo snapshot collection qua REST API rồi tải về
#   - Giữ KEEP_DAYS ngày gần nhất
#
# Cron ví dụ (2h sáng mỗi ngày):
#   0 2 * * * cd /home/<user>/chat-tlu && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
QDRANT="${QDRANT_LOCAL_URL:-http://127.0.0.1:6333}"
COLLECTION="${COLLECTION_NAME:-nckh_docs}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-studybot_backend}"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"
echo "[$(date -Is)] Bắt đầu sao lưu vào $DEST"

# 1. SQLite — ghi ra /app/storage (bind-mount Backend/storage) rồi chuyển sang thư mục backup
docker exec "$BACKEND_CONTAINER" python - <<'PY'
import sqlite3
for src, dst in (("/app/app.db", "/app/storage/_bk_app.db"),
                 ("/app/storage/semantic_cache.db", "/app/storage/_bk_semantic_cache.db")):
    try:
        with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
            s.backup(d)
        print("ok", src)
    except sqlite3.OperationalError as e:
        print("bỏ qua", src, e)
PY
for f in app semantic_cache; do
  if [ -f "Backend/storage/_bk_$f.db" ]; then
    mv "Backend/storage/_bk_$f.db" "$DEST/$f.db"
  fi
done

# 2. Qdrant snapshot (bỏ qua nếu dùng Qdrant Cloud — Cloud có backup riêng)
if curl -fsS "$QDRANT/collections/$COLLECTION" >/dev/null 2>&1; then
  SNAP="$(curl -fsS -X POST "$QDRANT/collections/$COLLECTION/snapshots?wait=true" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["result"]["name"])')"
  curl -fsS -o "$DEST/$SNAP" "$QDRANT/collections/$COLLECTION/snapshots/$SNAP"
  curl -fsS -X DELETE "$QDRANT/collections/$COLLECTION/snapshots/$SNAP" >/dev/null
  echo "Qdrant snapshot: $SNAP"
else
  echo "Không kết nối được Qdrant local ($QDRANT) — bỏ qua snapshot"
fi

# 3. Dọn bản cũ
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} +
echo "[$(date -Is)] Xong. Dung lượng: $(du -sh "$DEST" | cut -f1)"
