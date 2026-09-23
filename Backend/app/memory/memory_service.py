import logging
import re
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import UserMemory

logger = logging.getLogger(__name__)

# Từ điển ánh xạ Khoa tại Đại học Thủy Lợi
TLU_FACULTIES = {
    "cntt": "Công nghệ thông tin",
    "công nghệ thông tin": "Công nghệ thông tin",
    "kinh tế": "Kinh tế và Quản lý",
    "kinh te": "Kinh tế và Quản lý",
    "cơ khí": "Cơ khí",
    "co khi": "Cơ khí",
    "công trình": "Kỹ thuật Công trình",
    "xây dựng": "Kỹ thuật Công trình",
    "thủy điện": "Kỹ thuật Tài nguyên nước",
    "tài nguyên nước": "Kỹ thuật Tài nguyên nước",
    "môi trường": "Hóa và Môi trường",
    "điện": "Điện - Điện tử",
    "điện tử": "Điện - Điện tử",
}

# Từ điển ánh xạ Ngành phổ biến tại TLU
TLU_MAJORS = {
    "ktpm": "Kỹ thuật phần mềm",
    "kỹ thuật phần mềm": "Kỹ thuật phần mềm",
    "khmt": "Khoa học máy tính",
    "khoa học máy tính": "Khoa học máy tính",
    "httt": "Hệ thống thông tin",
    "hệ thống thông tin": "Hệ thống thông tin",
    "cntt": "Công nghệ thông tin",
    "an ninh mạng": "An toàn thông tin",
    "an toàn thông tin": "An toàn thông tin",
    "trí tuệ nhân tạo": "Trí tuệ nhân tạo & Khoa học dữ liệu",
    "ai": "Trí tuệ nhân tạo & Khoa học dữ liệu",
    "quản trị kinh doanh": "Quản trị kinh doanh",
    "qtkd": "Quản trị kinh doanh",
    "kế toán": "Kế toán",
    "kinh tế xây dựng": "Kinh tế xây dựng",
    "tài chính ngân hàng": "Tài chính ngân hàng",
    "logistics": "Logistics và Quản lý chuỗi cung ứng",
}


def extract_student_profile(text: str) -> dict[str, str]:
    """
    Trích xuất thực thể hồ sơ sinh viên bằng Rule-based Regex tốc độ cao (0ms),
    không làm chậm luồng chat và không tốn chi phí gọi LLM.
    """
    profile: dict[str, str] = {}
    lower = text.lower()

    # 1. Nhận diện Khóa sinh viên (vd: K63, K64, K65, khóa 64, khoá 65)
    cohort_match = re.search(r"\b(?:k|khóa|khoá)\s*(\d{2})\b", lower)
    if cohort_match:
        profile["khoa_hoc"] = f"K{cohort_match.group(1)}"

    # 2. Nhận diện Khoa
    faculty_match = re.search(r"\bkhoa\s+([a-zA-Zà-ỹÀ-Ỹ\s]+?)(?:,|\.|\n|$|\bngành|\blớp)", lower)
    if faculty_match:
        cand = faculty_match.group(1).strip()
        for k, name in TLU_FACULTIES.items():
            if k in cand:
                profile["khoa"] = name
                break

    # 3. Nhận diện Ngành học
    major_match = re.search(r"\b(?:ngành|chuyên ngành)\s+([a-zA-Zà-ỹÀ-Ỹ\s]+?)(?:,|\.|\n|$|\bkhoa|\blớp)", lower)
    if major_match:
        cand = major_match.group(1).strip()
        for k, name in TLU_MAJORS.items():
            if k in cand:
                profile["nganh"] = name
                break

    # Nếu trực tiếp nói "tôi học ktpm", "mình học cntt"
    if "nganh" not in profile:
        for k, name in TLU_MAJORS.items():
            if re.search(rf"\bhọc\s+{re.escape(k)}\b", lower):
                profile["nganh"] = name
                break

    # 4. Nhận diện Mục tiêu CPA / Điểm số
    cpa_match = re.search(r"\b(?:mục tiêu|target|cần|muốn)\s*(?:cpa|gpa|điểm)\s*(?:là|khoảng|đạt)?\s*([1-4](?:\.\d{1,2})?)\b", lower)
    if cpa_match:
        profile["muc_tieu_cpa"] = cpa_match.group(1)

    # 5. Nhận diện Môn nợ / Cần học lại / Cải thiện
    retake_match = re.search(r"\b(?:nợ môn|học lại môn|thi lại môn|trượt môn)\s+([a-zA-Zà-ỹÀ-Ỹ0-9\s]+?)(?:,|\.|\n|$|\bcần|\bđể|\bvới)", lower)
    if retake_match:
        profile["mon_can_cai_thien"] = retake_match.group(1).strip().title()

    return profile


async def update_user_memories(
    user_id: str,
    text: str,
    db: AsyncSession,
) -> int:
    """
    Cổng vào (Input Gate): Trích xuất thực thể và cập nhật trạng thái tế bào nhớ (Cell State)
    vào SQLite cho user_id tương ứng.
    """
    if not user_id or user_id == "default_user":
        return 0

    extracted = extract_student_profile(text)
    if not extracted:
        return 0

    count = 0
    now = datetime.now(timezone.utc)

    for key, val in extracted.items():
        res = await db.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
            )
        )
        existing = res.scalar_one_or_none()

        if existing:
            existing.value = val
            existing.updated_at = now
        else:
            new_mem = UserMemory(
                user_id=user_id,
                key=key,
                value=val,
                confidence=1.0,
                created_at=now,
                updated_at=now,
            )
            db.add(new_mem)
        count += 1

    try:
        await db.commit()
    except Exception as e:
        logger.warning("Không thể lưu bộ nhớ cho %s: %s", user_id, e)

    return count


async def get_user_cell_state_prompt(user_id: str, db: AsyncSession) -> str:
    """
    Cổng ra (Output Gate): Đọc trạng thái tế bào nhớ của sinh viên và chuyển thành
    đoạn chỉ dẫn ngữ cảnh để tiêm (inject) vào System Instruction của mô hình.
    """
    if not user_id or user_id == "default_user":
        return ""

    res = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc())
    )
    memories = res.scalars().all()
    if not memories:
        return ""

    key_labels = {
        "khoa_hoc": "Khóa học",
        "khoa": "Khoa",
        "nganh": "Ngành học",
        "muc_tieu_cpa": "Mục tiêu điểm CPA",
        "mon_can_cai_thien": "Môn cần học lại/cải thiện",
    }

    lines = ["[HỒ SƠ & NGỮ CẢNH DÀI HẠN CỦA SINH VIÊN (GHI NHỚ XUYÊN SUỐT CÁC PHIÊN)]:"]
    for m in memories:
        lbl = key_labels.get(m.key, m.key)
        lines.append(f"- {lbl}: {m.value}")

    lines.append(
        "-> HÃY SỬ DỤNG THÔNG TIN TRÊN để cá nhân hóa câu trả lời (đúng chương trình đào tạo, niên khóa, quy chế áp dụng) mà không bắt sinh viên phải khai báo lại."
    )
    return "\n".join(lines)
