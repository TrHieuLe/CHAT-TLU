"""
test_phase4_intelligence.py — Bộ kiểm thử tự động cho Giai đoạn 4:
1. Bộ giải mã từ viết tắt TLU & Mở rộng truy vấn (Query Enhancer).
2. Bộ nhớ đệm ngữ nghĩa tốc độ cao (Semantic Cache).
3. API quản lý thống kê Semantic Cache.
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.rag.query_enhancer import enhance_query, normalize_abbreviations_only
from app.rag.semantic_cache import SemanticCache, get_semantic_cache
from main import app


def test_query_enhancer_abbreviations():
    """Kiểm tra việc giải mã và mở rộng các từ viết tắt TLU."""
    # Test ĐRL
    q1 = "Làm sao để tăng đrl kỳ này?"
    enh1 = enhance_query(q1)
    assert "đrl (điểm rèn luyện)" in enh1.lower()

    # Test CPA và Học bổng
    q2 = "cpa bao nhiêu thì được xét học bổng?"
    enh2 = enhance_query(q2)
    assert "cpa (điểm trung bình tích lũy cpa)" in enh2.lower()

    # Test KTX và KLTN
    q3 = "Thủ tục đăng ký ktx và nộp kltn như thế nào?"
    enh3 = enhance_query(q3)
    assert "ktx (ký túc xá)" in enh3.lower()
    assert "kltn (khóa luận tốt nghiệp)" in enh3.lower()

    # Câu không chứa từ viết tắt phải được giữ nguyên
    q_normal = "Học phí một tín chỉ khoa công nghệ thông tin là bao nhiêu?"
    assert enhance_query(q_normal) == q_normal


def test_normalize_abbreviations_only():
    """Kiểm tra thay thế trực tiếp từ viết tắt."""
    q = "đrl và hp kỳ này"
    norm = normalize_abbreviations_only(q)
    assert "điểm rèn luyện" in norm
    assert "học phần" in norm


def test_semantic_cache_exact_hit():
    """Kiểm tra exact match trong Semantic Cache (< 1ms)."""
    cache = SemanticCache(max_size=50)

    q = "Điều kiện nhận học bổng khuyến khích học tập TLU?"
    ans = "Sinh viên cần đạt CPA từ 2.5 trở lên và ĐRL từ 70 trở lên."
    sources = ["Quy_che_hoc_bong_2023.pdf"]

    # Lưu vào cache
    cache.put(q, ans, source_names=sources)

    # Truy vấn chính xác (bỏ hoa thường, chuẩn hóa)
    res = cache.get("điều kiện nhận học bổng khuyến khích học tập tlu?")
    assert res is not None
    cached_ans, cached_sources, match_type = res
    assert cached_ans == ans
    assert cached_sources == sources
    assert match_type == "exact"

    # Kiểm tra stats
    stats = cache.get_stats()
    assert stats["cached_entries"] == 1
    assert stats["cache_hits"] == 1
    assert stats["total_lookups"] == 1
    assert stats["hit_rate_pct"] == 100.0


def test_semantic_cache_vector_hit():
    """Kiểm tra semantic match qua cosine similarity."""
    cache = SemanticCache(max_size=50, similarity_threshold=0.92)

    # Tạo base vector giả lập
    vec1 = np.random.randn(128).astype(np.float32)
    vec1 = vec1 / np.linalg.norm(vec1)

    q1 = "Thời gian nộp học phí học kỳ 2"
    ans1 = "Hạn nộp học phí là ngày 28/02 hàng năm."
    cache.put(q1, ans1, ["Thong_bao_hoc_phi.pdf"], query_vector=vec1)

    # Vector tương tự (cosine similarity ~ 0.98)
    noise = np.random.randn(128).astype(np.float32) * 0.005
    vec2 = vec1 + noise
    vec2 = vec2 / np.linalg.norm(vec2)

    # Truy vấn với vector gần gũi nhưng câu chữ hơi khác
    res = cache.get("Hạn chót đóng học phí kỳ 2 là ngày nào?", query_vector=vec2)
    assert res is not None
    c_ans, c_sources, match_type = res
    assert c_ans == ans1
    assert match_type == "semantic"

    # Vector trực giao (hoàn toàn không liên quan, cosine similarity ~ 0)
    vec_unrelated = np.random.randn(128).astype(np.float32)
    vec_unrelated = vec_unrelated / np.linalg.norm(vec_unrelated)
    res_miss = cache.get("Đăng ký thi lại môn toán?", query_vector=vec_unrelated)
    assert res_miss is None


def test_cache_api_endpoints():
    """Kiểm tra các endpoints theo dõi cache qua HTTP API."""
    client = TestClient(app)

    # 1. Lấy thống kê cache
    resp = client.get("/api/chat/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "stats" in data
    assert "cached_entries" in data["stats"]
    assert "cache_hits" in data["stats"]

    # 2. Xóa cache
    resp_clear = client.delete("/api/chat/cache/clear")
    assert resp_clear.status_code == 200
    assert resp_clear.json()["ok"] is True
