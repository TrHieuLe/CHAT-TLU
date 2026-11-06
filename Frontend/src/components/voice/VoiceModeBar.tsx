"use client";

import clsx from "clsx";
import { Loader2, Mic, Square, Volume2 } from "lucide-react";
import type { ConversationState } from "@/hooks/useVoiceConversation";
import type { TTSPlayer } from "@/hooks/useTTSPlayer";

interface Props {
  state: ConversationState;
  interim: string;
  transcribing: boolean;
  error: string;
  tts: TTSPlayer;
  onExit: () => void;
  onInterrupt: () => void;
  onStopListening: () => void;
}

const RATE_OPTIONS = [
  { value: -20, label: "Chậm" },
  { value: 0, label: "Vừa" },
  { value: 20, label: "Nhanh" },
];

export default function VoiceModeBar({
  state,
  interim,
  transcribing,
  error,
  tts,
  onExit,
  onInterrupt,
  onStopListening,
}: Props) {
  const label =
    state === "listening"
      ? transcribing
        ? "Đang nhận dạng…"
        : "Đang nghe — hãy nói câu hỏi"
      : state === "thinking"
        ? "StudyBot đang tìm câu trả lời…"
        : "Đang đọc câu trả lời";

  const voices = tts.config?.voices ?? [];

  return (
    <section
      aria-label="Chế độ hội thoại giọng nói"
      aria-live="polite"
      className="flex flex-col gap-2 px-3 py-2.5 rounded-2xl border border-tlu-tint-2 bg-tlu-tint animate-fade-up"
    >
      <div className="flex items-center gap-3">
        <span
          className={clsx(
            "flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-white",
            state === "listening" ? "bg-tlu-red" : "bg-tlu-blue"
          )}
          aria-hidden="true"
        >
          {state === "listening" && !transcribing ? (
            <span className="relative flex h-4 w-4 items-center justify-center">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-50" />
              <Mic className="relative w-4 h-4" />
            </span>
          ) : state === "speaking" ? (
            <Volume2 className="w-4 h-4" />
          ) : (
            <Loader2 className="w-4 h-4 animate-spin" />
          )}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-tlu-blue-dark">{label}</p>
          {state === "listening" && interim ? (
            <p className="text-xs text-slate-600 italic truncate">&ldquo;{interim}&rdquo;</p>
          ) : (
            <p className="hidden sm:block text-xs text-slate-600">Nhấn Esc hoặc nút Dừng để thoát</p>
          )}
        </div>

        {state === "listening" && (
          <button
            onClick={onStopListening}
            className="h-9 px-3 rounded-lg text-[13px] font-medium text-tlu-blue-dark bg-white hover:bg-tlu-tint-2 transition-colors"
          >
            Nói xong
          </button>
        )}
        {state === "speaking" && (
          <button
            onClick={onInterrupt}
            className="h-9 px-3 rounded-lg text-[13px] font-medium text-tlu-blue-dark bg-white hover:bg-tlu-tint-2 transition-colors inline-flex items-center gap-1.5"
            title="Ngắt lời và hỏi tiếp"
          >
            <Mic className="w-4 h-4" />
            Hỏi tiếp
          </button>
        )}
        <button
          onClick={onExit}
          className="h-9 px-3 rounded-lg text-[13px] font-medium text-white bg-tlu-red hover:opacity-90 transition-opacity inline-flex items-center gap-1.5"
          aria-label="Dừng chế độ hội thoại"
        >
          <Square className="w-3.5 h-3.5" />
          Dừng
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-600">
        {voices.length > 0 && (
          <label className="inline-flex items-center gap-1.5">
            Giọng
            <select
              value={tts.settings.voice}
              onChange={(e) => tts.setSettings({ voice: e.target.value })}
              className="h-7 rounded-md border border-tlu-tint-2 bg-white px-1.5 text-xs text-tlu-ink"
            >
              {voices.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="inline-flex items-center gap-1.5">
          Tốc độ
          <select
            value={tts.settings.rate}
            onChange={(e) => tts.setSettings({ rate: Number(e.target.value) })}
            className="h-7 rounded-md border border-tlu-tint-2 bg-white px-1.5 text-xs text-tlu-ink"
          >
            {RATE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        {error && <span className="text-tlu-red">{error}</span>}
      </div>
    </section>
  );
}
