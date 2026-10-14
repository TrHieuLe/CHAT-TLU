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
- Việc tiếp theo nên làm là **làm sạch bộ test** (đã làm, xem mục dưới), và bổ sung câu hỏi thật bị dislike
  (trang admin → tab Phản hồi → "Thêm vào bộ eval", ghi ra `data/feedback_candidates.jsonl`).
  Chưa cần thử chunking hay re-index.

## Bộ test đã làm sạch: `data/tlu_testset_clean.json` (2026-10-14)

Sinh bằng `benchmark_eval/scripts/build_clean_testset.py`. Lý do loại hoặc sửa nhãn từng câu nằm ở
`data/tlu_testset_clean_changelog.md`. File `tlu_testset_246.json` giữ nguyên vì bảng trên và chương 4 dựa vào nó.

- 236 câu → 162 câu khác nhau (gộp 74 bản trùng, so khớp không phân biệt hoa/thường) → **120 câu**.
- Loại 42 câu: 24 câu nối tiếp ("giải thích cho tôi ý 1 đi", "vậy loại khá"), 8 yêu cầu ảnh trường/logo
  (`anhtruong.docx` không có trong index), 6 câu về trường khác (Bách khoa, Phenikaa),
  3 câu "tòa C1/C2 ở đâu" (`toa.docx` không có trong index), 1 câu xin lời khuyên chung chung.
- Gán lại nhãn: ground_truth chỉ gồm tài liệu có trong index và chứa câu trả lời (đã mở từng file trong `Backend/data/`).
  Nhãn cũ lấy từ nguồn mà hệ thống cũ trả về nên thường kèm tài liệu không liên quan (ChiTieu.txt, CauLacBo.txt,
  KyTucXa.txt…), khiến Hit@K bị dễ dãi. Thay đổi chính:
  - Học phí: `TATC.docx` → `HocPhi.txt` (+ `QĐ về Học phí final`). Đơn giá tín chỉ chỉ có trong `HocPhi.txt`.
  - "Học lực yếu có bị buộc thôi học không?": học bổng/rèn luyện/TATC → `QĐ-1226` + `QuyDinhHocTap.txt`.
  - "Có cần chứng chỉ CNTT để tốt nghiệp không?" (id 98): học phí/chỉ tiêu → 2 file CĐR CNTT (QĐ 411).
  - "Cho tôi điểm chuẩn của khoa CNTT đi": 2 file CĐR CNTT → `DiemChuan.txt`.
  - "sinh viên sẽ bị hạ bằng khi nào": thi trực tuyến/CĐR CNTT/khen thưởng → `QĐ-1226` + `QuyDinhHocTap.txt`.
  - Bảng chứng chỉ tham chiếu và tổ chức cấp chứng chỉ → `TATC.docx`. Quy đổi IELTS/TOEIC → `TA.docx`
    và `QĐ…1315.docx` (hai file giống hệt nhau nên luôn đi cùng). Bỏ các file `table_docx_*.png`, `SuKienSinhVien.txt`.
- `feedback_candidates.jsonl` chưa tồn tại nên chưa có câu nào từ phản hồi; chạy lại script build sau khi
  điền `ground_truth` cho các ứng viên để gộp vào.

Chạy: `python -X utf8 scripts/eval_retrieval_variants.py --testset ../benchmark_eval/data/tlu_testset_clean.json`

| Biến thể | Hit@4 | MRR@4 | Hit@8 |
|---|---|---|---|
| **qdrant_rrf (hiện tại)** | **94.2%** | 0.880 | 99.2% |
| dense | 91.7% | 0.844 | 95.0% |
| sparse | 95.0% | 0.842 | 96.7% |
| qdrant_rrf câu gốc (không enhancer) | 94.2% | 0.884 | 99.2% |
| rrf k=2 | 94.2% | 0.881 | 99.2% |
| rrf k=10 | 92.5% | 0.876 | 98.3% |
| rrf k=60 | 93.3% | 0.883 | 96.7% |
| rrf k=60 w_sparse=0.5 | 90.8% | 0.874 | 96.7% |
| rrf k=60 w_sparse=1.5 | 93.3% | 0.883 | 97.5% |
| rrf k=60 w_sparse=2.0 | 93.3% | 0.878 | 98.3% |
| rrf k=60 w_sparse=3.0 | 93.3% | 0.870 | 97.5% |
| score_fusion dense=0.3 | 93.3% | 0.863 | 97.5% |
| score_fusion dense=0.5 | 92.5% | 0.875 | 99.2% |
| score_fusion dense=0.7 | 91.7% | 0.876 | 97.5% |
| rrf k=60 4 danh sách (gốc + enhancer) | 93.3% | 0.883 | 96.7% |

### Nhận xét trên bộ sạch

- Hit@4 giảm nhẹ (95.3% → 94.2%) vì nhãn chặt hơn, còn MRR@4 tăng mạnh (0.768 → 0.880): tài liệu đúng
  thường nằm ở hạng 1. Hit@8 đạt 99.2% (chỉ 1 câu trượt).
- Sparse đơn lẻ cao hơn RRF 1 câu về Hit@4 (95.0%) nhưng MRR thấp hơn nhiều (0.842). RRF vẫn là lựa chọn
  cân bằng nhất → **kết luận giữ RRF không đổi**. Enhancer không còn tạo khác biệt về Hit@4 trên bộ sạch.
- 7 câu còn trượt Hit@4 là **lỗi retrieval thật**, không phải lỗi nhãn:
  - "điểm đầu vào / chỉ tiêu của khoa công nghệ thông tin" (id 29, 155, 191): cụm "công nghệ thông tin" kéo
    2 file CĐR CNTT lên đầu; `DiemChuan.txt`/`ChiTieu.txt` ở hạng 5–7.
  - "chỉ tiêu tất cả các ngành" (37), "khối ngành Kinh tế-quản lý có bao nhiêu ngành" (63): đúng tài liệu ở hạng 7.
  - "sinh viên sẽ bị hạ bằng khi nào" (157): cách nói "hạ bằng" không khớp "giảm đi một mức", hạng 5.
  - "cho tôi thông tin về trường" (221): quá ngắn, `introduce.txt` không có trong top 8.
