import logging
import re
from pathlib import Path
from typing import Any

class SimpleElement:
    """Đối tượng phần tử văn bản tương thích interface của unstructured element."""
    def __init__(self, text: str = "", category: str = "NarrativeText", page_number: int = 1, elem_id: str = ""):
        self.text = text
        self.category = category
        self.id = elem_id or str(abs(hash(f"{text}::{page_number}")))
        self.metadata = type("Metadata", (), {"page_number": page_number})()


log = logging.getLogger(__name__)

# Tạo lớp chunk
class Chunk:
    def __init__(
        self,
        title_id: str | None = None,
        title: str = "",
        content: str = "",
        pages: set[int] | None = None,
    ):
        self.title_id = title_id
        self.title = title
        self.content = content
        self.pages = pages or set()
    # Sắp xếp các số trang vì dùng set() không tự sắp xếp đc 
    def get_pages_list(self) -> list[int]:
        return sorted(list(self.pages))
    
    # Ép kiểu số trang về int 
    def add_page_ref(self, page: int | None):
        if page is None:
            return
        try:
            page = int(page)
            if page > 0:
                self.pages.add(page)
        except Exception:
            return
        
    #Đóng gói chunk thành 1 dict
    def to_dict(self):
        return {
            "title_id": self.title_id,
            "title": self.title,
            "content": self.content,
            "pages": sorted(list(self.pages)),
        }

#Đảm bảo số trang ít nhất là 1
def _safe_page_number(value: Any) -> int:
    try:
        page = int(value)
        return page if page > 0 else 1
    except Exception:
        return 1

#Tạo id cho title
def _make_title_id(title: str, page_number: int) -> str:
    return str(abs(hash(f"{title.strip()}::{page_number}")))

# Xóa các khoảng trắng
def _clean_text(text: str, preserve_newlines: bool = False) -> str:
    text = (text or "").replace("\xa0", " ")
    if preserve_newlines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text

#Phân loại đuôi file với fallback an toàn
def _partition_file(file_path: Path):
    file_ext = file_path.suffix.lower()

    # Thử dùng thư viện unstructured nếu có trong môi trường
    try:
        if file_ext == ".md":
            from unstructured.partition.md import partition_md
            return partition_md(filename=str(file_path))
        if file_ext in [".html", ".htm"]:
            from unstructured.partition.html import partition_html
            return partition_html(filename=str(file_path))
        if file_ext == ".txt":
            from unstructured.partition.text import partition_text
            return partition_text(filename=str(file_path))
        if file_ext == ".pdf":
            from unstructured.partition.auto import partition
            return partition(filename=str(file_path), strategy="fast")
    except Exception:
        pass

    # Fallback tự nhiên không phụ thuộc vào thư viện bên ngoài
    elements = []
    if file_ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    for line in text.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        cat = "Title" if (len(line) < 100 and (_extract_heading_level(line) is not None or line.isupper())) else "NarrativeText"
                        elements.append(SimpleElement(text=line, category=cat, page_number=page_idx))
            return elements
        except Exception as e:
            log.warning("Fallback pdfplumber: %s", e)

    if file_ext in [".docx", ".doc"]:
        try:
            import docx
            doc = docx.Document(file_path)
            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                is_heading = (
                    (p.style and getattr(p.style, "name", "").startswith(("Heading", "Tiêu đề")))
                    or (len(text) < 120 and (_extract_heading_level(text) is not None or text.isupper()))
                )
                cat = "Title" if is_heading else "NarrativeText"
                elements.append(SimpleElement(text=text, category=cat, page_number=1))

            try:
                from app.rag.table_extractor import extract_tables_from_docx
                docx_tables = extract_tables_from_docx(file_path)
                for tbl in docx_tables:
                    table_text = tbl.get("table_text", "")
                    page_num = tbl.get("page") or 1
                    if table_text:
                        elements.append(SimpleElement(text=table_text, category="Table", page_number=page_num))
            except Exception as e_tbl:
                log.warning("extract_tables_from_docx in partition: %s", e_tbl)

            if elements:
                return elements
        except Exception as e:
            log.warning("Fallback python-docx failed for %s: %s", file_path.name, e)

    if file_ext in [".xlsx", ".xls", ".csv"]:
        try:
            from app.rag.table_extractor import extract_tables_from_excel
            excel_tables = extract_tables_from_excel(file_path)
            for tbl in excel_tables:
                table_text = tbl.get("table_text", "")
                page_num = tbl.get("page") or 1
                if table_text:
                    elements.append(SimpleElement(text=table_text, category="Table", page_number=page_num))
            if elements:
                return elements
        except Exception as e:
            log.warning("Fallback excel extraction failed for %s: %s", file_path.name, e)

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cat = "Title" if (line.startswith("#") or (len(line) < 100 and _extract_heading_level(line) is not None)) else "NarrativeText"
            clean_l = line.lstrip("#").strip()
            elements.append(SimpleElement(text=clean_l, category=cat, page_number=1))
    except Exception as e:
        log.error("Native fallback read: %s", e)

    return elements

#Xử lý số la mã
def _roman_to_int(token: str) -> int:
    roman_map = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    token = token.lower()
    total = 0
    prev = 0
    for ch in reversed(token):
        val = roman_map.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total

#Đặt heading level cho text
def _extract_heading_level(text: str) -> int | None:
    """
    Heuristic level detector:
    1 -> Chương / Phần / Mục lớn / I. / 1.
    2 -> 1.1 / 1.1.
    3 -> 1.1.1 / 1.1.1.
    4 -> deeper numbered
    """
    t = _clean_text(text)
    if not t:
        return None

    lower = t.lower()

    if lower.startswith(("chương ", "chuong ", "phần ", "phan ")):
        return 1

    if lower.startswith(("mục ", "muc ")):
        return 2

    if re.match(r"^(điều|dieu)\s+(\d+|[ivxlcdm]+)", lower):
        return 2

    if re.match(r"^(khoản|khoan)\s+\d+", lower):
        return 3

    if re.match(r"^(điểm|diem)\s+[a-z]", lower) or re.match(r"^[a-z]\)\s+", lower):
        return 4

    m_roman = re.match(r"^([ivxlcdm]+)[\.\)]\s+", lower)
    if m_roman and _roman_to_int(m_roman.group(1)) > 0:
        return 1

    m_num = re.match(r"^(\d+(?:\.\d+){0,5})[\.\)]?\s+", t)
    if m_num:
        depth = m_num.group(1).count(".")
        if depth == 0:
            return 1
        if depth == 1:
            return 2
        if depth == 2:
            return 3
        return 4

    return None

#Kiểm tra heading
def _looks_like_heading(text: str, category: str = "") -> bool:
    t = _clean_text(text)
    if not t:
        return False

    if category == "Title":
        return True

    if len(t) > 180:
        return False

    if _extract_heading_level(t) is not None:
        return True

    if t.isupper() and len(t) <= 120:
        return True

    if re.match(r"^(Điều|Khoản|Mục|Phần|Chương)\b", t, flags=re.IGNORECASE):
        return True

    return False

#Chia cấp độ heading
def _heading_level(text: str, category: str = "") -> int:
    level = _extract_heading_level(text)
    if level is not None:
        return level

    t = _clean_text(text)

    if category == "Title":
        return 2 if len(t) <= 100 else 3

    if t.isupper() and len(t) <= 120:
        return 1

    if re.match(r"^(Điều)\b", t, flags=re.IGNORECASE):
        return 2

    if re.match(r"^(Khoản)\b", t, flags=re.IGNORECASE):
        return 3

    return 3

#Xử lý file txt
def _flat_txt_fallback(file_path: Path) -> dict:
    text = file_path.read_text(encoding="utf-8").strip()
    return {
        "titleId": _make_title_id(file_path.stem, 1),
        "title": file_path.stem,
        "content": text,
        "page_number": 1,
        "children": [],
        "pages": [1],
    }


_TXT_DOC_TITLE_RE = re.compile(r"^TÊN VĂN BẢN\s*:\s*(.+)$", flags=re.IGNORECASE)
_TXT_RECORD_RE = re.compile(r"^\d+\.\s+\S")
_TXT_RULE_RE = re.compile(r"^[-=_*]{5,}$")
# Dòng đánh dấu phần trong file dạng gạch đầu dòng, vd '- Phần 9 của văn bản quy định về xếp loại tốt nghiệp.'
_TXT_PART_RE = re.compile(r"^-?\s*Phần\s+\d+\s+của văn bản\b", flags=re.IGNORECASE)


def _txt_is_section(line: str) -> bool:
    """Dòng IN HOA ngắn (vd 'THÔNG TIN CHI TIẾT TỪNG NGÀNH', 'I. LỊCH SỬ ...') là tiêu đề mục."""
    if len(line) <= 150 and _TXT_PART_RE.match(line):
        return True
    if len(line) > 150 or line.startswith(("-", "+", "*")):
        return False
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def _txt_is_record(line: str) -> bool:
    """Dòng '6. Ngành Công nghệ thông tin' mở đầu một bản ghi trong danh sách đánh số."""
    return len(line) <= 160 and bool(_TXT_RECORD_RE.match(line))


def _txt_tree(file_path: Path) -> dict:
    """
    Dựng cây cho file .txt viết tay: dòng IN HOA là mục (cấp 1), dòng đánh số '1. ...' là bản ghi (cấp 2).
    Mỗi mục/bản ghi đánh dấu standalone để chunk_doc tách thành chunk riêng, mang theo đường dẫn tiêu đề
    (vd 'ĐIỂM CHUẨN ... > CHI TIẾT ... > 6. Ngành Công nghệ thông tin'). Trước đây cả file là một nút,
    nên một chunk ~800 token gộp hơn chục ngành và câu hỏi về một ngành không khớp được chunk nào.
    Tiêu đề tài liệu lấy từ dòng 'TÊN VĂN BẢN: ...' đầu file, hoặc dòng ngắn đầu tiên nếu ngay sau nó
    là một mục/bản ghi. File không có tiêu đề nào giữ nguyên cách cũ (một nút).
    """
    lines = [ln.strip() for ln in file_path.read_text(encoding="utf-8").splitlines()]
    lines = [ln for ln in lines if ln and not _TXT_RULE_RE.match(ln)]
    if not lines:
        return _flat_txt_fallback(file_path)

    title = file_path.stem
    m = _TXT_DOC_TITLE_RE.match(lines[0])
    if m:
        title = m.group(1).strip()
        lines = lines[1:]
    elif (
        len(lines) > 1
        and len(lines[0]) <= 150
        and not lines[0].startswith(("-", "+", "*"))
        and not _txt_is_record(lines[0])
        and (_txt_is_section(lines[1]) or _txt_is_record(lines[1]))
    ):
        title = lines[0]
        lines = lines[1:]

    if not any(_txt_is_section(ln) or _txt_is_record(ln) for ln in lines):
        flat = _flat_txt_fallback(file_path)
        flat["title"] = title
        flat["content"] = "\n".join(lines)
        return flat

    root = {
        "titleId": _make_title_id(title, 1),
        "title": title,
        "content": "",
        "page_number": 1,
        "children": [],
        "pages": [1],
    }
    section: dict | None = None
    current = root

    for line in lines:
        if _txt_is_section(line):
            section = _new_node(line.lstrip("-* ").rstrip("."), 1)
            section["standalone"] = True
            root["children"].append(section)
            current = section
        elif _txt_is_record(line):
            record = _new_node(line, 1)
            record["standalone"] = True
            (section or root)["children"].append(record)
            current = record
        else:
            current["content"] = f"{current['content']}\n{line}" if current["content"] else line

    return root

#Tạo nút rỗng
def _new_node(title: str, page_number: int) -> dict:
    return {
        "titleId": _make_title_id(title, page_number),
        "title": title,
        "content": "",
        "page_number": page_number,
        "children": [],
        "pages": [page_number] if page_number > 0 else [],
    }

#append nội dung và số trang vào node(title)
def _append_content(node: dict, text: str, page_number: int, is_table: bool = False):
    text = _clean_text(text, preserve_newlines=is_table)
    if not text:
        return

    if node.get("content"):
        node["content"] += "\n\n" + text
    else:
        node["content"] = text

    node.setdefault("pages", [])
    if page_number > 0 and page_number not in node["pages"]:
        node["pages"].append(page_number)

#Tạo nốt gốc
def _ensure_root(file_path: Path) -> dict:
    return {
        "titleId": _make_title_id(file_path.stem, -1),
        "title": file_path.stem,
        "content": "",
        "page_number": -1,
        "children": [],
        "pages": [],
    }

#Tạo cây 
def _build_tree_rule_based(elements: list[Any], file_path: Path) -> dict:
    root = _ensure_root(file_path)
    stack: list[tuple[int, dict]] = [(0, root)]
    current_node = root
    current_page = 1

    for el in elements:
        category = getattr(el, "category", "") or ""
        raw_text = getattr(el, "text", "") or ""
        is_table = (category == "Table") or ("|" in raw_text and "\n" in raw_text)
        text = _clean_text(raw_text, preserve_newlines=is_table)
        if not text:
            continue

        metadata = getattr(el, "metadata", None)
        page_number = getattr(metadata, "page_number", None) if metadata else None
        if page_number:
            current_page = _safe_page_number(page_number)

        if not is_table and _looks_like_heading(text, category):
            level = _heading_level(text, category)
            node = _new_node(text, current_page)

            while stack and stack[-1][0] >= level:
                stack.pop()
            #[0]: level và 1 : hộp Node
            parent = stack[-1][1] if stack else root
            parent.setdefault("children", []).append(node)
            stack.append((level, node))
            current_node = node
        else:
            _append_content(current_node, text, current_page, is_table=is_table)

    return root

#Gom tất cả chunk và number_page dựa vào title_id
def build_chunks_dict(content_items: list[dict[str, Any]]) -> dict[str, Chunk]:
    chunks: dict[str, Chunk] = {}

    for item in content_items:
        title_id = item.get("title_id")
        if not title_id:
            continue

        if title_id not in chunks:
            chunks[title_id] = Chunk(
                title_id=title_id,
                content="",
                pages=set(),
            )

        text = _clean_text(item.get("text") or "")
        if text:
            if chunks[title_id].content:
                chunks[title_id].content += "\n\n" + text
            else:
                chunks[title_id].content = text

        page_number = item.get("page_number")
        if page_number:
            chunks[title_id].add_page_ref(_safe_page_number(page_number))

    return chunks

#Đắp các content và page vào cây
def merge_content(node: dict, chunks: dict[str, Chunk], depth: int = 0):
    if not isinstance(node, dict):
        return node

    title_id = node.get("titleId")
    if title_id in chunks:
        chunk = chunks[title_id]
        if not node.get("content"):
            node["content"] = chunk.content
        node["pages"] = chunk.get_pages_list()
    else:
        node.setdefault("content", "")
        node.setdefault("pages", [])

    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            merge_content(child, chunks, depth + 1)

    return node

#Xử lý các file đưa vào
def chunk_by_title(file_path: str | Path) -> dict:
    file_path = Path(file_path)
    file_ext = file_path.suffix.lower()

    supported_exts = {".txt", ".md", ".html", ".htm", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv"}
    if file_ext not in supported_exts:
        raise ValueError(
            f"Định dạng file không được hỗ trợ: {file_ext}. "
            "Vui lòng cung cấp file Text (.txt), Markdown (.md), HTML (.html), PDF, Word (.docx) hoặc Excel (.xlsx, .csv)."
        )

    if file_ext == ".txt":
        return _txt_tree(file_path)

    elements = _partition_file(file_path)

    if not elements:
        return _ensure_root(file_path)

    structured = _build_tree_rule_based(elements, file_path)

    if not structured.get("children"):
        all_text = "\n\n".join(
            _clean_text(getattr(el, "text", "") or "", preserve_newlines=(getattr(el, "category", "") == "Table"))
            for el in elements
            if _clean_text(getattr(el, "text", "") or "")
        ).strip()
        structured["content"] = all_text
        structured["pages"] = sorted(
            list(
                {
                    _safe_page_number(getattr(getattr(el, "metadata", None), "page_number", 1))
                    for el in elements
                    if getattr(el, "metadata", None) is not None
                }
            )
        )
        return structured

    structured.setdefault("titleId", _make_title_id(file_path.stem, -1))
    structured.setdefault("title", file_path.stem)
    structured.setdefault("content", "")
    structured.setdefault("page_number", -1)
    structured.setdefault("children", [])
    structured.setdefault("pages", [])

    return structured
#Dành cho những tài liệu tự viết tay
def chunk_manually_doc(file_path: str | Path) -> dict:
    path = Path(file_path)
    elements = _partition_file(path)
    if not elements:
        return _ensure_root(path)

    nodes = []
    is_title = True
    node = dict()

    for el in elements:
        text = el.text.strip()
        log.info(f"Processing {el.category}: {text[:10]}...")

        if text == "#####":  # kết thúc 1 đoạn
            if node:
                nodes.append(node)
            node = {}
            is_title = True
        elif is_title:
            node = {
                "title_id": el.id,
                "title": text,
                "content": "",
                "page_number": []
            }
            is_title = False
        else:
            node.setdefault("content", "")
            node.setdefault("page_number", [])
            node["content"] += text + "\n"
            page_number = getattr(el.metadata, "page_number", None)
            if isinstance(page_number, int):
                node["page_number"].append(page_number)

    return {
        "titleId": _make_title_id(path.stem, -1),
        "title": path.stem,
        "content": "",
        "pages": [-1],
        "children": nodes,
    }