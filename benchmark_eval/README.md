# Bộ Kiểm Thử Số Liệu Thực Nghiệm Báo Cáo Dự Án CHAT-TLU (StudyBot)

Thư mục này chứa toàn bộ mã nguồn kiểm thử định lượng, dữ liệu thực tế và các tệp nhật ký (logs) đối soát số liệu cho **Chương 4** và **Chương 5** của báo cáo dự án.

---

## 📂 Cấu Trúc Thư Mục

```text
benchmark_eval/
├── data/
│   ├── tlu_testset_246.json          # 236-246 câu hỏi thực tế từ CSDL đã gán nhãn Ground Truth
│   └── tlu_abbreviations_eval.json   # 28 bộ câu hỏi test chuyên sâu từ viết tắt học vụ
├── scripts/
│   ├── eval_table_4_1_retrieval.py    # Kiểm thử so sánh 4 mô hình truy xuất (Bảng 4.1)
│   ├── eval_table_4_2_enhancer.py     # Đo tỷ lệ hiểu đúng 28 từ viết tắt TLU (Bảng 4.2)
│   ├── eval_table_4_3_cache.py        # Mô phỏng 500 queries đo Hit Rate & Độ trễ (Bảng 4.3)
│   ├── eval_table_4_4_triad.py        # Đo lường bộ khung RAG Triad (Bảng 4.4)
│   └── run_all_benchmarks.py          # Script Master: Chạy toàn bộ chỉ với 1 lệnh
├── logs/
│   ├── table_4_1_retrieval.log        # Log chi tiết truy xuất từng câu hỏi & bảng so sánh 4.1
│   ├── table_4_2_enhancer.log         # Log kết quả trước và sau khi giải mã viết tắt 4.2
│   ├── table_4_3_cache.log            # Log đo độ trễ và tỷ lệ tiết kiệm token API 4.3
│   ├── table_4_4_triad.log            # Log điểm Faithfulness và Relevance 4.4
│   └── benchmark_summary.md           # Báo cáo tổng hợp đối chiếu số liệu đo được vs số liệu báo cáo
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
4. **Kiểm thử Bảng 4.4 (RAG Triad - Chống ảo giác)**:
   ```powershell
   .\Backend\venv\Scripts\python.exe -X utf8 benchmark_eval\scripts\eval_table_4_4_triad.py
   ```

---

## 📊 Vị Trí Xem Kết Quả & Log

Sau khi chạy xong, toàn bộ kết quả chi tiết từng câu hỏi và bảng tổng hợp được lưu tại:
- Báo cáo tổng hợp Markdown: [`benchmark_eval/logs/benchmark_summary.md`](logs/benchmark_summary.md)
- Log Bảng 4.1: [`benchmark_eval/logs/table_4_1_retrieval.log`](logs/table_4_1_retrieval.log)
- Log Bảng 4.2: [`benchmark_eval/logs/table_4_2_enhancer.log`](logs/table_4_2_enhancer.log)
- Log Bảng 4.3: [`benchmark_eval/logs/table_4_3_cache.log`](logs/table_4_3_cache.log)
- Log Bảng 4.4: [`benchmark_eval/logs/table_4_4_triad.log`](logs/table_4_4_triad.log)
