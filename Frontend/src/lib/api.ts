export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSource {
  id?: string | number;
  title?: string;
  name?: string;
  filename?: string;
  file_name?: string;
  source?: string;
}

export interface ImageChatResponse {
  ok: boolean;
  answer: string;
  image_url?: string;
  sources?: ChatSource[];
}

export function toAbsoluteApiUrl(path: string) {
  if (!path) return "";
  if (path.startsWith("blob:")) return path;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
}

import { getUserId } from "./user";

export function trimDocumentExtension(filename: string) {
  return filename.trim().replace(/\s*\.[^.]+$/, "").trim();
}

export function buildDocumentReferenceUrl(sourceName: string) {
  const filename = trimDocumentExtension(sourceName);
  return `${API_BASE}/api/document/reference/${encodeURIComponent(filename)}`;
}

export async function createSession(): Promise<ChatSession> {
  const r = await fetch(`${API_BASE}/api/sessions/`, {
    method: "POST",
    headers: { "X-User-ID": getUserId() },
  });
  if (!r.ok) throw new Error("Không tạo được session");
  return r.json();
}

export async function getSessions(): Promise<ChatSession[]> {
  const r = await fetch(`${API_BASE}/api/sessions/`, {
    headers: { "X-User-ID": getUserId() },
  });
  if (!r.ok) return [];
  return r.json();
}

export async function getHistory(sid: string) {
  const r = await fetch(`${API_BASE}/api/sessions/${sid}/history`, {
    headers: { "X-User-ID": getUserId() },
  });
  if (!r.ok) return [];
  return r.json();
}

export async function deleteSession(sid: string) {
  await fetch(`${API_BASE}/api/sessions/${sid}`, {
    method: "DELETE",
    headers: { "X-User-ID": getUserId() },
  });
}

export async function renameSession(sid: string, title: string): Promise<{ id: string; title: string }> {
  const r = await fetch(`${API_BASE}/api/sessions/${sid}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": getUserId(),
    },
    body: JSON.stringify({ title }),
  });
  if (!r.ok) throw new Error("Không đổi tên được session");
  return r.json();
}

export function getSessionExportUrl(sid: string, format: "markdown" | "json" = "markdown") {
  return `${API_BASE}/api/sessions/${sid}/export?format=${format}&user_id=${encodeURIComponent(getUserId())}`;
}

export async function sendFeedback(
  sessionId: string,
  rating: "like" | "dislike",
  messageId?: number,
  comment?: string
) {
  const r = await fetch(`${API_BASE}/api/chat/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-ID": getUserId(),
    },
    body: JSON.stringify({
      session_id: sessionId,
      message_id: messageId,
      rating,
      comment,
    }),
  });
  return r.ok;
}

export async function uploadImage(
  sessionId: string,
  file: File,
  question?: string
): Promise<ImageChatResponse> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("image", file);
  if (question?.trim()) form.append("question", question.trim());

  const r = await fetch(`${API_BASE}/api/chat/image`, {
    method: "POST",
    headers: { "X-User-ID": getUserId() },
    body: form,
  });

  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(text || "Không gửi được ảnh lên backend");
  }

  return r.json();
}

export async function streamChat(
  sessionId: string,
  question: string,
  onChunk: (t: string) => void,
  onSources: (s: ChatSource[]) => void,
  onDone: () => void,
  onError: (e: string) => void,
  onImages?: (urls: string[]) => void
) {
  let r: Response;
  try {
    r = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": getUserId(),
      },
      body: JSON.stringify({ session_id: sessionId, question }),
    });
  } catch {
    onError("Không kết nối được backend. Kiểm tra FastAPI port 8000.");
    return;
  }

  if (!r.ok || !r.body) {
    onError(`Lỗi server ${r.status}`);
    return;
  }

  const reader = r.body.getReader();
  const dec = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += dec.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data: ")) continue;

      const data = line.slice(6);

      if (data === "[DONE]") {
        onDone();
        return;
      }

      if (data.startsWith("[SOURCES]")) {
        try {
          onSources(JSON.parse(data.slice(9)));
        } catch {}
        continue;
      }

      if (data.startsWith("[IMAGES]")) {
        try {
          const urls: string[] = JSON.parse(data.slice(8));
          if (onImages && urls.length > 0) onImages(urls);
        } catch {}
        continue;
      }

      // Backend gửi delta dưới dạng JSON string (json.dumps) để newline không
      // phá vỡ SSE protocol. Parse ở đây để khôi phục đúng \n, tab, unicode.
      try {
        onChunk(JSON.parse(data));
      } catch {
        // Fallback cho backend cũ gửi text thô với \n escaped
        onChunk(data.replace(/\\n/g, "\n"));
      }
    }
  }

  onDone();
}

import type { DocumentItem, DocumentStats, UserMemoryItem, CrawlerStatus } from "./types";

export async function getDocuments(): Promise<DocumentItem[]> {
  try {
    const r = await fetch(`${API_BASE}/api/document/list`);
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

export async function getDocumentStats(): Promise<DocumentStats | null> {
  try {
    const r = await fetch(`${API_BASE}/api/document/stats`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export async function uploadDocument(file: File): Promise<{ ok: boolean; message?: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("auto", "true");

  try {
    const r = await fetch(`${API_BASE}/api/document/upload`, {
      method: "POST",
      body: form,
    });
    if (!r.ok) {
      const text = await r.text().catch(() => "");
      return { ok: false, message: text || `Lỗi tải lên (${r.status})` };
    }
    return { ok: true };
  } catch (err: any) {
    return { ok: false, message: err?.message || "Lỗi kết nối máy chủ" };
  }
}

export async function deleteDocument(docId: string): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/api/document/${docId}`, {
      method: "DELETE",
    });
    return r.ok;
  } catch {
    return false;
  }
}

export async function getUserMemories(): Promise<UserMemoryItem[]> {
  try {
    const r = await fetch(`${API_BASE}/api/memory/`, {
      headers: { "X-User-ID": getUserId() },
    });
    if (!r.ok) return [];
    return await r.json();
  } catch {
    return [];
  }
}

export async function deleteUserMemory(key: string): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/api/memory/${encodeURIComponent(key)}`, {
      method: "DELETE",
      headers: { "X-User-ID": getUserId() },
    });
    return r.ok;
  } catch {
    return false;
  }
}

export async function clearAllUserMemories(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/api/memory/`, {
      method: "DELETE",
      headers: { "X-User-ID": getUserId() },
    });
    return r.ok;
  } catch {
    return false;
  }
}

export async function triggerCrawler(maxArticles: number = 5): Promise<{
  ok: boolean;
  message?: string;
  crawled_count?: number;
  articles?: any[];
}> {
  try {
    const r = await fetch(`${API_BASE}/api/crawler/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_articles: maxArticles }),
    });
    return await r.json();
  } catch (err: any) {
    return { ok: false, message: err?.message || "Lỗi kết nối máy chủ khi cào dữ liệu" };
  }
}

export async function getCrawlerStatus(): Promise<CrawlerStatus | null> {
  try {
    const r = await fetch(`${API_BASE}/api/crawler/status`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}


