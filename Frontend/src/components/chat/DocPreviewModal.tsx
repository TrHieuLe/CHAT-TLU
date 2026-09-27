"use client";

import React, { useState, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  X,
  ExternalLink,
  Download,
  FileText,
  FileCode,
  FileSpreadsheet,
  Loader2,
  Copy,
  Check,
  BookOpen,
  AlertCircle,
  Maximize2,
  Minimize2,
  Search,
} from "lucide-react";
import { getDocumentTextPreview, DocumentTextPreview } from "@/lib/api";

interface DocPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  docUrl: string;
}

export default function DocPreviewModal({
  isOpen,
  onClose,
  title,
  docUrl,
}: DocPreviewModalProps) {
  const [loading, setLoading] = useState(true);
  const [previewData, setPreviewData] = useState<DocumentTextPreview | null>(null);
  const [copied, setCopied] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Nhận diện loại file
  const lowerTitle = (title || "").toLowerCase();
  const isPdf = lowerTitle.endsWith(".pdf");
  const isDocx = lowerTitle.endsWith(".docx") || lowerTitle.endsWith(".doc");
  const isExcel =
    lowerTitle.endsWith(".xlsx") ||
    lowerTitle.endsWith(".xls") ||
    lowerTitle.endsWith(".csv");
  const isText =
    lowerTitle.endsWith(".txt") ||
    lowerTitle.endsWith(".md") ||
    lowerTitle.endsWith(".json");

  useEffect(() => {
    if (!isOpen) {
      setPreviewData(null);
      setLoading(true);
      setLoadError(false);
      setSearchQuery("");
      return;
    }

    setLoading(true);
    setLoadError(false);
    setSearchQuery("");

    // Đối với DOCX, Excel, TXT, MD hoặc file không phải PDF: Tải nội dung text trích xuất từ server
    if (isDocx || isExcel || isText || !isPdf) {
      getDocumentTextPreview(title)
        .then((data) => {
          if (data && data.ok) {
            setPreviewData(data);
          } else {
            setPreviewData(null);
          }
        })
        .catch(() => setLoadError(true))
        .finally(() => setLoading(false));
    } else {
      // Đối với PDF: Loading được quản lý qua sự kiện onLoad của iframe
      setLoading(true);
    }
  }, [isOpen, title, isPdf, isDocx, isExcel, isText]);

  if (!isOpen) return null;

  const handleCopyText = async () => {
    if (!previewData?.content) return;
    try {
      await navigator.clipboard.writeText(previewData.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  const renderFileIcon = () => {
    if (isPdf) return <FileText className="w-5 h-5 text-red-600" />;
    if (isDocx) return <FileText className="w-5 h-5 text-blue-600" />;
    if (isExcel) return <FileSpreadsheet className="w-5 h-5 text-emerald-600" />;
    if (isText) return <FileCode className="w-5 h-5 text-emerald-600" />;
    return <FileSpreadsheet className="w-5 h-5 text-amber-600" />;
  };

  const getFormatBadge = () => {
    if (isPdf) return "Tài liệu PDF";
    if (isDocx) return "Văn bản Word (.docx)";
    if (isExcel) return "Bảng tính Excel (.xlsx / .csv)";
    if (isText) return "Tệp văn bản (.txt / .md)";
    return "Tài liệu tham khảo";
  };

  // Đếm kết quả tìm kiếm
  const matchCount = useMemo(() => {
    if (!searchQuery.trim() || !previewData?.content) return 0;
    try {
      const regex = new RegExp(searchQuery.trim(), "gi");
      const matches = previewData.content.match(regex);
      return matches ? matches.length : 0;
    } catch {
      return 0;
    }
  }, [searchQuery, previewData?.content]);

  const renderHighlightedNode = (node: React.ReactNode): React.ReactNode => {
    if (!searchQuery.trim() || typeof node !== "string") return node;
    try {
      const parts = node.split(
        new RegExp(`(${searchQuery.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")
      );
      return parts.map((part, i) =>
        part.toLowerCase() === searchQuery.trim().toLowerCase() ? (
          <mark key={i} className="bg-yellow-300 text-slate-900 rounded-xs px-0.5 font-medium">
            {part}
          </mark>
        ) : (
          part
        )
      );
    } catch {
      return node;
    }
  };

  const renderHighlightedText = (text: string) => {
    if (!searchQuery.trim()) return text;
    try {
      const parts = text.split(new RegExp(`(${searchQuery.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
      return parts.map((part, i) =>
        part.toLowerCase() === searchQuery.trim().toLowerCase() ? (
          <mark key={i} className="bg-yellow-300 text-slate-900 rounded-xs px-0.5 font-medium">
            {part}
          </mark>
        ) : (
          part
        )
      );
    } catch {
      return text;
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center ${
        isFullscreen ? "p-0" : "p-3 sm:p-4"
      } bg-slate-900/60 backdrop-blur-sm animate-fade-in`}
      onClick={onClose}
    >
      <div
        className={`relative ${
          isFullscreen ? "w-full h-full rounded-none" : "w-full max-w-5xl h-[88vh] rounded-2xl"
        } bg-white shadow-2xl flex flex-col overflow-hidden border border-slate-200 transition-all duration-200`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-200 bg-slate-50 gap-2">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="p-2 rounded-xl bg-white shadow-xs border border-slate-200 flex-shrink-0">
              {renderFileIcon()}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm sm:text-base font-semibold text-slate-800 truncate" title={title}>
                {title}
              </h3>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1 font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md border border-blue-100">
                  {getFormatBadge()}
                </span>
                <span className="hidden sm:inline">• Đại học Thủy lợi (TLU)</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
            {previewData?.content && (
              <button
                onClick={handleCopyText}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors border border-slate-200 bg-white"
                title="Sao chép nội dung văn bản"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="hidden sm:inline text-emerald-600">Đã chép</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Sao chép</span>
                  </>
                )}
              </button>
            )}

            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 rounded-lg transition-colors"
              title={isFullscreen ? "Thu nhỏ lại" : "Mở rộng toàn màn hình"}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <a
              href={docUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors border border-slate-200 bg-white"
              title="Mở trong tab mới"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Mở tab mới</span>
            </a>

            <a
              href={docUrl}
              download
              className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-xs"
              title="Tải về máy tính"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Tải về</span>
            </a>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-lg transition-colors ml-1"
              title="Đóng cửa sổ"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search Bar for Text/Docx */}
        {!isPdf && previewData?.content && (
          <div className="flex items-center justify-between px-4 sm:px-6 py-2 bg-slate-100/80 border-b border-slate-200 text-xs">
            <div className="flex items-center gap-2 flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm từ khóa trong văn bản..."
                className="w-full bg-white px-2.5 py-1 rounded-md border border-slate-200 outline-none focus:border-blue-400 text-slate-700"
              />
            </div>
            {searchQuery.trim() && (
              <span className="text-slate-500 font-medium ml-3">
                {matchCount > 0 ? `Tìm thấy ${matchCount} kết quả` : "Không tìm thấy kết quả"}
              </span>
            )}
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 bg-slate-100 relative overflow-hidden flex flex-col">
          {/* PDF Viewer */}
          {isPdf ? (
            <div className="w-full h-full relative">
              {loading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-50 z-10 gap-3">
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                  <p className="text-sm font-medium text-slate-600">Đang tải tài liệu PDF...</p>
                </div>
              )}
              <iframe
                src={docUrl}
                title={title}
                className="w-full h-full border-0"
                onLoad={() => setLoading(false)}
                onError={() => {
                  setLoading(false);
                  setLoadError(true);
                }}
              />
            </div>
          ) : (
            /* Word & Text Reader */
            <div className="flex-1 overflow-y-auto p-4 sm:p-8 bg-slate-50">
              {loading ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 py-20">
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                  <p className="text-sm font-medium text-slate-600">Đang chuẩn bị nội dung tài liệu...</p>
                </div>
              ) : previewData?.content ? (
                <div className="max-w-4xl mx-auto bg-white p-6 sm:p-10 rounded-2xl shadow-sm border border-slate-200">
                  <div className="mb-6 pb-4 border-b border-slate-100 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
                      <BookOpen className="w-4 h-4 text-blue-600" />
                      <span>Nội dung văn bản quy chế</span>
                    </div>
                    {previewData.file_size > 0 && (
                      <span className="text-xs text-slate-400">
                        Kích thước: {(previewData.file_size / 1024).toFixed(1)} KB
                      </span>
                    )}
                  </div>

                  <div className="prose prose-slate max-w-none text-sm sm:text-base leading-relaxed">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ children }) => (
                          <h1 className="text-xl font-bold text-slate-900 mt-6 mb-3 border-b border-slate-200 pb-2">
                            {React.Children.map(children, renderHighlightedNode)}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-lg font-bold text-slate-900 mt-5 mb-2 border-l-4 border-blue-600 pl-3 bg-blue-50/50 py-1 rounded-r">
                            {React.Children.map(children, renderHighlightedNode)}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-base font-semibold text-slate-800 mt-4 mb-2">
                            {React.Children.map(children, renderHighlightedNode)}
                          </h3>
                        ),
                        p: ({ children }) => {
                          const textStr =
                            typeof children === "string"
                              ? children
                              : Array.isArray(children) && typeof children[0] === "string"
                              ? children[0]
                              : "";
                          const isArticleHeader =
                            /^(Điều\s+\d+|Chương\s+[IVXLCDM\d]+|Mục\s+\d+|Phần\s+[IVXLCDM\d]+|QUYẾT ĐỊNH)/i.test(
                              textStr.trim()
                            );

                          if (isArticleHeader) {
                            return (
                              <div className="mt-6 pt-3 pb-1 border-l-4 border-blue-600 pl-3 font-bold text-slate-900 text-base sm:text-lg bg-blue-50/50 rounded-r-lg mb-3">
                                {React.Children.map(children, renderHighlightedNode)}
                              </div>
                            );
                          }
                          return (
                            <p className="text-slate-700 mb-3 whitespace-pre-wrap font-sans leading-relaxed">
                              {React.Children.map(children, renderHighlightedNode)}
                            </p>
                          );
                        },
                        table: ({ children }) => (
                          <div className="my-5 overflow-x-auto rounded-xl border border-slate-200 shadow-xs bg-white">
                            <table className="min-w-full divide-y divide-slate-200 text-left text-xs sm:text-sm">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-slate-100 font-semibold text-slate-700 border-b border-slate-200">
                            {children}
                          </thead>
                        ),
                        th: ({ children }) => (
                          <th className="px-3.5 py-2.5 font-semibold text-slate-800 border-b border-slate-200 bg-slate-50 whitespace-nowrap">
                            {React.Children.map(children, renderHighlightedNode)}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="px-3.5 py-2.5 text-slate-600 border-b border-slate-100 align-top">
                            {React.Children.map(children, renderHighlightedNode)}
                          </td>
                        ),
                        tr: ({ children }) => (
                          <tr className="hover:bg-blue-50/40 transition-colors odd:bg-white even:bg-slate-50/40">
                            {children}
                          </tr>
                        ),
                      }}
                    >
                      {previewData.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ) : (
                /* Fallback download card if text extraction isn't available */
                <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-16">
                  <div className="p-4 rounded-2xl bg-blue-50 border border-blue-100 text-blue-600">
                    {renderFileIcon()}
                  </div>
                  <div className="max-w-md">
                    <h4 className="text-base font-semibold text-slate-800 mb-1">{title}</h4>
                    <p className="text-xs text-slate-500 mb-6 leading-relaxed">
                      Tài liệu này được lưu trữ dưới định dạng {getFormatBadge()}. Bạn có thể tải về trực tiếp để mở bằng ứng dụng trên máy tính.
                    </p>
                    <a
                      href={docUrl}
                      download
                      className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-sm transition-all"
                    >
                      <Download className="w-4 h-4" />
                      <span>Tải tài liệu về máy</span>
                    </a>
                  </div>
                </div>
              )}
            </div>
          )}

          {loadError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-white z-20 gap-3 p-6 text-center">
              <AlertCircle className="w-10 h-10 text-amber-500" />
              <h4 className="text-base font-semibold text-slate-800">Không thể xem trực tiếp</h4>
              <p className="text-xs text-slate-500 max-w-sm">
                Trình duyệt không hỗ trợ xem trực tiếp định dạng này hoặc có sự cố mạng. Vui lòng tải file về máy.
              </p>
              <a
                href={docUrl}
                download
                className="mt-2 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Tải tài liệu về</span>
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export { DocPreviewModal };
