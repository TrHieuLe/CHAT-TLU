"""
test_restructure_titles.py — Unit tests cho module restructure_titles.

Bao gồm:
  - Chunk class: init, to_dict, add_page_ref, get_pages_list
  - _safe_page_number: ép kiểu page number
  - _make_title_id: tạo hash ID
  - _clean_text: chuẩn hóa khoảng trắng
  - _roman_to_int: chuyển số La Mã → int
  - _extract_heading_level: heuristic heading level
  - _looks_like_heading: kiểm tra heading
  - _heading_level: tính level
  - _new_node / _append_content / _ensure_root
  - build_chunks_dict: gom chunk theo title_id
  - chunk_by_title: xử lý file text
"""
import pytest
from app.rag.restructure_titles import (
    Chunk,
    _safe_page_number,
    _make_title_id,
    _clean_text,
    _roman_to_int,
    _extract_heading_level,
    _looks_like_heading,
    _heading_level,
    _new_node,
    _append_content,
    _ensure_root,
    build_chunks_dict,
    chunk_by_title,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Chunk class
# ═══════════════════════════════════════════════════════════════════════════════

class TestChunk:
    def test_init_defaults(self):
        c = Chunk()
        assert c.title_id is None
        assert c.title == ""
        assert c.content == ""
        assert c.pages == set()

    def test_init_with_values(self):
        c = Chunk(title_id="abc", title="Test", content="Body", pages={1, 2})
        assert c.title_id == "abc"
        assert c.content == "Body"
        assert c.pages == {1, 2}

    def test_get_pages_list_sorted(self):
        c = Chunk(pages={3, 1, 5, 2})
        assert c.get_pages_list() == [1, 2, 3, 5]

    def test_add_page_ref_valid(self):
        c = Chunk()
        c.add_page_ref(5)
        c.add_page_ref(3)
        assert c.pages == {3, 5}

    def test_add_page_ref_none(self):
        c = Chunk()
        c.add_page_ref(None)
        assert c.pages == set()

    def test_add_page_ref_zero_ignored(self):
        c = Chunk()
        c.add_page_ref(0)
        assert c.pages == set()

    def test_add_page_ref_negative_ignored(self):
        c = Chunk()
        c.add_page_ref(-1)
        assert c.pages == set()

    def test_to_dict(self):
        c = Chunk(title_id="x", title="T", content="C", pages={2, 1})
        d = c.to_dict()
        assert d["title_id"] == "x"
        assert d["pages"] == [1, 2]  # sorted


# ═══════════════════════════════════════════════════════════════════════════════
# Utility functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafePageNumber:
    def test_positive_int(self):
        assert _safe_page_number(5) == 5

    def test_string_number(self):
        assert _safe_page_number("3") == 3

    def test_zero(self):
        assert _safe_page_number(0) == 1

    def test_negative(self):
        assert _safe_page_number(-5) == 1

    def test_invalid(self):
        assert _safe_page_number("abc") == 1

    def test_none(self):
        assert _safe_page_number(None) == 1


class TestMakeTitleId:
    def test_returns_string(self):
        result = _make_title_id("Test Title", 1)
        assert isinstance(result, str)

    def test_deterministic(self):
        a = _make_title_id("Title", 1)
        b = _make_title_id("Title", 1)
        assert a == b

    def test_different_inputs(self):
        a = _make_title_id("A", 1)
        b = _make_title_id("B", 1)
        assert a != b


class TestCleanText:
    def test_removes_nbsp(self):
        assert _clean_text("hello\xa0world") == "hello world"

    def test_collapses_whitespace(self):
        assert _clean_text("a   b  c") == "a b c"

    def test_strips(self):
        assert _clean_text("  text  ") == "text"

    def test_empty(self):
        assert _clean_text("") == ""
        assert _clean_text(None) == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Roman numeral conversion
# ═══════════════════════════════════════════════════════════════════════════════

class TestRomanToInt:
    @pytest.mark.parametrize("roman,expected", [
        ("I", 1), ("II", 2), ("III", 3), ("IV", 4), ("V", 5),
        ("IX", 9), ("X", 10), ("XIV", 14), ("XL", 40), ("L", 50),
        ("C", 100), ("i", 1), ("iv", 4), ("xiv", 14),
    ])
    def test_conversions(self, roman, expected):
        assert _roman_to_int(roman) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# Heading detection & level
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractHeadingLevel:
    def test_chapter(self):
        assert _extract_heading_level("Chương 1: Giới thiệu") == 1

    def test_phan(self):
        assert _extract_heading_level("Phần 2: Nội dung") == 1

    def test_muc(self):
        assert _extract_heading_level("Mục 1: Quy định chung") == 2

    def test_roman_numeral(self):
        assert _extract_heading_level("III. Phương pháp nghiên cứu") == 1

    def test_numbered_1(self):
        assert _extract_heading_level("1. Giới thiệu") == 1

    def test_numbered_1_1(self):
        assert _extract_heading_level("1.1 Bối cảnh") == 2

    def test_numbered_1_1_1(self):
        assert _extract_heading_level("1.1.1 Chi tiết") == 3

    def test_plain_text(self):
        assert _extract_heading_level("Đây là nội dung thường") is None

    def test_empty(self):
        assert _extract_heading_level("") is None


class TestLooksLikeHeading:
    def test_title_category(self):
        assert _looks_like_heading("Bất kỳ text gì", "Title") is True

    def test_chapter(self):
        assert _looks_like_heading("Chương 1: Mở đầu") is True

    def test_uppercase(self):
        assert _looks_like_heading("PHƯƠNG PHÁP NGHIÊN CỨU") is True

    def test_dieu(self):
        assert _looks_like_heading("Điều 5: Quyền lợi sinh viên") is True

    def test_long_text_not_heading(self):
        text = "Đây là đoạn văn dài " * 20
        assert _looks_like_heading(text) is False

    def test_plain_text(self):
        assert _looks_like_heading("Nội dung bình thường ngắn") is False

    def test_empty(self):
        assert _looks_like_heading("") is False


class TestHeadingLevel:
    def test_chapter_level_1(self):
        assert _heading_level("Chương 1: Giới thiệu") == 1

    def test_title_category_short(self):
        assert _heading_level("Tiêu đề ngắn", "Title") == 2

    def test_uppercase_level_1(self):
        assert _heading_level("PHƯƠNG PHÁP") == 1

    def test_dieu_level_2(self):
        assert _heading_level("Điều 1") == 2

    def test_khoan_level_3(self):
        assert _heading_level("Khoản 1") == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Node helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestNodeHelpers:
    def test_new_node(self):
        node = _new_node("Title", 5)
        assert node["title"] == "Title"
        assert node["page_number"] == 5
        assert node["children"] == []
        assert 5 in node["pages"]
        assert "titleId" in node

    def test_append_content_to_empty(self):
        node = {"content": "", "pages": []}
        _append_content(node, "Hello world", 1)
        assert node["content"] == "Hello world"
        assert 1 in node["pages"]

    def test_append_content_accumulates(self):
        node = {"content": "First", "pages": [1]}
        _append_content(node, "Second", 2)
        assert "First" in node["content"]
        assert "Second" in node["content"]
        assert 2 in node["pages"]

    def test_append_empty_content_ignored(self):
        node = {"content": "Existing", "pages": []}
        _append_content(node, "", 1)
        assert node["content"] == "Existing"

    def test_ensure_root(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("x")
        root = _ensure_root(f)
        assert root["title"] == "test"
        assert root["children"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# build_chunks_dict
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildChunksDict:
    def test_basic(self):
        items = [
            {"title_id": "a", "text": "Content A", "page_number": 1},
            {"title_id": "a", "text": "More A", "page_number": 2},
            {"title_id": "b", "text": "Content B", "page_number": 3},
        ]
        chunks = build_chunks_dict(items)
        assert "a" in chunks
        assert "b" in chunks
        assert "More A" in chunks["a"].content
        assert chunks["a"].pages == {1, 2}

    def test_skips_empty_title_id(self):
        items = [{"title_id": None, "text": "orphan"}]
        assert build_chunks_dict(items) == {}

    def test_empty_input(self):
        assert build_chunks_dict([]) == {}


# ═══════════════════════════════════════════════════════════════════════════════
# chunk_by_title (file-based, needs tmp file)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChunkByTitle:
    def test_txt_file(self, tmp_text_file):
        result = chunk_by_title(tmp_text_file)
        assert "title" in result
        assert "content" in result
        assert result["title"] == "sample"
        assert "Giới thiệu" in result["content"]

    def test_unsupported_extension(self, tmp_path):
        bad = tmp_path / "file.xyz"
        bad.write_text("data")
        with pytest.raises(ValueError, match="không được hỗ trợ"):
            chunk_by_title(bad)

    def test_string_path_accepted(self, tmp_text_file):
        """Chấp nhận cả str lẫn Path."""
        result = chunk_by_title(str(tmp_text_file))
        assert result["title"] == "sample"


class TestTxtTree:
    """File .txt viết tay: mục IN HOA + bản ghi đánh số thành chunk riêng, mang đường dẫn tiêu đề."""

    @pytest.fixture
    def list_file(self, tmp_path):
        f = tmp_path / "DiemChuan.txt"
        f.write_text(
            "TÊN VĂN BẢN: ĐIỂM CHUẨN CÁC NGÀNH\n"
            "CHI TIẾT ĐIỂM CHUẨN TỪNG NGÀNH\n"
            "1. Ngành Kỹ thuật cơ khí\n"
            "- Điểm chuẩn thi trung học phổ thông: 22.60 điểm\n"
            "2. Ngành Công nghệ thông tin\n"
            "- Điểm chuẩn thi trung học phổ thông: 23.23 điểm\n"
            "TỔNG HỢP\n"
            "- Ngành có điểm chuẩn cao nhất: Luật kinh tế.\n",
            encoding="utf-8",
        )
        return f

    def test_tree_structure(self, list_file):
        tree = chunk_by_title(list_file)
        assert tree["title"] == "ĐIỂM CHUẨN CÁC NGÀNH"
        sections = tree["children"]
        assert [s["title"] for s in sections] == ["CHI TIẾT ĐIỂM CHUẨN TỪNG NGÀNH", "TỔNG HỢP"]
        records = sections[0]["children"]
        assert [r["title"] for r in records] == ["1. Ngành Kỹ thuật cơ khí", "2. Ngành Công nghệ thông tin"]
        assert all(r["standalone"] for r in records)
        assert "23.23" in records[1]["content"]

    def test_one_chunk_per_record_with_header(self, list_file):
        from app.rag.doc_preprocessor import chunk_doc
        chunks = [c["text"] for c in chunk_doc(chunk_by_title(list_file), model="x")]
        assert len(chunks) == 3
        cntt = [c for c in chunks if "Công nghệ thông tin" in c]
        assert len(cntt) == 1
        assert cntt[0].startswith("ĐIỂM CHUẨN CÁC NGÀNH > CHI TIẾT ĐIỂM CHUẨN TỪNG NGÀNH > 2. Ngành Công nghệ thông tin")
        assert "23.23" in cntt[0] and "22.60" not in cntt[0]

    def test_first_line_title_before_numbered_list(self, tmp_path):
        f = tmp_path / "DonVi.txt"
        f.write_text("Các đơn vị - Trường Đại học Thủy lợi\n1. Phòng Đào tạo\nĐiện thoại: 0243\n", encoding="utf-8")
        tree = chunk_by_title(f)
        assert tree["title"] == "Các đơn vị - Trường Đại học Thủy lợi"
        assert tree["content"] == ""
        assert tree["children"][0]["title"] == "1. Phòng Đào tạo"

    def test_plain_bullets_stay_flat(self, tmp_path):
        f = tmp_path / "flat.txt"
        f.write_text("- Ý thứ nhất.\n- Ý thứ hai.\n", encoding="utf-8")
        tree = chunk_by_title(f)
        assert tree["title"] == "flat"
        assert tree["children"] == []
        assert "Ý thứ hai" in tree["content"]
