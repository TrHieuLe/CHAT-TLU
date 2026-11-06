"use client";

import { createContext, useContext } from "react";
import type { TTSPlayer } from "@/hooks/useTTSPlayer";

export const TTSContext = createContext<TTSPlayer | null>(null);

/** Trình phát giọng đọc dùng chung; null khi component nằm ngoài provider. */
export function useTTS(): TTSPlayer | null {
  return useContext(TTSContext);
}

/** Khoá ổn định cho một câu trả lời (để biết nút Nghe nào đang phát). */
export function speechKeyFor(msg: { id?: number | string; content: string }): string {
  return msg.id != null ? `msg-${msg.id}` : `txt-${msg.content.length}-${msg.content.slice(0, 40)}`;
}
