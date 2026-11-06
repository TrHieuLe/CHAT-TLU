"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getVoiceConfig, synthesizeSpeech, VoiceConfig } from "@/lib/api";

export type TTSStatus = "idle" | "loading" | "playing" | "paused";

export interface PlayOptions {
  /** Gọi khi đọc xong (ok=true) hoặc lỗi không đọc được (ok=false). Không gọi khi bị stop(). */
  onEnded?: (ok: boolean) => void;
}

export interface VoiceSettings {
  voice: string;
  rate: number; // % so với tốc độ chuẩn, vd -20 / 0 / +20
}

const SETTINGS_KEY = "studybot_voice_settings";
const MAX_CACHED_CLIPS = 30;
// Dịch vụ edge-tts đôi khi chậm/lỗi: quá thời gian này thì đọc bằng giọng trình duyệt
const BACKEND_TTS_TIMEOUT_MS = 15000;

function loadSettings(): Partial<VoiceSettings> {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSettings(s: VoiceSettings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {}
}

/** Bỏ markdown thô cho giọng đọc của trình duyệt (backend có bộ chuẩn hoá đầy đủ hơn). */
function roughPlainText(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\$\$[\s\S]*?\$\$/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/^\s*\|?\s*:?-{2,}.*$/gm, "")
    .replace(/[|*#_`>~]/g, " ")
    .replace(/%/g, " phần trăm")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Trình phát giọng đọc dùng chung: mỗi lúc chỉ đọc một câu trả lời.
 * Ưu tiên giọng neural từ backend (edge-tts); backend lỗi thì dùng giọng vi-VN của trình duyệt.
 */
export function useTTSPlayer() {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [status, setStatus] = useState<TTSStatus>("idle");
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [settings, setSettingsState] = useState<VoiceSettings>({ voice: "", rate: 0 });
  const [browserTTS, setBrowserTTS] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const clipCache = useRef(new Map<string, string>()); // key → object URL
  const tokenRef = useRef(0); // tăng mỗi lần play/stop để bỏ qua callback cũ
  const modeRef = useRef<"audio" | "browser">("audio");

  useEffect(() => {
    setBrowserTTS(typeof window !== "undefined" && "speechSynthesis" in window);
    const saved = loadSettings();
    getVoiceConfig().then((cfg) => {
      setConfig(cfg);
      const voices = cfg?.voices.map((v) => v.id) ?? [];
      setSettingsState({
        voice: saved.voice && voices.includes(saved.voice) ? saved.voice : cfg?.default_voice ?? "",
        rate: typeof saved.rate === "number" ? saved.rate : 0,
      });
    });
    const cache = clipCache.current;
    return () => {
      abortRef.current?.abort();
      audioRef.current?.pause();
      cache.forEach((url) => URL.revokeObjectURL(url));
      cache.clear();
    };
  }, []);

  const setSettings = useCallback((next: Partial<VoiceSettings>) => {
    setSettingsState((prev) => {
      const merged = { ...prev, ...next };
      saveSettings(merged);
      return merged;
    });
  }, []);

  const stop = useCallback(() => {
    tokenRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setStatus("idle");
    setActiveKey(null);
  }, []);

  const speakWithBrowser = useCallback(
    (text: string, token: number, opts?: PlayOptions) => {
      if (!("speechSynthesis" in window)) {
        setStatus("idle");
        setActiveKey(null);
        setError("Trình duyệt không hỗ trợ đọc văn bản");
        opts?.onEnded?.(false);
        return;
      }
      modeRef.current = "browser";
      const u = new SpeechSynthesisUtterance(roughPlainText(text).slice(0, 3000));
      u.lang = "vi-VN";
      const vi = window.speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith("vi"));
      if (vi) u.voice = vi;
      u.rate = Math.min(2, Math.max(0.5, 1 + settings.rate / 100));
      const finish = (ok: boolean) => {
        if (tokenRef.current !== token) return;
        setStatus("idle");
        setActiveKey(null);
        opts?.onEnded?.(ok);
      };
      u.onend = () => finish(true);
      u.onerror = () => finish(false);
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
      setStatus("playing");
    },
    [settings.rate]
  );

  const play = useCallback(
    async (key: string, text: string, opts?: PlayOptions) => {
      if (!text.trim()) return;

      // Bấm lại đúng câu đang đọc: tạm dừng / đọc tiếp
      if (activeKey === key && status !== "idle") {
        const usingBrowser = modeRef.current === "browser";
        if (status === "playing") {
          if (usingBrowser) window.speechSynthesis.pause();
          else audioRef.current?.pause();
          setStatus("paused");
          return;
        }
        if (status === "paused") {
          if (usingBrowser) window.speechSynthesis.resume();
          else await audioRef.current?.play().catch(() => {});
          setStatus("playing");
          return;
        }
        if (status === "loading") return;
      }

      stop();
      const token = tokenRef.current;
      setError("");
      setActiveKey(key);

      if (!config?.tts_enabled) {
        speakWithBrowser(text, token, opts);
        return;
      }

      setStatus("loading");
      const cacheKey = `${key}|${settings.voice}|${settings.rate}`;
      let url = clipCache.current.get(cacheKey);
      if (!url) {
        const ctrl = new AbortController();
        abortRef.current = ctrl;
        const timer = window.setTimeout(() => ctrl.abort(), BACKEND_TTS_TIMEOUT_MS);
        try {
          const blob = await synthesizeSpeech(text, settings.voice || undefined, settings.rate, ctrl.signal);
          url = URL.createObjectURL(blob);
          clipCache.current.set(cacheKey, url);
          if (clipCache.current.size > MAX_CACHED_CLIPS) {
            const [oldKey, oldUrl] = clipCache.current.entries().next().value as [string, string];
            URL.revokeObjectURL(oldUrl);
            clipCache.current.delete(oldKey);
          }
        } catch (e) {
          if (tokenRef.current !== token) return; // đã bị stop
          console.warn("TTS backend lỗi, dùng giọng trình duyệt:", e);
          speakWithBrowser(text, token, opts);
          return;
        } finally {
          window.clearTimeout(timer);
        }
      }
      if (tokenRef.current !== token) return;

      if (!audioRef.current) audioRef.current = new Audio();
      const audio = audioRef.current;
      modeRef.current = "audio";
      audio.src = url;
      audio.onended = () => {
        if (tokenRef.current !== token) return;
        setStatus("idle");
        setActiveKey(null);
        opts?.onEnded?.(true);
      };
      audio.onerror = () => {
        if (tokenRef.current !== token) return;
        speakWithBrowser(text, token, opts);
      };
      try {
        await audio.play();
        if (tokenRef.current === token) setStatus("playing");
      } catch {
        // Trình duyệt chặn tự phát (chưa có thao tác người dùng)
        if (tokenRef.current !== token) return;
        setStatus("idle");
        setActiveKey(null);
        setError("Trình duyệt chặn tự phát âm thanh — hãy bấm nút Nghe.");
        opts?.onEnded?.(false);
      }
    },
    [activeKey, status, config, settings, stop, speakWithBrowser]
  );

  return {
    available: !!config?.tts_enabled || browserTTS,
    config,
    status,
    activeKey,
    error,
    settings,
    setSettings,
    play,
    stop,
  };
}

export type TTSPlayer = ReturnType<typeof useTTSPlayer>;
