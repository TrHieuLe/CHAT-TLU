"""SemanticCache: canonical match, chặn câu khác ý, TTL, lưu SQLite, theo dõi kho tài liệu."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.rag import semantic_cache as sc
from app.rag.semantic_cache import SemanticCache, canonical_key, numbers_compatible

ANSWER = "Câu trả lời mẫu đủ dài để được lưu."


def _vec(seed: int = 0) -> np.ndarray:
    v = np.random.default_rng(seed).standard_normal(64).astype(np.float32)
    return v / np.linalg.norm(v)


class TestCanonical:
    @pytest.mark.parametrize("a,b", [
        ("Điều kiện xét tốt nghiệp là gì?", "Cho em hỏi điều kiện xét tốt nghiệp là gì ạ?"),
        ("Thủ tục đăng ký ký túc xá?", "thủ tục đăng ký ktx"),
        ("Quy định thi lại ra sao?", "quy định thi lại như thế nào ạ?"),
    ])
    def test_filler_variants_hit(self, a, b):
        c = SemanticCache()
        c.put(a, ANSWER)
        res = c.get(b)
        assert res is not None and res[2] == "canonical"

    @pytest.mark.parametrize("a,b", [
        ("Xếp loại học lực giỏi cần CPA bao nhiêu?", "Xếp loại học lực khá cần CPA bao nhiêu?"),
        ("Học lại học phần có mất phí không?", "Thi lại học phần có mất phí không?"),
        ("Đăng ký ktx khi nào?", "Đăng ký ktx ở đâu?"),
        ("Có được thi lại không?", "Có được thi lại"),
    ])
    def test_different_meaning_never_hits_even_with_same_vector(self, a, b):
        c = SemanticCache(similarity_threshold=0.5)
        v = _vec()
        c.put(a, ANSWER, query_vector=v)
        assert c.get(b, query_vector=v) is None

    def test_numbers_must_match(self):
        assert not numbers_compatible("Học phí học kỳ 1", "Học phí học kỳ 2")
        assert not numbers_compatible("CPA dưới 1.0", "CPA dưới 2,0")
        assert numbers_compatible("CPA 2,5", "cpa 2.5")
        c = SemanticCache(similarity_threshold=0.5)
        v = _vec()
        c.put("Học phí học kỳ 1 bao nhiêu?", ANSWER, query_vector=v)
        assert c.get("bao nhiêu học phí học kỳ 2", query_vector=v) is None

    def test_canonical_key_expands_abbreviations(self):
        assert canonical_key("đrl") == canonical_key("điểm rèn luyện")


class TestLifecycle:
    def test_ttl_expiry(self):
        c = SemanticCache(ttl_seconds=10)
        c.put("Điều kiện tốt nghiệp?", ANSWER)
        c._entries[0].created_at = time.time() - 11
        assert c.get("Điều kiện tốt nghiệp?") is None
        assert c.get_stats()["cached_entries"] == 0

    def test_eviction_keeps_size(self):
        c = SemanticCache(max_size=3)
        for i in range(5):
            c.put(f"Câu hỏi số {i} về quy chế", ANSWER, query_vector=_vec(i))
        assert c.get_stats()["cached_entries"] == 3
        assert c._matrix.shape[0] == 3

    def test_persist_and_reload(self, tmp_path):
        db = str(tmp_path / "cache.db")
        c1 = SemanticCache(persist_path=db)
        v = _vec(1)
        c1.put("Học kỳ 2 thời gian nộp học phí", ANSWER, ["HocPhi.txt"], query_vector=v)
        c1.set_meta("kb_points_count", "227")

        c2 = SemanticCache(persist_path=db)
        assert c2.get_stats()["cached_entries"] == 1
        assert c2.get_meta("kb_points_count") == "227"
        res = c2.get("Thời gian nộp học phí học kỳ 2", query_vector=v)
        assert res == (ANSWER, ["HocPhi.txt"], "semantic")

        c2.clear()
        assert SemanticCache(persist_path=db).get_stats()["cached_entries"] == 0


@pytest.mark.asyncio
class TestKbFingerprint:
    async def test_clears_cache_when_points_count_changes(self):
        cache = SemanticCache()
        client = AsyncMock()
        with patch.object(sc, "_semantic_cache_instance", cache):
            client.get_collection.return_value = SimpleNamespace(points_count=227)
            assert await sc.check_kb_fingerprint(client, "c") is False  # lần đầu: chỉ ghi nhận
            cache.put("Điều kiện tốt nghiệp?", ANSWER)

            assert await sc.check_kb_fingerprint(client, "c") is False  # không đổi
            assert cache.get_stats()["cached_entries"] == 1

            client.get_collection.return_value = SimpleNamespace(points_count=240)
            assert await sc.check_kb_fingerprint(client, "c") is True
            assert cache.get_stats()["cached_entries"] == 0


def test_title_persisted_and_old_schema_migrated(tmp_path):
    import sqlite3
    db = str(tmp_path / "old.db")
    # Schema cũ (chưa có cột title)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE semantic_cache (normalized_query TEXT PRIMARY KEY, query TEXT, answer TEXT,"
                " sources TEXT, vector BLOB, created_at REAL, last_accessed REAL, hits INTEGER)")
    con.execute("INSERT INTO semantic_cache VALUES ('cũ', 'cũ', ?, '[]', NULL, ?, ?, 0)", (ANSWER, time.time(), time.time()))
    con.commit()
    con.close()

    c1 = SemanticCache(persist_path=db)
    assert c1.get("cũ") is not None
    c1.put("Điều kiện tốt nghiệp?", ANSWER, title="Điều kiện tốt nghiệp")

    entry, kind = SemanticCache(persist_path=db).get_entry("cho em hỏi điều kiện tốt nghiệp ạ")
    assert kind == "canonical" and entry.title == "Điều kiện tốt nghiệp"
