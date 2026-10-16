"""Các hàm thuần của đánh giá câu trả lời (app/eval/answer_metrics.py) — không gọi API."""
import json

from app.eval.answer_metrics import (
    aggregate,
    agreement,
    bootstrap_ci,
    build_judge_prompt,
    cohen_kappa,
    combine_refused,
    extract_dieu,
    has_citation,
    is_refusal_text,
    item_scores,
    parse_judgment,
    wrong_dieu,
)


class TestCitation:
    def test_extract_dieu_case_insensitive(self):
        assert extract_dieu("Theo Điều 5 và điều 12, khoản 3") == {"5", "12"}

    def test_has_citation_khoan_only(self):
        assert has_citation("căn cứ Khoản 2")
        assert not has_citation("không có trích dẫn")

    def test_wrong_dieu(self):
        ctx = ["[CONTEXT 1] ... Điều 5. Điều kiện tốt nghiệp ...", "Điều 7 ..."]
        assert wrong_dieu("Theo Điều 5 và Điều 9", ctx) == {"9"}
        assert wrong_dieu("Theo Điều 7", ctx) == set()


class TestRefusal:
    def test_canonical_refusal(self):
        txt = "Tài liệu quy chế hiện tại chưa có thông tin cụ thể về vấn đề này. Bạn vui lòng liên hệ Phòng Đào tạo"
        assert is_refusal_text(txt)

    def test_normal_answer(self):
        assert not is_refusal_text("Học phí là 450.000đ/tín chỉ (Điều 3).")

    def test_judge_overrides_rule(self):
        # Trả lời được phần chính nhưng ghi 'chưa đề cập' phần phụ → judge nói không từ chối
        assert combine_refused(True, False) is False
        assert combine_refused(False, True) is True
        assert combine_refused(True, None) is True


class TestParseJudgment:
    def test_valid_with_fences(self):
        raw = "```json\n" + json.dumps({
            "claims": [{"text": "a", "supported": True}, {"text": "b", "supported": False}],
            "answer_relevance": 4, "context_sufficient": True, "refused": False,
            "key_facts": [{"fact": "x", "status": "covered"}],
        }) + "\n```"
        j = parse_judgment(raw)
        assert len(j["claims"]) == 2
        assert j["answer_relevance"] == 4
        assert j["key_facts"][0]["status"] == "covered"

    def test_invalid_json(self):
        assert parse_judgment("không phải json") is None
        assert parse_judgment("[1, 2]") is None

    def test_missing_and_bad_fields(self):
        j = parse_judgment(json.dumps({
            "claims": [{"text": "a"}, "rác", {"text": "b", "supported": True}],
            "answer_relevance": "9",
            "refused": "yes",
            "key_facts": [{"fact": "x", "status": "maybe"}],
        }))
        assert j["claims"] == [{"text": "b", "supported": True}]
        assert j["answer_relevance"] == 5  # bị kẹp về thang 1–5
        assert j["refused"] is None and j["context_sufficient"] is None
        assert j["key_facts"] == []

    def test_prompt_contains_inputs(self):
        p = build_judge_prompt("Học phí?", ["ctx A"], "450k", ["450.000đ/tín chỉ"])
        assert "Học phí?" in p and "ctx A" in p and "450.000đ/tín chỉ" in p


def _judgment(supported=(True,), rel=5, ctx=True, refused=False, facts=()):
    return {
        "claims": [{"text": str(i), "supported": s} for i, s in enumerate(supported)],
        "answer_relevance": rel, "context_sufficient": ctx, "refused": refused,
        "key_facts": [{"fact": str(i), "status": s} for i, s in enumerate(facts)],
    }


class TestItemScores:
    def test_basic(self):
        item = {"id": 1, "question": "q", "key_facts": ["a", "b"]}
        ans = {"answer": "Theo Điều 5 và Điều 9 thì ..."}
        s = item_scores(item, ans, _judgment(supported=(True, True, False), rel=3,
                                             facts=("covered", "contradicted")), ["Điều 5 ..."])
        assert abs(s["faithfulness"] - 2 / 3) < 1e-9
        assert s["answer_relevance"] == 0.5
        assert s["correctness"] == 0.5 and s["contradicted"] is True
        assert s["has_citation"] and s["wrong_dieu"] == ["9"]

    def test_no_judgment(self):
        s = item_scores({"id": 1}, {"answer": "Tài liệu quy chế hiện tại chưa có thông tin"}, None, [])
        assert s["refused"] is True
        assert s["faithfulness"] is None and s["answer_relevance"] is None
        assert s["has_citation"] is False


class TestAggregate:
    def _row(self, item, answer, j, ctx=()):
        return {"item": item, "scores": item_scores(item, {"answer": answer}, j, list(ctx))}

    def test_refusal_metrics(self):
        rows = [
            # câu không có trong tài liệu, từ chối đúng
            self._row({"id": 1, "expect_refusal": True}, "chưa có thông tin", _judgment(supported=(), refused=True, ctx=False)),
            # câu không có trong tài liệu, bịa
            self._row({"id": 2, "expect_refusal": True}, "Có, 5 triệu", _judgment(supported=(False,), ctx=False)),
            # câu trả lời được, ngữ cảnh đủ nhưng từ chối → từ chối sai
            self._row({"id": 3}, "chưa có thông tin", _judgment(supported=(), refused=True, rel=1)),
            # câu trả lời được, ngữ cảnh thiếu, từ chối → không tính vào từ chối sai
            self._row({"id": 4}, "chưa có thông tin", _judgment(supported=(), refused=True, rel=1, ctx=False)),
            self._row({"id": 5}, "Theo Điều 2 ...", _judgment(), ["Điều 2"]),
        ]
        agg = aggregate(rows)
        assert agg["refusal_recall"]["mean"] == 0.5 and agg["refusal_recall"]["n"] == 2
        assert agg["false_refusal_rate"]["mean"] == 0.5 and agg["false_refusal_rate"]["n"] == 2
        assert agg["context_relevance"]["mean"] == 2 / 3
        assert agg["citation_rate"]["mean"] == 1.0 and agg["citation_rate"]["n"] == 1
        assert agg["wrong_citation_rate"]["mean"] == 0.0
        # faithfulness tính trên mọi câu có khẳng định, kể cả câu bịa ở bộ không trả lời được
        assert agg["faithfulness"]["mean"] == 0.5 and agg["faithfulness"]["n"] == 2

    def test_empty_metric(self):
        agg = aggregate([])
        assert agg["faithfulness"] == {"mean": None, "ci": None, "n": 0}


class TestStats:
    def test_bootstrap_constant(self):
        assert bootstrap_ci([1.0] * 20) == (1.0, 1.0)

    def test_bootstrap_contains_mean(self):
        vals = [0.0] * 30 + [1.0] * 70
        lo, hi = bootstrap_ci(vals)
        assert lo < 0.7 < hi and 0.55 < lo and hi < 0.85

    def test_kappa(self):
        a = [True, True, False, False]
        assert cohen_kappa(a, a) == 1.0
        assert cohen_kappa(a, [not x for x in a]) == -1.0
        assert cohen_kappa([True] * 3, [True] * 3) == 1.0
        assert cohen_kappa([], []) is None
        assert agreement(a, [True, False, False, False]) == 0.75
