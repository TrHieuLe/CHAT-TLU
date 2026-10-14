from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "nckh_docs"
    COLLECTION_NAME: str = "nckh_docs"
    UNSPLASH_ACCESS_KEY: str | None = None
    EMBEDDING_VECTOR_SIZE: int = 1024
    # Tên model trên HuggingFace hub (dùng cache ~/.cache/huggingface) hoặc đường dẫn thư mục model
    EMBEDDING_MODEL: str = "BAAI/bge-m3"

    CHUNK_SIZE: int = 800
    OVERLAP: int = 100

    CUDA_VISIBLE_DEVICES: str = ""
    DEVICE: str = "cpu"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def EFFECTIVE_GEMINI_API_KEY(self) -> str:
        key = self.GOOGLE_API_KEY or self.GEMINI_API_KEY
        if not key:
            raise ValueError("Cần GOOGLE_API_KEY hoặc GEMINI_API_KEY")
        return key

    @field_validator("GEMINI_MODEL")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return v.strip()
    TEMPERATURE: float = 0.7
    MAX_OUTPUT_TOKENS: int = 4096

    # Reranking & Retrieval Optimization
    # Tắt mặc định: trên bộ test TLU, hybrid RRF không rerank cho HitRate/MRR bằng hoặc cao hơn
    # (246 câu: 68.2%/0.606 vs 67.8%/0.555) trong khi reranker tốn 7-9s/câu trên CPU.
    # Nếu bật lại, nên dùng RERANKER_QUANTIZE_INT8=true + RERANKER_MAX_LENGTH=256 (~3.6s).
    ENABLE_RERANKER: bool = False
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    RETRIEVE_CANDIDATES_K: int = 8
    TOP_K: int = 4
    MIN_RELEVANCE_SCORE: float = 0.15

    # Latency tuning
    WARMUP_MODELS: bool = True              # nạp sẵn embedder + reranker khi khởi động
    QUERY_MAX_LENGTH: int = 512             # max token khi embed câu hỏi
    GEMINI_THINKING_BUDGET: int | None = None  # None = mặc định model; một số model (vd flash-lite-latest) từ chối budget=0
    LLM_FIRST_TOKEN_TIMEOUT: float = 12.0   # giây chờ chunk đầu trước khi đổi sang model dự phòng
    HISTORY_MAX_MESSAGES: int = 30          # số tin nhắn gần nhất đọc từ DB mỗi lượt
    RERANKER_BATCH_SIZE: int = 1            # batch nhỏ = ít padding; trên CPU nhanh hơn nhiều
    RERANKER_MAX_LENGTH: int = 512
    RERANKER_QUANTIZE_INT8: bool = False    # int8 dynamic quantization trên CPU
    QDRANT_KEEPALIVE_SECONDS: float = 600.0  # giữ kết nối HTTP tới Qdrant (mặc định httpx chỉ 5s)
    # Semantic cache (câu hỏi lượt đầu, không cá nhân hóa)
    SEMANTIC_CACHE_THRESHOLD: float = 0.90   # kèm điều kiện cùng từ nội dung — xem semantic_cache.py
    SEMANTIC_CACHE_MAX_SIZE: int = 1000
    SEMANTIC_CACHE_TTL_SECONDS: float = 7 * 24 * 3600
    SEMANTIC_CACHE_DB: str = "./semantic_cache.db"   # rỗng = chỉ lưu RAM
    TORCH_NUM_THREADS: int | None = None    # None = dùng toàn bộ CPU core (torch mặc định chỉ dùng một nửa)
    # Crawler thông báo web trường (WordPress REST API)
    TLU_CRAWL_BASE_URL: str = "https://tlu.edu.vn"
    TLU_CRAWL_CATEGORY_IDS: list[int] = [2010]   # category "Thông báo"
    TLU_CRAWL_TIMEOUT_SECONDS: float = 20.0


settings = Settings()