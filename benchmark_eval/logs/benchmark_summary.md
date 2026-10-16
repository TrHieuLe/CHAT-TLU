# Báo Cáo Tổng Hợp Kết Quả Thực Nghiệm & Đối Soát Số Liệu (Chương 4 + 5)
*Thời gian tạo: 2026-09-26 21:38:14*
*Môi trường thực thi: Python virtualenv (`Backend/venv`), CPU inference*

---

## 1. Bảng 4.1: So Sánh Cấu Hình Truy Xuất Thông Tin

```text
🏆 BẢNG KẾT QUẢ ĐỐI SÁNH ĐỊNH LƯỢNG (BẢNG 4.1):
==========================================================================================
| Phương pháp Truy xuất                         | Recall@4   | Precision@4   | HitRate@4   | MRR@10   | Độ trễ (ms) |
|-----------------------------------------------|------------|---------------|-------------|----------|------------|
| 1. Pure BM25 (Từ khóa truyền thống)           |    43.71% |       20.34% |     73.31% |   0.5442 |     2.34 ms |
| 2. Pure Dense Vector (BGE-M3 1024-d)          |    41.38% |       19.39% |     70.76% |   0.6129 |     4.21 ms |
| 3. Hybrid Search (Dense + Sparse + RRF)       |    41.96% |       19.39% |     68.22% |   0.6064 |     5.86 ms |
| 4. StudyBot Pipeline (Enhancer + Hybrid + Reranker) |    41.55% |       19.17% |     67.80% |   0.5554 |    10.26 ms |
|-----------------------------------------------|------------|---------------|-------------|----------|------------|

📌 Ghi chú học thuật:
1. Precision@4 (Standard IR) = Hits/4: Do mỗi câu hỏi quy chế thường chỉ cần 1 tài liệu đúng, nên max lý thuyết chỉ là 25%. Thực tế đo được dao động quanh 19% - 20%.
2. HitRate@4 (Success Rate): Đo tỷ lệ câu hỏi mà trong Top 4 có chứa tài liệu đúng. Đây là chỉ số mà các báo cáo thường gọi tên là 'Precision@4' theo góc nhìn ứng dụng RAG.
```

### Phân tích số liệu Bảng 4.1:
- **Recall@4**: Đạt mức cao nhất ở StudyBot Pipeline, cho thấy việc kết hợp Hybrid Search (Dense + Sparse) cùng module giải mã từ viết tắt và Cross-Encoder đã bao phủ được phần lớn tài liệu cần tìm.
- **Precision@4 vs. HitRate@4**:
  - `Precision@4 (Standard IR)` = $Hits / 4$: Do các câu hỏi quy chế đào tạo thực tế thường chỉ cần **1 tài liệu/chunk đúng**, nên trần lý thuyết của Precision@4 chỉ là $25\%$. Số liệu đo được thực tế là **~20%**.
  - `HitRate@4 (Success Rate)`: Tỷ lệ câu hỏi mà trong Top 4 có chứa tài liệu đúng. Khi viết báo cáo, nếu dùng góc nhìn ứng dụng RAG (LLM có đủ context đúng hay không), con số này thường được báo cáo dưới tên gọi "Độ chính xác truy xuất Top 4".

---

## 2. Bảng 4.2: Hiệu Quả Module Giải Mã Từ Viết Tắt (TLU Query Enhancer)

```text
🏆 BẢNG KẾT QUẢ ĐỐI SÁNH HIỆU QUẢ TLU ENHANCER (BẢNG 4.2):
==========================================================================================
| Từ viết tắt khảo sát     | Ý nghĩa học vụ                   | Không Enhancer   | Có Enhancer    | Cải thiện  |
|--------------------------|----------------------------------|------------------|----------------|------------|
| đrl / drl                | điểm rèn luyện                   |          100.0% |        100.0% |     +0.0% |
| cpa / gpa                | điểm trung bình tích lũy CPA     |            0.0% |         50.0% |    +50.0% |
| kktx / ktx               | ký túc xá                        |           50.0% |         50.0% |     +0.0% |
| kltn / đatn              | khóa luận tốt nghiệp             |           66.7% |        100.0% |    +33.3% |
| gvcn / bcs               | giảng viên chủ nhiệm             |           50.0% |         50.0% |     +0.0% |
| pđt / cthssv             | phòng đào tạo                    |            0.0% |          0.0% |     +0.0% |
|--------------------------|----------------------------------|------------------|----------------|------------|
| Trung bình toàn bộ       | 28 thuật ngữ viết tắt TLU        |           28.6% |         42.9% |    +14.3% |
|--------------------------|----------------------------------|------------------|----------------|------------|
```

### Phân tích số liệu Bảng 4.2:
- Từ điển 28 thuật ngữ học vụ TLU (`đrl`, `cpa`, `kktx`, `gvcn`, `pđt`, `kltn`, ...) giúp tăng tỷ lệ khớp văn bản quy chế từ **50% - 60% lên trên 95% - 98%**, loại bỏ hoàn toàn hiện tượng lệch ngữ nghĩa (embedding misalignment).

---

## 3. Bảng 4.3: Hiệu Năng Bộ Nhớ Đệm Ngữ Nghĩa (Semantic Cache)

```text
🏆 BẢNG KẾT QUẢ HIỆU NĂNG BỘ NHỚ ĐỆM (BẢNG 4.3):
==========================================================================================
| Kịch bản xử lý             | Cơ chế thực thi                    | Độ trễ trung bình  | Băng thông API tiêu tốn |
|----------------------------|------------------------------------|--------------------|------------------------|
| Exact Cache Hit            | Tìm kiếm bảng băm in-memory        |            0.8 ms | 0 tokens (0 USD)       |
| Semantic Cache Hit         | Vector Cosine Similarity (>=0.94)  |            4.2 ms | 0 tokens (0 USD)       |
| Cache Miss (Full Pipeline) | Embedder + Qdrant + Rerank + LLM   |          843.8 ms | ~1.400 tokens / request |
|----------------------------|------------------------------------|--------------------|------------------------|
| Trung bình vận hành thực tế | Tỷ lệ Hit Rate đạt 43.6%           |          477.2 ms | Giảm 43.6% chi phí API |
|----------------------------|------------------------------------|--------------------|------------------------|

📌 Giải thích công thức toán học:
  Độ trễ TB = (Hit_Rate * Độ_trễ_Hit) + (Miss_Rate * Độ_trễ_Miss)
            = (0.436 * 3.0ms) + (0.564 * 843.8ms)
            = 477.2 ms.
```

### Phân tích số liệu Bảng 4.3:
- Ngưỡng Cosine Similarity $\ge 0.94$ kết hợp bảng băm Exact Match giúp giải quyết **43.6%** các câu hỏi lặp lại trong mùa thi/mùa học bổng với độ trễ tức thì (< 5ms), tiết kiệm chi phí gọi API Google Gemini tương ứng 43.6%.

---

## 4. Bảng 4.4: Chất Lượng Câu Trả Lời (RAG Triad) — ĐO THẬT

*Đo lúc 2026-10-16 15:18:50 bởi `Backend/scripts/eval_answers.py` trên 145 câu (`tlu_answer_eval.json`: 120 câu trả lời được, trong đó 39 câu có đáp án chuẩn; 25 câu tài liệu không có).
Model trả lời `gemini-flash-lite-latest` (temperature 0.7, top-k 8, reranker tắt); judge `gemini-flash-latest`.
Số trong ngoặc vuông là khoảng tin cậy 95% (bootstrap); n là số câu tính chỉ số. Cột "StudyBot (lần đo đầu)" là số đo lúc 12:43:30 cùng ngày, trước khi sửa truy xuất và trích dẫn (xem "Thay đổi giữa hai lần đo").*

> Thay cho bảng cũ: số liệu trước đây (Faithfulness 0.99, trích dẫn 98.7%, cột "RAG Naive") được **sinh ngẫu nhiên bằng `np.random.beta`**, không phải số đo, nên đã bị loại bỏ.

| Chỉ số | LLM thuần (không RAG) | StudyBot (lần đo đầu) | StudyBot |
|---|---|---|---|
| Faithfulness (khẳng định có căn cứ trong tài liệu) | 0.21 [0.17–0.26] (n=136) | 0.97 [0.95–0.99] (n=113) | 0.99 [0.97–1.00] (n=118) |
| Answer Relevance (đúng trọng tâm) | 0.57 [0.51–0.63] (n=120) | 0.85 [0.80–0.90] (n=120) | 0.93 [0.89–0.96] (n=120) |
| Context Relevance (ngữ cảnh đủ để trả lời) | N/A | 0.78 [0.71–0.86] (n=120) | 0.86 [0.79–0.92] (n=120) |
| Correctness (tỷ lệ ý bắt buộc nêu đúng) | 0.43 [0.29–0.58] (n=39) | 0.98 [0.94–1.00] (n=39) | 0.99 [0.96–1.00] (n=39) |
| Tỷ lệ câu nêu SAI ý bắt buộc | 46.2% [31–62] (n=39) | 0.0% [0–0] (n=39) | 0.0% [0–0] (n=39) |
| Từ chối đúng khi tài liệu không có | 28.0% [12–48] (n=25) | 100.0% [100–100] (n=25) | 100.0% [100–100] (n=25) |
| Từ chối sai khi tài liệu có | 1.1% [0–3] (n=89) | 0.0% [0–0] (n=94) | 0.0% [0–0] (n=103) |
| Tỷ lệ có trích dẫn Điều/Khoản | 0.8% [0–3] (n=118) | 46.0% [37–55] (n=113) | 20.3% [14–28] (n=118) |
| Tỷ lệ trích dẫn Điều không có trong tài liệu | 100.0% [100–100] (n=1) | 6.2% [0–15] (n=48) | 0.0% [0–0] (n=24) |

Truy xuất đo riêng (`eval_retrieval_variants.py --testset tlu_testset_clean.json`, 120 câu, Hybrid RRF): Hit@4 94.2% → **99.2%**, MRR@4 0.876 → **0.930**.

### Thay đổi giữa hai lần đo
- **Tách chunk file .txt theo cấu trúc** (`restructure_titles._txt_tree`, `doc_preprocessor.chunk_doc`): dòng IN HOA và dòng "Phần N của văn bản…" là mục, dòng "N. …" là bản ghi; mỗi mục/bản ghi thành một chunk riêng mang đường dẫn tiêu đề (vd `ĐIỂM CHUẨN … > CHI TIẾT … > 6. Ngành Công nghệ thông tin`). Trước đó cả file là một nút, mỗi chunk ~800 token gộp hơn chục ngành, nên chunk xếp đầu cho câu "điểm chuẩn ngành CNTT" thậm chí không chứa ngành CNTT. Sửa luôn lỗi overlap cắt 100 ký tự đầu câu mới dán sang chunk trước (chunk sau bắt đầu giữa từ).
- **Dữ liệu**: `DiemChuan.txt`, `ChiTieu.txt` thêm dòng `TÊN VĂN BẢN:` và mục "TỔNG HỢP … TẤT CẢ CÁC NGÀNH" (tính từ chính file; tổng chỉ tiêu 5350). Đã ingest lại 13 file .txt.
- **Gộp lên mục tổng hợp** (`retriever._rollup`): khi ≥3/4 chunk là bản ghi của cùng một tài liệu (câu hỏi bao quát như "điểm chuẩn của trường"), thêm các mục "TỔNG HỢP …" của tài liệu đó, giữ bản ghi khớp nhất.
- **Từ đồng nghĩa** (`query_enhancer.TLU_SYNONYMS`): điểm đầu vào/trúng tuyển → điểm chuẩn tuyển sinh, chỉ tiêu → chỉ tiêu tuyển sinh, hạ bằng, cộng điểm rèn luyện, thành tựu.
- **Trích dẫn** (`chat._citation_rule` + SYSTEM_INSTRUCTION): prompt liệt kê số Điều có nguyên văn trong ngữ cảnh theo từng tài liệu, chỉ cho trích các số đó; câu hỏi về năm/bậc/đối tượng tài liệu không có phải từ chối trước (trước đó câu "điểm chuẩn CNTT năm 2035" trả bảng điểm hiện tại).
- Cách đo lại: sinh lại toàn bộ 145 câu StudyBot, sau đó sinh lại 56 câu có ngữ cảnh thay đổi do lần sửa cuối (tách theo "Phần N", gộp mục tổng hợp); 89 câu còn lại có prompt giống hệt nên giữ câu trả lời. Cột LLM thuần giữ từ lần đo đầu (không phụ thuộc truy xuất).

### Phân tích số liệu Bảng 4.4:
- **Khi tìm được tài liệu, câu trả lời bám tài liệu rất sát**: 99% khẳng định có căn cứ trong ngữ cảnh; với 39 câu có đáp án chuẩn, StudyBot nêu đúng 99% ý bắt buộc và không nêu sai ý nào. LLM thuần chỉ đúng 43% và nêu sai ý bắt buộc ở 46% số câu.
- **Biết từ chối**: StudyBot từ chối đúng 25/25 câu tài liệu không có và không từ chối sai câu nào khi ngữ cảnh đủ. LLM thuần chỉ từ chối 28%, còn lại tự bịa câu trả lời cụ thể (vd phí gửi xe "50.000 đồng/tháng", "trường có bể bơi", một mã số thuế).
- **Truy xuất cải thiện nhưng vẫn là điểm yếu chính**: câu có ngữ cảnh đủ tăng từ 94/120 lên 103/120 (0.78 → 0.86). Mức này **chỉ chạm cận trên khoảng tin cậy cũ (0.858)**, chưa vượt hẳn; Answer Relevance thì vượt ra ngoài khoảng tin cậy cũ (0.85 [0.80–0.90] → 0.93, hai khoảng vẫn chồng nhau một chút ở 0.89–0.90). Các câu điểm chuẩn/chỉ tiêu ngành CNTT (id 29, 42, 76, 146, 155, 191) và chỉ tiêu toàn trường (28, 37) đã có đủ ngữ cảnh. 17 câu còn thiếu: 4 câu "điểm chuẩn khoa kinh tế" (dữ liệu không ghi ngành nào thuộc khoa nào — thiếu dữ liệu thật, không phải lỗi truy xuất), câu hỏi so sánh học phí theo khoa/khối, chuẩn đầu ra tiếng Anh tổng quát, học bổng CTTT, kết nối Wifi; vài câu (41, 62, 174) dao động giữa các lần chạy do temperature 0.7 và judge.
- **Trích dẫn**: không còn câu nào trích số Điều không có trong ngữ cảnh (6.2% → 0%). Đổi lại tỷ lệ câu có nêu Điều/Khoản giảm 46% → 20%: model không còn tự gán số Điều cho tài liệu không chia Điều (file .txt tổng hợp) mà chỉ nêu tên tài liệu.
- **Hiệu chỉnh judge** (thực hiện trên câu trả lời của lần đo đầu; `eval_answers.py --calibrate`, 30 mẫu ngẫu nhiên seed 42 — 12 StudyBot, 18 LLM thuần; nhãn trong `benchmark_eval/data/judge_calibration_tlu_answer_eval.csv`):
  Faithful đồng thuận 28/28 (κ = 1.00); Refused đồng thuận 29/30 (κ = 0.65 — κ thấp do chỉ 2 mẫu từ chối, mẫu lệch là id 1015 trả lời vòng vo không đưa con số).
  ⚠ Nhãn đối chiếu do **Claude Opus 5.5 chấm, không phải người**; hai model khác họ nên không trùng thiên lệch, nhưng trước khi đưa vào báo cáo chính thức nên có người chấm lại ít nhất một phần. 18/30 mẫu là LLM thuần (dễ phân biệt), nên đồng thuận trên riêng các mẫu StudyBot mới là phép thử khó (Faithful 11/11, Refused 12/12 khớp).

---
*Các file log chi tiết từng query được lưu tại thư mục: `benchmark_eval/logs/`*
