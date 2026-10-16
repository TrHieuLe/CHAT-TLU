# Bộ Kiểm Thử Số Liệu Thực Nghiệm Báo Cáo Dự Án CHAT-TLU (StudyBot)

Thư mục này chứa toàn bộ mã nguồn kiểm thử định lượng, dữ liệu thực tế và các tệp nhật ký (logs) đối soát số liệu cho **Chương 4** và **Chương 5** của báo cáo dự án.

---

## 📂 Cấu Trúc Thư Mục

```text
benchmark_eval/
├── data/
│   ├── tlu_testset_246.json          # 236-246 câu hỏi thực tế từ CSDL đã gán nhãn Ground Truth
│   ├── tlu_abbreviations_eval.json   # 28 bộ câu hỏi test chuyên sâu từ viết tắt học vụ
│   ├── tlu_testset_clean.json        # 120 câu đã làm sạch nhãn (xem tlu_testset_clean_changelog.md)
│   ├── tlu_key_facts.json            # Ý bắt buộc (đáp án chuẩn) cho ~40 câu — nguồn để duyệt
│   ├── tlu_unanswerable.json         # 25 câu tài liệu không có → chatbot phải từ chối
│   └── tlu_answer_eval.json          # Bộ đánh giá câu trả lời (sinh bởi build_answer_eval.py)
├── scripts/
│   ├── eval_table_4_1_retrieval.py    # Kiểm thử so sánh 4 mô hình truy xuất (Bảng 4.1)
│   ├── eval_table_4_2_enhancer.py     # Đo tỷ lệ hiểu đúng 28 từ viết tắt TLU (Bảng 4.2)
│   ├── eval_table_4_3_cache.py        # ⚠ MÔ PHỎNG 500 queries (vector ngẫu nhiên), chưa đo hệ thống thật (Bảng 4.3)
│   ├── eval_table_4_4_triad.py        # In Bảng 4.4 từ kết quả đo thật của Backend/scripts/eval_answers.py
│   ├── build_answer_eval.py           # Gộp tlu_answer_eval.json từ bộ sạch + key facts + câu từ chối
│   └── run_all_benchmarks.py          # Script Master: Chạy toàn bộ chỉ với 1 lệnh
├── logs/
│   ├── table_4_1_retrieval.log        # Log chi tiết truy xuất từng câu hỏi & bảng so sánh 4.1
│   ├── table_4_2_enhancer.log         # Log kết quả trước và sau khi giải mã viết tắt 4.2
│   ├── table_4_3_cache.log            # Log đo độ trễ và tỷ lệ tiết kiệm token API 4.3
│   ├── table_4_4_triad.log            # Log điểm Faithfulness và Relevance 4.4
│   └── benchmark_summary.md           # Báo cáo tổng hợp đối chiếu số liệu đo được vs số liệu báo cáo
├── results/
│   └── answer_eval_tlu_answer_eval.{json,md}  # Kết quả đo chất lượng câu trả lời (được commit)
└── README.md                          # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 Cách Chạy Kiểm Thử

Bạn có thể chạy toàn bộ 4 bài kiểm thử chỉ với **1 câu lệnh duy nhất** từ thư mục gốc của dự án:

```powershell
.\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\run_all_benchmarks.py
```

Hoặc chạy riêng từng kịch bản kiểm thử:

1. **Kiểm thử Bảng 4.1 (Cấu hình truy xuất)**:
   ```powershell
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\eval_table_4_1_retrieval.py
   ```
2. **Kiểm thử Bảng 4.2 (Giải mã từ viết tắt)**:
   ```powershell
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\eval_table_4_2_enhancer.py
   ```
3. **Kiểm thử Bảng 4.3 (Bộ nhớ đệm Semantic Cache)**:
   ```powershell
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\eval_table_4_3_cache.py
   ```
4. **Kiểm thử Bảng 4.4 (Chất lượng câu trả lời — đo thật, cần Qdrant + `GEMINI_API_KEY`)**:
   ```powershell
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\build_answer_eval.py
   cd Backend
   .\venv\Scripts\python.exe -X utf8 scripts\eval_answers.py                      # sinh + chấm + report (có cache, chạy lại được khi bị 429)
   .\venv\Scripts\python.exe -X utf8 scripts\eval_answers.py --export-calibration # xuất 30 mẫu để chấm tay
   .\venv\Scripts\python.exe -X utf8 scripts\eval_answers.py --calibrate          # đồng thuận judge vs người chấm
   cd ..
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\eval_table_4_4_triad.py
   ```
   Chỉ số: Faithfulness, Answer Relevance, Context Relevance, Correctness theo key facts, tỷ lệ từ chối đúng/sai,
   tỷ lệ trích dẫn Điều/Khoản và trích dẫn sai — mỗi chỉ số kèm khoảng tin cậy 95%.
   Hai cấu hình: StudyBot (pipeline thật) và LLM thuần (cùng model, không đưa ngữ cảnh).

---

## 📊 Vị Trí Xem Kết Quả & Log

Sau khi chạy xong, toàn bộ kết quả chi tiết từng câu hỏi và bảng tổng hợp được lưu tại:
- Báo cáo tổng hợp Markdown: [`benchmark_eval/logs/benchmark_summary.md`](logs/benchmark_summary.md)
- Log Bảng 4.1: [`benchmark_eval/logs/table_4_1_retrieval.log`](logs/table_4_1_retrieval.log)
- Log Bảng 4.2: [`benchmark_eval/logs/table_4_2_enhancer.log`](logs/table_4_2_enhancer.log)
- Log Bảng 4.3: [`benchmark_eval/logs/table_4_3_cache.log`](logs/table_4_3_cache.log)
- Log Bảng 4.4: [`benchmark_eval/logs/table_4_4_triad.log`](logs/table_4_4_triad.log)
- Kết quả đo câu trả lời: [`benchmark_eval/results/answer_eval_tlu_answer_eval.md`](results/answer_eval_tlu_answer_eval.md)
