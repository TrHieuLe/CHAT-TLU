"use client";
import { useRef, useState, KeyboardEvent, ChangeEvent, ClipboardEvent } from "react";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { ArrowUp, Mic, MicOff, Loader2, Image as ImageIcon, X } from "lucide-react";
import clsx from "clsx";

interface Props {
  onSend: (t: string) => void;
  onSendImage: (file: File, prompt?: string) => void;
  loading: boolean;
  hasDocs: boolean;
}

export default function ChatInput({ onSend, onSendImage, loading, hasDocs }: Props) {
  const [val, setVal] = useState("");
  const [pickedImage, setPickedImage] = useState<File | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { listening, supported, interim, start, stop } = useVoiceInput(
    (final) => setVal((p) => (p ? p + " " + final : final).trim())
  );

  const resize = () => {
    if (!ref.current) return;
    ref.current.style.height = "auto";
    ref.current.style.height = Math.min(ref.current.scrollHeight, 160) + "px";
  };

  const sendText = () => {
    const text = val.trim();
    if (!text || loading) return;
    onSend(text);
    setVal("");
    if (ref.current) ref.current.style.height = "auto";
  };

  const sendImageFile = () => {
    if (!pickedImage || loading) return;
    const prompt = val.trim();
    onSendImage(pickedImage, prompt || undefined);
    setPickedImage(null);
    setVal("");
    if (fileRef.current) fileRef.current.value = "";
    if (ref.current) ref.current.style.height = "auto";
  };

  const handleMainSend = () => {
    if (pickedImage) {
      sendImageFile();
      return;
    }
    sendText();
  };

  // Kiểm tra loại/kích thước ảnh, dùng chung cho chọn file và dán (Ctrl+V)
  const acceptImage = (file: File): boolean => {
    const okType = ["image/png", "image/jpeg", "image/jpg", "image/webp"].includes(file.type);
    if (!okType) {
      alert("Chỉ hỗ trợ PNG, JPG, JPEG, WEBP");
      return false;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert("Ảnh vượt quá 5MB");
      return false;
    }

    setPickedImage(file);
    return true;
  };

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!acceptImage(file)) e.target.value = "";
  };

  const onPasteImage = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const item = Array.from(e.clipboardData?.items ?? []).find(
      (it) => it.kind === "file" && it.type.startsWith("image/")
    );
    const blob = item?.getAsFile();
    if (!blob) return; // dán chữ: giữ hành vi mặc định

    e.preventDefault();
    const ext = blob.type.split("/")[1] || "png";
    const file = blob.name && blob.name !== "image.png"
      ? blob
      : new File([blob], `anh-dan-${Date.now()}.${ext}`, { type: blob.type });
    if (acceptImage(file) && fileRef.current) fileRef.current.value = "";
  };

  const display = listening && interim ? val + (val ? " " : "") + interim : val;
  const canSend = pickedImage ? !loading : !!val.trim() && !loading;

  return (
    <div className="space-y-2">
      {listening && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-tlu-tint border border-tlu-tint-2 rounded-xl animate-fade-up">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-tlu-red opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-tlu-red" />
          </span>
          <span className="text-xs text-tlu-blue-dark font-medium">Đang nghe tiếng Việt…</span>
          {interim && (
            <span className="text-xs text-slate-600 italic truncate max-w-[200px]">
              "{interim}"
            </span>
          )}
        </div>
      )}

      {pickedImage && (
        <div className="flex items-center justify-between gap-3 px-3 py-2 rounded-xl border border-tlu-tint-2 bg-tlu-tint animate-fade-up">
          <div className="flex items-center gap-2 min-w-0">
            <ImageIcon className="w-4 h-4 text-tlu-blue flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-slate-800 font-medium truncate">{pickedImage.name}</p>
              <p className="text-xs text-slate-600">
                {(pickedImage.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              setPickedImage(null);
              if (fileRef.current) fileRef.current.value = "";
            }}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-600 hover:text-tlu-red hover:bg-white transition-colors"
            title="Bỏ ảnh"
            aria-label="Bỏ ảnh đã chọn"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div
        className={clsx(
          "flex items-end gap-2 p-1.5 md:p-2.5 md:pl-3 rounded-[18px] md:rounded-[20px] border-[1.5px] transition-all duration-200 shadow-[0_6px_24px_rgba(14,42,94,0.08)]",
          listening
            ? "border-tlu-blue bg-tlu-tint ring-2 ring-tlu-tint-2"
            : "border-tlu-line bg-white focus-within:border-tlu-blue focus-within:ring-2 focus-within:ring-tlu-tint-2"
        )}
      >
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/webp"
          className="hidden"
          onChange={onPickFile}
        />

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          title="Gửi ảnh thông báo để StudyBot đọc giúp"
          aria-label="Gửi ảnh"
          className="flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition-colors bg-tlu-tint text-tlu-blue hover:bg-tlu-tint-2 disabled:opacity-50"
        >
          <ImageIcon className="w-5 h-5" />
        </button>

        <textarea
          ref={ref}
          value={display}
          onChange={(e) => {
            setVal(e.target.value);
            resize();
          }}
          onPaste={onPasteImage}
          onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleMainSend();
            }
          }}
          placeholder={
            pickedImage
              ? "Thêm câu hỏi cho ảnh này..."
              : listening
                ? "Đang nhận giọng nói..."
                : "Nhập câu hỏi…"
          }
          disabled={loading}
          rows={1}
          aria-label="Câu hỏi của bạn"
          className="flex-1 min-w-0 bg-transparent resize-none outline-none text-[15px] text-tlu-ink placeholder:text-slate-500 leading-6 max-h-40 py-2.5 px-1 disabled:opacity-60"
        />

        {supported && (
          <button
            onClick={() => (listening ? stop() : start())}
            disabled={loading}
            title={listening ? "Dừng ghi âm" : "Nhập bằng giọng nói"}
            aria-label={listening ? "Dừng ghi âm" : "Nhập bằng giọng nói"}
            className={clsx(
              "flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition-colors disabled:opacity-50",
              listening
                ? "bg-tlu-red text-white"
                : "text-slate-600 hover:text-tlu-blue hover:bg-tlu-tint"
            )}
          >
            {listening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
        )}

        <button
          onClick={handleMainSend}
          disabled={!canSend}
          className={clsx(
            "flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition-colors",
            canSend
              ? "bg-tlu-blue text-white hover:bg-tlu-blue-dark"
              : "bg-tlu-tint text-tlu-on-navy-3 cursor-not-allowed"
          )}
          title={pickedImage ? "Gửi ảnh" : "Gửi tin nhắn"}
          aria-label={pickedImage ? "Gửi ảnh" : "Gửi tin nhắn"}
        >
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowUp className="w-5 h-5" />}
        </button>
      </div>

    </div>
  );
}