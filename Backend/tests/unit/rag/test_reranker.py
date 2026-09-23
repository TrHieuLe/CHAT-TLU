"""
test_reranker.py — Unit tests cho module reranker.py
"""
import pytest
from unittest.mock import MagicMock, patch

from app.rag.reranker import Reranker, _sigmoid


class TestSigmoid:
    def test_zero(self):
        assert abs(_sigmoid(0.0) - 0.5) < 1e-5

    def test_positive(self):
        assert _sigmoid(5.0) > 0.99

    def test_negative(self):
        assert _sigmoid(-5.0) < 0.01

    def test_extremes(self):
        assert _sigmoid(100.0) == 1.0
        assert _sigmoid(-100.0) == 0.0


class TestReranker:
    def test_empty_chunks(self):
        reranker = Reranker()
        assert reranker.rerank("query", []) == []

    def test_disabled_reranker(self):
        reranker = Reranker()
        chunks = ["chunk 1", "chunk 2", "chunk 3"]
        with patch("app.rag.reranker.settings.ENABLE_RERANKER", False):
            results = reranker.rerank("query", chunks, top_k=2)
            assert len(results) == 2
            assert results[0][0] == "chunk 1"
            assert results[0][1] == 1.0

    def test_fallback_lexical_rerank(self):
        """Khi không có model, fallback dựa trên overlap từ khóa."""
        reranker = Reranker()
        reranker._model = None
        reranker._load_failed = True

        query = "học bổng khuyến khích"
        chunks = [
            {"content": "Quy chế thi lại và học lại cho sinh viên"},
            {"content": "Tiêu chuẩn xét học bổng khuyến khích học tập kỳ 1"},
            {"content": "Hướng dẫn đăng ký ký túc xá"},
        ]

        results = reranker.rerank(query, chunks, top_k=2)
        assert len(results) == 2
        # Chunk 2 chứa "học bổng khuyến khích" phải đứng đầu
        best_chunk, score = results[0]
        assert "học bổng" in best_chunk["content"]
        assert score > results[1][1]

    def test_point_payload_extraction(self):
        """Kiểm tra trích xuất text từ đối tượng Point có payload."""
        class MockPoint:
            def __init__(self, content):
                self.payload = {"content": content}

        reranker = Reranker()
        reranker._model = None
        reranker._load_failed = True

        query = "điểm chuẩn ngành CNTT"
        chunks = [
            MockPoint("Thông tin điểm chuẩn ngành CNTT năm 2024 là 25.5"),
            MockPoint("Lịch thi học kỳ 2 năm học 2024"),
        ]

        results = reranker.rerank(query, chunks, top_k=1)
        assert len(results) == 1
        assert "CNTT" in results[0][0].payload["content"]
