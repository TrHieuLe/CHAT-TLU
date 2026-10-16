"""
answer_metrics.py — Hàm thuần cho đánh giá chất lượng câu trả lời (không gọi API).

Dùng bởi scripts/eval_answers.py; tách riêng để unit test được.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any, Iterable

# ─── Trích dẫn Điều/Khoản ────────────────────────────────────────────────────

_DIEU_RE = re.compile(r"\bđiều\s+(\d+)", re.IGNORECASE)
_KHOAN_RE = re.compile(r"\bkhoản\s+(\d+)", re.IGNORECASE)


def extract_dieu(text: str) -> set[str]:
    """Các số Điều được nhắc trong văn bản (vd 'Điều 5', 'điều 12')."""
    return set(_DIEU_RE.findall(text or ""))


def has_citation(text: str) -> bool:
    return bool(_DIEU_RE.search(text or "") or _KHOAN_RE.search(text or ""))


def wrong_dieu(answer: str, contexts: Iterable[str]) -> set[str]:
    """Số Điều có trong câu trả lời nhưng không xuất hiện trong bất kỳ ngữ cảnh nào."""
    ctx_dieu: set[str] = set()
    for c in contexts:
        ctx_dieu |= extract_dieu(c)
    return extract_dieu(answer) - ctx_dieu


# ─── Phát hiện câu từ chối ───────────────────────────────────────────────────

_REFUSAL_PATTERNS = [
    "chưa có thông tin",
    "không có thông tin",
    "chưa đề cập",
    "không đề cập",
    "không tìm thấy thông tin",
    "chưa tìm thấy thông tin",
]


def is_refusal_text(answer: str) -> bool:
    """Câu trả lời có chứa câu từ chối kiểu 'tài liệu chưa có thông tin' (theo SYSTEM_INSTRUCTION).

    Chỉ là tín hiệu theo luật; câu trả lời vừa trả lời một phần vừa nói 'chưa đề cập' phần khác cũng
    khớp, nên kết luận cuối cùng kết hợp với nhãn 'refused' của judge (xem combine_refused).
    """
    t = (answer or "").lower()
    return any(p in t for p in _REFUSAL_PATTERNS)


def combine_refused(rule: bool, judge: bool | None) -> bool:
    """Judge quyết định khi có nhãn (nó phân biệt từ chối toàn bộ vs từ chối một phần); không có thì dùng luật."""
    return bool(judge) if judge is not None else rule


# ─── Prompt và parse kết quả judge ───────────────────────────────────────────

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "supported": {"type": "boolean"},
                },
                "required": ["text", "supported"],
            },
        },
        "answer_relevance": {"type": "integer"},
        "context_sufficient": {"type": "boolean"},
        "refused": {"type": "boolean"},
        "key_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string"},
                    "status": {"type": "string", "enum": ["covered", "missing", "contradicted"]},
                },
                "required": ["fact", "status"],
            },
        },
    },
    "required": ["claims", "answer_relevance", "context_sufficient", "refused", "key_facts"],
}


def build_judge_prompt(question: str, contexts: list[str], answer: str, key_facts: list[str] | None) -> str:
    ctx = "\n\n---\n\n".join(contexts) if contexts else "(không có ngữ cảnh)"
    facts = "\n".join(f"- {f}" for f in key_facts) if key_facts else "(không có)"
    return f"""Bạn là giám khảo chấm chất lượng câu trả lời của chatbot học vụ Trường Đại học Thủy Lợi.
Chấm nghiêm khắc, chỉ dựa vào NGỮ CẢNH bên dưới, không dùng hiểu biết riêng.

# CÂU HỎI
{question}

# NGỮ CẢNH (trích từ tài liệu quy chế của trường)
{ctx}

# CÂU TRẢ LỜI CẦN CHẤM
{answer}

# Ý BẮT BUỘC (đáp án chuẩn)
{facts}

# YÊU CẦU
1. claims: tách CÂU TRẢ LỜI thành các khẳng định thông tin (con số, điều kiện, quy định, thủ tục, số Điều/Khoản).
   Bỏ qua câu chào hỏi, câu khuyên liên hệ phòng ban, câu định dạng. Mỗi khẳng định: supported=true chỉ khi
   NGỮ CẢNH nêu rõ hoặc suy ra trực tiếp được; ngược lại supported=false. Câu từ chối thì claims=[].
2. answer_relevance: 1-5, câu trả lời giải quyết đúng trọng tâm câu hỏi đến mức nào
   (5 = trả lời đầy đủ đúng điều được hỏi; 1 = lạc đề hoặc không trả lời). Câu từ chối chấm 1.
3. context_sufficient: NGỮ CẢNH có chứa đủ thông tin để trả lời câu hỏi không (đánh giá NGỮ CẢNH, không phải câu trả lời).
4. refused: true nếu câu trả lời về cơ bản từ chối / nói tài liệu không có thông tin thay vì trả lời câu hỏi.
   Trả lời được phần chính và chỉ ghi chú thiếu một phần nhỏ thì refused=false.
5. key_facts: với MỖI Ý BẮT BUỘC (nếu có), status = covered (câu trả lời nêu đúng), missing (không nêu),
   contradicted (nêu sai / mâu thuẫn). Không có ý bắt buộc thì key_facts=[].
Chỉ trả về JSON đúng schema."""


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    return m.group(1) if m else t


def parse_judgment(text: str) -> dict | None:
    """Parse và chuẩn hóa JSON của judge; trả None nếu không dùng được."""
    try:
        data = json.loads(_strip_fences(text))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    claims = []
    for c in data.get("claims") or []:
        if isinstance(c, dict) and isinstance(c.get("supported"), bool):
            claims.append({"text": str(c.get("text", "")), "supported": c["supported"]})

    rel = data.get("answer_relevance")
    try:
        rel = min(5, max(1, int(rel)))
    except (TypeError, ValueError):
        rel = None

    facts = []
    for f in data.get("key_facts") or []:
        if isinstance(f, dict) and f.get("status") in ("covered", "missing", "contradicted"):
            facts.append({"fact": str(f.get("fact", "")), "status": f["status"]})

    def _bool(key):
        v = data.get(key)
        return v if isinstance(v, bool) else None

    return {
        "claims": claims,
        "answer_relevance": rel,
        "context_sufficient": _bool("context_sufficient"),
        "refused": _bool("refused"),
        "key_facts": facts,
    }


# ─── Chỉ số trên từng câu ────────────────────────────────────────────────────

def item_scores(item: dict, answer: dict, judgment: dict | None, reference_contexts: list[str]) -> dict:
    """Điểm của một câu hỏi × một cấu hình.

    item: một dòng bộ test (question, expect_refusal, key_facts...).
    answer: {"answer": str, "ctx_parts": [...]} của cấu hình này.
    reference_contexts: ngữ cảnh dùng để kiểm tra trích dẫn (ngữ cảnh StudyBot truy xuất được;
    với cấu hình không RAG đây là bằng chứng tham chiếu).
    """
    text = answer.get("answer", "")
    j = judgment or {}
    refused = combine_refused(is_refusal_text(text), j.get("refused"))

    claims = j.get("claims") or []
    faith = (sum(c["supported"] for c in claims) / len(claims)) if claims else None

    rel = j.get("answer_relevance")
    rel_norm = (rel - 1) / 4 if isinstance(rel, int) else None

    facts = j.get("key_facts") or []
    if item.get("key_facts") and facts:
        correctness = sum(f["status"] == "covered" for f in facts) / len(facts)
        contradicted = any(f["status"] == "contradicted" for f in facts)
    else:
        correctness, contradicted = None, None

    cites = has_citation(text) and not refused
    wrong = sorted(wrong_dieu(text, reference_contexts)) if extract_dieu(text) else []

    return {
        "refused": refused,
        "faithfulness": faith,
        "answer_relevance": rel_norm,
        "context_sufficient": j.get("context_sufficient"),
        "correctness": correctness,
        "contradicted": contradicted,
        "has_citation": cites,
        "cites_dieu": bool(extract_dieu(text)),
        "wrong_dieu": wrong,
    }


# ─── Tổng hợp + khoảng tin cậy ───────────────────────────────────────────────

def bootstrap_ci(values: list[float], *, n_boot: int = 2000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    """Khoảng tin cậy percentile bootstrap cho trung bình."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int(n_boot * alpha / 2)]
    hi = means[min(n_boot - 1, int(n_boot * (1 - alpha / 2)))]
    return (lo, hi)


def _metric(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "ci": None, "n": 0}
    lo, hi = bootstrap_ci(values)
    return {"mean": sum(values) / len(values), "ci": [lo, hi], "n": len(values)}


def aggregate(rows: list[dict]) -> dict:
    """rows: [{"item": {...}, "scores": item_scores(...)}] của MỘT cấu hình."""
    answerable = [r for r in rows if not r["item"].get("expect_refusal")]
    unanswerable = [r for r in rows if r["item"].get("expect_refusal")]
    s = lambda r: r["scores"]  # noqa: E731

    # Từ chối sai: chỉ tính khi ngữ cảnh thật sự đủ để trả lời (ngữ cảnh thiếu thì từ chối là đúng)
    ctx_ok = [r for r in answerable if s(r)["context_sufficient"] is True]
    answered = [r for r in answerable if not s(r)["refused"]]
    dieu = [r for r in answered if s(r)["cites_dieu"]]

    return {
        "faithfulness": _metric([s(r)["faithfulness"] for r in rows if s(r)["faithfulness"] is not None]),
        "answer_relevance": _metric([s(r)["answer_relevance"] for r in answerable if s(r)["answer_relevance"] is not None]),
        "context_relevance": _metric([float(s(r)["context_sufficient"]) for r in answerable
                                      if s(r)["context_sufficient"] is not None]),
        "correctness": _metric([s(r)["correctness"] for r in answerable if s(r)["correctness"] is not None]),
        "contradiction_rate": _metric([float(s(r)["contradicted"]) for r in answerable if s(r)["contradicted"] is not None]),
        "refusal_recall": _metric([float(s(r)["refused"]) for r in unanswerable]),
        "false_refusal_rate": _metric([float(s(r)["refused"]) for r in ctx_ok]),
        "citation_rate": _metric([float(s(r)["has_citation"]) for r in answered]),
        "wrong_citation_rate": _metric([float(bool(s(r)["wrong_dieu"])) for r in dieu]),
    }


# ─── Đồng thuận judge vs người chấm ──────────────────────────────────────────

def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa cho hai dãy nhãn nhị phân cùng độ dài."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def agreement(a: list[bool], b: list[bool]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    return sum(x == y for x, y in zip(a, b)) / len(a)
