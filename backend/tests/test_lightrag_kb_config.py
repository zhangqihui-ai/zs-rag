from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.knowledge_base import KnowledgeBase
from app.services.lightrag_engine import (
    get_lightrag_config,
    invalidate_lightrag_instance,
    resolve_lightrag_entity_extract_max_gleaning,
    resolve_lightrag_entity_types,
    resolve_lightrag_language,
)


def _make_lightrag_kb(**config: object) -> KnowledgeBase:
    kb = KnowledgeBase(
        id=42,
        enterprise_space_id=1,
        name="test-graph-kb",
        kb_type="lightrag",
        config={"lightrag": config},
    )
    return kb


def test_get_lightrag_config_reads_nested_dict() -> None:
    kb = _make_lightrag_kb(entity_types=["Person"], entity_extract_max_gleaning=0)
    cfg = get_lightrag_config(kb)
    assert cfg["entity_types"] == ["Person"]
    assert cfg["entity_extract_max_gleaning"] == 0


def test_resolve_lightrag_language_default() -> None:
    assert resolve_lightrag_language({}) == "Chinese"
    assert resolve_lightrag_language({"language": "English"}) == "English"


def test_get_lightrag_instance_passes_kb_entity_config() -> None:
    kb = _make_lightrag_kb(
        entity_types=["Organization", "Concept"],
        entity_extract_max_gleaning=0,
        language="Chinese",
    )
    mock_rag = MagicMock()
    mock_rag.initialize_storages = AsyncMock()

    async def _run() -> None:
        with (
            patch("app.services.lightrag_engine._instance_cache", {}),
            patch("app.services.lightrag_engine._patch_lightrag_milvus_batched_upsert"),
            patch("app.services.lightrag_engine.ensure_lightrag_embedding_dimension", return_value=1024),
            patch("app.services.lightrag_engine._get_llm_model") as mock_llm,
            patch("app.services.lightrag_engine._build_embedding_func") as mock_embed,
            patch("app.services.lightrag_engine._build_llm_func"),
            patch("app.services.lightrag_engine._build_lightrag_tokenizer", return_value=MagicMock()),
            patch("app.services.lightrag_engine._get_lightrag_runtime") as mock_runtime,
            patch("app.services.lightrag_engine._lightrag_runtime_env"),
            patch("app.services.lightrag_engine.LightRAG", return_value=mock_rag) as mock_lightrag_cls,
        ):
            mock_llm.return_value = MagicMock(model_name="test-llm")
            mock_embed.return_value = MagicMock()
            runtime = MagicMock()
            runtime.env_lock = AsyncMock()
            runtime.env_lock.__aenter__ = AsyncMock(return_value=None)
            runtime.env_lock.__aexit__ = AsyncMock(return_value=None)
            mock_runtime.return_value = runtime
            db = MagicMock()

            from app.services.lightrag_engine import get_lightrag_instance

            invalidate_lightrag_instance(kb.id)
            await get_lightrag_instance(db, kb)

        _, kwargs = mock_lightrag_cls.call_args
        assert kwargs["addon_params"]["language"] == "Chinese"
        assert kwargs["addon_params"]["entity_types"] == ["Organization", "Concept"]
        assert kwargs["entity_extract_max_gleaning"] == 0

    asyncio.run(_run())


def test_resolve_helpers_with_partial_config() -> None:
    cfg = {"entity_types": ["Person", "Location"], "entity_extract_max_gleaning": 1}
    assert resolve_lightrag_entity_types(cfg) == ["Person", "Location"]
    assert resolve_lightrag_entity_extract_max_gleaning(cfg) == 1
