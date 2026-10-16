# Đánh giá chất lượng câu trả lời — `tlu_answer_eval.json`

*Sinh lúc 2026-10-16 12:43:30 · 145 câu · model trả lời `gemini-flash-lite-latest` · judge `gemini-flash-latest` · thiếu 0 lượt chấm*

Số trong ngoặc vuông là khoảng tin cậy 95% (bootstrap); n là số câu tính chỉ số đó.
Faithfulness của cột LLM thuần được chấm theo cùng ngữ cảnh StudyBot truy xuất được (bằng chứng tham chiếu).

| Chỉ số | LLM thuần (không RAG) | StudyBot |
|---|---|---|
| Faithfulness (khẳng định có căn cứ trong tài liệu) | 0.21 [0.17–0.26] (n=136) | 0.97 [0.95–0.99] (n=113) |
| Answer Relevance (đúng trọng tâm) | 0.57 [0.51–0.63] (n=120) | 0.85 [0.80–0.90] (n=120) |
| Context Relevance (ngữ cảnh đủ để trả lời) | N/A | 0.78 [0.71–0.86] (n=120) |
| Correctness (tỷ lệ ý bắt buộc nêu đúng) | 0.43 [0.29–0.58] (n=39) | 0.98 [0.94–1.00] (n=39) |
| Tỷ lệ câu nêu SAI ý bắt buộc | 46.2% [31–62] (n=39) | 0.0% [0–0] (n=39) |
| Từ chối đúng khi tài liệu không có | 28.0% [12–48] (n=25) | 100.0% [100–100] (n=25) |
| Từ chối sai khi tài liệu có | 1.1% [0–3] (n=89) | 0.0% [0–0] (n=94) |
| Tỷ lệ có trích dẫn Điều/Khoản | 0.8% [0–3] (n=118) | 46.0% [37–55] (n=113) |
| Tỷ lệ trích dẫn Điều không có trong tài liệu | 100.0% [100–100] (n=1) | 6.2% [0–15] (n=48) |

## 10 câu StudyBot điểm thấp nhất

- **id 63** — Khối ngành KInh tế-quản lý có bao nhiêu ngành · faith=0.50 · rel=0.75 · refused=False · ctx_đủ=False
- **id 81** — Điểm chữ A tương ứng với thang điểm 10 là bao nhiêu? · faith=0.50 · rel=1.00 · refused=False · ctx_đủ=True
- **id 97** — Sinh viên tốt nghiệp sau 3 tháng kể từ khi đủ điều kiện có được nhận bằng không? · faith=0.50 · rel=1.00 · refused=False · ctx_đủ=True
- **id 101** — Điểm chữ I là gì? · faith=0.67 · rel=0.50 · refused=False · ctx_đủ=False
- **id 36** — Cho tôi quy chế tính điểm bằng chữ · faith=0.69 · rel=1.00 · refused=False · ctx_đủ=True
- **id 152** — Quy chế thi lại, học lại như thế nào? · faith=0.80 · rel=0.75 · refused=False · ctx_đủ=False
- **id 125** — Cần bao nhiêu tín chỉ tích lũy để lên năm thứ hai nhóm ngành Kỹ thuật? · faith=0.80 · rel=1.00 · refused=False · ctx_đủ=True
- **id 39** — Tiêu chí lấy điểm để xét học bổng của trường đại học thủy lợi là như nào · faith=0.83 · rel=1.00 · refused=False · ctx_đủ=True
- **id 197** — Ngành nào có điểm đầu vào cao nhất khoa kinh tế · faith=0.86 · rel=0.75 · refused=False · ctx_đủ=False
- **id 18** — Điều kiện tốt nghiệp gồm những gì? · faith=0.86 · rel=1.00 · refused=False · ctx_đủ=True
