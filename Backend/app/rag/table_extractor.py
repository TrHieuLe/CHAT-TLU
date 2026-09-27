"""
table_extractor.py — Bóc tách bảng dữ liệu chuẩn từ PDF, DOCX và Excel (XLSX, XLS, CSV).
Tạo bảng Markdown chuẩn, khử newlines trong ô, lọc bỏ bảng rác và bảng tiêu ngữ hành chính.
"""
import csv
import logging
import re
from pathlib import Path
from typing import Any, List, Dict, Optional

log = logging.getLogger(__name__)


def _clean_cell(val: Any) -> str:
    """Làm sạch ô dữ liệu: khử newlines, escape pipe, bỏ khoảng trắng thừa."""
    if val is None:
        return ""
    text = str(val).strip()
    # Khử ký tự xuống dòng bên trong cell để tránh làm vỡ dòng của Markdown table
    text = re.sub(r"[\r\n]+", " ", text)
    # Thay thế dấu gạch đứng để không xung đột cột Markdown
    text = text.replace("|", "/")
    # Gộp các khoảng trắng liên tiếp
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_letterhead_or_noise(rows: List[List[str]]) -> bool:
    """
    Kiểm tra xem bảng có phải là bảng tiêu ngữ hành chính (Quốc hiệu, Tiêu ngữ)
    hoặc bảng bố cục không chứa dữ liệu học vụ thực chất hay không.
    """
    if not rows or len(rows) < 2:
        return True

    # Nếu bảng chỉ có 1 cột duy nhất -> đó là đoạn văn bản đóng khung, không phải bảng
    max_cols = max(len(r) for r in rows)
    if max_cols < 2:
        return True

    combined_text = " ".join(" ".join(r) for r in rows[:3]).lower()

    # Nhận diện quốc hiệu / tiêu ngữ hành chính đầu văn bản
    if (
        ("bộ nông nghiệp" in combined_text or "bộ giáo dục" in combined_text or "trường đại học thủy lợi" in combined_text)
        and ("cộng hoà xã hội" in combined_text or "độc lập" in combined_text)
    ):
        return True

    # Nhận diện tiêu đề quyết định đóng khung
    if "quyết định" in combined_text and ("ban hành" in combined_text or "về việc" in combined_text) and len(rows) <= 3:
        return True

    return False


def _to_markdown_table(data: List[List[str]]) -> Optional[str]:
    """Chuyển đổi ma trận chuỗi thành bảng Markdown chuẩn chỉnh."""
    if not data or len(data) < 2:
        return None

    # Xác định số cột tối đa của bảng
    num_cols = max(len(row) for row in data)
    if num_cols < 2:
        return None

    # Đồng bộ số cột cho tất cả các hàng
    normalized_data = []
    for row in data:
        cleaned_row = [_clean_cell(c) for c in row]
        if len(cleaned_row) < num_cols:
            cleaned_row.extend([""] * (num_cols - len(cleaned_row)))
        elif len(cleaned_row) > num_cols:
            cleaned_row = cleaned_row[:num_cols]
        # Bỏ qua hàng hoàn toàn rỗng
        if any(cleaned_row):
            normalized_data.append(cleaned_row)

    if len(normalized_data) < 2:
        return None

    md_lines = []
    header = normalized_data[0]
    md_lines.append("| " + " | ".join(header) + " |")
    md_lines.append("|" + "|".join(["---"] * num_cols) + "|")

    for row in normalized_data[1:]:
        md_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(md_lines)


def extract_tables_from_pdf(pdf_path: Path, output_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Dùng pdfplumber detect bảng trong PDF.
    Lọc bỏ bảng 1 cột và chuẩn hóa cell text.
    """
    try:
        import pdfplumber
    except ImportError:
        log.error("Cần cài đặt: pip install pdfplumber")
        return []

    results = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    tables = page.find_tables()
                    if not tables:
                        continue

                    for tbl_idx, table in enumerate(tables):
                        raw_data = table.extract()
                        if not raw_data or len(raw_data) < 2:
                            continue

                        # Kiểm tra xem có phải bảng tiêu ngữ hoặc bảng rác 1 cột
                        cleaned_matrix = [[_clean_cell(c) for c in row] for row in raw_data]
                        if _is_letterhead_or_noise(cleaned_matrix):
                            continue

                        table_text = _to_markdown_table(cleaned_matrix)
                        if not table_text:
                            continue

                        results.append({
                            "page": page_num,
                            "table_text": table_text,
                            "type": "table",
                        })
                        log.info("  🗃  Đã trích xuất bảng PDF hợp lệ tại trang %s (bảng %s)", page_num, tbl_idx + 1)

                except Exception as page_err:
                    log.warning("Lỗi xử lý bảng tại trang %s: %s", page_num, page_err)

    except Exception as e:
        log.error("Lỗi khi mở đọc PDF %s: %s", pdf_path.name, e)

    return results


def extract_tables_from_docx(docx_path: Path, output_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Dùng python-docx đọc bảng trong DOCX.
    Khử trùng lặp ô gộp và chuẩn hóa markdown table.
    """
    try:
        import docx as python_docx
    except ImportError:
        log.error("Cần cài đặt: pip install python-docx")
        return []

    results = []

    try:
        doc = python_docx.Document(str(docx_path))

        for tbl_idx, table in enumerate(doc.tables):
            try:
                data = []
                for row in table.rows:
                    row_cells = []
                    prev_cell = None
                    for cell in row.cells:
                        # Khử lặp khi gặp ô gộp ngang (merged cells)
                        if prev_cell is not None and cell._tc is prev_cell._tc:
                            continue
                        row_cells.append(_clean_cell(cell.text))
                        prev_cell = cell

                    if any(row_cells):
                        data.append(row_cells)

                if not data or len(data) < 2:
                    continue

                if _is_letterhead_or_noise(data):
                    continue

                table_text = _to_markdown_table(data)
                if not table_text:
                    continue

                results.append({
                    "page": None,
                    "table_text": table_text,
                    "type": "table",
                })
                log.info("  🗃  Đã trích xuất bảng DOCX hợp lệ #%s (%s hàng)", tbl_idx + 1, len(data))

            except Exception as e:
                log.warning("Lỗi xử lý bảng DOCX #%s: %s", tbl_idx, e)

    except Exception as e:
        log.error("Lỗi khi mở đọc DOCX %s: %s", docx_path.name, e)

    return results


def extract_tables_from_excel(excel_path: Path, output_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Đọc các bảng tính từ file Excel (.xlsx, .xls) hoặc CSV.
    Mỗi sheet được chuyển thành 1 bảng Markdown với tiêu đề sheet rõ ràng.
    """
    ext = excel_path.suffix.lower()
    results = []

    if ext == ".csv":
        try:
            with open(excel_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                data = [[_clean_cell(c) for c in row] for row in reader if any(row)]
            table_text = _to_markdown_table(data)
            if table_text:
                results.append({
                    "page": None,
                    "table_text": table_text,
                    "sheet_name": "CSV",
                    "type": "table",
                })
                log.info("  🗃  Đã trích xuất bảng CSV: %s", excel_path.name)
        except Exception as e:
            log.error("Lỗi đọc CSV %s: %s", excel_path.name, e)
        return results

    # Xử lý .xlsx / .xls qua openpyxl
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(excel_path), data_only=True)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            raw_data = []
            for row in sheet.iter_rows(values_only=True):
                if any(row):
                    raw_data.append([_clean_cell(c) for c in row])

            if len(raw_data) < 2:
                continue

            table_text = _to_markdown_table(raw_data)
            if table_text:
                labeled_table = f"### Bảng: {sheet_name}\n\n{table_text}"
                results.append({
                    "page": None,
                    "table_text": labeled_table,
                    "sheet_name": sheet_name,
                    "type": "table",
                })
                log.info("  🗃  Đã trích xuất bảng Excel sheet '%s' (%s hàng)", sheet_name, len(raw_data))

    except Exception as e:
        log.error("Lỗi đọc file Excel %s: %s", excel_path.name, e)

    return results


def extract_all_tables(file_path: Path, output_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Tự động nhận diện định dạng tệp và trích xuất tất cả bảng biểu chuẩn xác.
    Hỗ trợ: .pdf, .docx, .doc, .xlsx, .xls, .csv.
    """
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return extract_tables_from_pdf(file_path, output_dir)
    elif ext in [".docx", ".doc"]:
        return extract_tables_from_docx(file_path, output_dir)
    elif ext in [".xlsx", ".xls", ".csv"]:
        return extract_tables_from_excel(file_path, output_dir)
    else:
        log.info("Định dạng %s không hỗ trợ trích xuất bảng", ext)
        return []