"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  FileText,
  UploadCloud,
  Trash2,
  ArrowLeft,
  Database,
  Layers,
  FileCheck2,
  RefreshCw,
  Search,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  X,
  Globe,
  Sparkles,
} from "lucide-react";
import {
  getDocuments,
  getDocumentStats,
  uploadDocument,
  deleteDocument,
  buildDocumentReferenceUrl,
  triggerCrawler,
  getCrawlerStatus,
} from "@/lib/api";
import { DocumentItem, DocumentStats, CrawlerStatus } from "@/lib/types";
import DocPreviewModal from "@/components/chat/DocPreviewModal";

export default function AdminPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Modal preview tài liệu
  const [previewDoc, setPreviewDoc] = useState<{ isOpen: boolean; title: string; url: string }>({
    isOpen: false,
    title: "",
    url: "",
  });

  // Modal xác nhận xóa
  const [deleteTarget, setDeleteTarget] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Crawler state
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus | null>(null);
  const [isCrawling, setIsCrawling] = useState<boolean>(false);
  const [crawlLimit, setCrawlLimit] = useState<number>(5);
  const [crawlFeedback, setCrawlFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [docs, st, crStatus] = await Promise.all([
        getDocuments(),
        getDocumentStats(),
        getCrawlerStatus().catch(() => null),
      ]);
      setDocuments(docs);
      setStats(st);
      if (crStatus) {
        setCrawlerStatus(crStatus);
      }
    } catch (e) {
      console.error("Lỗi tải dữ liệu admin:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleRunCrawler = async () => {
    setIsCrawling(true);
    setCrawlFeedback(null);
    try {
      const res = await triggerCrawler(crawlLimit);
      if (res.ok) {
        setCrawlFeedback({
          type: "success",
          message: `Thu thập thành công! ${res.crawled_count} bài viết mới từ TLU đã được ingest vào hệ thống RAG.`,
        });
        await loadData();
      } else {
        setCrawlFeedback({
          type: "error",
          message: res.message || "Có lỗi xảy ra trong quá trình quét thông báo TLU.",
        });
      }
    } catch (err: any) {
      setCrawlFeedback({
        type: "error",
        message: err?.message || "Không thể kết nối đến máy chủ Crawler.",
      });
    } finally {
      setIsCrawling(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];

    // Chỉ nhận định dạng được hỗ trợ
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (![".pdf", ".docx", ".txt", ".md"].includes(ext)) {
      setUploadError("Chỉ hỗ trợ các tệp: .pdf, .docx, .txt, .md");
      return;
    }

    setUploadError(null);
    setUploadSuccess(null);
    setUploading(true);

    try {
      const res = await uploadDocument(file);
      if (res.ok) {
        setUploadSuccess(`Đã nạp và vector hoá thành công tài liệu: "${file.name}"`);
        await loadData();
      } else {
        setUploadError(res.message || "Quá trình nạp tài liệu thất bại");
      }
    } catch (err: any) {
      setUploadError(err?.message || "Lỗi không xác định khi tải tệp");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const ok = await deleteDocument(deleteTarget.id);
      if (ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
        setStats((prev) =>
          prev
            ? {
                ...prev,
                total_documents: Math.max(0, prev.total_documents - 1),
                total_chunks: Math.max(0, prev.total_chunks - (deleteTarget.chunk_count || 0)),
              }
            : null
        );
      }
    } catch (err) {
      console.error("Lỗi xóa tài liệu:", err);
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const filteredDocs = documents.filter((doc) =>
    (doc.original_name || doc.filename).toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-10 h-10 flex-shrink-0 bg-blue-50 rounded-xl p-1.5 border border-blue-100 shadow-inner">
              <Image
                src="/logo-tlu.png"
                alt="Logo Đại học Thủy Lợi"
                fill
                className="object-contain"
                priority
              />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-slate-900 leading-tight">
                Quản Trị Cơ Sở Tri Thức
              </h1>
              <p className="text-xs text-blue-600 font-semibold">
                Hệ thống StudyBot • Đại học Thủy Lợi
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              title="Làm mới dữ liệu"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-600" : ""}`} />
              Làm mới
            </button>

            <Link
              href="/"
              className="inline-flex items-center gap-2 px-3.5 py-1.5 text-xs sm:text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-sm transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Về phòng chat</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* KPI Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-sm flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0">
              <FileCheck2 className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Tài liệu quy chế
              </p>
              <h3 className="text-2xl font-black text-slate-800">
                {stats ? stats.total_documents : documents.length}
              </h3>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-sm flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-sky-50 border border-sky-100 flex items-center justify-center text-sky-600 flex-shrink-0">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Thông báo TLU đã cào
              </p>
              <h3 className="text-2xl font-black text-slate-800">
                {crawlerStatus?.total_crawled_articles || 0}
              </h3>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-sm flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Tổng số Chunks vector
              </p>
              <h3 className="text-2xl font-black text-slate-800">
                {stats ? stats.total_chunks.toLocaleString("vi-VN") : 0}
              </h3>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-sm flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 flex-shrink-0">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Qdrant Collection
              </p>
              <h3 className="text-lg font-bold text-slate-800 truncate max-w-[150px]">
                {stats?.collection_name || "nckh_docs"}
              </h3>
            </div>
          </div>
        </div>

        {/* TLU Web Crawler Control Section */}
        <div className="bg-gradient-to-br from-white via-sky-50/30 to-blue-50/20 rounded-2xl p-6 border border-sky-200/80 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-sky-600 text-white flex items-center justify-center shadow-md shadow-sky-600/20">
                <Globe className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-900">
                    Cào Thông Báo Tự Động từ Website TLU
                  </h2>
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-sky-700 bg-sky-100 px-2.5 py-0.5 rounded-full border border-sky-200">
                    <Sparkles className="w-3 h-3 text-sky-600" />
                    Auto Crawler
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Quét và trích xuất các thông báo mới nhất từ website chính của trường (tlu.edu.vn), tự động phân tích và nạp vào Qdrant Vector DB.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 self-end sm:self-center">
              <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                <span>Số bài quét:</span>
                <select
                  value={crawlLimit}
                  onChange={(e) => setCrawlLimit(Number(e.target.value))}
                  disabled={isCrawling}
                  className="bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-semibold focus:outline-none focus:border-sky-500 shadow-sm cursor-pointer"
                >
                  <option value={3}>3 bài mới nhất</option>
                  <option value={5}>5 bài mới nhất</option>
                  <option value={10}>10 bài mới nhất</option>
                  <option value={15}>15 bài mới nhất</option>
                </select>
              </div>

              <button
                onClick={handleRunCrawler}
                disabled={isCrawling}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 disabled:bg-sky-400 rounded-xl shadow-sm transition-all shadow-sky-600/20"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isCrawling ? "animate-spin" : ""}`} />
                <span>{isCrawling ? "Đang quét & nạp dữ liệu..." : "Quét thông báo ngay"}</span>
              </button>
            </div>
          </div>

          {crawlFeedback && (
            <div
              className={`flex items-center gap-2 text-xs font-medium p-3 rounded-xl border ${
                crawlFeedback.type === "success"
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-rose-700 bg-rose-50 border-rose-200"
              }`}
            >
              {crawlFeedback.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
              )}
              <span>{crawlFeedback.message}</span>
            </div>
          )}

          {crawlerStatus && crawlerStatus.latest_announcements && crawlerStatus.latest_announcements.length > 0 && (
            <div className="pt-2 border-t border-sky-100/80">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Thông báo vừa cào gần đây:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {crawlerStatus.latest_announcements.slice(0, 4).map((art) => (
                  <div
                    key={art.id}
                    className="flex items-center justify-between p-2.5 bg-white/80 rounded-xl border border-slate-200/70 text-xs"
                  >
                    <div className="truncate pr-2">
                      <p className="font-medium text-slate-800 truncate">
                        {art.title}
                      </p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {art.chunks} chunks • {art.created_at ? new Date(art.created_at).toLocaleDateString("vi-VN") : "Hôm nay"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Upload Zone */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-blue-600" />
            Tải lên tài liệu quy chế mới
          </h2>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              handleFileUpload(e.dataTransfer.files);
            }}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-3 ${
              isDragOver
                ? "border-blue-500 bg-blue-50/50"
                : "border-slate-200 hover:border-blue-300 hover:bg-slate-50/70"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileUpload(e.target.files)}
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              disabled={uploading}
            />

            <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center shadow-inner">
              <UploadCloud className="w-6 h-6" />
            </div>

            <div>
              <p className="text-sm font-semibold text-slate-700">
                {uploading ? (
                  <span className="text-blue-600 flex items-center gap-2 justify-center">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Đang phân tích, trích xuất cấu trúc văn bản và vector hoá...
                  </span>
                ) : (
                  <>
                    Nhấp để chọn tệp hoặc <span className="text-blue-600">kéo thả tệp vào đây</span>
                  </>
                )}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Hỗ trợ các định dạng văn bản pháp quy: PDF, DOCX, TXT, MD (tối đa 50MB)
              </p>
            </div>
          </div>

          {uploadError && (
            <div className="flex items-center gap-2 text-xs font-medium text-rose-600 bg-rose-50 border border-rose-100 p-3 rounded-xl">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {uploadSuccess && (
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-100 p-3 rounded-xl">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{uploadSuccess}</span>
            </div>
          )}
        </div>

        {/* Documents Table */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Danh mục tài liệu trong hệ thống</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Các văn bản đang phục vụ trả lời tư vấn cho sinh viên
              </p>
            </div>

            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm kiếm tài liệu..."
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-blue-500 focus:bg-white transition-colors"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50/70 text-slate-500 font-semibold border-b border-slate-100">
                <tr>
                  <th className="px-5 py-3.5">Tên tài liệu</th>
                  <th className="px-4 py-3.5">Định dạng</th>
                  <th className="px-4 py-3.5">Dung lượng</th>
                  <th className="px-4 py-3.5">Số Chunks</th>
                  <th className="px-4 py-3.5">Thời gian tạo</th>
                  <th className="px-4 py-3.5">Trạng thái</th>
                  <th className="px-5 py-3.5 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-slate-400">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                      Đang tải danh sách tài liệu...
                    </td>
                  </tr>
                ) : filteredDocs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-slate-400">
                      Chưa có tài liệu nào phù hợp.
                    </td>
                  </tr>
                ) : (
                  filteredDocs.map((doc) => {
                    const previewUrl = buildDocumentReferenceUrl(doc.filename);
                    return (
                      <tr key={doc.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-5 py-3.5 font-medium text-slate-800">
                          <div className="flex items-center gap-2 max-w-sm sm:max-w-md truncate">
                            <FileText className="w-4 h-4 text-blue-500 flex-shrink-0" />
                            <span className="truncate" title={doc.original_name}>
                              {doc.original_name}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="inline-block uppercase px-2 py-0.5 text-[10px] font-bold bg-slate-100 text-slate-600 rounded">
                            {doc.file_type || "Văn bản"}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-500">{formatFileSize(doc.file_size)}</td>
                        <td className="px-4 py-3.5">
                          <span className="font-semibold text-indigo-600">
                            {doc.chunk_count || 0}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-400">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5" />
                            <span>
                              {doc.created_at
                                ? new Date(doc.created_at).toLocaleDateString("vi-VN")
                                : "N/A"}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          {doc.status === "ok" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                              <CheckCircle2 className="w-3 h-3" /> Hoạt động
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                              <AlertCircle className="w-3 h-3" /> Đang xử lý
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <div className="inline-flex items-center gap-1">
                            <button
                              onClick={() =>
                                setPreviewDoc({
                                  isOpen: true,
                                  title: doc.original_name,
                                  url: previewUrl,
                                })
                              }
                              className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                              title="Xem trước tài liệu"
                            >
                              <Eye className="w-4 h-4" />
                            </button>

                            <a
                              href={previewUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                              title="Mở tài liệu trong tab mới"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>

                            <button
                              onClick={() => setDeleteTarget(doc)}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                              title="Xóa tài liệu"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-100 space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center">
              <h3 className="text-base font-bold text-slate-900">Xác nhận xóa tài liệu?</h3>
              <p className="text-xs text-slate-500 mt-2">
                Bạn có chắc chắn muốn xóa tài liệu{" "}
                <span className="font-semibold text-slate-800">
                  &quot;{deleteTarget.original_name}&quot;
                </span>
                ? Thao tác này sẽ xoá toàn bộ dữ liệu vector của tài liệu khỏi Qdrant và cơ sở dữ liệu.
              </p>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="flex-1 px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
              >
                Hủy bỏ
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="flex-1 px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-sm transition-colors flex items-center justify-center gap-1.5"
              >
                {isDeleting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Đang xóa...
                  </>
                ) : (
                  "Đồng ý xóa"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Document Preview Modal */}
      <DocPreviewModal
        isOpen={previewDoc.isOpen}
        onClose={() => setPreviewDoc((prev) => ({ ...prev, isOpen: false }))}
        title={previewDoc.title}
        docUrl={previewDoc.url}
      />
    </div>
  );
}
