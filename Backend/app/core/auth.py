from fastapi import Header, Query, Request


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
    """
    if x_user_id and x_user_id.strip():
        return x_user_id.strip()
    if user_id and user_id.strip():
        return user_id.strip()
    return "default_user"
