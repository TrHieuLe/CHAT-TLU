/**
 * Quản lý định danh người dùng ẩn danh (Anonymous Guest ID).
 * Tự động tạo UUID duy nhất lưu vào localStorage của trình duyệt,
 * giúp phân tách hoàn toàn dữ liệu giữa các sinh viên khi chạy trên Cloud/Vercel.
 */

const USER_ID_KEY = "studybot_user_id";

export function getUserId(): string {
  if (typeof window === "undefined") {
    return "server_rendered";
  }

  try {
    let uid = localStorage.getItem(USER_ID_KEY);
    if (!uid || uid.trim() === "") {
      // Sinh UUIDv4 duy nhất cho thiết bị / trình duyệt
      uid = typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "user_" + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
      localStorage.setItem(USER_ID_KEY, uid);
    }
    return uid;
  } catch {
    return "guest_fallback";
  }
}
