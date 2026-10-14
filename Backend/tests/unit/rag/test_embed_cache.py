"""Cache embedding câu hỏi trong retriever: câu lặp lại không encode lại."""
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.rag.retriever import Retriever


@pytest.mark.asyncio
async def test_repeated_query_embeds_once():
    async_client = AsyncMock()
    async_client.query_points.return_value = MagicMock(points=[])
    r = Retriever(client=MagicMock(), async_client=async_client)
    with patch("app.rag.retriever.embedder") as mock_emb:
        mock_emb.get_embeddings.return_value = ([np.ones(4)], [{"1": 0.5}])
        await r.retrieve_v3("Điều kiện tốt nghiệp?")
        await r.retrieve_v3("  điều kiện   tốt nghiệp? ")
        assert mock_emb.get_embeddings.call_count == 1
        assert async_client.query_points.await_count == 2


@pytest.mark.asyncio
async def test_failed_embedding_not_cached():
    async_client = AsyncMock()
    async_client.query_points.return_value = MagicMock(points=[])
    r = Retriever(client=MagicMock(), async_client=async_client)
    with patch("app.rag.retriever.embedder") as mock_emb:
        mock_emb.get_embeddings.return_value = ([], [])
        await r.retrieve_v3("q")
        await r.retrieve_v3("q")
        assert mock_emb.get_embeddings.call_count == 2
