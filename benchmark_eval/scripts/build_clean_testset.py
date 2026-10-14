"""
build_clean_testset.py — Làm sạch bộ đánh giá retrieval tlu_testset_246.json.

Bộ gốc (236 câu) sinh từ log chat: ground_truth là các nguồn hệ thống cũ đã trả về, nên lẫn
nhiều tài liệu không chứa câu trả lời, nhiều câu lặp lại, câu hỏi nối tiếp và yêu cầu in ảnh.
Script này:
  1. Gộp các câu trùng (so khớp sau khi bỏ hoa/thường, khoảng trắng, dấu ? cuối).
  2. Áp quyết định thủ công cho từng câu: loại (DROP) hoặc gán lại nhãn (LABEL) theo tài liệu
     thực sự chứa câu trả lời trong Backend/data/ (đã mở từng tài liệu để kiểm tra).
  3. Gộp các câu từ data/feedback_candidates.jsonl đã điền ground_truth (nút "Thêm vào bộ eval").
  4. Ghi data/tlu_testset_clean.json và data/tlu_testset_clean_changelog.md.

File gốc tlu_testset_246.json giữ nguyên vì số liệu chương 4 dựa vào nó.

Cách dùng (thư mục gốc repo):
    python -X utf8 benchmark_eval/scripts/build_clean_testset.py
"""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
SRC = DATA / "tlu_testset_246.json"
FEEDBACK = DATA / "feedback_candidates.jsonl"
OUT = DATA / "tlu_testset_clean.json"
CHANGELOG = DATA / "tlu_testset_clean_changelog.md"

# ─── Nhóm tài liệu (tên file như trong payload doc_name của Qdrant) ─────────────
HOCPHI = ["HocPhi.txt"]  # mức thu theo tín chỉ 2024–2025 (chỉ file này có số tiền)
QD_HOCPHI = ["QĐ về Học phí final (25-10-2021).docx"]  # quy định học phí, miễn giảm
HB = ["QĐ ve HBKKHT, HBCS .docx", "HocBong.txt"]
QC = ["QĐ-1226-Quy che dao tao dai hoc-DHTL .docx", "QuyDinhHocTap.txt"]  # QuyDinhHocTap tóm tắt phần điểm của QĐ 1226
QC1226 = ["QĐ-1226-Quy che dao tao dai hoc-DHTL .docx"]
TA = ["TA.docx", "QĐ về tiếng anh CTTT.300921.QD.1315.docx"]  # hai file có nội dung giống hệt nhau
TATC = ["TATC.docx"]
CDR_CNTT = ["QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf", "QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf"]
OLP = ["QĐ 1089 thi OLP môn học .docx"]
KT = ["QĐ Khen thưởng - KL .docx"]
RL = ["QĐ đánh giá KQRL .docx"]
DIEMCHUAN = ["DiemChuan.txt"]
CHITIEU = ["ChiTieu.txt"]
INTRO = ["introduce.txt"]
WIFI = ["Wifi.txt"]
THUVIEN = ["ThuVien.txt"]
DKTC = ["DangKyTinChi.txt"]
GDTC = ["QD_1038_16.07.2021_GDTC.docx"]

# Lý do loại
FOLLOWUP = "câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước"
IMAGE = "yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index"
OUT_SCOPE = "ngoài phạm vi (trường khác)"
NO_SOURCE = "không có tài liệu nào trong index trả lời (toa.docx chưa được index)"
VAGUE = "câu hỏi chung chung/xin lời khuyên, không có tài liệu đích"

# Quyết định theo id đại diện (id nhỏ nhất của nhóm câu trùng).
# ("drop", lý do) hoặc ("label", ground_truth mới, ghi chú hoặc None)
DECISIONS: dict[int, tuple] = {
    # Học phí
    1: ("label", HOCPHI + QD_HOCPHI, "mức thu theo tín chỉ chỉ có trong HocPhi.txt"),
    8: ("label", HOCPHI + QD_HOCPHI, "nhãn cũ TATC.docx (học phí tiếng Anh tăng cường) sai"),
    11: ("label", HOCPHI, "nhãn cũ TATC.docx sai; mức 420.000đ/tín chỉ ngành CNTT nằm trong HocPhi.txt"),
    61: ("label", HOCPHI, "so sánh mức học phí giữa các khối ngành chỉ có trong HocPhi.txt"),
    62: ("label", HOCPHI, None),
    63: ("label", HOCPHI, "danh sách ngành theo khối Kinh tế – Quản lý nằm trong HocPhi.txt"),
    174: ("label", HOCPHI + QD_HOCPHI, None),
    107: ("label", QD_HOCPHI, "miễn giảm học phí cho SV dân tộc thiểu số / cận nghèo ở QĐ học phí"),
    24: ("label", HB + HOCPHI, "cần mức học bổng (% học phí) và đơn giá tín chỉ CNTT"),
    # Tiếng Anh tăng cường (TATC) — bảng tham chiếu chứng chỉ, tổ chức cấp chứng chỉ
    2: ("label", TATC, "bảng chứng chỉ tham chiếu tương đương nằm trong TATC.docx"),
    3: ("label", TATC, "danh sách tổ chức cấp chứng chỉ (IIG, British Council, IDP) nằm trong TATC.docx"),
    4: ("label", TATC, None),
    5: ("label", TATC, None),
    15: ("label", TATC, "in ảnh bảng trong tài liệu → vẫn đo được truy xuất tài liệu chứa bảng"),
    123: ("label", TATC, None),
    124: ("label", TATC, None),
    # Tiếng Anh chương trình tiên tiến (QĐ 1315)
    27: ("label", TA, "bảng quy đổi điểm IELTS/TOEIC nằm trong QĐ 1315 (TA.docx)"),
    52: ("label", TA, None),
    53: ("label", TA, None),
    55: ("label", TA, None),
    188: ("label", TA, None),
    198: ("label", TA, "bỏ các file ảnh table_docx_*.png (không có trong index)"),
    213: ("label", TA, "bỏ các file ảnh table_docx_*.png (không có trong index)"),
    30: ("label", TA, None),
    89: ("label", TA, None),
    90: ("label", TA, None),
    91: ("label", TA, None),
    92: ("label", TA, None),
    93: ("label", TA, None),
    94: ("label", TA, None),
    95: ("label", TA, None),
    175: ("label", TA + TATC + QC1226, "bỏ ảnh table_docx_*.png; bỏ CĐR CNTT (không phải tiếng Anh)"),
    # Quy chế đào tạo (QĐ 1226)
    18: ("label", QC, "bỏ SuKienSinhVien.txt (không có trong index)"),
    36: ("label", QC, None),
    38: ("label", QC, None),
    51: ("label", QC + HB, None),
    58: ("label", QC, "bỏ SuKienSinhVien.txt (không có trong index)"),
    64: ("label", QC, None),
    157: ("label", QC, "nhãn cũ (thi trực tuyến, CĐR CNTT, khen thưởng) không chứa điều kiện hạ bằng"),
    158: ("label", QC, "bỏ CĐR CNTT"),
    71: ("label", QC, None),
    72: ("label", QC, None),
    79: ("label", QC1226 + DKTC, "giới hạn tín chỉ/học kỳ ở Điều 8 QĐ 1226 và DangKyTinChi.txt"),
    80: ("label", QC1226 + DKTC, None),
    81: ("label", QC, None),
    82: ("label", QC, None),
    83: ("label", QC, None),
    84: ("label", QC, None),
    85: ("label", QC, None),
    86: ("label", QC, None),
    87: ("label", QC, None),
    88: ("label", QC, None),
    96: ("label", QC1226 + GDTC, None),
    97: ("label", QC1226, None),
    99: ("label", QC1226, "học cùng lúc hai chương trình: Điều 17 QĐ 1226"),
    100: ("label", QC, None),
    101: ("label", QC, None),
    102: ("label", QC, None),
    103: ("label", QC, "nhãn cũ (học bổng, rèn luyện, TATC) sai; buộc thôi học do học lực ở QĐ 1226"),
    125: ("label", QC1226, "bảng xếp trình độ năm học theo tín chỉ ở QĐ 1226"),
    127: ("label", QC1226 + KT, "buộc thôi học: do học lực (QĐ 1226) hoặc kỷ luật (QĐ khen thưởng – KL)"),
    152: ("label", QC + DKTC, None),
    # Chuẩn đầu ra CNTT (QĐ 411)
    98: ("label", CDR_CNTT, "nhãn cũ của id 98 (học phí, chỉ tiêu) sai; 13 bản sao còn lại đã gán đúng"),
    109: ("label", CDR_CNTT, None),
    110: ("label", CDR_CNTT, None),
    111: ("label", CDR_CNTT, None),
    112: ("label", CDR_CNTT, None),
    199: ("label", CDR_CNTT, None),
    200: ("label", CDR_CNTT, None),
    # Học bổng
    39: ("label", HB, None),
    41: ("label", HB, None),
    114: ("label", HB, None),
    115: ("label", HB, None),
    116: ("label", HB, None),
    117: ("label", HB, None),
    118: ("label", HB, None),
    119: ("label", HB, None),
    147: ("label", HB, None),
    148: ("label", HB, None),
    170: ("label", HB, None),
    186: ("label", HB, None),
    230: ("label", HB, None),
    # Olympic, khen thưởng, rèn luyện
    105: ("label", OLP, None),
    106: ("label", OLP, None),
    113: ("label", OLP, None),
    120: ("label", KT, None),
    121: ("label", KT, None),
    122: ("label", KT, None),
    26: ("label", RL, None),
    35: ("label", RL, None),
    77: ("label", RL, None),
    # Tuyển sinh
    28: ("label", CHITIEU, None),
    29: ("label", CHITIEU, None),
    37: ("label", CHITIEU, None),
    42: ("label", DIEMCHUAN, None),
    43: ("label", DIEMCHUAN, None),
    76: ("label", DIEMCHUAN, None),
    145: ("label", DIEMCHUAN, None),
    146: ("label", DIEMCHUAN, "nhãn cũ (2 file CĐR CNTT) sai"),
    153: ("label", DIEMCHUAN, None),
    155: ("label", DIEMCHUAN, None),
    156: ("label", DIEMCHUAN, None),
    191: ("label", DIEMCHUAN, None),
    196: ("label", DIEMCHUAN, None),
    197: ("label", DIEMCHUAN, None),
    # Giới thiệu trường, dịch vụ
    21: ("label", INTRO, None),
    22: ("label", INTRO, None),
    23: ("label", INTRO, None),
    31: ("label", INTRO, "bỏ anhtruong.docx (không có trong index)"),
    56: ("label", INTRO, None),
    163: ("label", INTRO, None),
    201: ("label", INTRO, "bỏ anhtruong.docx"),
    215: ("label", INTRO, "bỏ anhtruong.docx"),
    217: ("label", INTRO, "bỏ anhtruong.docx"),
    221: ("label", INTRO, "nhãn cũ (khen thưởng, học phí) sai"),
    222: ("label", INTRO, "bỏ anhtruong.docx"),
    32: ("label", THUVIEN, None),
    33: ("label", WIFI, None),
    34: ("label", WIFI, None),
    154: ("label", WIFI, None),
    # Câu nối tiếp
    40: ("drop", FOLLOWUP), 44: ("drop", FOLLOWUP), 54: ("drop", FOLLOWUP), 59: ("drop", FOLLOWUP),
    65: ("drop", FOLLOWUP), 67: ("drop", FOLLOWUP), 69: ("drop", FOLLOWUP), 70: ("drop", FOLLOWUP),
    73: ("drop", FOLLOWUP), 74: ("drop", FOLLOWUP), 149: ("drop", FOLLOWUP), 159: ("drop", FOLLOWUP),
    165: ("drop", FOLLOWUP), 167: ("drop", FOLLOWUP), 168: ("drop", FOLLOWUP), 171: ("drop", FOLLOWUP),
    172: ("drop", FOLLOWUP), 173: ("drop", FOLLOWUP), 176: ("drop", FOLLOWUP), 178: ("drop", FOLLOWUP),
    187: ("drop", FOLLOWUP), 194: ("drop", FOLLOWUP), 209: ("drop", FOLLOWUP), 212: ("drop", FOLLOWUP),
    # Ảnh / ngoài phạm vi / không có nguồn
    46: ("drop", "yêu cầu in lại ảnh người dùng gửi, không phải truy xuất tài liệu"),
    47: ("drop", IMAGE),
    202: ("drop", IMAGE), 203: ("drop", IMAGE), 206: ("drop", IMAGE), 208: ("drop", IMAGE),
    214: ("drop", IMAGE), 226: ("drop", IMAGE),
    204: ("drop", OUT_SCOPE), 205: ("drop", OUT_SCOPE), 207: ("drop", OUT_SCOPE),
    210: ("drop", OUT_SCOPE), 211: ("drop", OUT_SCOPE), 227: ("drop", OUT_SCOPE),
    224: ("drop", NO_SOURCE), 225: ("drop", NO_SOURCE), 228: ("drop", NO_SOURCE),
    75: ("drop", VAGUE),
}


def norm(q: str) -> str:
    return re.sub(r"\s+", " ", q).strip().rstrip("?").strip().lower()


def basename(name: str) -> str:
    return (name or "").replace("\\", "/").split("/")[-1]


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    groups: dict[str, list[dict]] = {}
    for q in data:
        groups.setdefault(norm(q["question"]), []).append(q)

    reps = {min(x["id"] for x in g): g for g in groups.values()}
    missing = sorted(set(reps) - set(DECISIONS))
    extra = sorted(set(DECISIONS) - set(reps))
    assert not missing and not extra, f"thiếu quyết định: {missing}; id không phải đại diện: {extra}"

    clean, log_label, log_drop = [], [], []
    for rid in sorted(reps):
        g = sorted(reps[rid], key=lambda x: x["id"])
        ids = [x["id"] for x in g]
        old = sorted({basename(d) for x in g for d in x["ground_truth"]})
        dec = DECISIONS[rid]
        if dec[0] == "drop":
            log_drop.append((ids, g[0]["question"], dec[1]))
            continue
        gt = dec[1]
        clean.append({"id": rid, "question": g[0]["question"].strip(), "ground_truth": gt,
                      "source_ids": ids, "origin": "tlu_testset_246"})
        if sorted(gt) != old or len(ids) > 1:
            log_label.append((ids, g[0]["question"], old, gt, dec[2]))

    # Câu từ phản hồi người dùng (chỉ lấy câu đã được điền ground_truth)
    added = []
    if FEEDBACK.exists():
        seen = {norm(q["question"]) for q in clean}
        next_id = max(q["id"] for q in data) + 1
        for line in FEEDBACK.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            gt = [basename(d) for d in rec.get("ground_truth") or []]
            if not gt or norm(rec["question"]) in seen:
                continue
            seen.add(norm(rec["question"]))
            clean.append({"id": next_id, "question": rec["question"].strip(), "ground_truth": gt,
                          "origin": f"feedback:{rec.get('feedback_id')}"})
            added.append((next_id, rec["question"]))
            next_id += 1

    OUT.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_dup = len(data) - len(groups)
    lines = [
        "# Changelog bộ test sạch `tlu_testset_clean.json`",
        "",
        "Sinh tự động bởi `benchmark_eval/scripts/build_clean_testset.py` từ `tlu_testset_246.json`.",
        "",
        f"- Bộ gốc: {len(data)} câu, {len(groups)} câu khác nhau sau chuẩn hóa (bỏ {n_dup} bản trùng).",
        f"- Loại: {len(log_drop)} câu (tính theo câu khác nhau).",
        f"- Bộ sạch: {len(clean)} câu ({len(added)} câu từ feedback_candidates.jsonl).",
        "",
        "Nguyên tắc gán nhãn: ground_truth chỉ gồm tài liệu **có trong index** và **chứa câu trả lời**.",
        "Các nhãn cũ lấy từ nguồn hệ thống cũ trả về nên thường kèm tài liệu không liên quan",
        "(ChiTieu.txt, CauLacBo.txt, KyTucXa.txt...) và file không được index",
        "(SuKienSinhVien.txt, anhtruong.docx, toa.docx, table_docx_*.png).",
        "`TA.docx` và `QĐ về tiếng anh CTTT...1315.docx` có nội dung giống hệt nhau nên luôn đi cùng nhau.",
        "",
        "## Câu bị loại",
        "",
        "| id gốc | Câu hỏi | Lý do |",
        "|---|---|---|",
    ]
    for ids, q, why in log_drop:
        lines.append(f"| {', '.join(map(str, ids))} | {q.strip()} | {why} |")
    lines += ["", "## Câu đổi nhãn hoặc gộp bản trùng", "",
              "| id gốc | Câu hỏi | Nhãn cũ (hợp các bản) | Nhãn mới | Ghi chú |", "|---|---|---|---|---|"]
    for ids, q, old, new, note in log_label:
        extra_note = f"gộp {len(ids)} bản" if len(ids) > 1 else ""
        note = "; ".join(x for x in (note, extra_note) if x)
        lines.append(f"| {', '.join(map(str, ids))} | {q.strip()} | {'<br>'.join(old)} | {'<br>'.join(new)} | {note} |")
    lines += ["", "## Câu thêm từ phản hồi người dùng", ""]
    if added:
        lines += [f"- id {i}: {q}" for i, q in added]
    else:
        lines.append(f"Chưa có (`{FEEDBACK.name}` chưa tồn tại hoặc chưa có câu nào được điền ground_truth).")
    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(data)} → {len(clean)} câu; loại {len(log_drop)}; đổi nhãn/gộp {len(log_label)}; thêm {len(added)}")


if __name__ == "__main__":
    main()
