# Đánh giá các cách gộp dense + sparse trên Qdrant thật (2026-10-14)

Script: `Backend/scripts/eval_retrieval_variants.py` (BGE-M3 + collection `nckh_docs` đang chạy, 236 câu của `data/tlu_testset_246.json`).

> Lưu ý: `scripts/eval_table_4_1_retrieval.py` mô phỏng "dense" bằng TF-IDF+SVD trên corpus tự cắt, **không** đo pipeline thật.
> Kết luận "BM25 tốt hơn pipeline" (HitRate ~68–73%) trong `logs/benchmark_summary.md` vì vậy không áp dụng cho hệ thống đang chạy.

| Biến thể | Hit@4 | MRR@4 | Hit@8 |
|---|---|---|---|
| **qdrant_rrf (hiện tại)** | **95.3%** | 0.768 | 96.6% |
| dense | 85.2% | 0.704 | 94.1% |
| sparse | 92.8% | 0.724 | 96.6% |
| qdrant_rrf câu gốc (không enhancer) | 94.1% | 0.766 | 96.2% |
| rrf k=2 | 95.3% | 0.773 | 96.6% |
| rrf k=10 | 93.2% | 0.772 | 96.6% |
| rrf k=60 | 93.6% | 0.775 | 96.2% |
| rrf k=60 w_sparse=0.5 | 91.5% | 0.769 | 96.2% |
| rrf k=60 w_sparse=1.5 | 93.2% | 0.774 | 96.2% |
| rrf k=60 w_sparse=2.0 | 93.2% | 0.777 | 96.6% |
| rrf k=60 w_sparse=3.0 | 94.5% | 0.783 | 97.0% |
| score_fusion dense=0.3 | 94.9% | 0.772 | 96.6% |
| score_fusion dense=0.5 | 92.4% | 0.775 | 97.0% |
| score_fusion dense=0.7 | 90.3% | 0.749 | 95.8% |
| rrf k=60 4 danh sách (gốc + enhancer) | 92.4% | 0.775 | 96.2% |

## Kết luận

- Cấu hình hiện tại (RRF của Qdrant + query enhancer) đã tốt nhất về Hit@4; chênh lệch giữa các biến thể chỉ 1–3 câu / 236 → **giữ nguyên**, không đổi fusion.
- Hybrid tốt hơn rõ rệt so với chỉ dense (+10 điểm) hoặc chỉ sparse (+2.5 điểm). Enhancer giúp +1.2 điểm.
- 11 câu trượt gần như đều do nhãn của bộ test: câu hỏi nối tiếp ("giải thích ý đầu"), yêu cầu in ảnh,
  hoặc ground truth lệch (vd "học phí" gán `TATC.docx` trong khi hệ thống trả đúng "QĐ về Học phí").
- Việc tiếp theo nên làm là **làm sạch bộ test**, và bổ sung câu hỏi thật bị dislike
  (trang admin → tab Phản hồi → "Thêm vào bộ eval", ghi ra `data/feedback_candidates.jsonl`).
  Chưa cần thử chunking hay re-index.
