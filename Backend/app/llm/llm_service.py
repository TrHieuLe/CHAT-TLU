"""
llm_service.py — Dịch vụ LLM tích hợp Google GenAI SDK (google-genai) mới nhất.
Cung cấp:
  - Streaming câu trả lời kèm chat history
  - Xử lý Multimodal ảnh (Gemini Vision)
  - Tự động sinh tiêu đề ngắn gọn cho session bằng AI
  - Đếm token an toàn
"""

import logging
import os
import re
from typing import AsyncGenerator, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self._client = None
        self._legacy_model = None

    def _get_api_key(self) -> str:
        key = getattr(settings, "EFFECTIVE_GEMINI_API_KEY", None)
        if not key:
            key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        return key

    def _get_client(self):
        if self._client is not None:
            return self._client

        api_key = self._get_api_key()
        if not api_key:
            logger.warning("Chưa cấu hình GEMINI_API_KEY / GOOGLE_API_KEY")
            return None

        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            logger.info("✅ Đã khởi tạo Google GenAI Client (SDK mới)")
            return self._client
        except Exception as e:
            logger.warning("Không thể khởi tạo google-genai Client: %s", e)
            return None

    def _get_legacy_genai(self):
        try:
            import google.generativeai as legacy_genai
            api_key = self._get_api_key()
            if api_key:
                legacy_genai.configure(api_key=api_key)
            return legacy_genai
        except Exception as e:
            logger.error("Không thể tải google.generativeai: %s", e)
            return None

    async def stream_chat_response(
        self,
        *,
        history: List[dict],
        prompt: str,
        system_instruction: str,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream câu trả lời từ Gemini dựa trên lịch sử hội thoại và prompt.
        """
        temp = temperature if temperature is not None else settings.TEMPERATURE
        max_tokens = max_output_tokens if max_output_tokens is not None else settings.MAX_OUTPUT_TOKENS
        model_name = settings.GEMINI_MODEL

        client = self._get_client()
        if client is not None:
            try:
                from google.genai import types

                # Chuẩn bị contents
                contents = []
                for msg in history:
                    role = "user" if msg.get("role") == "user" else "model"
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=msg.get("content", ""))]
                        )
                    )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)]
                    )
                )

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temp,
                    max_output_tokens=max_tokens,
                )

                response_stream = await client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=config,
                )

                async for chunk in response_stream:
                    text_delta = getattr(chunk, "text", "") or ""
                    if text_delta:
                        yield text_delta
                return
            except Exception as e:
                logger.warning("google-genai streaming error, falling back to legacy: %s", e)

        # Fallback sang google.generativeai
        legacy = self._get_legacy_genai()
        if legacy is not None:
            model = legacy.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                generation_config=legacy.GenerationConfig(
                    temperature=temp,
                    max_output_tokens=max_tokens,
                ),
            )
            chat_s = model.start_chat(
                history=[
                    {"role": m["role"], "parts": [{"text": m["content"]}]}
                    for m in history
                ]
            )
            stream = await chat_s.send_message_async(prompt, stream=True)
            async for chunk in stream:
                txt = getattr(chunk, "text", None)
                if not txt:
                    candidates = getattr(chunk, "candidates", None) or []
                    for cand in candidates:
                        parts = getattr(getattr(cand, "content", None), "parts", None) or []
                        for part in parts:
                            p_txt = getattr(part, "text", None)
                            if p_txt:
                                txt = (txt or "") + p_txt
                if txt:
                    yield txt

    async def generate_image_answer(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        system_instruction: str,
    ) -> str:
        """Xử lý ảnh người dùng upload bằng Gemini Vision."""
        client = self._get_client()
        model_name = settings.GEMINI_MODEL

        if client is not None:
            try:
                from google.genai import types

                img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                text_part = types.Part.from_text(text=prompt)

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=settings.TEMPERATURE,
                    max_output_tokens=settings.MAX_OUTPUT_TOKENS,
                )

                res = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[img_part, text_part],
                    config=config,
                )
                return getattr(res, "text", "") or ""
            except Exception as e:
                logger.warning("google-genai image analysis failed, fallback: %s", e)

        # Fallback
        from io import BytesIO
        from PIL import Image
        legacy = self._get_legacy_genai()
        if legacy is not None:
            pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
            model = legacy.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                generation_config=legacy.GenerationConfig(
                    temperature=settings.TEMPERATURE,
                    max_output_tokens=settings.MAX_OUTPUT_TOKENS,
                ),
            )
            res = await model.generate_content_async([prompt, pil_img])
            return getattr(res, "text", "") or ""

        return ""

    async def generate_title(self, question: str) -> str:
        """
        Dùng Gemini tạo tiêu đề ngắn gọn (3-6 từ) cho cuộc trò chuyện.
        """
        if not question or not question.strip():
            return "Cuộc trò chuyện mới"

        cleaned_q = question.strip()
        prompt = (
            "Tóm tắt câu hỏi của sinh viên sau đây thành một tiêu đề ngắn gọn từ 3 đến 6 từ. "
            "Chỉ trả về đúng tiêu đề, bằng tiếng Việt, không dùng dấu ngoặc kép, không có từ thừa:\n\n"
            f"Câu hỏi: {cleaned_q}\nTiêu đề:"
        )

        client = self._get_client()
        model_name = settings.GEMINI_MODEL
        if client is not None:
            try:
                from google.genai import types
                res = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=30,
                    ),
                )
                title = (getattr(res, "text", None) or "").strip()
                title = re.sub(r'^["\'\s]+|["\'\s\.]+$', '', title)
                if title and len(title) <= 80:
                    return title
            except Exception as e:
                logger.debug("AI title generation error: %s", e)

        # Fallback thô nếu AI thất bại
        short = cleaned_q[:50].strip()
        return short + ("..." if len(cleaned_q) > 50 else "")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, int(len(text.split()) * 1.3))


llm_service = LLMService()
llm_client = llm_service