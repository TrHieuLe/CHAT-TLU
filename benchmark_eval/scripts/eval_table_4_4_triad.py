#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_table_4_4_triad.py
Bảng 4.4 (Chương 4): chất lượng câu trả lời theo RAG Triad + trích dẫn + khả năng từ chối.

Script này KHÔNG tự sinh số liệu: nó đọc kết quả đo thật do Backend/scripts/eval_answers.py tạo ra
(Gemini trả lời thật trên Qdrant thật, một model Gemini mạnh hơn chấm điểm) và in thành bảng.

Chạy đo trước (trong thư mục Backend/):
    python -X utf8 scripts/eval_answers.py
Rồi in bảng:
    python -X utf8 benchmark_eval/scripts/eval_table_4_4_triad.py
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "Backend"))

LOG_FILE = ROOT / "benchmark_eval" / "logs" / "table_4_4_triad.log"
RESULT_FILE = ROOT / "benchmark_eval" / "results" / "answer_eval_tlu_answer_eval.json"


def log(msg=""):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== LOG BẢNG 4.4: CHẤT LƯỢNG CÂU TRẢ LỜI (RAG TRIAD) ===\n")
        f.write(f"Thời gian chạy: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    if not RESULT_FILE.exists():
        log(f"✗ Chưa có kết quả đo: {RESULT_FILE.relative_to(ROOT)}")
        log("  Chạy trước: cd Backend && python -X utf8 scripts/eval_answers.py")
        sys.exit(1)

    from scripts.eval_answers import render_table  # noqa: E402  (Backend/scripts)

    data = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    meta = data["meta"]
    log(f"✓ Kết quả đo lúc {meta['generated_at']} trên {meta['n_items']} câu ({meta['testset']})")
    log(f"  Model trả lời: {meta.get('answer_model')} · judge: {meta['judge_model']}"
        f" · thiếu {meta.get('missing_judgments', 0)} lượt chấm")
    log("")
    log("=" * 90)
    log("🏆 BẢNG KẾT QUẢ ĐÁNH GIÁ RAG TRIAD (BẢNG 4.4):")
    log("=" * 90)
    log(render_table(data["summary"]))
    log("")
    log("Ghi chú: số trong ngoặc vuông là khoảng tin cậy 95% (bootstrap), n là số câu tính chỉ số.")
    log("Faithfulness của LLM thuần được chấm theo cùng ngữ cảnh StudyBot truy xuất (bằng chứng tham chiếu).")


if __name__ == "__main__":
    main()
