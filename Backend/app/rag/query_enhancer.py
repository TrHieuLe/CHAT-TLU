"""
query_enhancer.py — Module tối ưu truy vấn và giải mã từ viết tắt học vụ ĐH Thủy Lợi (TLU).
Giúp chuyển đổi các từ viết tắt thông dụng của sinh viên thành từ khóa ngữ nghĩa chính quy,
tăng độ chính xác (Precision & Recall) khi tìm kiếm quy chế qua Dense & Sparse Vector.
"""
import re
from typing import Dict

# Từ điển các thuật ngữ viết tắt phổ biến tại ĐH Thủy Lợi
TLU_ABBREVIATIONS: Dict[str, str] = {
    r"\bđrl\b": "điểm rèn luyện",
    r"\bdrl\b": "điểm rèn luyện",
    r"\bhp\b": "học phần",
    r"\bcpa\b": "điểm trung bình tích lũy CPA",
    r"\bgpa\b": "điểm trung bình học kỳ GPA",
    r"\bctđt\b": "chương trình đào tạo",
    r"\bctdt\b": "chương trình đào tạo",
    r"\bkktx\b": "ký túc xá",
    r"\bktx\b": "ký túc xá",
    r"\bkltn\b": "khóa luận tốt nghiệp",
    r"\bđatn\b": "đồ án tốt nghiệp",
    r"\bdatn\b": "đồ án tốt nghiệp",
    r"\bgvcn\b": "giảng viên chủ nhiệm",
    r"\bcbl\b": "cán bộ lớp",
    r"\bbcl\b": "ban cán sự lớp",
    r"\bbcs\b": "ban cán sự lớp",
    r"\btlu\b": "Trường Đại học Thủy Lợi",
    r"\bpđt\b": "phòng đào tạo",
    r"\bpdt\b": "phòng đào tạo",
    r"\bcthssv\b": "phòng chính trị và công tác sinh viên",
    r"\bkhht\b": "kế hoạch học tập",
    r"\btkm\b": "thi kết thúc học phần",
    r"\bnckh\b": "nghiên cứu khoa học",
    r"\bcntt\b": "công nghệ thông tin",
    r"\bktpm\b": "kỹ thuật phần mềm",
    r"\bkhmt\b": "khoa học máy tính",
    r"\bhttt\b": "hệ thống thông tin",
    r"\battt\b": "an toàn thông tin",
    r"\bbldt\b": "bảo lưu đào tạo",
    r"\bxxtn\b": "xét công nhận tốt nghiệp",
}


# Cách nói thường ngày của sinh viên -> thuật ngữ trong văn bản. Không có thuật ngữ này, câu
# "điểm đầu vào khoa công nghệ thông tin" chỉ khớp cụm "công nghệ thông tin" và kéo về văn bản
# Chuẩn đầu ra CNTT thay vì bảng điểm chuẩn.
TLU_SYNONYMS: Dict[str, str] = {
    r"\bđiểm đầu vào\b": "điểm chuẩn tuyển sinh",
    r"\bđiểm trúng tuyển\b": "điểm chuẩn tuyển sinh",
    r"\bchỉ tiêu\b(?! tuyển sinh)": "chỉ tiêu tuyển sinh",
    r"\bhạ (?:loại )?bằng\b": "giảm mức xếp loại tốt nghiệp",
    r"\bcộng điểm rèn luyện\b": "khung đánh giá kết quả rèn luyện",
    r"\bthành tựu\b": "thành tích, danh hiệu, giải thưởng",
}


def _expand(text: str, pattern: str, full_meaning: str) -> str:
    return re.sub(pattern, lambda m: f"{m.group(0)} ({full_meaning})", text, flags=re.IGNORECASE)


def enhance_query(query: str) -> str:
    """
    Phát hiện các từ viết tắt học vụ và cách nói thường ngày trong câu hỏi của sinh viên
    và bổ sung từ khóa mở rộng đầy đủ.

    Ví dụ:
        'đrl bao nhiêu thì được học bổng?'
        -> 'đrl (điểm rèn luyện) bao nhiêu thì được học bổng?'
        'điểm đầu vào ngành cntt'
        -> 'điểm đầu vào (điểm chuẩn tuyển sinh) ngành cntt (công nghệ thông tin)'
    """
    if not query:
        return ""

    enhanced = query
    for pattern, full_meaning in TLU_ABBREVIATIONS.items():
        if re.search(pattern, enhanced, flags=re.IGNORECASE):
            enhanced = _expand(enhanced, pattern, full_meaning)

    for pattern, full_meaning in TLU_SYNONYMS.items():
        if full_meaning.lower() not in enhanced.lower() and re.search(pattern, enhanced, flags=re.IGNORECASE):
            enhanced = _expand(enhanced, pattern, full_meaning)

    return enhanced


def normalize_abbreviations_only(query: str) -> str:
    """
    Thay thế trực tiếp từ viết tắt bằng từ ngữ chính quy đầy đủ.
    """
    if not query:
        return ""

    result = query
    for pattern, full_meaning in TLU_ABBREVIATIONS.items():
        result = re.sub(pattern, full_meaning, result, flags=re.IGNORECASE)

    return result
