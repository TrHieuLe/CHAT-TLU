# CƠ SỞ TOÁN HỌC VÀ CHỨNG MINH TÍNH ƯU VIỆT CỦA KIẾN TRÚC STUDYBOT (ADVANCED RAG)

Tài liệu này cung cấp toàn bộ cơ sở lý thuyết toán học, các định lý và công thức chứng minh vì sao kiến trúc **StudyBot Pipeline (Query Enhancer + Hybrid RRF + Cross-Encoder Reranker)** có hiệu năng vượt trội hơn hẳn phương pháp tìm kiếm từ khóa truyền thống (**Pure BM25**) và tìm kiếm vector đơn lẻ (**Pure Dense Search**).

---

## 1. MÔ HÌNH BM25 VÀ ĐỊNH LÝ "KHUYẾT TỪ VỰNG" (VOCABULARY MISMATCH)

### 1.1. Công thức tính điểm BM25 Okapi
Điểm tương đồng giữa câu hỏi truy vấn $Q = \{q_1, q_2, \dots, q_n\}$ và một đoạn tài liệu $D$ trong kho dữ liệu được tính theo công thức:

$$\text{Score}_{\text{BM25}}(D, Q) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Trong đó:
- $f(q_i, D)$: Tần số xuất hiện (Term Frequency) của từ $q_i$ trong tài liệu $D$.
- $|D|$: Độ dài (số lượng từ) của đoạn tài liệu $D$.
- $\text{avgdl}$: Độ dài trung bình của toàn bộ các tài liệu trong kho dữ liệu.
- $k_1, b$: Các siêu tham số điều chỉnh độ bão hòa tần số từ và chuẩn hóa độ dài ($k_1 = 1.5, b = 0.75$).
- $\text{IDF}(q_i)$: Trọng số nghịch đảo tần số tài liệu:
  $$\text{IDF}(q_i) = \ln\left( \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1 \right)$$
  (với $N$ là tổng số tài liệu, $n(q_i)$ là số tài liệu chứa từ $q_i$).

### 1.2. Định lý Khuyết Từ Vựng (Vocabulary Mismatch Theorem)
> **Định lý 1 (Triệt tiêu điểm số do khuyết từ):**
> Giả sử một khái niệm học vụ $C$ được người dùng hỏi qua tập từ vựng $V_Q \subset Q$ (ví dụ: $V_Q = \{\text{"trượt"}, \text{"môn"}\}$), nhưng văn bản quy chế chính thức $D^*$ biểu diễn cùng khái niệm $C$ bằng tập từ vựng hành chính $V_D \subset D^*$ (ví dụ: $V_D = \{\text{"học phần"}, \text{"không đạt"}, \text{"điểm F"}\}$).
>
> Nếu $V_Q \cap V_D = \emptyset$, thì:
> $$\forall q_i \in V_Q, \quad f(q_i, D^*) = 0$$
> Dẫn đến:
> $$\text{Score}_{\text{BM25}}(D^*, Q) = 0$$

* **Hệ quả đối với Ranking:**
  Khi $\text{Score}_{\text{BM25}}(D^*, Q) = 0$, tài liệu đúng $D^*$ bị xếp ở đáy danh sách ứng viên:
  $$\text{Rank}(D^*) \to \infty \implies \frac{1}{\text{Rank}(D^*)} = 0 \implies \text{MRR@10} = 0, \quad \text{Recall@4} = 0$$
* **Kết luận:** BM25 hoàn toàn bất lực trước ngôn ngữ tự nhiên, từ lóng, từ đồng nghĩa và từ viết tắt của sinh viên.

---

## 2. KHÔNG GIAN VECTOR NGỮ NGHĨA (DENSE EMBEDDING VỚI BGE-M3)

### 2.1. Ánh xạ sang không gian tiềm ẩn (Latent Semantic Space)
Thay vì khớp chuỗi ký tự rời rạc, mô hình Deep Learning **BAAI/bge-m3** đóng vai trò là một hàm ánh xạ phi tuyến tính nhiều tầng:

$$E: \mathcal{X} \to \mathbb{R}^d, \quad d = 1024$$

Biến đổi mỗi văn bản $x$ thành một vector đặc trưng ngữ nghĩa $\mathbf{e}_x \in \mathbb{R}^{1024}$ đã được chuẩn hóa L2 ($\|\mathbf{e}_x\|_2 = 1$).

### 2.2. Khoảng cách ngữ nghĩa Cosine (Cosine Similarity)
Mức độ tương đồng ngữ nghĩa giữa câu hỏi $Q$ và tài liệu $D$ được tính bằng tích vô hướng:

$$\text{sim}_{\text{dense}}(Q, D) = \frac{\mathbf{e}_Q \cdot \mathbf{e}_D}{\|\mathbf{e}_Q\|_2 \|\mathbf{e}_D\|_2} = \cos(\theta_{\mathbf{e}_Q, \mathbf{e}_D}) = \sum_{k=1}^{1024} e_{Q, k} \cdot e_{D, k}$$

### 2.3. Cơ chế huấn luyện Contrastive Learning giải quyết bài toán đồng nghĩa
Mô hình BGE-M3 được tối ưu bằng hàm mất mát tương phản (InfoNCE Loss):

$$\mathcal{L}_{\text{contrastive}} = - \log \frac{\exp\left(\frac{\text{sim}(\mathbf{e}_Q, \mathbf{e}_{D^+})}{\tau}\right)}{\exp\left(\frac{\text{sim}(\mathbf{e}_Q, \mathbf{e}_{D^+})}{\tau}\right) + \sum_{j=1}^{K} \exp\left(\frac{\text{sim}(\mathbf{e}_Q, \mathbf{e}_{D^-_j})}{\tau}\right)}$$

Trong đó $D^+$ là tài liệu chứa câu trả lời đúng, $D^-_j$ là các tài liệu nhiễu (negative samples), và $\tau$ là tham số nhiệt độ.

* **Chứng minh toán học:**
  Quá trình huấn luyện ép góc hình học giữa vector câu hỏi và vector tài liệu cùng ngữ nghĩa co nhỏ lại:
  $$\theta_{\mathbf{e}_Q, \mathbf{e}_{D^+}} \to 0 \implies \cos(\theta) \to 1 \implies \text{sim}_{\text{dense}}(Q, D^*) \approx 1$$
  ngay cả khi giữa $Q$ và $D^*$ **không có bất kỳ một ký tự nào trùng nhau** ($V_Q \cap V_D = \emptyset$).

---

## 3. TOÁN HỌC CỦA TLU QUERY ENHANCER (TRIỆT TIÊU ĐỘ LỆCH VECTOR)

Khi sinh viên dùng từ viết tắt (ví dụ: `đrl`, `cpa`, `kktx`), khoảng cách Hamming và khoảng cách vector giữa từ viết tắt và văn bản quy chế rất lớn:

$$\|\mathbf{e}_{\text{"đrl"}} - \mathbf{e}_{\text{"điểm rèn luyện"}}\|_2 \gg 0$$

Module `query_enhancer.py` thực hiện một ánh xạ mở rộng tập từ:

$$Q \xrightarrow{\text{Enhance}} Q' = Q \oplus \mathcal{M}(Q)$$

Ví dụ:
$$\text{"đrl bao nhiêu được học bổng"} \to \text{"đrl (điểm rèn luyện) bao nhiêu được học bổng"}$$

* **Ý nghĩa toán học:**
  Ánh xạ này tạo ra một vector mới $\mathbf{e}_{Q'}$ là tổ hợp lồi (convex combination) trong không gian ngữ nghĩa:
  $$\mathbf{e}_{Q'} \approx \alpha \mathbf{e}_{Q} + (1 - \alpha) \mathbf{e}_{\mathcal{M}(Q)}, \quad 0 < \alpha < 1$$
  Kéo hướng của vector câu hỏi dịch chuyển trực tiếp về trung tâm cụm phân bố dữ liệu của văn bản quy chế:
  $$\text{sim}(\mathbf{e}_{Q'}, \mathbf{e}_{D^*}) > \text{sim}(\mathbf{e}_Q, \mathbf{e}_{D^*})$$
  Điều này lý giải vì sao độ chính xác nhận diện từ viết tắt trong Bảng 4.2 tăng từ **57.7% lên 97.0%**.

---

## 4. HỢP NHẤT THỨ HẠNG RRF (RECIPROCAL RANK FUSION)

Để tận dụng đồng thời ưu điểm của Dense Retrieval (bắt ngữ nghĩa) và Sparse Retrieval (bắt từ khóa chính xác như mã số quyết định `QĐ 1226`, mã học phần `INT101`), hệ thống áp dụng thuật toán RRF.

### 4.1. Công thức RRF tổng quát
Với một tài liệu $d \in \mathcal{D}$ xuất hiện trong danh sách xếp hạng của phương pháp Dense ($r_{\text{dense}}(d)$) và Sparse ($r_{\text{sparse}}(d)$):

$$\text{Score}_{\text{RRF}}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k + r_m(d)}$$

Hằng số làm mượt chuẩn hóa chọn $k = 60$.

### 4.2. Chứng minh tính ổn định (Robustness) của RRF
1. **Trường hợp 1 (Tài liệu chỉ khớp từ khóa cứng):**
   Mã quyết định hoặc mã môn học hiếm gặp. Sparse Search xếp top 1 ($r_{\text{sparse}} = 1$), Dense Search xếp thứ 100 ($r_{\text{dense}} = 100$):
   $$\text{Score}_{\text{RRF}}(d) = \frac{1}{60 + 1} + \frac{1}{60 + 100} = \frac{1}{61} + \frac{1}{160} \approx 0.01639 + 0.00625 = \mathbf{0.02264}$$
2. **Trường hợp 2 (Tài liệu chỉ khớp ngữ nghĩa tự nhiên):**
   Câu hỏi dùng từ đồng nghĩa. Dense Search xếp top 1 ($r_{\text{dense}} = 1$), Sparse Search không tìm thấy ($r_{\text{sparse}} \to \infty$):
   $$\text{Score}_{\text{RRF}}(d) = \frac{1}{60 + 1} + 0 \approx \mathbf{0.01639}$$
3. **Trường hợp 3 (Tài liệu thỏa mãn cả ngữ nghĩa lẫn từ khóa):**
   Cả Dense và Sparse đều xếp top 1 ($r_{\text{dense}} = 1, r_{\text{sparse}} = 1$):
   $$\text{Score}_{\text{RRF}}(d) = \frac{1}{61} + \frac{1}{61} = \frac{2}{61} \approx \mathbf{0.03279}$$

* **Định lý phân tách điểm số:**
  $$\text{Score}_{\text{Case 3}} > \text{Score}_{\text{Case 1}} > \text{Score}_{\text{Case 2}} \gg \text{Score}_{\text{Nhiễu}}$$
  RRF triệt tiêu sự mất cân bằng về thang đo phân phối điểm (score distribution scale) giữa Cosine Similarity và BM25 Log-odds, tạo ra danh sách ứng viên có chất lượng vượt trội.

---

## 5. MÔ HÌNH CROSS-ENCODER RERANKER (TƯƠNG TÁC TOKEN ĐA TẦNG)

Trong giai đoạn đầu (Bi-Encoder), câu hỏi $Q$ và tài liệu $D$ được mã hóa hoàn toàn độc lập: $\mathbf{e}_Q = E(Q)$ và $\mathbf{e}_D = E(D)$. Chúng chỉ tương tác ở lớp cuối cùng qua phép nhân vô hướng.

Ở giai đoạn hai, **BAAI/bge-reranker-base** áp dụng kiến trúc Cross-Encoder:
$$\mathbf{H} = \text{Transformer}(\text{[CLS]} \circ Q \circ \text{[SEP]} \circ D)$$

### 5.1. Cơ chế Self-Attention đa tầng (Full Cross-Attention)
Mỗi token thứ $i$ trong câu hỏi được tính trọng số chú ý với mọi token thứ $j$ trong tài liệu ở tất cả 12 tầng Transformer:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{\mathbf{Q} \mathbf{K}^T}{\sqrt{d_k}}\right) \mathbf{V}$$

Điểm liên quan cuối cùng được tính từ token phân lớp $\mathbf{h}_{[\text{CLS}]}$ qua hàm Sigmoid:

$$s(Q, D) = \sigma(\mathbf{W} \mathbf{h}_{[\text{CLS}]} + b) = \frac{1}{1 + e^{-(\mathbf{W} \mathbf{h}_{[\text{CLS}]} + b)}} \in [0.0, 1.0]$$

Nhờ cơ chế này, mô hình phát hiện được các mối quan hệ ngữ pháp tinh tế như quan hệ phủ định (*"không được xét"* vs *"được xét"*), điều kiện kèm theo (*"trừ trường hợp..."*), mà các mô hình Bi-Encoder hay BM25 thường bỏ sót.

---

## 6. TOÁN HỌC CỦA CÁC CHỈ SỐ ĐÁNH GIÁ (METRICS DERIVATION)

### 6.1. Recall@K (Khả năng bao phủ tài liệu đúng)
$$\text{Recall@K} = \frac{|R_K(Q) \cap G(Q)|}{|G(Q)|}$$
- $G(Q)$: Tập hợp các tài liệu/chunk thực sự chứa đáp án (Ground Truth).
- $R_K(Q)$: Tập hợp $K$ tài liệu được hệ thống truy xuất về đầu tiên ($K = 4$).

### 6.2. Phân biệt Precision@K và HitRate@K trong RAG
> **Nghịch lý toán học của Precision@K cố định:**
> Trong bài toán RAG học vụ, đại đa số câu hỏi của sinh viên chỉ có đúng **1 tài liệu/chunk duy nhất** chứa câu trả lời ($|G(Q)| = 1$).
> Khi hệ thống cố định trả về $K = 4$ chunks:
> $$\text{Precision@4} = \frac{|R_4(Q) \cap G(Q)|}{4} \le \frac{|G(Q)|}{4} = \frac{1}{4} = 25\%$$
> Kể cả khi hệ thống tìm kiếm hoàn hảo 100%, $\text{Precision@4}$ cũng không thể vượt quá **25%**!
> 
> Trong khi đó, **HitRate@K (Success Rate@K)** đo lường:
> $$\text{HitRate@K} = \begin{cases} 1 & \text{nếu } |R_K(Q) \cap G(Q)| \ge 1 \\ 0 & \text{ngược lại} \end{cases}$$
> Điểm trung bình $\mathbb{E}[\text{HitRate@4}] = 91.8\%$ cho thấy trong 91.8% câu hỏi, tài liệu đúng chắc chắn có mặt trong Top 4 chunks gửi vào LLM.

### 6.3. MRR@10 (Mean Reciprocal Rank)
$$\text{MRR@10} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \text{RR}_i, \quad \text{RR}_i = \begin{cases} \frac{1}{\text{rank}_i} & \text{nếu } 1 \le \text{rank}_i \le 10 \\ 0 & \text{nếu } \text{rank}_i > 10 \end{cases}$$
$\text{MRR} = 0.934$ nghĩa là thứ hạng trung bình của tài liệu đúng đầu tiên là:
$$\overline{\text{Rank}} \approx \frac{1}{0.934} \approx 1.07$$
Tức là tài liệu đúng hầu như **luôn nằm ở vị trí số 1 (Top 1)** trước khi prompt được gửi vào mô hình Gemini.

### 6.4. Kỳ vọng độ trễ có bộ nhớ đệm (Weighted Cache Latency)
Gọi $p_{\text{hit}}$ là xác suất trúng cache ($43.6\%$), $L_{\text{hit}}$ là độ trễ cache ($3.0\text{ ms}$), $L_{\text{miss}}$ là độ trễ Full Pipeline ($843.8\text{ ms}$):

$$\mathbb{E}[L] = p_{\text{hit}} \cdot L_{\text{hit}} + (1 - p_{\text{hit}}) \cdot L_{\text{miss}}$$
$$\mathbb{E}[L] = (0.436 \times 3.0) + (0.564 \times 843.8) = 1.31 + 475.90 = \mathbf{477.2\text{ ms}}$$

---

## 7. BẢNG TỔNG KẾT SO SÁNH LÝ THUYẾT

| Tiêu chí | Pure BM25 | Pure Dense (Embedding) | StudyBot Pipeline |
| :--- | :--- | :--- | :--- |
| **Bản chất toán học** | Khớp từ vựng (Exact Lexical Overlap) | Tích vô hướng vector (Cosine Angle) | Đa tầng: Enhancer $\to$ Hybrid RRF $\to$ Cross-Attention |
| **Xử lý từ viết tắt/từ lóng** | Bất lực (Score = 0) | Trung bình (dễ lệch hướng vector) | **Xuất sắc** (Chuẩn hóa Convex Combination) |
| **Độ chính xác xếp hạng (MRR)** | Thấp ($0.54$) | Khá ($0.69$) | **Rất cao** ($0.93 - 0.96$) |
| **Khả năng triệt tiêu Hallucination** | Thấp | Khá | **Tối ưu** (Faithfulness đạt $0.98$) |
