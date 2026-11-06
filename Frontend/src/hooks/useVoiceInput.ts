"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import { getVoiceConfig, transcribeAudio } from "@/lib/api";

export interface VoiceInputOptions {
  /** true: dừng sau khi người dùng nói xong một câu (dùng cho chế độ hội thoại). */
  singleUtterance?: boolean;
  /** Gọi khi phiên nghe kết thúc (sau khi đã gọi onFinal nếu có kết quả).
   *  fatal=true: lỗi không tự khắc phục được (vd chưa cấp quyền micro) — đừng nghe lại. */
  onEnd?: (info: { fatal: boolean }) => void;
}

type Engine = "browser" | "server" | null;

// Ngưỡng phát hiện im lặng cho chế độ ghi âm gửi lên server
const SILENCE_RMS = 0.015;
const SILENCE_AFTER_SPEECH_MS = 1500;
const NO_SPEECH_TIMEOUT_MS = 8000;

function pickRecorderMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
    if (MediaRecorder.isTypeSupported?.(m)) return m;
  }
  return undefined;
}

/**
 * Nhập bằng giọng nói tiếng Việt.
 * - Có Web Speech API (Chrome/Edge): nhận dạng ngay trên trình duyệt như trước.
 * - Không có (Firefox, một số Safari): ghi âm bằng MediaRecorder rồi gửi lên
 *   /api/voice/stt (faster-whisper) nếu backend bật STT.
 */
export function useVoiceInput(onFinal?: (text: string) => void, options?: VoiceInputOptions) {
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [engine, setEngine] = useState<Engine>(null);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState("");

  const recRef = useRef<any>(null);
  const mediaRef = useRef<{
    recorder: MediaRecorder;
    stream: MediaStream;
    ctx?: AudioContext;
    raf?: number;
    timers: number[];
    heardSpeech?: boolean;
    cancelled?: boolean;
  } | null>(null);
  const maxSecondsRef = useRef(60);
  const fatalRef = useRef(false);

  // Lưu callback vào ref để React không tạo lại recognizer liên tục
  const onFinalRef = useRef(onFinal);
  const optsRef = useRef(options);
  useEffect(() => {
    onFinalRef.current = onFinal;
    optsRef.current = options;
  }, [onFinal, options]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SR) {
      setEngine("browser");
      return;
    }
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
    let alive = true;
    getVoiceConfig().then((cfg) => {
      if (!alive || !cfg?.stt_enabled) return;
      maxSecondsRef.current = cfg.stt_max_seconds || 60;
      setEngine("server");
    });
    return () => {
      alive = false;
    };
  }, []);

  const cleanupMedia = useCallback(() => {
    const m = mediaRef.current;
    if (!m) return;
    m.timers.forEach((t) => clearTimeout(t));
    if (m.raf) cancelAnimationFrame(m.raf);
    m.stream.getTracks().forEach((t) => t.stop());
    m.ctx?.close().catch(() => {});
    mediaRef.current = null;
  }, []);

  const startBrowser = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    if (recRef.current) {
      try { recRef.current.abort(); } catch {}
    }

    const rec = new SR();
    rec.lang = "vi-VN";
    rec.continuous = !optsRef.current?.singleUtterance;
    rec.interimResults = true;

    rec.onstart = () => {
      setListening(true);
      setInterim("");
    };

    rec.onresult = (e: any) => {
      let fin = "", tmp = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) fin += e.results[i][0].transcript;
        else tmp += e.results[i][0].transcript;
      }
      setInterim(tmp); // Chỉ hiện chữ đang nói dở
      if (fin && onFinalRef.current) onFinalRef.current(fin.trim());
    };

    rec.onerror = (e: any) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed" || e.error === "audio-capture") {
        fatalRef.current = true;
        setError(e.error === "audio-capture" ? "Không tìm thấy micro" : "Chưa được cấp quyền dùng micro");
      }
      if (e.error !== "no-speech") setListening(false);
    };

    rec.onend = () => {
      if (recRef.current !== rec) return; // đã có phiên mới thay thế
      recRef.current = null;
      setListening(false);
      setInterim("");
      optsRef.current?.onEnd?.({ fatal: fatalRef.current });
    };

    try {
      rec.start();
      recRef.current = rec;
    } catch {}
  }, []);

  const startServer = useCallback(async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Chưa được cấp quyền dùng micro");
      optsRef.current?.onEnd?.({ fatal: true });
      return;
    }
    const mime = pickRecorderMime();
    const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    const chunks: BlobPart[] = [];
    const media: NonNullable<typeof mediaRef.current> = { recorder, stream, timers: [] };
    mediaRef.current = media;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = async () => {
      const heardSpeech = media.heardSpeech !== false;
      cleanupMedia();
      setListening(false);
      const blob = new Blob(chunks, { type: recorder.mimeType || mime || "audio/webm" });
      if (blob.size > 0 && heardSpeech && !media.cancelled) {
        setTranscribing(true);
        try {
          const text = (await transcribeAudio(blob)).trim();
          if (text && onFinalRef.current) onFinalRef.current(text);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Không nhận dạng được giọng nói");
        } finally {
          setTranscribing(false);
        }
      }
      if (!media.cancelled) optsRef.current?.onEnd?.({ fatal: false });
    };

    const stopRec = () => {
      if (recorder.state !== "inactive") recorder.stop();
    };
    media.timers.push(window.setTimeout(stopRec, (maxSecondsRef.current - 1) * 1000));

    // Chế độ hội thoại: tự dừng khi người dùng im lặng sau khi đã nói
    if (optsRef.current?.singleUtterance && typeof AudioContext !== "undefined") {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
      media.ctx = ctx;
      const buf = new Float32Array(analyser.fftSize);
      let spoke = false;
      let silentSince = 0;
      media.heardSpeech = false;
      const tick = () => {
        if (mediaRef.current !== media) return;
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        const rms = Math.sqrt(sum / buf.length);
        const now = performance.now();
        if (rms > SILENCE_RMS) {
          spoke = true;
          media.heardSpeech = true;
          silentSince = 0;
        } else if (spoke) {
          if (!silentSince) silentSince = now;
          else if (now - silentSince > SILENCE_AFTER_SPEECH_MS) return stopRec();
        }
        media.raf = requestAnimationFrame(tick);
      };
      media.raf = requestAnimationFrame(tick);
      media.timers.push(window.setTimeout(() => !spoke && stopRec(), NO_SPEECH_TIMEOUT_MS));
    }

    recorder.start(250);
    setListening(true);
    setInterim("");
  }, [cleanupMedia]);

  const start = useCallback(() => {
    if (typeof window === "undefined" || !engine) return;
    setError("");
    fatalRef.current = false;
    if (engine === "browser") startBrowser();
    else void startServer();
  }, [engine, startBrowser, startServer]);

  /** Dừng nghe; kết quả đã nói vẫn được xử lý (với ghi âm: gửi lên server). */
  const stop = useCallback(() => {
    if (recRef.current) {
      try { recRef.current.stop(); } catch {}
    }
    const m = mediaRef.current;
    if (m && m.recorder.state !== "inactive") m.recorder.stop();
    setListening(false);
    setInterim("");
  }, []);

  /** Huỷ hẳn, không xử lý và không gọi onEnd (vd thoát chế độ hội thoại). */
  const cancel = useCallback(() => {
    const rec = recRef.current;
    recRef.current = null;
    if (rec) {
      try { rec.abort(); } catch {}
    }
    const m = mediaRef.current;
    if (m) {
      m.cancelled = true;
      if (m.recorder.state !== "inactive") m.recorder.stop();
      else cleanupMedia();
    }
    setListening(false);
    setInterim("");
  }, [cleanupMedia]);

  useEffect(() => cancel, [cancel]);

  return {
    listening,
    transcribing,
    supported: engine !== null,
    engine,
    interim,
    error,
    start,
    stop,
    cancel,
  };
}
