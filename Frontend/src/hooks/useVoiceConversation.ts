"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Message } from "@/lib/types";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import type { TTSPlayer } from "@/hooks/useTTSPlayer";
import { speechKeyFor } from "@/components/voice/TTSProvider";

export type ConversationState = "idle" | "listening" | "thinking" | "speaking";

const MAX_EMPTY_TURNS = 2; // im lặng liên tiếp bao nhiêu lượt thì tự thoát

/**
 * Chế độ hội thoại rảnh tay: nghe → gửi câu hỏi → chờ trả lời xong → đọc to → nghe tiếp.
 * Không bật micro khi đang đọc để micro không thu lại tiếng loa.
 */
export function useVoiceConversation({
  messages,
  loading,
  send,
  tts,
}: {
  messages: Message[];
  loading: boolean;
  send: (q: string) => void | Promise<void>;
  tts: TTSPlayer;
}) {
  const [state, setStateRaw] = useState<ConversationState>("idle");
  const stateRef = useRef<ConversationState>("idle");
  const transcriptRef = useRef("");
  const emptyTurnsRef = useRef(0);
  const sentAtLengthRef = useRef(0);
  const messagesLengthRef = useRef(messages.length);
  messagesLengthRef.current = messages.length;

  const setState = useCallback((s: ConversationState) => {
    stateRef.current = s;
    setStateRaw(s);
  }, []);

  const listenRef = useRef<() => void>(() => {});

  const voice = useVoiceInput(
    (text) => {
      transcriptRef.current = (transcriptRef.current + " " + text).trim();
    },
    {
      singleUtterance: true,
      onEnd: ({ fatal }) => {
        if (stateRef.current !== "listening") return;
        if (fatal) {
          setState("idle"); // vd chưa cấp quyền micro: thoát, lỗi hiện dưới ô nhập
          return;
        }
        const q = transcriptRef.current.trim();
        transcriptRef.current = "";
        if (!q) {
          emptyTurnsRef.current += 1;
          if (emptyTurnsRef.current >= MAX_EMPTY_TURNS) setState("idle");
          else listenRef.current();
          return;
        }
        emptyTurnsRef.current = 0;
        sentAtLengthRef.current = messagesLengthRef.current;
        setState("thinking");
        void send(q);
      },
    }
  );

  const listen = useCallback(() => {
    transcriptRef.current = "";
    setState("listening");
    voice.start();
  }, [voice, setState]);
  listenRef.current = listen;

  const start = useCallback(() => {
    tts.stop();
    emptyTurnsRef.current = 0;
    listen();
  }, [tts, listen]);

  const exit = useCallback(() => {
    setState("idle");
    voice.cancel();
    tts.stop();
  }, [voice, tts, setState]);

  /** Bấm mic khi bot đang đọc: ngắt lời và nghe câu mới. */
  const interrupt = useCallback(() => {
    tts.stop();
    emptyTurnsRef.current = 0;
    listen();
  }, [tts, listen]);

  // Câu trả lời mới stream xong → đọc to
  useEffect(() => {
    if (stateRef.current !== "thinking" || loading) return;
    if (messages.length <= sentAtLengthRef.current) return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== "model" || last.isStreaming) return;
    if (!last.content.trim()) {
      listen(); // lỗi / trả lời rỗng: nghe tiếp
      return;
    }
    setState("speaking");
    void tts.play(speechKeyFor(last), last.content, {
      onEnded: () => {
        if (stateRef.current === "speaking") listen();
      },
    });
  }, [messages, loading, tts, listen, setState]);

  // Esc để thoát
  useEffect(() => {
    if (state === "idle") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") exit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, exit]);

  return {
    state,
    active: state !== "idle",
    supported: voice.supported,
    interim: voice.interim,
    transcribing: voice.transcribing,
    error: voice.error || tts.error,
    micError: voice.error,
    start,
    exit,
    interrupt,
    stopListening: voice.stop,
  };
}
