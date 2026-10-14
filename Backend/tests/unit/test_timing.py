"""Unit tests cho app.core.timing và timeout chunk đầu của llm_service."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core import timing


class TestStageTimer:
    def setup_method(self):
        timing.clear_stats()

    def test_stage_records_duration(self):
        t = timing.StageTimer("t")
        with t.stage("embed"):
            pass
        rec = t.finish()
        assert "embed" in rec
        assert rec["total"] >= rec["embed"]

    def test_module_stage_uses_current_timer(self):
        t = timing.StageTimer("t")
        with timing.stage("qdrant"):
            pass
        assert "qdrant" in t.stages
        t.finish()
        assert timing.current_timer() is None

    def test_module_stage_without_timer_is_noop(self):
        with timing.stage("x"):
            pass  # không lỗi

    def test_mark_since_start_only_once(self):
        t = timing.StageTimer("t")
        t.mark_since_start("ttft")
        first = t.stages["ttft"]
        t.mark_since_start("ttft")
        assert t.stages["ttft"] == first
        t.finish()

    def test_stats_percentiles(self):
        for ms in (10, 20, 30, 40, 50):
            t = timing.StageTimer("chat")
            t.mark("llm", ms)
            t.finish()
        stats = timing.get_stats("chat")
        assert stats["requests"] == 5
        assert stats["stages_ms"]["llm"]["p50"] == 30
        assert stats["stages_ms"]["llm"]["max"] == 50


class _FakeStream:
    def __init__(self, texts, delay=0.0, fail_after=None):
        self.texts, self.delay, self.fail_after = texts, delay, fail_after

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i, t in enumerate(self.texts):
            if self.fail_after is not None and i == self.fail_after:
                raise RuntimeError("stream broken")
            await asyncio.sleep(self.delay)
            yield SimpleNamespace(text=t)


def _service(primary_stream, fallback_stream):
    """LLMService giả: model 'primary-model' trả primary_stream, các model dự phòng trả fallback_stream."""
    from app.llm.llm_service import LLMService

    async def _gen_stream(*, model, contents, config):
        return primary_stream if model == "primary-model" else fallback_stream

    client = MagicMock()
    client.aio.models.generate_content_stream = _gen_stream
    svc = LLMService()
    svc._client = client
    svc._get_legacy_genai = lambda: None
    return svc


@pytest.mark.asyncio
class TestLLMFirstTokenTimeout:
    async def _collect(self, svc):
        return [d async for d in svc.stream_chat_response(history=[], prompt="hi", system_instruction="s")]

    async def test_slow_model_falls_back(self):
        from app.core.config import settings
        svc = _service(_FakeStream(["slow"], delay=1.0), _FakeStream(["fast", "!"]))
        with patch.object(settings, "LLM_FIRST_TOKEN_TIMEOUT", 0.1), \
             patch.object(settings, "GEMINI_MODEL", "primary-model"):
            out = await self._collect(svc)
        assert out == ["fast", "!"]

    async def test_mid_stream_failure_does_not_duplicate(self):
        from app.core.config import settings
        svc = _service(_FakeStream(["a", "b", "c"], fail_after=2), _FakeStream(["other"]))
        with patch.object(settings, "GEMINI_MODEL", "primary-model"):
            out = await self._collect(svc)
        assert out == ["a", "b"]
