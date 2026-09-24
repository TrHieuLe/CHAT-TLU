FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho OCR, PDF & build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    poppler-utils \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt pip mới nhất và PyTorch CPU trước (chỉ ~180MB thay vì kéo bản CUDA 2.6GB gây tràn RAM)
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

# Cài đặt các Python dependencies còn lại
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy toàn bộ mã nguồn backend
COPY . .

# Expose port FastAPI
EXPOSE 8000

# Khởi chạy uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
