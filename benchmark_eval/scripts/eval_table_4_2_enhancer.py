#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_table_4_2_enhancer.py
Kiểm thử và đánh giá định lượng cho Bảng 4.2 (Chương 4).
Hiệu quả của Module Giải mã Từ viết tắt TLU (TLU Query Enhancer) trên 28 thuật ngữ học đường.
"""

import sys
import os
import json
import time
import unicodedata
import re
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "Backend"))

from app.rag.query_enhancer import enhance_query, TLU_ABBREVIATIONS

LOG_FILE = ROOT / "benchmark_eval" / "logs" / "table_4_2_enhancer.log"
DATASET_FILE = ROOT / "benchmark_eval" / "data" / "tlu_abbreviations_eval.json"

def log(msg=""):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def tokenize(text):
    text = unicodedata.normalize("NFC", text).lower()
    return re.findall(r"\w+", text)

def load_corpus():
    import docx
    import pdfplumber

    data_dir = ROOT / "Backend" / "data"
    corpus = []
    
    file_list = list(data_dir.rglob("*.*"))
    for f in file_list:
        if f.suffix not in ['.txt', '.docx', '.pdf']:
            continue
        doc_name = f.name
        content = ""
        try:
            if f.suffix == '.txt':
                content = f.read_text(encoding='utf-8', errors='ignore')
            elif f.suffix == '.docx':
                doc = docx.Document(f)
                content = "\n".join([p.text for p in doc.paragraphs if p.text])
            elif f.suffix == '.pdf':
                with pdfplumber.open(f) as pdf:
                    content = "\n".join([p.extract_text() or "" for p in pdf.pages])
        except Exception:
            continue
        if content.strip():
            corpus.append({"doc_name": doc_name, "text": content})
    return corpus

class LexicalMatcher:
    def __init__(self, corpus):
        self.corpus = corpus

    def search(self, query, top_k=4):
        q_tokens = set(tokenize(query))
        scores = []
        for idx, doc in enumerate(self.corpus):
            doc_tokens = set(tokenize(doc["text"]))
            overlap = len(q_tokens.intersection(doc_tokens))
            scores.append((overlap, doc["doc_name"]))
        scores.sort(key=lambda x: -x[0])
        return [doc_name for _, doc_name in scores[:top_k]]

def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== LOG ĐÁNH GIÁ ĐỊNH LƯỢNG BẢNG 4.2: TLU QUERY ENHANCER ===\n")
        f.write(f"Thời gian chạy: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    log("=" * 80)
    log("🚀 BẮT ĐẦU CHẠY THỰC NGHIỆM ĐÁNH GIÁ BẢNG 4.2 (QUERY ENHANCER BENCHMARK)")
    log("=" * 80)

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        abbr_list = json.load(f)
    log(f"✓ Đã nạp danh sách {len(abbr_list)} thuật ngữ viết tắt TLU để kiểm thử.")

    corpus = load_corpus()
    matcher = LexicalMatcher(corpus)
    log(f"✓ Đã nạp {len(corpus)} tài liệu quy chế làm căn cứ đối soát.")

    results = []
    log("\n--- [CHI TIẾT KIỂM THỬ TỪNG THUẬT NGỮ VIẾT TẮT] ---")
    
    for item in abbr_list:
        abbr = item["abbr"]
        full = item["full"]
        q_raw = item["sample_q"]
        expected_doc = item["doc"].split("/")[-1].lower()

        # 1. Truy xuất KHÔNG có Enhancer
        top_raw = matcher.search(q_raw, top_k=4)
        hit_raw = any(expected_doc in d.lower() for d in top_raw)
        
        # 2. Truy xuất CÓ TLU Enhancer
        q_enh = enhance_query(q_raw)
        top_enh = matcher.search(q_enh, top_k=4)
        hit_enh = any(expected_doc in d.lower() for d in top_enh)

        results.append({
            "abbr": abbr,
            "full": full,
            "q_raw": q_raw,
            "q_enh": q_enh,
            "hit_raw": 1.0 if hit_raw else 0.0,
            "hit_enh": 1.0 if hit_enh else 0.0,
        })
        
        status_raw = "✅ ĐÚNG" if hit_raw else "❌ TRƯỢT"
        status_enh = "✅ ĐÚNG" if hit_enh else "❌ TRƯỢT"
        log(f"  [{abbr.upper()}] \"{q_raw}\"")
        log(f"    -> Mở rộng: \"{q_enh}\"")
        log(f"    -> Không Enhancer: {status_raw} | Có Enhancer: {status_enh}")

    # Gom nhóm theo các nhóm từ viết tắt đại diện như Bảng 4.2
    groups = {
        "đrl / drl": ["đrl", "drl"],
        "cpa / gpa": ["cpa", "gpa"],
        "kktx / ktx": ["kktx", "ktx"],
        "kltn / đatn": ["kltn", "đatn", "datn"],
        "gvcn / bcs": ["gvcn", "bcs"],
        "pđt / cthssv": ["pđt", "pdt", "cthssv"],
    }

    log("\n" + "=" * 90)
    log("🏆 BẢNG KẾT QUẢ ĐỐI SÁNH HIỆU QUẢ TLU ENHANCER (BẢNG 4.2):")
    log("=" * 90)
    header = f"| {'Từ viết tắt khảo sát':<24} | {'Ý nghĩa học vụ':<32} | {'Không Enhancer':<16} | {'Có Enhancer':<14} | {'Cải thiện':<10} |"
    sep = "|" + "-" * 26 + "|" + "-" * 34 + "|" + "-" * 18 + "|" + "-" * 16 + "|" + "-" * 12 + "|"
    log(header)
    log(sep)

    for grp_label, abbr_keys in groups.items():
        sub_items = [r for r in results if r["abbr"] in abbr_keys]
        if sub_items:
            acc_raw = np.mean([r["hit_raw"] for r in sub_items]) * 100.0
            acc_enh = np.mean([r["hit_enh"] for r in sub_items]) * 100.0
            diff = acc_enh - acc_raw
            meaning = sub_items[0]["full"]
            line = f"| {grp_label:<24} | {meaning:<32} | {acc_raw:>14.1f}% | {acc_enh:>12.1f}% | {diff:>+8.1f}% |"
            log(line)

    total_acc_raw = np.mean([r["hit_raw"] for r in results]) * 100.0
    total_acc_enh = np.mean([r["hit_enh"] for r in results]) * 100.0
    total_diff = total_acc_enh - total_acc_raw
    log(sep)
    summary_line = f"| {'Trung bình toàn bộ':<24} | {'28 thuật ngữ viết tắt TLU':<32} | {total_acc_raw:>14.1f}% | {total_acc_enh:>12.1f}% | {total_diff:>+8.1f}% |"
    log(summary_line)
    log(sep)

if __name__ == "__main__":
    main()
