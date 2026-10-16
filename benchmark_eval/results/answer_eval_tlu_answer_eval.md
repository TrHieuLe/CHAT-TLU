# Đánh giá chất lượng câu trả lời — `tlu_answer_eval.json`

*Sinh lúc 2026-10-16 15:18:50 · 145 câu · model trả lời `gemini-flash-lite-latest` · judge `gemini-flash-latest` · thiếu 0 lượt chấm*

Số trong ngoặc vuông là khoảng tin cậy 95% (bootstrap); n là số câu tính chỉ số đó.
Faithfulness của cột LLM thuần được chấm theo cùng ngữ cảnh StudyBot truy xuất được (bằng chứng tham chiếu).

| Chỉ số | LLM thuần (không RAG) | StudyBot |
|---|---|---|
| Faithfulness (khẳng định có căn cứ trong tài liệu) | 0.21 [0.17–0.26] (n=136) | 0.99 [0.97–1.00] (n=118) |
| Answer Relevance (đúng trọng tâm) | 0.57 [0.51–0.63] (n=120) | 0.93 [0.89–0.96] (n=120) |
| Context Relevance (ngữ cảnh đủ để trả lời) | N/A | 0.86 [0.79–0.92] (n=120) |
| Correctness (tỷ lệ ý bắt buộc nêu đúng) | 0.43 [0.29–0.58] (n=39) | 0.99 [0.96–1.00] (n=39) |
| Tỷ lệ câu nêu SAI ý bắt buộc | 46.2% [31–62] (n=39) | 0.0% [0–0] (n=39) |
| Từ chối đúng khi tài liệu không có | 28.0% [12–48] (n=25) | 100.0% [100–100] (n=25) |
| Từ chối sai khi tài liệu có | 1.1% [0–3] (n=89) | 0.0% [0–0] (n=103) |
| Tỷ lệ có trích dẫn Điều/Khoản | 0.8% [0–3] (n=118) | 20.3% [14–28] (n=118) |
| Tỷ lệ trích dẫn Điều không có trong tài liệu | 100.0% [100–100] (n=1) | 0.0% [0–0] (n=24) |

## 10 câu StudyBot điểm thấp nhất

- **id 63** — Khối ngành KInh tế-quản lý có bao nhiêu ngành · faith=0.13 · rel=0.75 · refused=False · ctx_đủ=False
- **id 114** — Học bổng loại Giỏi có giá trị bằng bao nhiêu % học phí? · faith=0.67 · rel=1.00 · refused=False · ctx_đủ=True
- **id 27** — quy đổi điểm từ các chứng chỉ Tiếng Anh quốc tế · faith=0.86 · rel=0.75 · refused=False · ctx_đủ=True
- **id 197** — Ngành nào có điểm đầu vào cao nhất khoa kinh tế · faith=0.87 · rel=0.50 · refused=False · ctx_đủ=False
- **id 127** — vậy phải làm sao thì mới bị buộc thôi học · faith=0.91 · rel=1.00 · refused=False · ctx_đủ=True
- **id 103** — Học lực yếu có bị buộc thôi học không? · faith=N/A · rel=0.00 · refused=True · ctx_đủ=False
- **id 186** — sinh viên chất lượng tiên tiến không được xét hocj bổng à · faith=N/A · rel=0.00 · refused=True · ctx_đủ=False
- **id 201** — Trường đại học thủy lợi · faith=1.00 · rel=0.25 · refused=False · ctx_đủ=True
- **id 215** — đại học thủy lợi · faith=1.00 · rel=0.25 · refused=False · ctx_đủ=True
- **id 52** — Quy đổi điểm chứng chỉ tiếng anh quốc tế · faith=1.00 · rel=0.50 · refused=False · ctx_đủ=True
