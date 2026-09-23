# Kế hoạch Triển khai StudyBot / CHAT-TLU lên Google Cloud Platform (GCP)

Tài liệu này hướng dẫn chi tiết từng bước đưa hệ thống **StudyBot (CHAT-TLU)** từ môi trường phát triển cục bộ (Localhost) lên máy chủ đám mây **Google Cloud Platform (GCE)** để phục vụ chạy thử nghiệm thực tế (Living Labs) và demo cho Ban giám khảo chương trình **RE:ACT - Youth Innovation Challenge**.

---

## 1. Kiến trúc Tổng thể trên Cloud

```text
       [ Người dùng / Ban giám khảo ]
                     │
                     │ HTTPS (Cổng 443 / SSL Let's Encrypt)
                     ▼
  +─────────────────────────────────────────────────────────────+
  │             Google Compute Engine (GCE Instance)            │
  │                  Khu vực: Singapore (asia-southeast1)       │
  │                                                             │
  │  +───────────────────────────────────────────────────────+  │
  │  │                 Nginx Reverse Proxy                   │  │
  │  │  - Điều hướng domain -> Frontend (:3000)              │  │
  │  │  - Điều hướng /api/   -> Backend (:8000)               │  │
  │  │  - Tắt buffer cho Server-Sent Events (SSE)            │  │
  │  +──────────────┬────────────────────────┬───────────────+  │
  │                 │                        │                  │
  │                 ▼                        ▼                  │
  │        +─────────────────+      +─────────────────+         │
  │        │ Next.js Frontend│      │ FastAPI Backend │         │
  │        │ (Cổng 3000)     │      │ (Cổng 8000)     │         │
  │        +─────────────────+      +────────┬────────+         │
  │                                          │                  │
  │                  ┌───────────────────────┴───────────────┐  │
  │                  ▼                                       ▼  │
  │         +─────────────────+                    +──────────┴+│
  │         │  Qdrant (VDB)   │                    │ SQLite DB ││
  │         │  (Cổng 6333)    │                    │ (app.db)  ││
  │         +─────────────────+                    +───────────+│
  │                  │                                          │
  │                  ▼ (Docker Volumes)                         │
  │          [qdrant_data / persistent SSD]                     │
  +─────────────────────────────────────────────────────────────+
```

---

## 2. Dự toán Tài nguyên & Chi phí

* **Tài khoản dùng thử**: Đăng ký mới tại [cloud.google.com](https://cloud.google.com/) nhận ngay **300 USD credit (sử dụng trong 90 ngày)**.
* **Cấu hình máy chủ đề xuất**:
  * **Loại máy (Machine Type)**: `e2-standard-2` (2 vCPU, 8 GB RAM).
  * **Ổ đĩa (Boot Disk)**: 30 GB SSD (Ubuntu 22.04 LTS).
  * **Khu vực (Region)**: `asia-southeast1` (Singapore) – độ trễ về Việt Nam < 40ms.
* **Chi phí ước tính**: Khoảng **$48.5/tháng** (được trừ trực tiếp vào gói 300 USD tài trợ, **chi phí thực tế = 0 VNĐ**).
* **Lý do cần 8GB RAM**: Backend chạy trực tiếp model đa ngôn ngữ `BAAI/bge-m3` và `BAAI/bge-reranker-base` qua PyTorch, kết hợp với Qdrant và Next.js. Dung lượng 8GB đảm bảo hệ thống không bao giờ bị tràn RAM (OOM).

---

## 3. Lộ trình Triển khai Chi tiết

### GIAI ĐOẠN 1: Tạo Máy ảo trên Google Cloud Console

1. Truy cập **Google Cloud Console** $\rightarrow$ Chọn hoặc tạo mới 1 Project (ví dụ: `studybot-production`).
2. Vào menu **Compute Engine** $\rightarrow$ **VM instances** $\rightarrow$ Bấm **Create Instance**.
3. Điền các thông số:
   * **Name**: `studybot-server`
   * **Region**: `asia-southeast1` (Singapore) | **Zone**: `asia-southeast1-a` (hoặc b/c).
   * **Series**: `E2` | **Machine type**: `e2-standard-2` (2 vCPU, 8 GB memory).
   * **Boot disk**: Nhấn **Change**:
     * Operating system: **Ubuntu**
     * Version: **Ubuntu 22.04 LTS**
     * Size: **30 GB** (Standard persistent disk hoặc Balanced).
   * **Firewall**: Tích chọn cả 2 mục:
     * [x] **Allow HTTP traffic**
     * [x] **Allow HTTPS traffic**
4. Nhấn **Create** và chờ 30 giây để máy ảo khởi động.

---

### GIAI ĐOẠN 2: Thiết lập IP Tĩnh & Tường Lửa (Static IP & Firewall)

Mặc định IP của máy ảo là IP động (Ephemeral). Cần cố định IP để không bị đổi khi khởi động lại:
1. Vào **VPC network** $\rightarrow$ **IP addresses**.
2. Tìm dòng địa chỉ IP bên ngoài (External IP) của máy `studybot-server`.
3. Bấm vào dấu ba chấm ở cuối dòng $\rightarrow$ Chọn **Promote to static external IP address**. Đặt tên là `studybot-static-ip` $\rightarrow$ Nhấn **Reserve**.

---

### GIAI ĐOẠN 3: Cấu hình Hệ thống qua SSH

Bấm nút **SSH** màu đen trên dòng máy ảo tại giao diện web của GCP để mở cửa sổ terminal:

#### 1. Tạo bộ nhớ đệm chống tràn RAM (4GB Swapfile)
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 2. Cài đặt Docker & Docker Compose
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```
*(Sau lệnh này, gõ `exit` rồi bấm SSH vào lại để kích hoạt quyền chạy Docker không cần sudo).*

#### 3. Tải mã nguồn dự án
```bash
# Clone repository của bạn về máy ảo
git clone https://github.com/TrHieuLe/CHAT-TLU.git chat-tlu
cd chat-tlu
```

#### 4. Thiết lập biến môi trường
Tạo file `.env` ở thư mục gốc:
```bash
nano .env
```
Nội dung file `.env`:
```env
GEMINI_API_KEY=dien_api_key_cua_ban_o_day
GOOGLE_API_KEY=dien_api_key_cua_ban_o_day
GEMINI_MODEL=gemini-2.5-flash
COLLECTION_NAME=nckh_docs
QDRANT_URL=http://qdrant:6333
DATABASE_URL=sqlite+aiosqlite:///./app.db
# Khi dùng chung domain qua Nginx reverse proxy, để trống NEXT_PUBLIC_API_URL để frontend tự gọi relative path (/api/...)
NEXT_PUBLIC_API_URL=
```
*(Bấm `Ctrl + O` $\rightarrow$ `Enter` để lưu, `Ctrl + X` để thoát).*

#### 5. Khởi tạo Database & Chạy Docker Compose
Khởi tạo file database trước để tránh Docker daemon mount nhầm thành thư mục:
```bash
touch Backend/app.db
```

Khởi động toàn bộ dịch vụ:
```bash
docker-compose up -d --build
```
Kiểm tra xem các container đã chạy thành công chưa:
```bash
docker ps
```
*(Kết quả hiển thị đủ 3 container: `studybot_qdrant`, `studybot_backend`, `studybot_frontend` ở trạng thái Up).*

#### 6. Nạp dữ liệu kiến thức (Ingest Data)
```bash
docker exec -it studybot_backend python ingest.py
```

---

### GIAI ĐOẠN 4: Cấu hình Domain, Nginx & Chứng chỉ SSL (HTTPS)

Trình duyệt yêu cầu kết nối **HTTPS** thì tính năng nhận diện giọng nói (Web Speech API) và truy cập camera mới được cấp quyền hoạt động.

#### 1. Tạo tên miền
* **Tùy chọn A (Miễn phí)**: Vào [DuckDNS](https://www.duckdns.org/), đăng nhập và tạo 1 domain (ví dụ: `studybot-tlu.duckdns.org`) trỏ vào Static IP của máy GCP.
* **Tùy chọn B (Tên miền riêng)**: Mua tên miền tại Namecheap, Cloudflare, hoặc Tenten... rồi thêm bản ghi `A` trỏ về Static IP.

#### 2. Cấu hình Nginx làm Reverse Proxy
Tạo file cấu hình Nginx:
```bash
sudo nano /etc/nginx/sites-available/studybot
```
Dán cấu hình sau (thay `yourdomain.com` bằng domain thật của bạn):
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Tăng giới hạn dung lượng upload file tài liệu PDF
    client_max_body_size 50M;

    # 1. Frontend Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 2. Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CẤU HÌNH QUAN TRỌNG: Hỗ trợ Server-Sent Events (SSE Stream)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        chunked_transfer_encoding off;
    }
}
```

Kích hoạt cấu hình và khởi động lại Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/studybot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

#### 3. Kích hoạt chứng chỉ SSL HTTPS miễn phí (Certbot)
```bash
sudo certbot --nginx -d yourdomain.com
```
*Chọn `Yes` hoặc điền email theo hướng dẫn. Certbot sẽ tự động chèn cấu hình SSL và gia hạn mỗi 90 ngày.*

---

## 4. Quy trình Cập nhật & Nâng cấp (Upgrade Workflow)

### Kịch bản 1: Sửa code tính năng mới (Code Updates)
1. Bạn thực hiện chỉnh sửa, kiểm thử tại máy cá nhân.
2. Đẩy code lên GitHub:
   ```bash
   git add .
   git commit -m "Them tinh nang A"
   git push origin main
   ```
3. Trên máy chủ Google Cloud (mở terminal SSH):
   ```bash
   cd ~/chat-tlu
   git pull origin main
   docker-compose up -d --build
   ```
   *Docker sẽ chỉ build lại những phần có code thay đổi. Dữ liệu lịch sử chat (`app.db`) và cơ sở dữ liệu vector (`qdrant_data`) được lưu trên volume độc lập nên không bị ảnh hưởng.*

### Kịch bản 2: Nạp thêm văn bản quy chế / thông báo mới (RAG Updates)
* **Cách 1 (Nhanh nhất)**: Đăng nhập giao diện web, vào mục Quản lý tài liệu và nhấn **Tải lên tài liệu PDF**. Hệ thống tự động bóc tách và nạp vào Qdrant ngay lập tức.
* **Cách 2**: Chép file `.pdf`, `.docx` vào thư mục `Backend/data/` trên server rồi chạy:
  ```bash
  docker exec -it studybot_backend python ingest.py
  ```

### Kịch bản 3: Nâng cấp phần cứng máy chủ (Scale Up)
Khi số lượng sinh viên sử dụng tăng cao trong chiến dịch Living Labs:
1. Vào Google Cloud Console $\rightarrow$ Chọn máy ảo $\rightarrow$ Bấm **Stop**.
2. Nhấn **Edit** $\rightarrow$ Đổi cấu hình từ `e2-standard-2` (8GB RAM) lên `e2-standard-4` (16GB RAM).
3. Bấm **Save** $\rightarrow$ Bấm **Start** lại máy ảo.
*(Mọi dữ liệu, IP và cấu hình đều giữ nguyên 100%, thao tác chỉ mất 2 phút).*

---

## 5. Bảng Lệnh Nhanh Vận hành (Cheat Sheet)

| Tác vụ | Câu lệnh |
| :--- | :--- |
| **Xem trạng thái các container** | `docker ps` |
| **Xem log thời gian thực của Backend** | `docker logs -f studybot_backend` |
| **Xem log thời gian thực của Frontend** | `docker logs -f studybot_frontend` |
| **Khởi động lại toàn bộ hệ thống** | `docker-compose restart` |
| **Tắt toàn bộ hệ thống** | `docker-compose down` |
| **Kiểm tra mức sử dụng RAM / CPU** | `htop` hoặc `docker stats` |
| **Sao lưu cơ sở dữ liệu chat** | `cp Backend/app.db ~/backup_app_$(date +%F).db` |

---
*Kế hoạch này đảm bảo sản phẩm của bạn hoạt động bền bỉ, tốc độ phản hồi cao và bảo mật để sẵn sàng xuất hiện trước Ban giám khảo RE:ACT.*
