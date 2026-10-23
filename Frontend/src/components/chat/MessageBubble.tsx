"use client";

import { useMemo, useState } from "react";
import { Message } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SHL } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  BookOpen,
  ExternalLink,
  Image as ImageIcon,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Eye,
  FileText,
} from "lucide-react";
import { buildDocumentReferenceUrl, sendFeedback, toAbsoluteApiUrl } from "@/lib/api";
import { getSmartFollowups } from "@/lib/followups";
import clsx from "clsx";

type NormalizedSource = {
  key: string;
  title: string;
  href: string;
};

interface MessageBubbleProps {
  msg: Message;
  /** Câu hỏi của người dùng mà tin nhắn này trả lời (dùng để chọn gợi ý) */
  question?: string;
  sessionId?: string;
  isLast?: boolean;
  onRegenerate?: () => void;
  onSuggestionClick?: (text: string) => void;
  onPreviewDocument?: (url: string, title: string) => void;
}

export default function MessageBubble({
  msg,
  question,
  sessionId,
  isLast,
  onRegenerate,
  onSuggestionClick,
  onPreviewDocument,
}: MessageBubbleProps) {
  const isUser = msg.role === "user";
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"like" | "dislike" | null>(null);

  const sources = useMemo(() => normalizeSources(msg.sources ?? []), [msg.sources]);

  const followups = useMemo(() => {
    if (isUser || msg.isStreaming || !msg.content || !isLast) return [];
    return getSmartFollowups(msg.content, question, sources.map((s) => s.title));
  }, [isUser, msg.isStreaming, msg.content, isLast, question, sources]);

  const imageUrls = useMemo(() => {
    if (!msg.images || msg.images.length === 0) return [];

    return msg.images
      .map((url) => {
        if (!url) return "";
        return toAbsoluteApiUrl(url);
      })
      .filter(Boolean);
  }, [msg.images]);

  const handleCopy = async () => {
    if (!msg.content) return;
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleFeedback = async (rating: "like" | "dislike") => {
    if (feedback === rating || !sessionId) return;
    setFeedback(rating);
    const numId = typeof msg.id === "number" ? msg.id : (msg.id ? parseInt(String(msg.id), 10) : undefined);
    await sendFeedback(sessionId, rating, Number.isFinite(numId) ? numId : undefined);
  };

  return (
    <div
      className={clsx(
        "flex gap-3 animate-fade-up w-full",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* --- AVATAR: chỉ hiện cho StudyBot (khiên TLU) --- */}
      {!isUser && (
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white border border-tlu-tint-2 flex items-center justify-center">
          <img src="/logo-tlu.png" alt="StudyBot" width={22} height={29} className="w-[22px] h-[29px] object-contain" />
        </div>
      )}

      {/* --- NỘI DUNG TIN NHẮN --- */}
      <div className={clsx("space-y-3 min-w-0", isUser ? "max-w-[80%] md:max-w-[72%]" : "flex-1 max-w-full")}>
        <div
          className={clsx(
            "text-[15px]",
            isUser
              ? "px-4 py-3 bg-tlu-blue text-white rounded-[18px] rounded-br-[4px]"
              : "px-5 py-4 md:px-[22px] md:py-5 bg-white text-slate-800 rounded-[18px] rounded-tl-[4px] border border-tlu-border"
          )}
        >
          {isUser ? (
            <div>
              {imageUrls.length > 0 && (
                <div className="mb-3 space-y-2">
                  <div className="grid gap-2">
                    {imageUrls.map((url, idx) => (
                      <Img
                        key={`${url}-${idx}`}
                        src={url}
                        alt={`Ảnh đã gửi ${idx + 1}`}
                        userImage
                      />
                    ))}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-white/80">
                    <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>Ảnh bạn đã gửi</span>
                  </div>
                </div>
              )}
              {msg.content?.trim() && (
                <p className="leading-relaxed whitespace-pre-wrap break-words">
                  {msg.content}
                </p>
              )}
            </div>
          ) : (
            <div>
              <MD content={msg.content} />

              {imageUrls.length > 0 && (
                <div className="mt-4 space-y-3">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-tlu-tint text-tlu-blue-dark text-xs font-semibold">
                    <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                    Ảnh liên quan
                  </span>

                  <div className="grid gap-3">
                    {imageUrls.map((url, idx) => (
                      <Img
                        key={`${url}-${idx}`}
                        src={url}
                        alt={`Hình minh họa ${idx + 1}`}
                        userImage={false}
                      />
                    ))}
                  </div>
                </div>
              )}

              {msg.isStreaming && (
                <span className="inline-block w-2.5 h-4 bg-tlu-blue animate-pulse ml-1 rounded-sm align-text-bottom" />
              )}
            </div>
          )}
        </div>

        {/* --- NGUỒN THAM KHẢO --- */}
        {!isUser && sources.length > 0 && (
          <section aria-label="Nguồn tham khảo" className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.06em] text-tlu-muted">
              <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Nguồn tham khảo</span>
            </div>

            <ul className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
              {sources.map((source) => (
                <li key={source.key} className="flex flex-col gap-1.5 p-3 rounded-xl border border-tlu-tint-2 bg-white min-w-0">
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-bold text-tlu-blue">
                    <FileText className="w-3.5 h-3.5" aria-hidden="true" />
                    {fileKind(source.title)}
                  </span>
                  <span className="text-[13px] font-semibold leading-snug text-tlu-ink break-words line-clamp-2" title={source.title}>
                    {prettySourceTitle(source.title)}
                  </span>
                  <div className="flex items-center gap-3 pt-0.5">
                    {onPreviewDocument && (
                      <button
                        onClick={() => onPreviewDocument(source.href, source.title)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-tlu-blue hover:text-tlu-blue-dark"
                      >
                        <Eye className="w-3.5 h-3.5" aria-hidden="true" />
                        Xem trước
                      </button>
                    )}
                    <a
                      href={source.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-tlu-muted hover:text-tlu-blue"
                      aria-label={`Mở ${source.title} trong tab mới`}
                    >
                      <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                      Mở
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* --- THANH CÔNG CỤ --- */}
        {!isUser && !msg.isStreaming && msg.content && (
          <div className="flex flex-wrap items-center gap-1 -ml-1">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 h-9 px-2.5 rounded-lg text-[13px] text-slate-600 hover:text-tlu-ink hover:bg-tlu-tint transition-colors"
              title="Sao chép câu trả lời"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-700" />
                  <span className="text-emerald-700 font-medium">Đã chép</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span>Sao chép</span>
                </>
              )}
            </button>

            <button
              onClick={() => handleFeedback("like")}
              className={clsx(
                "w-9 h-9 rounded-lg flex items-center justify-center transition-colors",
                feedback === "like" ? "text-tlu-blue bg-tlu-tint" : "text-slate-600 hover:text-tlu-blue hover:bg-tlu-tint"
              )}
              aria-label="Câu trả lời hữu ích"
              aria-pressed={feedback === "like"}
              title="Câu trả lời hữu ích"
            >
              <ThumbsUp className="w-4 h-4" />
            </button>

            <button
              onClick={() => handleFeedback("dislike")}
              className={clsx(
                "w-9 h-9 rounded-lg flex items-center justify-center transition-colors",
                feedback === "dislike" ? "text-tlu-red bg-red-50" : "text-slate-600 hover:text-tlu-red hover:bg-red-50"
              )}
              aria-label="Câu trả lời chưa chính xác"
              aria-pressed={feedback === "dislike"}
              title="Câu trả lời chưa chính xác"
            >
              <ThumbsDown className="w-4 h-4" />
            </button>

            {isLast && onRegenerate && (
              <button
                onClick={onRegenerate}
                className="inline-flex items-center gap-1.5 h-9 px-2.5 rounded-lg text-[13px] text-slate-600 hover:text-tlu-blue hover:bg-tlu-tint transition-colors"
                title="Tạo lại câu trả lời"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Tạo lại</span>
              </button>
            )}
          </div>
        )}

        {/* --- GỢI Ý CÂU HỎI TIẾP THEO --- */}
        {followups.length > 0 && onSuggestionClick && (
          <div className="flex flex-wrap gap-2 animate-fade-up" aria-label="Gợi ý câu hỏi tiếp theo">
            {followups.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(chip)}
                className="inline-flex items-center min-h-9 px-3.5 py-1.5 rounded-full border border-tlu-tint-2 bg-tlu-tint text-tlu-blue-dark text-[13px] font-medium text-left hover:bg-tlu-tint-2 transition-colors"
              >
                {chip}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Nhãn loại tài liệu theo đuôi file */
function fileKind(title: string) {
  const ext = (title.split(".").pop() || "").toLowerCase();
  if (ext === "pdf") return "PDF";
  if (ext === "docx" || ext === "doc") return "Văn bản Word";
  if (ext === "xlsx" || ext === "xls" || ext === "csv") return "Bảng tính";
  if (ext === "md") return "Thông báo";
  if (ext === "txt") return "Tóm tắt";
  return "Tài liệu";
}

/** Tên hiển thị gọn: bỏ đuôi file, thay gạch dưới bằng khoảng trắng */
function prettySourceTitle(title: string) {
  return title.replace(/\.(pdf|docx?|xlsx?|csv|md|txt)$/i, "").replace(/_/g, " ").trim() || title;
}

// ==========================================
// CÁC HÀM TIỆN ÍCH VÀ XỬ LÝ (Giữ nguyên logic gốc của bạn)
// ==========================================

function normalizeSources(rawSources: any[]): NormalizedSource[] {
  if (!Array.isArray(rawSources) || rawSources.length === 0) return [];

  const cleaned = rawSources
    .map((item) => {
      if (!item) return null;

      let title = "";
      if (typeof item === "string") {
        title = item;
      } else if (typeof item === "object") {
        title = item.title || item.name || item.filename || item.file_name || item.source || "";
      }

      const sanitizedTitle = sanitizeSourceTitle(title);
      if (!sanitizedTitle) return null;

      return {
        key: `${sanitizedTitle}-${buildDocumentReferenceUrl(sanitizedTitle)}`,
        title: sanitizedTitle,
        href: buildDocumentReferenceUrl(sanitizedTitle),
      };
    })
    .filter(Boolean) as NormalizedSource[];

  const deduped = new Map<string, NormalizedSource>();
  cleaned.forEach((source) => {
    if (!deduped.has(source.title)) {
      deduped.set(source.title, source);
    }
  });

  return Array.from(deduped.values());
}

function sanitizeSourceTitle(title: string) {
  if (!title) return "";
  let cleaned = String(title).trim();
  cleaned = cleaned
    .replace(/\[(BẢNG|TABLE|CONTEXT)\s*\d+\]/gi, "")
    .replace(/\[[^\]]*\]/g, "")
    .replace(/\(\s*Nguồn:\s*/gi, "")
    .replace(/\)\s*$/g, "")
    .replace(/^\s*Nguồn:\s*/gi, "")
    .replace(/^\s*Nguon:\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim().replace(/^,\s*/, "").replace(/,\s*$/, "").trim();
  if (!cleaned) return "";
  const badValues = new Set(["bảng", "context", "table", "nguồn", "nguon", "không rõ nguồn"]);
  if (badValues.has(cleaned.toLowerCase())) return "";
  if (/\.(png|jpg|jpeg|webp|gif|bmp)$/i.test(cleaned)) return "";
  return cleaned;
}

function MD({ content }: { content: string }) {
  const normalized = useMemo(() => normalizeBotMarkdown(content || ""), [content]);

  if (!normalized) return null;

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code({ inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const lang = match?.[1] || "";
          const code = String(children).replace(/\n$/, "");

          if (!inline && lang) {
            return (
              <div className="my-4 rounded-xl overflow-hidden border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between px-4 py-2 bg-slate-100 border-b border-slate-200">
                  <span className="text-xs text-slate-600 font-mono font-medium">{lang}</span>
                  <CopyBtn text={code} />
                </div>
                <SHL
                  style={oneDark}
                  language={lang}
                  PreTag="div"
                  customStyle={{ margin: 0, background: "#1e293b", fontSize: "0.85rem", lineHeight: "1.6", padding: "1rem" }}
                  {...props}
                >
                  {code}
                </SHL>
              </div>
            );
          }
          return (
            <code className="px-1.5 py-0.5 rounded bg-tlu-tint text-tlu-blue-dark border border-tlu-tint-2 text-[0.85em] font-mono">
              {children}
            </code>
          );
        },
        img({ src, alt }: any) {
          return <Img src={src || ""} alt={alt || "Hình minh họa"} userImage={false} />;
        },
        table: ({ children }) => (
          <div className="overflow-x-auto rounded-xl border border-tlu-border my-4">
            <table className="w-full text-sm text-left">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-tlu-tint text-tlu-blue-dark">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-4 py-2.5 font-semibold text-tlu-blue-dark align-top">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-4 py-2.5 border-t border-tlu-border text-slate-800 align-top whitespace-pre-wrap break-words">
            {children}
          </td>
        ),
        h1: ({ children }) => <h1 className="text-xl font-bold text-tlu-navy mt-6 mb-3">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-bold text-tlu-navy mt-5 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold text-slate-800 mt-4 mb-2">{children}</h3>,
        ul: ({ children }) => <ul className="list-disc list-outside ml-5 space-y-1.5 my-3 text-slate-700">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-outside ml-5 space-y-1.5 my-3 text-slate-700">{children}</ol>,
        li: ({ children }) => <li className="pl-1">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="pl-4 pr-3 py-2 my-4 text-slate-700 bg-tlu-tint rounded-lg">
            {children}
          </blockquote>
        ),
        p: ({ children }) => (
          <p className="my-2 leading-[1.65] text-slate-800 whitespace-pre-wrap break-words">
            {children}
          </p>
        ),
        strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
        em: ({ children }) => <em className="italic text-slate-600">{children}</em>,
        hr: () => <hr className="border-slate-200 my-5" />,
        a: ({ href, children }) => (
          <a
            href={href} target="_blank" rel="noopener noreferrer"
            className="text-tlu-blue font-medium hover:text-tlu-blue-dark underline underline-offset-2 transition-colors"
          >
            {children}
          </a>
        ),
      }}
    >
      {normalized}
    </ReactMarkdown>
  );
}

// CÁC HÀM KIỂM TRA & LỌC TEXT (Giữ nguyên gốc)
function isSeparatorRow(line: string) { return /^\|?[:\-|]+\|?$/.test(line.replace(/\s/g, "")); }
function countPipes(line: string) { return (line.match(/\|/g) || []).length; }
function looksLikeBrokenTableBlock(lines: string[], startIndex: number) {
  const first = lines[startIndex] || ""; const second = lines[startIndex + 1] || "";
  if (!first.trim().startsWith("|") || !second.trim().startsWith("|") || !isSeparatorRow(second)) return false;
  if (first.length > 300 || second.length > 300) return true;
  const hp = countPipes(first); const sp = countPipes(second);
  if (hp < 2 || sp < 2 || Math.abs(hp - sp) > 2) return true;
  for (let i = startIndex + 2; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim() || !line.trim().startsWith("|")) break;
    if (line.length > 500) return true;
    const p = countPipes(line);
    if (p < 2 || p > hp + 4) return true;
  }
  return false;
}
function isNoiseLine(line: string) {
  const t = line.toLowerCase().trim();
  return (!t || /\[context\s*\d+\]/i.test(line) || /\[bảng\s*\d+\]/i.test(line) || /\[table\s*\d+\]/i.test(line) || /^\(?\s*nguồn\s*:/i.test(t) || /^\(?\s*nguon\s*:/i.test(t) || /^\(\s*nguồn\s*:\s*.*\)\s*$/i.test(t) || /^\(\s*nguon\s*:\s*.*\)\s*$/i.test(t) || t === "(nguồn:)" || t === "(nguon:)" || t === "nguồn:" || t === "nguon:" || t.startsWith("dựa trên tài liệu") || t.startsWith("dựa trên context") || t.startsWith("theo context") || t.startsWith("theo tài liệu [context"));
}
function isMeaninglessRow(text: string) {
  const t = text.toLowerCase().replace(/[*_`\[\]]/g, "").replace(/\s+/g, " ").trim();
  const badRows = ["yêu cầu — chi tiết", "nội dung — chi tiết", "tiêu chí — chi tiết", "chi tiết — nội dung", "nội dung đánh giá — điểm tối đa — các tiêu chí cụ thể", "cách đạt chuẩn đầu ra công nghệ thông tin — chi tiết", "yêu cầu để đạt chuẩn đầu ra công nghệ thông tin — chi tiết", "điều kiện để được miễn thi — nội dung cụ thể"];
  return badRows.includes(t);
}
function convertBrokenTable(lines: string[], startIndex: number) {
  const out: string[] = []; let i = startIndex;
  while (i < lines.length) {
    const current = lines[i] || "";
    if (!current.trim()) { i++; break; }
    if (!current.trim().startsWith("|")) break;
    let cleaned = current.trim();
    if (cleaned.startsWith("|")) cleaned = cleaned.slice(1);
    if (cleaned.endsWith("|")) cleaned = cleaned.slice(0, -1);
    if (/^[:\-|]+$/.test(cleaned.replace(/\s/g, ""))) { i++; continue; }
    const parts = cleaned.split("|").map((part) => sanitizeInline(part)).filter(Boolean);
    if (parts.length >= 2) {
      const left = parts[0]; const right = parts.slice(1).join(" ").trim();
      const rowText = `${left} — ${right}`.trim();
      if (!isMeaninglessRow(rowText) && !isNoiseLine(rowText)) {
        out.push(`- **${left}**`);
        if (right) out.push(`  - ${right}`);
      }
    } else if (parts.length === 1) {
      const rowText = parts[0].trim();
      if (!isMeaninglessRow(rowText) && !isNoiseLine(rowText)) out.push(`- ${rowText}`);
    }
    i++;
  }
  return { out, nextIndex: i };
}
function sanitizeInline(text: string) {
  return text.replace(/\[DONE\]/g, "").replace(/\[CONTENT\]/g, "").replace(/\[CONTEXT\s*\d+\]/gi, "").replace(/\[BẢNG\s*\d+\]/gi, "").replace(/\[TABLE\s*\d+\]/gi, "").replace(/^\s*\(?\s*Nguồn\s*:[^\n]*\)?\s*$/gim, "").replace(/^\s*\(?\s*Nguon\s*:[^\n]*\)?\s*$/gim, "").replace(/<br\s*\/?>/gi, "\n- ").replace(/\s+/g, " ").trim();
}
// Ô bảng GFM không chứa được xuống dòng: đổi <br> trong dòng bảng thành "• ý 1 • ý 2"
// trước khi <br> còn lại bị đổi thành "\n" (nếu không dòng bảng bị cắt đôi).
// Cùng quy tắc với _join_cell_breaks ở Backend (chat_formatters.py).
function joinTableCellBreaks(text: string) {
  if (!/<br/i.test(text)) return text;
  return text.split("\n").map((line) => {
    if (!line.trim().startsWith("|")) return line;
    return line
      .replace(/\s*<br\s*\/?>\s*(?:[-*•]\s+)?/gi, " • ")
      .replace(/\|\s*[-*]\s+(?=[^|]*•)/g, "| • ");
  }).join("\n");
}
function normalizeBrokenMarkdownTables(text: string) {
  const lines = text.split("\n"); const out: string[] = []; let i = 0;
  while (i < lines.length) {
    const line = lines[i] || ""; const next = lines[i + 1] || "";
    if (!(line.trim().startsWith("|") && next.trim().startsWith("|") && isSeparatorRow(next))) {
      out.push(line); i++; continue;
    }
    if (!looksLikeBrokenTableBlock(lines, i)) { out.push(line); i++; continue; }
    const converted = convertBrokenTable(lines, i);
    out.push(...converted.out); i = converted.nextIndex;
  }
  return out.join("\n");
}
function convertDashRowsToMarkdown(text: string) {
  const lines = text.split("\n"); const out: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { out.push(""); continue; }
    if (isNoiseLine(line)) continue;
    const cleaned = line.replace(/^\d+\.\s*/, "").trim();
    if (cleaned.includes(" — ")) {
      const [left, ...rest] = cleaned.split(" — ");
      const title = left.trim(); const detail = rest.join(" — ").trim();
      if (title) out.push(`- **${title}**`);
      if (detail) {
        detail.replace(/<br\s*\/?>/gi, "\n- ").split("\n").map(x => x.trim()).filter(Boolean).forEach(d => {
          const normalized = d.replace(/^-+\s*/, "").trim();
          if (normalized) out.push(`  - ${normalized}`);
        });
      }
      continue;
    }
    out.push(cleaned);
  }
  return out.join("\n");
}
function dedupeLines(text: string) {
  const lines = text.split("\n"); const out: string[] = []; const seen = new Set<string>();
  for (const raw of lines) {
    const line = raw.trimRight(); const key = line.trim().toLowerCase().replace(/\s+/g, " ");
    if (!key) { if (out.length > 0 && out[out.length - 1] !== "") out.push(""); continue; }
    if (seen.has(key)) continue;
    seen.add(key); out.push(line);
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
function normalizeBotMarkdown(text: string) {
  if (!text) return "";
  
  // Dọn dẹp các mã code rác sinh ra từ API nếu có
  let cleaned = joinTableCellBreaks(text.replace(/\r\n/g, "\n"))
    .replace(/\[DONE\]/g, "")
    .replace(/\[CONTENT\]/g, "")
    .replace(/\[CONTEXT\s*\d+\]/gi, "")
    .replace(/\[BẢNG\s*\d+\]/gi, "")
    .replace(/\[TABLE\s*\d+\]/gi, "")
    .replace(/^\s*\(?\s*Nguồn\s*:[^\n]*\)?\s*$/gim, "")
    .replace(/^\s*\(?\s*Nguon\s*:[^\n]*\)?\s*$/gim, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/[ \t]+\n/g, "\n");

  cleaned = normalizeBrokenMarkdownTables(cleaned);
  cleaned = convertDashRowsToMarkdown(cleaned);

  // ĐÃ SỬA LỖI CẮT CHỮ: Bỏ hoàn toàn việc lọc isNoiseLine và dedupeLines 
  // vì nó chính là nguyên nhân xóa nhầm các đoạn chữ đang stream từ bot.
  return cleaned.trim();
}

// ==========================================
// CÁC COMPONENT PHỤ TRỢ
// ==========================================

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="text-xs text-slate-600 hover:text-tlu-blue font-medium transition-colors bg-white px-2 py-1 rounded border border-tlu-border"
    >
      {copied ? "✓ Đã copy" : "Copy"}
    </button>
  );
}

function Img({ src, alt, userImage = false }: { src: string; alt: string; userImage?: boolean }) {
  const [err, setErr] = useState(false);
  const [loaded, setLoaded] = useState(false);

  if (err) {
    return (
      <div className="my-2 rounded-xl border border-tlu-border bg-tlu-ground p-5 text-center text-slate-600">
        <ImageIcon className="w-6 h-6 mx-auto mb-2 text-tlu-muted" aria-hidden="true" />
        <p className="text-xs">Không tải được ảnh: {alt}</p>
      </div>
    );
  }

  return (
    <figure className="my-3 relative">
      {!loaded && (
        <div className="rounded-xl bg-tlu-tint border border-tlu-border animate-pulse w-full" style={{ height: "200px" }} />
      )}
      <img
        src={src}
        alt={alt}
        onError={() => setErr(true)}
        onLoad={() => setLoaded(true)}
        loading="lazy"
        className={clsx(
          "rounded-xl w-full border border-tlu-border transition-opacity duration-300",
          loaded ? "opacity-100" : "opacity-0 absolute top-0 left-0",
          userImage ? "object-contain bg-white" : "object-cover"
        )}
        style={{ maxHeight: "400px" }}
      />
      {alt && loaded && !userImage && (
        <figcaption className="text-xs text-tlu-muted text-center mt-2">
          {alt}
        </figcaption>
      )}
    </figure>
  );
}
