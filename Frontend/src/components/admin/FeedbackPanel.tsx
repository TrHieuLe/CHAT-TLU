"use client";

import React, { useEffect, useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquareWarning, FlaskConical, History, RefreshCw } from "lucide-react";
import { addFeedbackToEval, getCrawlRuns, getFeedbackList, getFeedbackSummary } from "@/lib/api";
import { CrawlRun, FeedbackItem, FeedbackSummary } from "@/lib/types";

const PAGE_SIZE = 10;

function formatTime(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

/** Phản hồi like/dislike của người dùng: tỉ lệ, biểu đồ theo ngày, danh sách câu bị chê. */
export function FeedbackPanel() {
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [filter, setFilter] = useState<"dislike" | "like" | undefined>("dislike");
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Record<number, string>>({});

  useEffect(() => {
    getFeedbackSummary(30).then(setSummary);
  }, []);

  useEffect(() => {
    setLoading(true);
    getFeedbackList(filter, PAGE_SIZE, page * PAGE_SIZE)
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [filter, page]);

  const handleAddToEval = async (id: number) => {
    const res = await addFeedbackToEval(id);
    setNotice((prev) => ({ ...prev, [id]: res.message || (res.ok ? "Đã thêm" : "Lỗi") }));
  };

  const likes = summary?.totals.like ?? 0;
  const dislikes = summary?.totals.dislike ?? 0;
  const rated = likes + dislikes;
  // Đủ 30 ngày trên trục (ngày không có đánh giá để trống); backend nhóm theo ngày UTC
  const counts = new Map(summary?.by_day.map((d) => [d.date, d]) ?? []);
  const series = Array.from({ length: summary?.days ?? 0 }, (_, i) => {
    const date = new Date(Date.now() - (summary!.days - 1 - i) * 86_400_000).toISOString().slice(0, 10);
    return counts.get(date) ?? { date, like: 0, dislike: 0 };
  });
  const maxDay = Math.max(1, ...series.map((d) => d.like + d.dislike));
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <MessageSquareWarning className="w-5 h-5 text-amber-600" />
          Phản hồi của người dùng (30 ngày)
        </h2>
        <div className="flex items-center gap-4 text-sm">
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <ThumbsUp className="w-4 h-4" /> {likes}
          </span>
          <span className="inline-flex items-center gap-1 text-rose-700">
            <ThumbsDown className="w-4 h-4" /> {dislikes}
          </span>
          <span className="text-slate-500">
            Hài lòng: <b className="text-slate-800">{rated ? Math.round((likes / rated) * 100) : 0}%</b>
          </span>
        </div>
      </div>

      {rated > 0 && (
        <div className="flex items-end gap-1 h-16" aria-label="Số đánh giá theo ngày">
          {series.map((d) => (
            <div
              key={d.date}
              className="flex-1 min-w-[3px] h-full flex flex-col justify-end bg-slate-50 rounded-sm"
              title={`${d.date}: ${d.like} thích, ${d.dislike} không thích`}
            >
              <div className="bg-rose-400 rounded-t-sm" style={{ height: `${(d.dislike / maxDay) * 100}%` }} />
              <div className="bg-emerald-400" style={{ height: `${(d.like / maxDay) * 100}%` }} />
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 text-xs">
        {([
          ["dislike", "Không thích"],
          ["like", "Thích"],
          [undefined, "Tất cả"],
        ] as const).map(([value, label]) => (
          <button
            key={label}
            onClick={() => {
              setFilter(value);
              setPage(0);
            }}
            className={`px-3 py-1 rounded-lg font-medium ${
              filter === value ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto text-slate-500">{total} phản hồi</span>
      </div>

      <div className="divide-y divide-slate-100">
        {loading ? (
          <div className="py-6 text-center text-slate-400 text-sm">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto" />
          </div>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-slate-400 text-sm">Chưa có phản hồi nào.</p>
        ) : (
          items.map((fb) => (
            <div key={fb.id} className="py-3 space-y-1.5">
              <div className="flex items-start gap-2">
                {fb.rating === "dislike" ? (
                  <ThumbsDown className="w-4 h-4 mt-0.5 text-rose-600 flex-shrink-0" />
                ) : (
                  <ThumbsUp className="w-4 h-4 mt-0.5 text-emerald-600 flex-shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-800">
                    {fb.question || <span className="italic text-slate-400">(không gắn được câu hỏi)</span>}
                  </p>
                  {fb.answer && (
                    <details className="text-xs text-slate-600 mt-1">
                      <summary className="cursor-pointer text-slate-500">Câu trả lời của bot</summary>
                      <p className="whitespace-pre-wrap mt-1 max-h-48 overflow-auto bg-slate-50 rounded-lg p-2">
                        {fb.answer}
                      </p>
                    </details>
                  )}
                  <p className="text-[11px] text-slate-400 mt-1">
                    {formatTime(fb.created_at)}
                    {fb.sources.length > 0 && <> · Nguồn: {fb.sources.join(", ")}</>}
                    {fb.comment && <> · “{fb.comment}”</>}
                  </p>
                </div>
                {fb.question && (
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleAddToEval(fb.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
                      title="Ghi câu hỏi vào benchmark_eval/data/feedback_candidates.jsonl"
                    >
                      <FlaskConical className="w-3.5 h-3.5" />
                      Thêm vào bộ eval
                    </button>
                    {notice[fb.id] && <span className="text-[11px] text-slate-500">{notice[fb.id]}</span>}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-xs">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="px-2 py-1 rounded bg-slate-100 disabled:opacity-40"
          >
            Trước
          </button>
          <span>
            {page + 1}/{pages}
          </span>
          <button
            disabled={page + 1 >= pages}
            onClick={() => setPage((p) => p + 1)}
            className="px-2 py-1 rounded bg-slate-100 disabled:opacity-40"
          >
            Sau
          </button>
        </div>
      )}
    </div>
  );
}

/** Lịch sử các phiên quét thông báo (thủ công + theo lịch). */
export function CrawlRunsPanel({ refreshKey }: { refreshKey?: string | null }) {
  const [data, setData] = useState<{ schedule_interval_hours: number; runs: CrawlRun[] } | null>(null);

  useEffect(() => {
    getCrawlRuns(8).then(setData);
  }, [refreshKey]);

  if (!data) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
        <History className="w-3.5 h-3.5" />
        Lịch sử quét ·{" "}
        {data.schedule_interval_hours > 0
          ? `tự động mỗi ${data.schedule_interval_hours} giờ`
          : "lịch tự động đang tắt"}
      </p>
      {data.runs.length === 0 ? (
        <p className="text-xs text-slate-400">Chưa có phiên quét nào được ghi lại.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500">
              <tr className="text-left">
                <th className="py-1 pr-3 font-medium">Bắt đầu</th>
                <th className="py-1 pr-3 font-medium">Kiểu</th>
                <th className="py-1 pr-3 font-medium">Mới</th>
                <th className="py-1 pr-3 font-medium">Cập nhật</th>
                <th className="py-1 pr-3 font-medium">Bỏ qua</th>
                <th className="py-1 pr-3 font-medium">Lỗi</th>
              </tr>
            </thead>
            <tbody className="text-slate-700">
              {data.runs.map((r) => (
                <tr key={r.id} className="border-t border-slate-100" title={r.errors.join("\n")}>
                  <td className="py-1 pr-3 whitespace-nowrap">{formatTime(r.started_at)}</td>
                  <td className="py-1 pr-3">{r.trigger === "schedule" ? "Theo lịch" : "Thủ công"}</td>
                  <td className="py-1 pr-3">{r.new}</td>
                  <td className="py-1 pr-3">{r.updated}</td>
                  <td className="py-1 pr-3">{r.skipped}</td>
                  <td className={`py-1 pr-3 ${r.failed ? "text-rose-600 font-semibold" : ""}`}>{r.failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
