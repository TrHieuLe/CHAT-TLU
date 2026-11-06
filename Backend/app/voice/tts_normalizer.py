"""
tts_normalizer.py — Biến câu trả lời Markdown của StudyBot thành văn bản thuần để đọc to.

Học theo bộ chuẩn hoá của dự án AI-SQL (bỏ markdown, đọc %, tiền tệ, đơn vị "/năm"),
mở rộng cho câu trả lời của TLU: bảng Markdown, LaTeX, ngày tháng, từ viết tắt học vụ.
"""
import re

from app.rag.query_enhancer import TLU_ABBREVIATIONS

# Bảng dài hơn số dòng này thì không đọc từng dòng (nghe rất mệt), chỉ nhắc xem trên màn hình
TABLE_READ_MAX_ROWS = 5
TABLE_SKIP_TEXT = "Chi tiết xem bảng trên màn hình."

# Viết tắt hay gặp trong câu trả lời nhưng không có trong từ điển truy vấn
_EXTRA_ABBREVIATIONS: dict[str, str] = {
    r"\bĐH\b": "đại học",
    r"\bSV\b": "sinh viên",
    r"\bGV\b": "giảng viên",
    r"\bTP\.": "thành phố",
    r"\bTP\b": "thành phố",
    r"\bSĐT\b": "số điện thoại",
}

_UNIT_WORDS = {"năm": "một năm", "tháng": "một tháng", "ngày": "một ngày", "lần": "một lần",
               "kỳ": "một kỳ", "học kỳ": "một học kỳ", "tín chỉ": "một tín chỉ", "người": "một người"}

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")


def _speech_abbreviations() -> list[tuple[re.Pattern, str]]:
    """Từ điển viết tắt TLU dùng cho đọc to.

    Bỏ những mục mà nghĩa đầy đủ đã chứa chính từ viết tắt (vd "cpa" → "... CPA"),
    vì thay vào sẽ đọc lặp; những mục đó edge-tts tự đánh vần được.
    """
    out: list[tuple[re.Pattern, str]] = []
    for pattern, meaning in TLU_ABBREVIATIONS.items():
        abbr = re.sub(r"\\b", "", pattern)
        if abbr.lower() in meaning.lower():
            continue
        out.append((re.compile(pattern, re.IGNORECASE), meaning))
    for pattern, meaning in _EXTRA_ABBREVIATIONS.items():
        out.append((re.compile(pattern), meaning))
    return out


_ABBREVIATIONS = _speech_abbreviations()


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", line))


def _table_to_speech(lines: list[str]) -> str:
    rows = [_split_row(l) for l in lines if not _is_separator_row(l)]
    if len(rows) < 2:
        return ". ".join(" ".join(r) for r in rows)
    header, body = rows[0], rows[1:]
    if len(body) > TABLE_READ_MAX_ROWS:
        return TABLE_SKIP_TEXT
    spoken = []
    for row in body:
        parts = []
        for i, cell in enumerate(row):
            if not cell:
                continue
            col = header[i] if i < len(header) else ""
            parts.append(f"{col}: {cell}" if col and i > 0 else cell)
        spoken.append(", ".join(parts))
    return ". ".join(spoken) + "."


def _replace_tables(text: str) -> str:
    out: list[str] = []
    block: list[str] = []

    def flush():
        if block:
            out.append(_table_to_speech(block))
            block.clear()

    for line in text.split("\n"):
        if line.strip().startswith("|") and line.count("|") >= 2:
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def _strip_markdown(t: str) -> str:
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)           # code block
    t = re.sub(r"\$\$.*?\$\$", " (xem trên màn hình) ", t, flags=re.DOTALL)
    t = re.sub(r"\\\[.*?\\\]", " (xem trên màn hình) ", t, flags=re.DOTALL)
    t = re.sub(r"\$([^$\n]{1,80})\$", r"\1", t)                 # LaTeX inline ngắn: giữ nội dung
    t = re.sub(r"\\(?:frac|times|cdot|leq|geq|text|mathrm)\b", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                  # ảnh
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)              # link → chữ
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\[(?:CONTEXT|BẢNG|NGỮ CẢNH)\s*\d*\]", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\[\d+\]", "", t)                               # trích dẫn [1]
    t = re.sub(r"<[^>]+>", " ", t)                              # thẻ HTML
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE) # tiêu đề
    t = re.sub(r"^\s*>\s?", "", t, flags=re.MULTILINE)          # trích dẫn
    t = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", t, flags=re.MULTILINE)  # gạch đầu dòng
    t = re.sub(r"^\s*([-*_]\s*){3,}$", "", t, flags=re.MULTILINE)       # kẻ ngang
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    return t


def _normalize_numbers_units(t: str) -> str:
    # Ngày tháng: 15/9/2026 → ngày 15 tháng 9 năm 2026; 15/09 → ngày 15 tháng 9
    def _date(m: re.Match) -> str:
        d, mo = int(m.group(1)), int(m.group(2))
        if not (1 <= d <= 31 and 1 <= mo <= 12):
            return m.group(0)
        year = f" năm {m.group(3)}" if m.group(3) else ""
        return f"ngày {d} tháng {mo}{year}"

    t = re.sub(r"\b(?:ngày\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", _date, t)
    # Dạng ngắn 15/9 chỉ khi có chữ "ngày" đứng trước — tránh đọc nhầm điểm "8/10"
    t = re.sub(r"\bngày\s+(\d{1,2})/(\d{1,2})()\b(?!/)", _date, t)
    # Khoảng: 7h30 → 7 giờ 30
    t = re.sub(r"\b(\d{1,2})h(\d{2})\b", r"\1 giờ \2", t)
    t = re.sub(r"\b(\d{1,2})h\b", r"\1 giờ", t)
    # Phần trăm: 6,10% → 6 phẩy 10 phần trăm
    t = re.sub(r"(\d+)[,.](\d+)\s*%", r"\1 phẩy \2 phần trăm", t)
    t = re.sub(r"(\d+)\s*%", r"\1 phần trăm", t)
    t = t.replace("%", " phần trăm ")
    # Tiền tệ
    t = re.sub(r"\b(?:VNĐ|VND)\b", "đồng", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d)\s*(?:đ|₫)(?=[\s/.,;)]|$)", r"\1 đồng", t)
    t = re.sub(r"(\d)\s*USD\b", r"\1 đô la Mỹ", t)
    t = re.sub(r"\bUSD\b", "đô la Mỹ", t)
    # Đơn vị dạng "/năm", "/tín chỉ"
    for unit, spoken in sorted(_UNIT_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\s*/\s*{unit}\b", f" {spoken}", t, flags=re.IGNORECASE)
    # Dải số: 7-8 → 7 đến 8 (không đụng ngày đã xử lý)
    # (bỏ qua số bắt đầu bằng 0 như số điện thoại 024-3852...)
    t = re.sub(r"(?<![\w/.,-])([1-9]\d{0,3}(?:[.,]\d+)?)\s*[-–]\s*([1-9]\d{0,3}(?:[.,]\d+)?)(?![\w/-])",
               r"\1 đến \2", t)
    # Dấu ≥ ≤
    t = t.replace("≥", " lớn hơn hoặc bằng ").replace("≤", " nhỏ hơn hoặc bằng ")
    t = re.sub(r">=", " lớn hơn hoặc bằng ", t)
    t = re.sub(r"<=", " nhỏ hơn hoặc bằng ", t)
    return t


def _expand_abbreviations(t: str) -> str:
    for pattern, meaning in _ABBREVIATIONS:
        first = meaning.split(" ", 1)[0].lower()

        def repl(m: re.Match, meaning=meaning, first=first) -> str:
            # "Điểm ĐRL" → "Điểm rèn luyện" thay vì "Điểm điểm rèn luyện"
            before = m.string[: m.start()].rstrip().rsplit(" ", 1)[-1].lower()
            if before == first and " " in meaning:
                return meaning.split(" ", 1)[1]
            return meaning

        t = pattern.sub(repl, t)
    return t


def truncate_at_sentence(text: str, max_chars: int) -> str:
    """Cắt văn bản không quá max_chars, ưu tiên dừng ở cuối câu."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    sentences = _SENTENCE_END_RE.split(cut)
    if len(sentences) > 1:
        cut = " ".join(sentences[:-1])
    else:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + " … Phần còn lại xem trên màn hình."


def normalize_for_speech(markdown: str, max_chars: int | None = None) -> str:
    """Chuẩn hoá câu trả lời Markdown thành văn bản đọc được bằng TTS tiếng Việt."""
    if not markdown or not markdown.strip():
        return ""
    t = markdown.replace("\r\n", "\n")
    t = _replace_tables(t)
    t = _strip_markdown(t)
    t = _normalize_numbers_units(t)
    t = _expand_abbreviations(t)
    t = re.sub(r"[*#_`~|\[\]{}\\]", " ", t)
    # Mỗi dòng là một ý: thêm dấu chấm để TTS ngắt hơi
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    lines = [l if re.search(r"[.!?:;…,]$", l) else l + "." for l in lines]
    t = " ".join(lines)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([.,;:!?])\1+", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if max_chars:
        t = truncate_at_sentence(t, max_chars)
    return t
