"""
eval_cache_threshold.py — Chọn ngưỡng cosine cho Semantic Cache bằng vector BGE-M3 thật.

- PARAPHRASES: cùng ý, khác cách hỏi → NÊN trúng cache
- HARD_NEGATIVES: câu chữ gần giống nhưng khác ý → KHÔNG ĐƯỢC trúng (trúng = trả lời sai)
- Ngoài ra: cặp gần nhất giữa các câu khác nhau trong tlu_testset_246 (khác ground truth)

Câu hỏi đi qua enhance_query giống pipeline thật. In ra tỷ lệ trúng/sai theo từng ngưỡng,
có và không có bộ lọc "số trong câu phải khớp" (number guard) của SemanticCache.

    python scripts/eval_cache_threshold.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag import embedder  # noqa: E402
from app.rag.query_enhancer import enhance_query  # noqa: E402
from app.rag.semantic_cache import numbers_compatible  # noqa: E402

PARAPHRASES = [
    ("Điều kiện để được xét tốt nghiệp là gì?", "Cần những điều kiện gì để được công nhận tốt nghiệp?"),
    ("Cách tính điểm trung bình tích lũy CPA?", "CPA được tính như thế nào?"),
    ("Sinh viên bị cảnh báo học tập khi nào?", "Khi nào thì sinh viên bị cảnh báo học vụ?"),
    ("Học phí một tín chỉ là bao nhiêu?", "Một tín chỉ có giá bao nhiêu tiền?"),
    ("Thủ tục xin bảo lưu kết quả học tập như thế nào?", "Muốn bảo lưu kết quả học tập thì làm thủ tục gì?"),
    ("đrl bao nhiêu thì được xét học bổng?", "Điểm rèn luyện tối thiểu để được xét học bổng là bao nhiêu?"),
    ("Điều kiện đăng ký học vượt?", "Muốn học vượt cần điều kiện gì?"),
    ("Quy định về thi lại và học lại học phần?", "Học lại, thi lại học phần được quy định thế nào?"),
    ("Chuẩn đầu ra tiếng Anh ngành CNTT là gì?", "Ngành công nghệ thông tin yêu cầu chuẩn đầu ra tiếng Anh thế nào?"),
    ("Làm sao để đăng ký ở ký túc xá?", "Thủ tục đăng ký ktx như thế nào?"),
    ("Sinh viên bị buộc thôi học trong trường hợp nào?", "Khi nào sinh viên bị đuổi học?"),
    ("Thời gian đào tạo tối đa của hệ đại học là bao lâu?", "Sinh viên được học tối đa bao nhiêu năm?"),
    ("Điểm rèn luyện được đánh giá theo những tiêu chí nào?", "Các tiêu chí đánh giá điểm rèn luyện gồm những gì?"),
    ("Xếp loại học lực theo thang điểm 4 như thế nào?", "Thang điểm 4 xếp loại học lực ra sao?"),
    ("Sinh viên được khen thưởng khi nào?", "Những trường hợp nào sinh viên được khen thưởng?"),
    ("Hình thức kỷ luật sinh viên gồm những gì?", "Sinh viên vi phạm có thể bị kỷ luật ở các mức nào?"),
    ("Phòng đào tạo ở đâu?", "pđt nằm ở tòa nhà nào?"),
    ("Có những câu lạc bộ nào trong trường?", "Trường có các CLB sinh viên nào?"),
    ("Học bổng khuyến khích học tập xét như thế nào?", "Tiêu chí xét học bổng khuyến khích học tập là gì?"),
    ("Miễn giảm học phí cho đối tượng nào?", "Ai được miễn giảm học phí?"),
    ("Cách đăng ký tín chỉ mỗi học kỳ?", "Đăng ký học phần mỗi kỳ làm thế nào?"),
    ("Quy định thi trực tuyến như thế nào?", "Thi online được tổ chức theo quy định gì?"),
    ("Sinh viên ngoại trú cần khai báo gì?", "Quy định về sinh viên ở ngoại trú là gì?"),
    ("Điểm chuẩn ngành Kỹ thuật phần mềm năm nay?", "Năm nay ngành ktpm lấy bao nhiêu điểm?"),
]

HARD_NEGATIVES = [
    ("Học phí học kỳ 1 là bao nhiêu?", "Học phí học kỳ 2 là bao nhiêu?"),
    ("CPA dưới 1.0 thì bị gì?", "CPA dưới 2.0 thì bị gì?"),
    ("Điều kiện xét học bổng?", "Điều kiện xét tốt nghiệp?"),
    ("Điểm chuẩn ngành CNTT năm 2024?", "Điểm chuẩn ngành CNTT năm 2025?"),
    ("Điểm chuẩn ngành Kỹ thuật phần mềm?", "Điểm chuẩn ngành Khoa học máy tính?"),
    ("Thủ tục bảo lưu kết quả học tập?", "Thủ tục thôi học tự nguyện?"),
    ("Sinh viên năm nhất đăng ký tối đa bao nhiêu tín chỉ?", "Sinh viên năm cuối đăng ký tối đa bao nhiêu tín chỉ?"),
    ("Điểm rèn luyện loại xuất sắc là bao nhiêu?", "Điểm rèn luyện loại yếu là bao nhiêu?"),
    ("Học lại học phần có mất phí không?", "Thi lại học phần có mất phí không?"),
    ("Chuẩn đầu ra tiếng Anh ngành CNTT?", "Chuẩn đầu ra tiếng Anh chương trình tiên tiến?"),
    ("Khi nào bị cảnh báo học tập?", "Khi nào bị buộc thôi học?"),
    ("Điều kiện được học vượt?", "Điều kiện được học song ngành?"),
    ("Học bổng khuyến khích học tập?", "Học bổng chính sách?"),
    ("Đăng ký ở ký túc xá thế nào?", "Đăng ký ở ngoại trú thế nào?"),
    ("Hình thức khen thưởng sinh viên?", "Hình thức kỷ luật sinh viên?"),
    ("Thời gian đào tạo chuẩn là bao lâu?", "Thời gian đào tạo tối đa là bao lâu?"),
    ("Thi online có được dùng tài liệu không?", "Thi trực tiếp có được dùng tài liệu không?"),
    ("Miễn học phí cho sinh viên khuyết tật?", "Miễn học phí cho sinh viên dân tộc thiểu số?"),
    ("Xếp loại học lực giỏi cần CPA bao nhiêu?", "Xếp loại học lực khá cần CPA bao nhiêu?"),
    ("Lịch thi học kỳ 1?", "Lịch học học kỳ 1?"),
]

# Biến thể thực tế: cùng câu hỏi, khác từ đệm / viết tắt / dấu câu → NÊN trúng
FILLER_VARIANTS = [
    ("Điều kiện xét tốt nghiệp là gì?", "Cho em hỏi điều kiện xét tốt nghiệp là gì ạ?"),
    ("Cách tính CPA như thế nào?", "cách tính cpa thế nào vậy ạ"),
    ("Học phí một tín chỉ là bao nhiêu?", "Cho mình hỏi học phí một tín chỉ bao nhiêu?"),
    ("Thủ tục đăng ký ký túc xá?", "thủ tục đăng ký ktx"),
    ("Điểm rèn luyện xuất sắc là bao nhiêu điểm?", "đrl xuất sắc là bao nhiêu điểm vậy"),
    ("Điều kiện học vượt là gì?", "Hãy cho tôi biết điều kiện học vượt"),
    ("Quy định thi lại ra sao?", "quy định thi lại như thế nào ạ?"),
    ("Chuẩn đầu ra tiếng Anh CNTT?", "chuẩn đầu ra tiếng anh cntt là gì"),
    ("Khi nào bị cảnh báo học tập?", "Cho em hỏi khi nào thì bị cảnh báo học tập ạ"),
    ("Học bổng khuyến khích học tập xét thế nào?", "xin hỏi học bổng khuyến khích học tập xét như thế nào"),
]

THRESHOLDS =[0.86, 0.88, 0.90, 0.92, 0.94, 0.96]


def embed(texts):
    dense, _ = embedder.get_embeddings([enhance_query(t) for t in texts], max_length=512)
    v = np.asarray(dense, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def pair_sims(pairs):
    a = embed([p[0] for p in pairs])
    b = embed([p[1] for p in pairs])
    return (a * b).sum(axis=1)


def report(name, pairs, sims, want_hit):
    print(f"\n{name}: n={len(pairs)}  min={sims.min():.3f}  median={np.median(sims):.3f}  max={sims.max():.3f}")
    for (q1, q2), s in sorted(zip(pairs, sims), key=lambda x: -x[1] if not want_hit else x[1])[:6]:
        guard = numbers_compatible(q1, q2)
        print(f"   {s:.3f} guard={'ok ' if guard else 'BLK'} | {q1}  <->  {q2}")


def main():
    pos = pair_sims(PARAPHRASES)
    neg = pair_sims(HARD_NEGATIVES)
    report("PARAPHRASES (nên trúng) — thấp nhất", PARAPHRASES, pos, want_hit=True)
    report("HARD NEGATIVES (không được trúng) — cao nhất", HARD_NEGATIVES, neg, want_hit=False)

    testset = json.loads((ROOT.parent / "benchmark_eval" / "data" / "tlu_testset_246.json").read_text(encoding="utf-8"))
    qs = [t["question"] for t in testset]
    gts = [set(t["ground_truth"]) for t in testset]
    v = embed(qs)
    sim = v @ v.T
    np.fill_diagonal(sim, -1)
    nn_neg = []
    for i in range(len(qs)):
        j = int(sim[i].argmax())
        if qs[i].strip().lower() != qs[j].strip().lower() and not (gts[i] & gts[j]):
            nn_neg.append((qs[i], qs[j], float(sim[i, j])))
    nn_sims = np.array([x[2] for x in nn_neg])
    print(f"\nTESTSET: cặp gần nhất KHÁC tài liệu đúng: n={len(nn_neg)}  median={np.median(nn_sims):.3f}  max={nn_sims.max():.3f}")
    for q1, q2, s in sorted(nn_neg, key=lambda x: -x[2])[:5]:
        print(f"   {s:.3f} | {q1}  <->  {q2}")

    # Mô phỏng đúng logic SemanticCache.get (exact / canonical / semantic + guard)
    from app.rag.semantic_cache import SemanticCache
    pv1, pv2 = embed([p[0] for p in PARAPHRASES]), embed([p[1] for p in PARAPHRASES])
    nv1, nv2 = embed([p[0] for p in HARD_NEGATIVES]), embed([p[1] for p in HARD_NEGATIVES])

    def hits(pairs, v1, v2, t):
        out = []
        for (q1, q2), a, b in zip(pairs, v1, v2):
            c = SemanticCache(similarity_threshold=t)
            c.put(q1, "câu trả lời mẫu đủ dài", query_vector=a)
            r = c.get(q2, query_vector=b)
            out.append(r[2] if r else None)
        return out

    fv1, fv2 = embed([p[0] for p in FILLER_VARIANTS]), embed([p[1] for p in FILLER_VARIANTS])
    print("\nSemanticCache thật | ngưỡng | biến thể từ đệm trúng | paraphrase trúng | hard-neg trúng NHẦM")
    for t in THRESHOLDS:
        fh = hits(FILLER_VARIANTS, fv1, fv2, t)
        ph, nh = hits(PARAPHRASES, pv1, pv2, t), hits(HARD_NEGATIVES, nv1, nv2, t)
        print(f"  {t:.2f} | {sum(x is not None for x in fh):2d}/{len(fh)} | "
              f"{sum(x is not None for x in ph):2d}/{len(ph)} | {sum(x is not None for x in nh):2d}/{len(nh)}")
    fh = hits(FILLER_VARIANTS, fv1, fv2, 0.90)
    print("  biến thể @0.90:", [(FILLER_VARIANTS[i][1], m) for i, m in enumerate(fh)])

if __name__ == "__main__":
    main()
