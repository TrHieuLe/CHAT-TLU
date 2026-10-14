import re
import secrets

from fastapi import Header, HTTPException, Query, Request

from app.core.config import settings

# UUID do trình duyệt sinh, mã SV, hoặc fallback "user_xxx" — chặn chuỗi lạ/quá dài
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")


def get_current_user_id(
    request: Request,
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    user_id: str | None = Query(None),
) -> str:
    """
    Lấy ID người dùng (Guest Token UUID hoặc ID sinh viên đã đăng nhập).
    Thứ tự ưu tiên:
      1. Header `X-User-ID`
      2. Query param `user_id`
      3. Fallback: "default_user"

    Lưu ý: đây là mô hình guest token — ID do client tự sinh, không có xác thực.
    Chỉ kiểm tra định dạng để chặn dữ liệu rác.
    """
    for candidate in (x_user_id, user_id):
        if candidate and candidate.strip():
            uid = candidate.strip()
            if not _USER_ID_RE.match(uid):
                raise HTTPException(status_code=400, detail="User ID không hợp lệ")
            return uid
    return "default_user"


def require_admin(x_admin_key: str | None = Header(None, alias="X-Admin-Key")) -> None:
    """
    Bảo vệ endpoint quản trị (upload/xóa tài liệu, crawler, cache, perf).
    - ADMIN_AUTH_DISABLED=true: bỏ qua kiểm tra (chỉ dùng cho test/dev).
    - Chưa đặt ADMIN_API_KEY: từ chối (503) để không vô tình mở endpoint khi deploy.
    """
    if settings.ADMIN_AUTH_DISABLED:
        return
    expected = settings.ADMIN_API_KEY
    if not expected:
        raise HTTPException(status_code=503, detail="Server chưa cấu hình ADMIN_API_KEY")
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="Thiếu admin key")
    if not secrets.compare_digest(x_admin_key.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Admin key không đúng")
