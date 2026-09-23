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


def enhance_query(query: str) -> str:
    """
    Phát hiện các từ viết tắt học vụ trong câu hỏi của sinh viên
    và bổ sung từ khóa mở rộng đầy đủ.

    Ví dụ:
        'đrl bao nhiêu thì được học bổng?'
        -> 'đrl (điểm rèn luyện) bao nhiêu thì được học bổng?'
    """
    if not query:
        return ""

    enhanced = query
    for pattern, full_meaning in TLU_ABBREVIATIONS.items():
        if re.search(pattern, enhanced, flags=re.IGNORECASE):
            def _replacer(m):
                original = m.group(0)
                return f"{original} ({full_meaning})"

            enhanced = re.sub(pattern, _replacer, enhanced, flags=re.IGNORECASE)

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
