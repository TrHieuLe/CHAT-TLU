#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_answer_eval.py — Gộp bộ test đánh giá câu trả lời `tlu_answer_eval.json` từ:
  - tlu_testset_clean.json  : 120 câu trả lời được (id, question, ground_truth)
  - tlu_key_facts.json      : ý bắt buộc (key_facts) cho một phần các câu trên
  - tlu_unanswerable.json   : câu thuộc chủ đề TLU nhưng tài liệu không có → expect_refusal=true

Sửa nhãn ở hai file nguồn rồi chạy lại script này, không sửa tay file đầu ra.

    python -X utf8 benchmark_eval/scripts/build_answer_eval.py
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    clean = json.loads((DATA / "tlu_testset_clean.json").read_text(encoding="utf-8"))
    facts = json.loads((DATA / "tlu_key_facts.json").read_text(encoding="utf-8"))
    unans = json.loads((DATA / "tlu_unanswerable.json").read_text(encoding="utf-8"))

    ids = {q["id"] for q in clean}
    unknown = sorted(set(int(k) for k in facts["items"]) - ids)
    if unknown:
        raise SystemExit(f"key_facts có id không nằm trong bộ test sạch: {unknown}")

    out = []
    for q in clean:
        row = {"id": q["id"], "question": q["question"], "ground_truth": q["ground_truth"], "expect_refusal": False}
        kf = facts["items"].get(str(q["id"]))
        if kf:
            row["key_facts"] = kf["key_facts"]
        out.append(row)
    for q in unans["items"]:
        if q["id"] in ids:
            raise SystemExit(f"id câu từ chối trùng bộ test sạch: {q['id']}")
        out.append({"id": q["id"], "question": q["question"], "ground_truth": [], "expect_refusal": True})

    dst = DATA / "tlu_answer_eval.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_kf = sum(1 for r in out if r.get("key_facts"))
    n_ref = sum(1 for r in out if r["expect_refusal"])
    print(f"Đã ghi {dst.name}: {len(out)} câu ({len(out) - n_ref} trả lời được, {n_kf} có key_facts, "
          f"{n_ref} cần từ chối)")
    if not facts.get("reviewed") or not unans.get("reviewed"):
        print("⚠ key_facts / câu từ chối vẫn là BẢN NHÁP (reviewed=false) — cần người duyệt trước khi báo cáo số liệu.")


if __name__ == "__main__":
    main()
