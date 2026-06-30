"""LightRAG SDK integration: instance cache, ingest, query, delete."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import httpx
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.embedding_gateway import generate_embeddings, resolve_embedding_concurrency
from app.core.errors import AppError
from app.core.kb_type import KB_TYPE_LIGHTRAG, build_lightrag_workspace
from app.core.offline_tokenizer import build_offline_tokenizer
from app.core.provider_adapter import get_provider
from app.db.session import SessionLocal
from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument
from app.models.model_management import AIModel, AIModelDefault
from app.core.neo4j_runtime import resolve_neo4j_params
from app.core.milvus_client import drop_collection_if_exists

logger = logging.getLogger(__name__)

LightRagQueryMode = Literal["naive", "local", "global", "hybrid", "mix"]
LightRagIndexChunkMode = Literal["auto", "reuse_parse", "native"]

# LightRAG 默认 11 类实体（与 lightrag.constants.DEFAULT_ENTITY_TYPES 一致）
DEFAULT_LIGHTRAG_ENTITY_TYPES: tuple[str, ...] = (
    "Person",
    "Creature",
    "Organization",
    "Location",
    "Event",
    "Concept",
    "Method",
    "Content",
    "Data",
    "Artifact",
    "NaturalObject",
)

_instance_cache: dict[int, LightRAG] = {}
_instance_locks: dict[int, threading.Lock] = {}
_insert_locks: dict[int, threading.Lock] = {}
_cache_guard = threading.Lock()
_runtime_guard = threading.Lock()
# 当前入库期间累计「已向量化文本条数」（按 kb_id 计），用于 embedding 阶段进度展示。
# LightRAG 在 embedding 阶段不会增量写 text_chunks KV，故用本计数器作为实时进度。
_embedding_progress: dict[int, int] = {}
# 当前入库期间累计「命中 embedding 缓存（未重算）的文本条数」（按 kb_id 计），用于进度文案。
_embedding_cache_hits: dict[int, int] = {}
_embedding_progress_guard = threading.Lock()
STALE_PROCESSING_SECONDS = 30 * 60


def reset_lightrag_embedding_progress(kb_id: int) -> None:
    with _embedding_progress_guard:
        _embedding_progress[kb_id] = 0
        _embedding_cache_hits[kb_id] = 0


def _bump_lightrag_embedding_progress(kb_id: int, count: int) -> None:
    if count <= 0:
        return
    with _embedding_progress_guard:
        _embedding_progress[kb_id] = _embedding_progress.get(kb_id, 0) + count


def _bump_lightrag_embedding_cache_hits(kb_id: int, count: int) -> None:
    if count <= 0:
        return
    with _embedding_progress_guard:
        _embedding_cache_hits[kb_id] = _embedding_cache_hits.get(kb_id, 0) + count


def get_lightrag_embedding_progress(kb_id: int) -> int:
    with _embedding_progress_guard:
        return _embedding_progress.get(kb_id, 0)


def get_lightrag_embedding_cache_hits(kb_id: int) -> int:
    with _embedding_progress_guard:
        return _embedding_cache_hits.get(kb_id, 0)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_ROOT = BACKEND_DIR / "storage" / "lightrag"
LIGHTRAG_PRECHUNK_BOUNDARY = "\n\n⟦ZS-RAG-CHUNK⟧\n\n"
_milvus_upsert_patch_applied = False


def _lightrag_int_setting(name: str, default: int) -> int:
    """兼容未重启 worker 时 Settings 尚未加载新字段的情况。"""
    return int(getattr(get_settings(), name, default))


def build_lightrag_prechunked_text(chunks: list[str]) -> str:
    """将解析阶段切片拼接为 LightRAG 可识别的边界文本（配合 split_by_character_only）。"""
    return LIGHTRAG_PRECHUNK_BOUNDARY.join(chunks)


def resolve_lightrag_index_chunk_mode(lgr_cfg: dict[str, Any]) -> LightRagIndexChunkMode:
    raw = str(lgr_cfg.get("index_chunk_mode") or "auto").strip().lower()
    if raw in ("auto", "reuse_parse", "native"):
        return raw  # type: ignore[return-value]
    return "auto"


def resolve_lightrag_prechunk_min_chars(lgr_cfg: dict[str, Any]) -> int:
    raw = lgr_cfg.get("prechunk_min_chars")
    if raw is not None:
        return max(0, int(raw))
    return _lightrag_int_setting("lightrag_prechunk_min_chars", 150_000)


def resolve_lightrag_split_by_character_only(lgr_cfg: dict[str, Any]) -> bool:
    return bool(lgr_cfg.get("split_by_character_only", False))


def resolve_lightrag_entity_types(lgr_cfg: dict[str, Any]) -> list[str] | None:
    raw = lgr_cfg.get("entity_types")
    if not isinstance(raw, list):
        return None
    cleaned = [str(item).strip() for item in raw if str(item).strip()]
    return cleaned or None


def resolve_lightrag_entity_extract_max_gleaning(lgr_cfg: dict[str, Any]) -> int | None:
    raw = lgr_cfg.get("entity_extract_max_gleaning")
    if raw is None:
        return None
    return max(0, int(raw))


def resolve_lightrag_language(lgr_cfg: dict[str, Any]) -> str:
    raw = lgr_cfg.get("language")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "Chinese"


def should_use_lightrag_prechunks(
    parsed_text: str,
    prechunk_texts: list[str],
    *,
    index_chunk_mode: LightRagIndexChunkMode = "auto",
    prechunk_min_chars: int | None = None,
) -> bool:
    """大文档复用解析切片作索引大段；小文档交给 LightRAG 原生分块，与解析切片视图分离。"""
    mode = index_chunk_mode if index_chunk_mode in ("auto", "reuse_parse", "native") else "auto"
    if mode == "native":
        return False
    if not prechunk_texts:
        return False
    if mode == "reuse_parse":
        return True
    threshold = (
        prechunk_min_chars
        if prechunk_min_chars is not None
        else _lightrag_int_setting("lightrag_prechunk_min_chars", 150_000)
    )
    return len(parsed_text) >= threshold


def _estimate_prechunk_max_tokens(prechunk_texts: list[str]) -> int:
    """估算解析切片最大 token 数，用于避免 prechunk 入库时二次切分膨胀。"""
    if not prechunk_texts:
        return 0
    tokenizer = _build_lightrag_tokenizer()
    max_tokens = 0
    for text in prechunk_texts:
        if not text.strip():
            continue
        if tokenizer is not None:
            max_tokens = max(max_tokens, len(tokenizer.encode(text)))
        else:
            # tiktoken 路径：字符数粗估（中文约 1.5 字/token）
            max_tokens = max(max_tokens, int(len(text) / 1.5))
    return max_tokens


def resolve_lightrag_prechunk_insert_settings(
    lgr_cfg: dict[str, Any],
    prechunk_texts: list[str],
    *,
    base_chunk_token_size: int,
) -> tuple[bool, int]:
    """复用解析切片入库：默认仅按边界切分，并自动抬高 chunk_token_size 覆盖超大段。"""
    if "split_by_character_only" in lgr_cfg:
        split_by_character_only = bool(lgr_cfg.get("split_by_character_only"))
    else:
        split_by_character_only = True

    configured_size = lgr_cfg.get("chunk_token_size")
    chunk_token_size = (
        max(512, int(configured_size))
        if configured_size is not None
        else base_chunk_token_size
    )

    if not split_by_character_only or not prechunk_texts:
        return split_by_character_only, chunk_token_size

    max_prechunk_tokens = _estimate_prechunk_max_tokens(prechunk_texts)
    # 留白避免分词边界误差触发 ChunkTokenLimitExceededError
    needed = max(chunk_token_size, max_prechunk_tokens + 256)
    needed = min(32768, needed)
    if needed > base_chunk_token_size:
        logger.info(
            "LightRAG prechunk 自动提升 chunk_token_size %s→%s（max_prechunk_tokens=%s）",
            base_chunk_token_size,
            needed,
            max_prechunk_tokens,
        )
    return split_by_character_only, needed


def _patch_lightrag_milvus_batched_upsert() -> None:
    """LightRAG 默认单次 upsert 全量向量，易触发 Milvus gRPC 64MB 限制。"""
    global _milvus_upsert_patch_applied
    if _milvus_upsert_patch_applied:
        return
    try:
        from lightrag.kg.milvus_impl import MilvusVectorDBStorage
    except Exception as exc:
        logger.warning("LightRAG Milvus upsert 分批补丁未加载: %s", exc)
        return

    original_upsert = MilvusVectorDBStorage.upsert
    batch_size = max(1, _lightrag_int_setting("lightrag_milvus_upsert_batch_size", 128))

    async def batched_upsert(self: Any, data: dict[str, dict[str, Any]]) -> None:
        if not data or len(data) <= batch_size:
            await original_upsert(self, data)
            return
        items = list(data.items())
        for start in range(0, len(items), batch_size):
            await original_upsert(self, dict(items[start : start + batch_size]))

    MilvusVectorDBStorage.upsert = batched_upsert  # type: ignore[method-assign]
    _milvus_upsert_patch_applied = True
    logger.info("LightRAG Milvus upsert 分批补丁已启用，batch_size=%s", batch_size)


class _LightRagAsyncRuntime:
    """Dedicated asyncio loop thread for all LightRAG SDK calls."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.env_lock: asyncio.Lock | None = None
        self._start()

    def _start(self) -> None:
        def _run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from lightrag.kg.shared_storage import initialize_share_data

            initialize_share_data(1)
            self.env_lock = asyncio.Lock()
            self._loop = loop
            self._ready.set()
            loop.run_forever()

        self._thread = threading.Thread(target=_run_loop, daemon=True, name="lightrag-async")
        self._thread.start()
        self._ready.wait(timeout=30)
        if self._loop is None or self.env_lock is None:
            raise RuntimeError("LightRAG async runtime failed to start")

    def run(self, coro: Any, *, timeout: float | None = None) -> Any:
        if self._loop is None:
            raise RuntimeError("LightRAG async runtime is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)


_lightrag_runtime: _LightRagAsyncRuntime | None = None


def _get_lightrag_runtime() -> _LightRagAsyncRuntime:
    global _lightrag_runtime
    if _lightrag_runtime is not None:
        return _lightrag_runtime
    with _runtime_guard:
        if _lightrag_runtime is None:
            _lightrag_runtime = _LightRagAsyncRuntime()
        return _lightrag_runtime


def _lock_for_kb(kb_id: int) -> threading.Lock:
    with _cache_guard:
        if kb_id not in _instance_locks:
            _instance_locks[kb_id] = threading.Lock()
        return _instance_locks[kb_id]


def _insert_lock_for_kb(kb_id: int) -> threading.Lock:
    """同一图知识库串行入库，避免 LightRAG pipeline 并发导致状态错乱。"""
    with _cache_guard:
        if kb_id not in _insert_locks:
            _insert_locks[kb_id] = threading.Lock()
        return _insert_locks[kb_id]


def invalidate_lightrag_instance(kb_id: int) -> None:
    with _cache_guard:
        _instance_cache.pop(kb_id, None)


def get_lightrag_config(knowledge_base: KnowledgeBase) -> dict[str, Any]:
    config = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
    raw = config.get("lightrag")
    return dict(raw) if isinstance(raw, dict) else {}


def get_default_query_mode(knowledge_base: KnowledgeBase) -> str:
    mode = get_lightrag_config(knowledge_base).get("default_query_mode") or "mix"
    if mode in ("naive", "local", "global", "hybrid", "mix"):
        return str(mode)
    return "mix"


def _working_dir_for(knowledge_base: KnowledgeBase) -> Path:
    settings = get_settings()
    root = Path(settings.lightrag_storage_root or DEFAULT_STORAGE_ROOT)
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    path = root / workspace
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_llm_model(db: Session, knowledge_base: KnowledgeBase) -> AIModel:
    lgr_cfg = get_lightrag_config(knowledge_base)
    override_id = lgr_cfg.get("extract_llm_id")
    if override_id is not None:
        model = db.execute(
            select(AIModel)
            .options(selectinload(AIModel.provider))
            .where(
                AIModel.id == int(override_id),
                AIModel.enterprise_space_id == knowledge_base.enterprise_space_id,
            )
        ).scalar_one_or_none()
        if model is None:
            raise AppError(status_code=404, code="MODEL_NOT_FOUND", message="LightRAG 抽取 LLM 不存在")
        if not model.is_enabled:
            raise AppError(status_code=400, code="MODEL_DISABLED", message="LightRAG 抽取 LLM 未启用")
        if model.model_type != "llm":
            raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="extract_llm_id 须为 LLM 模型")
        return model

    binding = db.execute(
        select(AIModelDefault)
        .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
        .where(
            AIModelDefault.enterprise_space_id == knowledge_base.enterprise_space_id,
            AIModelDefault.model_type == "llm",
        )
    ).scalar_one_or_none()
    if binding is None or binding.model is None:
        raise AppError(status_code=400, code="LLM_NOT_CONFIGURED", message="企业空间未配置默认 LLM，无法运行 LightRAG")
    model = binding.model
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="默认 LLM 未启用")
    return model


def _get_embedding_model(db: Session, knowledge_base: KnowledgeBase) -> AIModel:
    from app.services.knowledge_base_service import get_embedding_model_for_knowledge_base

    return get_embedding_model_for_knowledge_base(db, knowledge_base=knowledge_base)


def describe_lightrag_models_for_log(db: Session, knowledge_base: KnowledgeBase) -> tuple[str, str]:
    """返回 (embedding 日志行, LLM 日志行)。"""
    from app.services.knowledge_base_service import format_ai_model_for_log

    embed = _get_embedding_model(db, knowledge_base)
    llm = _get_llm_model(db, knowledge_base)
    return (
        format_ai_model_for_log(embed, role="Embedding 模型"),
        format_ai_model_for_log(llm, role="实体抽取 LLM"),
    )


def _extract_llm_text(result_data: Any) -> str:
    if not isinstance(result_data, dict):
        return str(result_data or "")
    choices = result_data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content:
            return str(content)
    return str(result_data)


def _pymilvus_supports_multi_database() -> bool:
    try:
        import pymilvus

        major, minor, *_ = (int(x) for x in str(pymilvus.__version__).split(".")[:3])
        return (major, minor) >= (2, 5)
    except Exception:
        return False


def _milvus_db_name_for_lightrag(settings) -> str:
    """LightRAG 要求环境变量 MILVUS_DB_NAME 存在；pymilvus<2.5 无 list_databases，须传空值跳过。"""
    requested = (settings.milvus_db_name or "default").strip() or "default"
    if _pymilvus_supports_multi_database():
        return requested
    return ""


@contextmanager
def _lightrag_runtime_env(db: Session, knowledge_base: KnowledgeBase):
    settings = get_settings()
    neo4j = resolve_neo4j_params(db, knowledge_base)
    milvus_uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
    overrides = {
        "NEO4J_URI": neo4j.uri,
        "NEO4J_USERNAME": neo4j.username,
        "NEO4J_PASSWORD": neo4j.password or "",
        "MILVUS_URI": milvus_uri,
        "MILVUS_DB_NAME": _milvus_db_name_for_lightrag(settings),
    }
    if neo4j.database:
        overrides["NEO4J_DATABASE"] = neo4j.database
    if settings.milvus_username:
        overrides["MILVUS_USER"] = settings.milvus_username
    if settings.milvus_password:
        overrides["MILVUS_PASSWORD"] = settings.milvus_password
    if settings.tiktoken_cache_dir:
        overrides["TIKTOKEN_CACHE_DIR"] = settings.tiktoken_cache_dir

    saved: dict[str, str | None] = {}
    for key, value in overrides.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, previous in saved.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def _milvus_collection_dimension(
    host: str,
    port: int,
    collection_name: str,
    *,
    username: str | None,
    password: str | None,
) -> int | None:
    try:
        from pymilvus import Collection, connections, utility

        alias = f"lightrag_dim_{collection_name}"
        connections.connect(
            alias,
            host=host,
            port=str(port),
            user=username or "",
            password=password or "",
        )
        if not utility.has_collection(collection_name, using=alias):
            return None
        collection = Collection(collection_name, using=alias)
        for field in collection.schema.fields:
            if field.name == "vector":
                dim = field.params.get("dim")
                return int(dim) if dim is not None else None
    except Exception as exc:
        logger.warning("读取 Milvus collection 维度失败 %s: %s", collection_name, exc)
    return None


def _reset_lightrag_milvus_collections_if_needed(
    db: Session,
    knowledge_base: KnowledgeBase,
    *,
    expected_dimension: int,
) -> None:
    settings = get_settings()
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    suffixes = ("entities", "relationships", "chunks")
    for suffix in suffixes:
        collection_name = f"{workspace}_{suffix}"
        existing_dim = _milvus_collection_dimension(
            settings.milvus_host,
            settings.milvus_port,
            collection_name,
            username=settings.milvus_username,
            password=settings.milvus_password,
        )
        if existing_dim is not None and existing_dim != expected_dimension:
            result = drop_collection_if_exists(
                settings.milvus_host,
                settings.milvus_port,
                collection_name,
                username=settings.milvus_username,
                password=settings.milvus_password,
            )
            if not result.success:
                raise AppError(
                    status_code=502,
                    code="MILVUS_RESET_FAILED",
                    message=f"LightRAG Milvus 集合维度不匹配（{existing_dim}→{expected_dimension}），删除 {collection_name} 失败：{result.message}",
                )
            logger.info(
                "Dropped LightRAG Milvus collection %s due to dimension mismatch %s→%s",
                collection_name,
                existing_dim,
                expected_dimension,
            )
            invalidate_lightrag_instance(knowledge_base.id)


def ensure_lightrag_embedding_dimension(db: Session, knowledge_base: KnowledgeBase) -> int:
    from app.services.knowledge_base_service import resolve_knowledge_base_milvus_dimension

    dimension = resolve_knowledge_base_milvus_dimension(
        db,
        knowledge_base=knowledge_base,
        persist=True,
    )
    _reset_lightrag_milvus_collections_if_needed(db, knowledge_base, expected_dimension=dimension)
    return dimension


def _build_embedding_func(db: Session, knowledge_base: KnowledgeBase, *, dimension: int) -> EmbeddingFunc:
    kb_id = knowledge_base.id
    model = _get_embedding_model(db, knowledge_base)
    model_name = model.model_name
    settings = get_settings()
    embed_batch_size = max(
        1,
        int(getattr(settings, "lightrag_embedding_batch_num", 4)),
    )

    async def _embed(texts: list[str], **_kwargs: Any) -> np.ndarray:
        if not texts:
            return np.array([])

        def _run() -> list[list[float]]:
            with SessionLocal() as thread_db:
                kb = thread_db.get(KnowledgeBase, kb_id)
                if kb is None:
                    raise AppError(status_code=404, code="KB_NOT_FOUND", message="知识库不存在")
                embed_model = _get_embedding_model(thread_db, kb)
                return generate_embeddings(
                    embed_model,
                    list(texts),
                    batch_size=embed_batch_size,
                    on_cache_stats=lambda hit, _total: _bump_lightrag_embedding_cache_hits(kb_id, hit),
                    usage_db=thread_db,
                    usage_source="embedding",
                )

        vectors = await asyncio.to_thread(_run)
        _bump_lightrag_embedding_progress(kb_id, len(texts))
        return np.array(vectors, dtype=np.float32)

    return EmbeddingFunc(
        embedding_dim=dimension,
        max_token_size=8192,
        model_name=model_name,
        func=_embed,
    )


def _build_llm_func(db: Session, knowledge_base: KnowledgeBase):
    kb_id = knowledge_base.id
    settings = get_settings()
    llm_timeout_sec = _lightrag_int_setting("lightrag_llm_timeout_sec", 600)
    llm_timeout = httpx.Timeout(
        connect=30.0,
        read=float(llm_timeout_sec),
        write=30.0,
        pool=30.0,
    )
    max_retries = max(1, int(getattr(settings, "lightrag_llm_max_retries", 3)))

    async def _llm(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        keyword_extraction: bool = False,
        **_kwargs: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            for item in history_messages:
                role = str(item.get("role") or "user")
                content = str(item.get("content") or "")
                if content.strip():
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        def _is_retryable_llm_error(message: str | None) -> bool:
            text = (message or "").lower()
            return any(
                token in text
                for token in (
                    "timed out",
                    "timeout",
                    "temporarily unavailable",
                    "connection reset",
                    "connection refused",
                    "429",
                    "503",
                    "502",
                )
            )

        def _run() -> str:
            last_message = "LightRAG LLM 请求失败"
            for attempt in range(max_retries):
                with SessionLocal() as thread_db:
                    kb = thread_db.get(KnowledgeBase, kb_id)
                    if kb is None:
                        raise AppError(status_code=404, code="KB_NOT_FOUND", message="知识库不存在")
                    model = _get_llm_model(thread_db, kb)
                    provider = get_provider(model.provider)
                    try:
                        result = provider.chat(model.model_name, messages, timeout=llm_timeout)
                    finally:
                        provider.close()
                    if result.success:
                        return _extract_llm_text(result.data)
                    last_message = result.message or last_message
                if attempt < max_retries - 1 and _is_retryable_llm_error(last_message):
                    wait_sec = min(2**attempt, 8)
                    logger.warning(
                        "LightRAG LLM retry kb_id=%s attempt=%s/%s wait=%ss error=%s",
                        kb_id,
                        attempt + 1,
                        max_retries,
                        wait_sec,
                        last_message[:200],
                    )
                    time.sleep(wait_sec)
                    continue
                raise AppError(
                    status_code=502,
                    code="LIGHTRAG_LLM_FAILED",
                    message=last_message,
                )
            raise AppError(
                status_code=502,
                code="LIGHTRAG_LLM_FAILED",
                message=last_message,
            )

        return await asyncio.to_thread(_run)

    return _llm


def _build_lightrag_tokenizer():
    settings = get_settings()
    if settings.lightrag_use_tiktoken:
        return None
    return build_offline_tokenizer()


async def get_lightrag_instance(db: Session, knowledge_base: KnowledgeBase) -> LightRAG:
    if knowledge_base.kb_type != KB_TYPE_LIGHTRAG:
        raise AppError(status_code=400, code="KB_TYPE_NOT_LIGHTRAG", message="仅图知识库支持 LightRAG")

    kb_id = knowledge_base.id
    cached = _instance_cache.get(kb_id)
    if cached is not None:
        return cached

    lock = _lock_for_kb(kb_id)
    with lock:
        cached = _instance_cache.get(kb_id)
        if cached is not None:
            return cached

        workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
        working_dir = str(_working_dir_for(knowledge_base))
        dimension = ensure_lightrag_embedding_dimension(db, knowledge_base)
        llm_model = _get_llm_model(db, knowledge_base)
        embedding_func = _build_embedding_func(db, knowledge_base, dimension=dimension)
        llm_func = _build_llm_func(db, knowledge_base)
        settings = get_settings()
        offline_tokenizer = _build_lightrag_tokenizer()
        lgr_cfg = get_lightrag_config(knowledge_base)
        language = resolve_lightrag_language(lgr_cfg)
        entity_types = resolve_lightrag_entity_types(lgr_cfg)
        entity_extract_max_gleaning = resolve_lightrag_entity_extract_max_gleaning(lgr_cfg)

        _patch_lightrag_milvus_batched_upsert()

        llm_timeout_sec = _lightrag_int_setting("lightrag_llm_timeout_sec", 600)
        embedding_timeout_sec = int(getattr(settings, "embedding_timeout_sec", 300))
        embedding_batch_num = max(
            1,
            int(getattr(settings, "lightrag_embedding_batch_num", 4)),
        )
        # embedding 并发度：LightRAG 通过 embedding_func_max_async 控制同时发起的
        # _embed（即 HTTP）调用数。仅在 Embedding 后端为多实例/可并行时才提速。
        embedding_concurrency = resolve_embedding_concurrency(knowledge_base.config)
        addon_params: dict[str, Any] = {"language": language}
        if entity_types:
            addon_params["entity_types"] = entity_types
        rag_kwargs: dict[str, Any] = {
            "working_dir": working_dir,
            "workspace": workspace,
            "kv_storage": "JsonKVStorage",
            "vector_storage": "MilvusVectorDBStorage",
            "graph_storage": "Neo4JStorage",
            "doc_status_storage": "JsonDocStatusStorage",
            "llm_model_func": llm_func,
            "llm_model_name": llm_model.model_name,
            "embedding_func": embedding_func,
            "embedding_batch_num": embedding_batch_num,
            "embedding_func_max_async": embedding_concurrency,
            "default_llm_timeout": llm_timeout_sec,
            "default_embedding_timeout": embedding_timeout_sec,
            "chunk_token_size": _lightrag_int_setting("lightrag_chunk_token_size", 4096),
            "chunk_overlap_token_size": _lightrag_int_setting("lightrag_chunk_overlap_token_size", 50),
            "addon_params": addon_params,
        }
        if entity_extract_max_gleaning is not None:
            rag_kwargs["entity_extract_max_gleaning"] = entity_extract_max_gleaning
        if offline_tokenizer is not None:
            rag_kwargs["tokenizer"] = offline_tokenizer
        else:
            rag_kwargs["tiktoken_model_name"] = settings.lightrag_tiktoken_model

        runtime = _get_lightrag_runtime()
        async with runtime.env_lock:
            with _lightrag_runtime_env(db, knowledge_base):
                rag = LightRAG(**rag_kwargs)
                await rag.initialize_storages()

        _instance_cache[kb_id] = rag
        logger.info(
            "LightRAG instance ready kb_id=%s workspace=%s llm_timeout=%ss llm_worker=%ss "
            "embed_timeout=%ss embed_worker=%ss embed_batch=%s embed_concurrency=%s entity_types=%s glean=%s",
            kb_id,
            workspace,
            llm_timeout_sec,
            llm_timeout_sec * 2,
            embedding_timeout_sec,
            embedding_timeout_sec * 2,
            embedding_batch_num,
            embedding_concurrency,
            entity_types or "default",
            entity_extract_max_gleaning if entity_extract_max_gleaning is not None else "default",
        )
        return rag


def _document_lightrag_id(document: KnowledgeDocument) -> str:
    return f"doc-{document.id}"


def _lightrag_doc_status_path(knowledge_base: KnowledgeBase) -> Path:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    return _working_dir_for(knowledge_base) / workspace / "kv_store_doc_status.json"


def _read_lightrag_doc_status_store(knowledge_base: KnowledgeBase) -> dict[str, Any]:
    path = _lightrag_doc_status_path(knowledge_base)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_lightrag_doc_status_store(knowledge_base: KnowledgeBase, payload: dict[str, Any]) -> None:
    path = _lightrag_doc_status_path(knowledge_base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_lightrag_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _recover_stale_lightrag_processing(
    knowledge_base: KnowledgeBase,
    *,
    skip_doc_ids: set[str] | frozenset[str] | None = None,
) -> None:
    """Mark long-stuck processing entries as failed so pipeline can proceed."""
    payload = _read_lightrag_doc_status_store(knowledge_base)
    if not payload:
        return

    skip = skip_doc_ids or frozenset()
    now = datetime.now(timezone.utc)
    changed = False
    for doc_id, entry in payload.items():
        if doc_id in skip:
            continue
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip().lower()
        if status != "processing":
            continue

        stale_since = _parse_lightrag_timestamp(entry.get("updated_at"))
        if stale_since is None:
            meta = entry.get("metadata")
            if isinstance(meta, dict):
                stale_since = _parse_lightrag_timestamp(meta.get("processing_start_time"))
        if stale_since is None:
            continue
        age_sec = (now - stale_since).total_seconds()
        if age_sec < STALE_PROCESSING_SECONDS:
            continue

        entry["status"] = "failed"
        entry["error_msg"] = "stale processing recovered"
        entry["updated_at"] = now.isoformat()
        changed = True
        logger.warning(
            "Recovered stale LightRAG processing kb_id=%s doc_id=%s age_sec=%.0f",
            knowledge_base.id,
            doc_id,
            age_sec,
        )

    if changed:
        _write_lightrag_doc_status_store(knowledge_base, payload)


def _remove_lightrag_doc_status_entry(knowledge_base: KnowledgeBase, doc_id: str) -> None:
    payload = _read_lightrag_doc_status_store(knowledge_base)
    if doc_id not in payload:
        return
    del payload[doc_id]
    _write_lightrag_doc_status_store(knowledge_base, payload)


def purge_lightrag_document_local_state(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
) -> None:
    """删除失败或取消入库时的兜底：清 doc_status 与本文档相关 LLM 抽取缓存。"""
    doc_id = _document_lightrag_id(document)
    status, entry = _lightrag_doc_status(knowledge_base, document)
    chunk_ids: set[str] = set()
    if entry:
        chunks_list = entry.get("chunks_list")
        if isinstance(chunks_list, list):
            chunk_ids = {str(item) for item in chunks_list if str(item).strip()}

    _remove_lightrag_doc_status_entry(knowledge_base, doc_id)

    if chunk_ids:
        cache_path = _lightrag_llm_cache_path(knowledge_base)
        if cache_path.is_file():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                keys_to_drop = [
                    key
                    for key, item in payload.items()
                    if isinstance(item, dict)
                    and str(item.get("cache_type") or "") == "extract"
                    and str(item.get("chunk_id") or "") in chunk_ids
                ]
                if keys_to_drop:
                    for key in keys_to_drop:
                        payload.pop(key, None)
                    cache_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    invalidate_lightrag_instance(knowledge_base.id)
    logger.info(
        "LightRAG local state purged kb_id=%s doc=%s prior_status=%s chunks=%s",
        knowledge_base.id,
        doc_id,
        status or "none",
        len(chunk_ids),
    )


def wait_lightrag_kb_lock_released(kb_id: int, *, timeout_sec: float = 90.0) -> bool:
    """轮询 Redis 入库锁是否已释放（取消 worker 后轮询）。"""
    key = _lightrag_kb_lock_key(kb_id)
    settings = get_settings()
    redis_url = settings.redis_url
    if not redis_url:
        lock = _insert_locks.get(kb_id)
        if lock is None:
            return True
        return not lock.locked()

    import redis

    client = redis.from_url(redis_url, socket_connect_timeout=3.0)
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while time.monotonic() < deadline:
        if client.get(key) is None:
            return True
        time.sleep(1.0)
    return client.get(key) is None


async def _clear_lightrag_document_if_not_processed(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    on_progress: Callable[[str], None] | None = None,
) -> None:
    """入库前始终清理本文档在 LightRAG 中的旧状态（含无效 processed）。"""
    status, entry = _lightrag_doc_status(knowledge_base, document)
    if not entry:
        return
    if on_progress:
        on_progress(f"清理 LightRAG 旧图谱（{status or '未知'}），准备重新入库…")
    try:
        await delete_document_async(db, knowledge_base=knowledge_base, document=document)
    except AppError as exc:
        if exc.code not in ("LIGHTRAG_QUERY_FAILED",):
            logger.warning(
                "LightRAG delete before reinsert kb_id=%s doc_id=%s: %s",
                knowledge_base.id,
                document.id,
                exc.message,
            )
        _remove_lightrag_doc_status_entry(knowledge_base, _document_lightrag_id(document))
    invalidate_lightrag_instance(knowledge_base.id)


def _clear_lightrag_doc_status_for_resume(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    on_progress: Callable[[str], None] | None = None,
) -> None:
    """续传专用：仅重置 doc_status，使文档可重新入队处理。

    与 ``_clear_lightrag_document_if_not_processed`` 不同，本函数**不调用**
    ``adelete_by_doc_id``，因此保留：
    - Milvus ``chunks_vdb`` 中已写入的向量（配合 embedding 缓存，重算"秒回"）；
    - ``kv_store_llm_response_cache.json`` 中的实体抽取缓存（keep_cache，已完成段不重抽）；
    - 已写入的图谱实体/关系（重入库为幂等 upsert）。
    LightRAG 去重仅依据 doc_id 是否在 doc_status 中，故移除该条目即可触发重处理。
    """
    if on_progress:
        on_progress("续传：保留已向量化向量与实体抽取缓存，仅重置入库状态…")
    _remove_lightrag_doc_status_entry(knowledge_base, _document_lightrag_id(document))
    invalidate_lightrag_instance(knowledge_base.id)


def _lightrag_llm_cache_path(knowledge_base: KnowledgeBase) -> Path:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    return _working_dir_for(knowledge_base) / workspace / "kv_store_llm_response_cache.json"


def _count_lightrag_extracted_chunks(knowledge_base: KnowledgeBase, chunk_ids: list[str]) -> int:
    """从 LLM 抽取缓存统计已完成 <|COMPLETE|> 的 chunk 数（pipeline 内存进度不可用时兜底）。"""
    if not chunk_ids:
        return 0
    path = _lightrag_llm_cache_path(knowledge_base)
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    chunk_id_set = set(chunk_ids)
    completed: set[str] = set()
    for item in payload.values():
        if not isinstance(item, dict):
            continue
        if str(item.get("cache_type") or "") != "extract":
            continue
        chunk_id = str(item.get("chunk_id") or "")
        if chunk_id not in chunk_id_set:
            continue
        if "<|COMPLETE|>" in str(item.get("return") or ""):
            completed.add(chunk_id)
    return len(completed)


def _read_lightrag_doc_status(knowledge_base: KnowledgeBase, doc_id: str) -> dict[str, Any] | None:
    entry = _read_lightrag_doc_status_store(knowledge_base).get(doc_id)
    return entry if isinstance(entry, dict) else None


def _lightrag_doc_status(knowledge_base: KnowledgeBase, document: KnowledgeDocument) -> tuple[str | None, dict[str, Any] | None]:
    entry = _read_lightrag_doc_status(knowledge_base, _document_lightrag_id(document))
    if entry is None:
        return None, None
    status = str(entry.get("status") or "").strip().lower() or None
    return status, entry


def _chunk_count_from_lightrag_status_entry(entry: dict[str, Any] | None) -> int:
    if not entry:
        return 0
    chunks_list = entry.get("chunks_list")
    if isinstance(chunks_list, list) and chunks_list:
        return len(chunks_list)
    chunks_count = entry.get("chunks_count")
    if isinstance(chunks_count, int) and chunks_count > 0:
        return chunks_count
    return 0


def _resolve_lightrag_doc_chunk_keys(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
) -> list[str]:
    """优先 doc_status.chunks_list；缺失时从 text_chunks KV 按 full_doc_id 兜底。"""
    _, entry = _lightrag_doc_status(knowledge_base, document)
    chunks_list = entry.get("chunks_list") if entry else None
    if isinstance(chunks_list, list) and chunks_list:
        return [str(item) for item in chunks_list]

    doc_id = _document_lightrag_id(document)
    store = _read_lightrag_text_chunks_store(knowledge_base)
    ordered: list[tuple[int, str]] = []
    for key, raw in store.items():
        if not isinstance(raw, dict):
            continue
        if str(raw.get("full_doc_id") or "") != doc_id:
            continue
        order = raw.get("chunk_order_index")
        sort_key = int(order) if isinstance(order, int) else len(ordered)
        ordered.append((sort_key, str(key)))
    ordered.sort(key=lambda item: item[0])
    return [key for _, key in ordered]


def _lightrag_doc_has_indexed_chunks(knowledge_base: KnowledgeBase, document: KnowledgeDocument) -> bool:
    store = _read_lightrag_text_chunks_store(knowledge_base)
    for chunk_key in _resolve_lightrag_doc_chunk_keys(knowledge_base, document):
        raw = store.get(chunk_key)
        if isinstance(raw, dict) and str(raw.get("content") or "").strip():
            return True
    return False


def lightrag_document_chunk_count(knowledge_base: KnowledgeBase, document: KnowledgeDocument) -> int:
    """图知识库分块数来自 LightRAG 索引大段（text_chunks KV），而非 knowledge_chunk 表。"""
    store = _read_lightrag_text_chunks_store(knowledge_base)
    count = 0
    for chunk_key in _resolve_lightrag_doc_chunk_keys(knowledge_base, document):
        raw = store.get(chunk_key)
        if isinstance(raw, dict) and str(raw.get("content") or "").strip():
            count += 1
    if count > 0:
        return count
    _, entry = _lightrag_doc_status(knowledge_base, document)
    return _chunk_count_from_lightrag_status_entry(entry)


def apply_lightrag_chunk_counts(knowledge_base: KnowledgeBase, documents: list[KnowledgeDocument]) -> None:
    """列表/详情展示：DB chunk_count 仍为 0 时从 LightRAG 状态补齐（仅内存，不写库）。"""
    if not documents:
        return
    store = _read_lightrag_doc_status_store(knowledge_base)
    for document in documents:
        if document.chunk_count > 0 or document.status != "graph_indexed":
            continue
        raw = store.get(_document_lightrag_id(document))
        entry = raw if isinstance(raw, dict) else None
        count = _chunk_count_from_lightrag_status_entry(entry)
        if count > 0:
            document.chunk_count = count


def _lightrag_text_chunks_path(knowledge_base: KnowledgeBase) -> Path:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    return _working_dir_for(knowledge_base) / workspace / "kv_store_text_chunks.json"


def _read_lightrag_text_chunks_store(knowledge_base: KnowledgeBase) -> dict[str, Any]:
    path = _lightrag_text_chunks_path(knowledge_base)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _count_lightrag_text_chunks_for_doc(knowledge_base: KnowledgeBase, doc_id: str) -> int:
    """统计某文档在 text_chunks KV 中已写入的切片数（embedding 阶段进度参考）。"""
    store = _read_lightrag_text_chunks_store(knowledge_base)
    return sum(
        1
        for item in store.values()
        if isinstance(item, dict) and str(item.get("full_doc_id") or "") == doc_id
    )


def _lightrag_chunk_timestamp(raw: dict[str, Any]) -> datetime:
    for key in ("update_time", "create_time"):
        value = raw.get(key)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return datetime.now(timezone.utc)


def list_lightrag_document_chunks(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
) -> dict[str, Any]:
    """从 LightRAG kv_store_text_chunks 分页返回文档切片（图知识库专用）。"""
    chunk_keys = _resolve_lightrag_doc_chunk_keys(knowledge_base, document)
    if not chunk_keys:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    store = _read_lightrag_text_chunks_store(knowledge_base)
    ordered: list[tuple[int, str, dict[str, Any]]] = []
    for idx, chunk_key in enumerate(chunk_keys):
        chunk_key = str(chunk_key)
        raw = store.get(chunk_key)
        if not isinstance(raw, dict):
            continue
        order = raw.get("chunk_order_index")
        sort_key = int(order) if isinstance(order, int) else idx
        ordered.append((sort_key, chunk_key, raw))
    ordered.sort(key=lambda item: item[0])

    kw = (keyword or "").strip()
    if kw:
        ordered = [item for item in ordered if kw in str(item[2].get("content") or "")]

    total = len(ordered)
    start = max(0, (page - 1) * page_size)
    page_slice = ordered[start : start + page_size]

    items: list[dict[str, Any]] = []
    for offset, (sort_key, chunk_key, raw) in enumerate(page_slice):
        global_index = start + offset
        content = str(raw.get("content") or "")
        char_count = len(content)
        preview = content if char_count <= 240 else f"{content[:240]}…"
        tokens = raw.get("tokens")
        ts = _lightrag_chunk_timestamp(raw)
        items.append(
            {
                "id": -(global_index + 1),
                "chunk_uid": chunk_key,
                "document_id": document.id,
                "chunk_index": sort_key,
                "content": content,
                "content_preview": preview,
                "char_count": char_count,
                "token_count": int(tokens) if isinstance(tokens, int) else None,
                "start_offset": None,
                "end_offset": None,
                "page_no": None,
                "heading_path": None,
                "vector_status": "indexed",
                "vector_id": chunk_key,
                "metadata": {"source": "lightrag_text_chunk", "lightrag_chunk_id": chunk_key},
                "created_at": ts,
                "updated_at": ts,
            }
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _lightrag_document_excerpt(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    *,
    max_chars: int = 2000,
    max_chunks: int = 4,
) -> str:
    """从 LightRAG text_chunks 存储拼接文档前若干切片正文。

    图谱检索只命中文档级 reference（无 chunk 正文）时，用它兜底取回原文供引用展示。
    """
    chunk_keys = _resolve_lightrag_doc_chunk_keys(knowledge_base, document)
    if not chunk_keys:
        return ""
    store = _read_lightrag_text_chunks_store(knowledge_base)
    ordered: list[tuple[int, str]] = []
    for idx, chunk_key in enumerate(chunk_keys):
        raw = store.get(str(chunk_key))
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or "").strip()
        if not content:
            continue
        order = raw.get("chunk_order_index")
        sort_key = int(order) if isinstance(order, int) else idx
        ordered.append((sort_key, content))
    ordered.sort(key=lambda item: item[0])
    pieces: list[str] = []
    total = 0
    for _, content in ordered[:max_chunks]:
        pieces.append(content)
        total += len(content)
        if total >= max_chars:
            break
    text = "\n\n".join(pieces).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def _assert_lightrag_doc_indexed(knowledge_base: KnowledgeBase, document: KnowledgeDocument) -> None:
    status, entry = _lightrag_doc_status(knowledge_base, document)
    if entry is None:
        raise AppError(
            status_code=502,
            code="LIGHTRAG_INSERT_FAILED",
            message="LightRAG 未找到文档状态记录，入库可能未完成",
        )
    if status == "failed":
        error_msg = str(entry.get("error_msg") or "LightRAG 文档处理失败")
        raise AppError(
            status_code=502,
            code="LIGHTRAG_INSERT_FAILED",
            message=f"LightRAG 入库失败：{error_msg}",
        )
    if status != "processed":
        raise AppError(
            status_code=502,
            code="LIGHTRAG_INSERT_INCOMPLETE",
            message=f"LightRAG 文档尚未处理完成（当前状态：{status or '未知'}）",
        )
    if not _lightrag_doc_has_indexed_chunks(knowledge_base, document):
        raise AppError(
            status_code=502,
            code="LIGHTRAG_INSERT_INCOMPLETE",
            message="LightRAG 标记为已处理，但未找到可读的索引大段（text_chunks 为空或已失效）",
        )


def _parse_lightrag_chunk_extract_line(message: str) -> tuple[int, int, int, int] | None:
    chunk_match = re.match(
        r"Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel(?:\s+\S+)?$",
        (message or "").strip(),
    )
    if not chunk_match:
        return None
    return tuple(int(value) for value in chunk_match.groups())  # type: ignore[return-value]


def _emit_lightrag_wait_progress(
    on_progress: Callable[[str], None] | None,
    on_structured_progress: Callable[[str, int | None, int | None, str], None] | None,
    *,
    phase: str,
    current: int | None,
    total: int | None,
    message: str,
) -> None:
    """结构化进度回调已含日志写入时，避免 on_progress 重复 emit。"""
    if on_structured_progress is not None:
        on_structured_progress(phase, current, total, message)
    elif on_progress and message:
        on_progress(message)


def _pipeline_message_targets_doc(
    message: str,
    *,
    doc_id: str,
    file_name: str,
    active_pipeline_doc: str | None,
    doc_chunk_keys: set[str] | None = None,
) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    if "Deletion process completed" in msg or msg.startswith("Phase 1: Processing"):
        return False
    if msg.startswith("Processing d-id:"):
        return msg.split(":", 1)[-1].strip() == doc_id
    if re.match(r"Chunk \d+ of \d+", msg):
        chunk_key = msg.rsplit(" ", 1)[-1].strip()
        if doc_chunk_keys and chunk_key in doc_chunk_keys:
            return True
        return active_pipeline_doc == doc_id
    if msg.startswith("Extracting stage"):
        return file_name in msg
    return False


def _format_lightrag_progress_line(message: str) -> str:
    """将 LightRAG pipeline 英文日志转为用户可读的 SSE 进度。"""
    msg = (message or "").strip()
    if not msg:
        return ""
    chunk_match = re.match(
        r"Chunk (\d+) of (\d+) extracted (\d+) Ent \+ (\d+) Rel",
        msg,
    )
    if chunk_match:
        cur, total, ent, rel = chunk_match.groups()
        return f"LightRAG 实体抽取：第 {cur}/{total} 段，本段 {ent} 实体 + {rel} 关系"
    stage_match = re.match(r"Extracting stage (\d+)/(\d+):\s*(.+)", msg)
    if stage_match:
        cur, total, path = stage_match.groups()
        return f"LightRAG 抽取阶段 {cur}/{total}：{path}"
    if msg.startswith("Processing d-id:"):
        doc_key = msg.split(":", 1)[-1].strip()
        return f"LightRAG 正在处理文档 {doc_key}"
    if msg.startswith("Processing ") and " document(s)" in msg:
        return f"LightRAG {msg.replace('Processing', '队列处理', 1)}"
    if "All enqueued documents have been processed" in msg:
        return "LightRAG 队列文档已全部处理完成"
    return f"LightRAG：{msg}"


async def _wait_lightrag_document_processed(
    *,
    rag: LightRAG,
    db: Session,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    workspace: str,
    insert_task: asyncio.Task[None],
    on_progress: Callable[[str], None] | None,
    on_structured_progress: Callable[[str, int | None, int | None, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    poll_interval_sec: float = 2.0,
    prechunk_source_count: int | None = None,
) -> None:
    """等待 ainsert 结束且 doc_status=processed；管道繁忙时持续驱动并过滤无关文档进度。"""
    from app.services.document_process_tasks import DocumentProcessCancelled, check_cancelled

    doc_id = _document_lightrag_id(document)
    file_name = document.file_name
    last_line = ""
    last_chunk_idx = 0
    last_cache_chunk_idx = 0
    last_history_seen = 0
    reported_chunks_total: int | None = None
    last_heartbeat = 0.0
    last_enqueue_heartbeat = 0.0
    last_pending_notice = 0.0
    heartbeat_interval_sec = 10.0
    active_pipeline_doc: str | None = None
    wait_started = time.monotonic()
    wait_timeout_sec = float(_lightrag_int_setting("lightrag_insert_wait_timeout_sec", 7200))

    while True:
        if time.monotonic() - wait_started > wait_timeout_sec:
            raise AppError(
                status_code=502,
                code="LIGHTRAG_INSERT_TIMEOUT",
                message=f"LightRAG 入库等待超时（>{int(wait_timeout_sec)}s），请稍后重试「重建索引」",
            )
        try:
            check_cancelled(cancel_event)
        except DocumentProcessCancelled:
            if not insert_task.done():
                insert_task.cancel()
                with suppress(asyncio.CancelledError):
                    await insert_task
            raise

        if insert_task.done():
            exc = insert_task.exception()
            if exc is not None:
                raise exc

        status, entry = _lightrag_doc_status(knowledge_base, document)

        if status == "processed" and insert_task.done():
            if _lightrag_doc_has_indexed_chunks(knowledge_base, document):
                return
            raise AppError(
                status_code=502,
                code="LIGHTRAG_INSERT_INCOMPLETE",
                message=(
                    "LightRAG 标记为 processed 但索引大段为空或已失效，"
                    "请重新执行「重建索引」；若仍失败请联系管理员清理图谱缓存"
                ),
            )
        if status == "failed":
            err = str(entry.get("error_msg") or "LightRAG 文档处理失败") if entry else "LightRAG 文档处理失败"
            if on_progress:
                on_progress(f"LightRAG 文档处理失败：{err[:500]}")
            raise AppError(
                status_code=502,
                code="LIGHTRAG_INSERT_FAILED",
                message=f"LightRAG 入库失败：{err}",
            )

        try:
            from lightrag.kg.shared_storage import get_namespace_data

            pipeline_status = await get_namespace_data("pipeline_status", workspace=workspace)
            latest = str(pipeline_status.get("latest_message") or "").strip()
            if latest.startswith("Processing d-id:"):
                active_pipeline_doc = latest.split(":", 1)[-1].strip()

            doc_chunk_keys: set[str] | None = None
            if entry:
                chunks_list = entry.get("chunks_list")
                if isinstance(chunks_list, list) and chunks_list:
                    doc_chunk_keys = {str(item) for item in chunks_list}

            def _handle_pipeline_chunk_message(msg: str) -> None:
                nonlocal last_chunk_idx, last_line
                if not _pipeline_message_targets_doc(
                    msg,
                    doc_id=doc_id,
                    file_name=file_name,
                    active_pipeline_doc=active_pipeline_doc,
                    doc_chunk_keys=doc_chunk_keys,
                ):
                    return
                parsed = _parse_lightrag_chunk_extract_line(msg)
                if parsed is None:
                    formatted = _format_lightrag_progress_line(msg)
                    if formatted and on_progress and msg != last_line:
                        _emit_lightrag_wait_progress(
                            on_progress,
                            on_structured_progress,
                            phase="graph_indexing",
                            current=last_chunk_idx or None,
                            total=reported_chunks_total,
                            message=formatted,
                        )
                        last_line = msg
                    return
                cur, total_chunks, ent, rel = parsed
                last_chunk_idx = max(last_chunk_idx, cur)
                if reported_chunks_total is None:
                    reported_chunks_total = total_chunks
                formatted = f"LightRAG 实体抽取：第 {cur}/{total_chunks} 段，本段 {ent} 实体 + {rel} 关系"
                _emit_lightrag_wait_progress(
                    on_progress,
                    on_structured_progress,
                    phase="graph_indexing",
                    current=cur,
                    total=total_chunks,
                    message=formatted,
                )
                last_line = msg

            history = pipeline_status.get("history_messages")
            if isinstance(history, list) and len(history) > last_history_seen:
                for hist_msg in history[last_history_seen:]:
                    _handle_pipeline_chunk_message(str(hist_msg))
                last_history_seen = len(history)

            if (
                latest
                and latest != last_line
                and _pipeline_message_targets_doc(
                    latest,
                    doc_id=doc_id,
                    file_name=file_name,
                    active_pipeline_doc=active_pipeline_doc,
                    doc_chunk_keys=doc_chunk_keys,
                )
            ):
                if _parse_lightrag_chunk_extract_line(latest) is not None:
                    _handle_pipeline_chunk_message(latest)
                elif on_progress or on_structured_progress:
                    formatted = _format_lightrag_progress_line(latest)
                    if formatted:
                        _emit_lightrag_wait_progress(
                            on_progress,
                            on_structured_progress,
                            phase="graph_indexing",
                            current=last_chunk_idx or None,
                            total=reported_chunks_total,
                            message=formatted,
                        )
                    last_line = latest
            elif (
                on_progress or on_structured_progress
            ) and latest.startswith("Processing d-id:") and active_pipeline_doc and active_pipeline_doc != doc_id:
                if latest != last_line:
                    queued_msg = f"LightRAG 等待同库其他文档处理完成（当前 pipeline：{active_pipeline_doc}）…"
                    _emit_lightrag_wait_progress(
                        on_progress,
                        on_structured_progress,
                        phase="queued",
                        current=None,
                        total=None,
                        message=queued_msg,
                    )
                    last_line = latest
        except Exception as exc:
            logger.debug("LightRAG pipeline_status 读取失败 kb_id=%s: %s", knowledge_base.id, exc)

        if entry:
            chunks_count = entry.get("chunks_count")
            if isinstance(chunks_count, int) and chunks_count > 0 and chunks_count != reported_chunks_total:
                reported_chunks_total = chunks_count
                if (
                    prechunk_source_count
                    and prechunk_source_count > 0
                    and chunks_count > prechunk_source_count * 2
                ):
                    logger.warning(
                        "LightRAG 分块段数 %s 远大于解析切片 %s（×2 阈值），"
                        "可能未按解析边界入库或单块过宽触发 token 二次切分",
                        chunks_count,
                        prechunk_source_count,
                    )
                chunk_msg = (
                    f"LightRAG 分块完成：共 {chunks_count} 段，开始 LLM 实体/关系抽取（大文档可能需数十分钟）…"
                )
                _emit_lightrag_wait_progress(
                    on_progress,
                    on_structured_progress,
                    phase="graph_indexing",
                    current=0,
                    total=chunks_count,
                    message=chunk_msg,
                )

            chunks_list = entry.get("chunks_list")
            if isinstance(chunks_list, list) and chunks_list:
                cache_done = _count_lightrag_extracted_chunks(
                    knowledge_base,
                    [str(item) for item in chunks_list],
                )
                if cache_done > last_cache_chunk_idx:
                    last_cache_chunk_idx = cache_done
                    progress_idx = max(last_chunk_idx, cache_done)
                    cache_msg = f"LightRAG 实体抽取：已完成 {cache_done}/{len(chunks_list)} 段（LLM 缓存统计）"
                    _emit_lightrag_wait_progress(
                        on_progress,
                        on_structured_progress,
                        phase="graph_indexing",
                        current=progress_idx,
                        total=reported_chunks_total or len(chunks_list),
                        message=cache_msg,
                    )

        fresh_cache_done = last_cache_chunk_idx
        if entry:
            chunks_list = entry.get("chunks_list")
            if isinstance(chunks_list, list) and chunks_list:
                fresh_cache_done = _count_lightrag_extracted_chunks(
                    knowledge_base,
                    [str(item) for item in chunks_list],
                )
                last_cache_chunk_idx = max(last_cache_chunk_idx, fresh_cache_done)

        now = time.monotonic()
        display_idx = max(last_chunk_idx, fresh_cache_done)
        if (
            not insert_task.done()
            and on_progress
            and now - last_enqueue_heartbeat >= 15
            and status not in ("processing",)
        ):
            on_progress("LightRAG 正在提交文档入队…")
            last_enqueue_heartbeat = now

        if status in ("pending", "preprocessed", "processing") and insert_task.done():
            if on_progress and now - last_pending_notice >= 12:
                if status == "processing":
                    on_progress("LightRAG 实体抽取进行中，等待 pipeline 完成…")
                else:
                    on_progress("LightRAG 已入队，等待 pipeline 处理本文档…")
                last_pending_notice = now
        elif (
            reported_chunks_total
            and status not in (None, "processed", "failed")
            and now - last_heartbeat >= heartbeat_interval_sec
        ):
            elapsed_sec = int(now - wait_started)
            embedded_count = min(
                get_lightrag_embedding_progress(knowledge_base.id),
                reported_chunks_total,
            )
            cache_hits = min(
                get_lightrag_embedding_cache_hits(knowledge_base.id),
                embedded_count,
            )
            embedding_done = embedded_count >= reported_chunks_total

            if last_chunk_idx > 0 or fresh_cache_done > 0:
                heartbeat_msg = (
                    f"LightRAG 实体抽取进行中… 约 {display_idx}/{reported_chunks_total} 段"
                    f"（已等待 {elapsed_sec}s）"
                )
                heartbeat_current: int | None = display_idx
            elif not embedding_done:
                if cache_hits > 0:
                    heartbeat_msg = (
                        f"LightRAG 向量 embedding 进行中… 已向量化 {embedded_count}/"
                        f"{reported_chunks_total} 段（其中命中缓存 {cache_hits} 段，未重算；"
                        f"已等待 {elapsed_sec}s）"
                    )
                else:
                    heartbeat_msg = (
                        f"LightRAG 向量 embedding 进行中… 已向量化 {embedded_count}/"
                        f"{reported_chunks_total} 段（此阶段可能较慢；已等待 {elapsed_sec}s）"
                    )
                heartbeat_current = embedded_count
            else:
                heartbeat_msg = (
                    f"LightRAG 向量 embedding 已完成（{reported_chunks_total}/{reported_chunks_total} 段），"
                    f"LLM 实体/关系抽取进行中（已等待 {elapsed_sec}s，首段 LLM 可能较慢）…"
                )
                heartbeat_current = None

            _emit_lightrag_wait_progress(
                on_progress,
                on_structured_progress,
                phase="graph_indexing",
                current=heartbeat_current,
                total=reported_chunks_total,
                message=heartbeat_msg,
            )
            last_heartbeat = now

        await asyncio.sleep(poll_interval_sec)


async def insert_document_async(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    text: str,
    text_chunks: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_structured_progress: Callable[[str, int | None, int | None, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = False,
) -> None:
    doc_id = _document_lightrag_id(document)
    reset_lightrag_embedding_progress(knowledge_base.id)
    if resume:
        _clear_lightrag_doc_status_for_resume(knowledge_base, document, on_progress)
    else:
        await _clear_lightrag_document_if_not_processed(
            db,
            knowledge_base=knowledge_base,
            document=document,
            on_progress=on_progress,
        )
    _recover_stale_lightrag_processing(knowledge_base, skip_doc_ids={doc_id})
    ensure_lightrag_embedding_dimension(db, knowledge_base)
    rag = await get_lightrag_instance(db, knowledge_base)
    if on_progress:
        on_progress("LightRAG 实例就绪，正在提交文档入队…")
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    lgr_cfg = get_lightrag_config(knowledge_base)
    index_chunk_mode = resolve_lightrag_index_chunk_mode(lgr_cfg)
    prechunk_min_chars = resolve_lightrag_prechunk_min_chars(lgr_cfg)
    base_chunk_token_size = _lightrag_int_setting("lightrag_chunk_token_size", 4096)

    prechunked = [str(chunk).strip() for chunk in (text_chunks or []) if str(chunk).strip()]
    use_prechunks = should_use_lightrag_prechunks(
        text,
        prechunked,
        index_chunk_mode=index_chunk_mode,
        prechunk_min_chars=prechunk_min_chars,
    )
    if use_prechunks:
        split_by_character_only, chunk_token_size = resolve_lightrag_prechunk_insert_settings(
            lgr_cfg,
            prechunked,
            base_chunk_token_size=base_chunk_token_size,
        )
        if chunk_token_size != rag.chunk_token_size:
            rag.chunk_token_size = chunk_token_size
    else:
        split_by_character_only = resolve_lightrag_split_by_character_only(lgr_cfg)
        chunk_token_size = base_chunk_token_size
    logger.info(
        "LightRAG ainsert kb_id=%s doc=%s parse_chunks=%s index_mode=%s use_prechunks=%s "
        "prechunk_chars=%s text_chars=%s chunk_token_size=%s split_by_character_only=%s",
        knowledge_base.id,
        doc_id,
        len(prechunked),
        index_chunk_mode,
        use_prechunks,
        sum(len(item) for item in prechunked) if prechunked else 0,
        len(text),
        chunk_token_size,
        split_by_character_only,
    )

    async def _run_ainsert() -> None:
        with _lightrag_runtime_env(db, knowledge_base):
            if use_prechunks:
                bounded_text = build_lightrag_prechunked_text(prechunked)
                await rag.ainsert(
                    bounded_text,
                    split_by_character=LIGHTRAG_PRECHUNK_BOUNDARY,
                    split_by_character_only=split_by_character_only,
                    ids=[doc_id],
                    file_paths=[document.file_name],
                )
                return
            await rag.ainsert(
                text,
                ids=[doc_id],
                file_paths=[document.file_name],
            )

    insert_task = asyncio.create_task(_run_ainsert())
    try:
        await _wait_lightrag_document_processed(
            rag=rag,
            db=db,
            knowledge_base=knowledge_base,
            document=document,
            workspace=workspace,
            insert_task=insert_task,
            on_progress=on_progress,
            on_structured_progress=on_structured_progress,
            cancel_event=cancel_event,
            prechunk_source_count=len(prechunked) if use_prechunks else None,
        )
    except Exception:
        if not insert_task.done():
            insert_task.cancel()
            with suppress(asyncio.CancelledError):
                await insert_task
        raise

    _assert_lightrag_doc_indexed(knowledge_base, document)
    _, entry = _lightrag_doc_status(knowledge_base, document)
    chunks_count = entry.get("chunks_count") if entry else None
    if isinstance(chunks_count, int) and chunks_count > 0:
        done_msg = f"LightRAG 实体抽取完成：共 {chunks_count}/{chunks_count} 段，正在写入图谱…"
        _emit_lightrag_wait_progress(
            on_progress,
            on_structured_progress,
            phase="graph_indexing",
            current=chunks_count,
            total=chunks_count,
            message=done_msg,
        )
        if on_progress:
            on_progress(f"LightRAG 入库完成：共处理 {chunks_count} 段")
    elif on_progress:
        on_progress("LightRAG 入库完成")


async def _wait_lightrag_document_removed(
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    *,
    timeout_sec: float = 180.0,
    poll_interval_sec: float = 0.5,
) -> None:
    """删除后等待 doc_status 清空，避免重建索引时与入库 pipeline 交叉。"""
    doc_id = _document_lightrag_id(document)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        status, entry = _lightrag_doc_status(knowledge_base, document)
        if entry is None:
            return
        if status in (None, "", "failed"):
            _remove_lightrag_doc_status_entry(knowledge_base, doc_id)
            return
        await asyncio.sleep(poll_interval_sec)
    raise AppError(
        status_code=502,
        code="LIGHTRAG_DELETE_TIMEOUT",
        message=f"LightRAG 删除旧图谱超时（doc_id={doc_id}）",
    )


async def delete_document_async(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    wait_removed: bool = False,
) -> None:
    rag = await get_lightrag_instance(db, knowledge_base)
    doc_id = _document_lightrag_id(document)
    runtime = _get_lightrag_runtime()
    async with runtime.env_lock:
        with _lightrag_runtime_env(db, knowledge_base):
            await rag.adelete_by_doc_id(doc_id)
    invalidate_lightrag_instance(knowledge_base.id)
    if wait_removed:
        await _wait_lightrag_document_removed(knowledge_base, document)


def _map_citations(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    references: list[dict[str, Any]] | None,
    chunks: list[dict[str, Any]] | None,
) -> tuple[str, list[dict[str, Any]]]:
    refs = references or []
    chunk_items = chunks or []
    parts: list[str] = []
    citations: list[dict[str, Any]] = []
    ref_no = 0

    file_to_doc: dict[str, KnowledgeDocument] = {}
    docs = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.status != "deleted",
        )
    ).scalars().all()
    for doc in docs:
        file_to_doc[doc.file_name] = doc
        file_to_doc[doc.document_name] = doc

    seen_paths: set[str] = set()
    for chunk in chunk_items:
        file_path = str(chunk.get("file_path") or "").split("|||")[0].strip()
        content = str(chunk.get("content") or "").strip()
        if not content:
            continue
        key = file_path or content[:80]
        if key in seen_paths:
            continue
        seen_paths.add(key)
        ref_no += 1
        doc = file_to_doc.get(file_path) if file_path else None
        doc_name = doc.document_name if doc else (file_path or "文献")
        parts.append(f"[{ref_no}] 《{doc_name}》\n{content}")
        citations.append(
            {
                "ref": ref_no,
                "document_name": doc_name,
                "document_id": doc.id if doc else None,
                "file_path": file_path or None,
                "chunk_id": chunk.get("chunk_id"),
                "knowledge_base_id": knowledge_base.id,
                # 图谱库切片不在关系库，附正文供前端直接展示（chunk_id 为 LightRAG 内部 ID，无法 getChunk）
                "content": content,
            }
        )

    if not parts and refs:
        for ref in refs:
            file_path = str(ref.get("file_path") or "").split("|||")[0].strip()
            if not file_path or file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            ref_no += 1
            doc = file_to_doc.get(file_path)
            doc_name = doc.document_name if doc else file_path
            # 文档级 reference 不带正文，从本地 text_chunks 存储兜底取回原文片段。
            content = _lightrag_document_excerpt(knowledge_base, doc) if doc else ""
            if content:
                parts.append(f"[{ref_no}] 《{doc_name}》\n{content}")
            else:
                parts.append(f"[{ref_no}] 《{doc_name}》")
            citations.append(
                {
                    "ref": ref_no,
                    "document_name": doc_name,
                    "document_id": doc.id if doc else None,
                    "file_path": file_path,
                    "chunk_id": None,
                    "knowledge_base_id": knowledge_base.id,
                    "content": content or None,
                }
            )

    return "\n\n---\n\n".join(parts), citations


async def query_async(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    query: str,
    mode: LightRagQueryMode = "mix",
    top_k: int = 5,
    chunk_top_k: int | None = None,
    include_references: bool = True,
) -> dict[str, Any]:
    rag = await get_lightrag_instance(db, knowledge_base)
    param_kwargs: dict[str, Any] = {
        "mode": mode,
        "top_k": top_k,
        "include_references": include_references,
    }
    # chunk_top_k 控制向量侧召回的文档片段数；未指定时沿用 LightRAG 默认（20）。
    if chunk_top_k is not None and chunk_top_k > 0:
        param_kwargs["chunk_top_k"] = int(chunk_top_k)
    param = QueryParam(**param_kwargs)
    runtime = _get_lightrag_runtime()
    async with runtime.env_lock:
        with _lightrag_runtime_env(db, knowledge_base):
            payload = await rag.aquery_data(query, param)

    if payload.get("status") != "success":
        message = str(payload.get("message") or "LightRAG 查询失败")
        raise AppError(status_code=502, code="LIGHTRAG_QUERY_FAILED", message=message)

    data = payload.get("data") or {}
    entities = data.get("entities") or []
    relationships = data.get("relationships") or []
    chunks = data.get("chunks") or []
    references = data.get("references") or []
    answer_context, citations = _map_citations(
        db,
        knowledge_base=knowledge_base,
        references=references,
        chunks=chunks,
    )
    return {
        "query": query,
        "mode": mode,
        "answer_context": answer_context,
        "chunks": chunks,
        "entities": entities,
        "relationships": relationships,
        "citations": citations,
        "metadata": payload.get("metadata"),
    }


def _load_lightrag_kb(db: Session, *, space_id: int, kb_id: int) -> KnowledgeBase:
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if kb is None:
        raise AppError(status_code=404, code="KB_NOT_FOUND", message="知识库不存在")
    if kb.kb_type != KB_TYPE_LIGHTRAG:
        raise AppError(status_code=400, code="KB_TYPE_NOT_LIGHTRAG", message="仅图知识库支持 LightRAG")
    return kb


def _load_lightrag_document(db: Session, *, kb_id: int, document_id: int) -> KnowledgeDocument:
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    return document


async def _insert_document_runtime(
    space_id: int,
    kb_id: int,
    document_id: int,
    text: str,
    text_chunks: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_structured_progress: Callable[[str, int | None, int | None, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = False,
) -> None:
    with SessionLocal() as db:
        knowledge_base = _load_lightrag_kb(db, space_id=space_id, kb_id=kb_id)
        document = _load_lightrag_document(db, kb_id=kb_id, document_id=document_id)
        await insert_document_async(
            db,
            knowledge_base=knowledge_base,
            document=document,
            text=text,
            text_chunks=text_chunks,
            on_progress=on_progress,
            on_structured_progress=on_structured_progress,
            cancel_event=cancel_event,
            resume=resume,
        )


async def _delete_document_runtime(
    space_id: int,
    kb_id: int,
    document_id: int,
    *,
    wait_removed: bool = False,
) -> None:
    with SessionLocal() as db:
        knowledge_base = _load_lightrag_kb(db, space_id=space_id, kb_id=kb_id)
        document = _load_lightrag_document(db, kb_id=kb_id, document_id=document_id)
        await delete_document_async(
            db,
            knowledge_base=knowledge_base,
            document=document,
            wait_removed=wait_removed,
        )


async def _query_graph_runtime(
    space_id: int,
    kb_id: int,
    query: str,
    mode: LightRagQueryMode = "mix",
    top_k: int = 5,
    chunk_top_k: int | None = None,
    include_references: bool = True,
) -> dict[str, Any]:
    with SessionLocal() as db:
        knowledge_base = _load_lightrag_kb(db, space_id=space_id, kb_id=kb_id)
        return await query_async(
            db,
            knowledge_base=knowledge_base,
            query=query,
            mode=mode,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            include_references=include_references,
        )


def _lightrag_kb_lock_key(kb_id: int) -> str:
    return f"zs-rag:lightrag-insert:kb:{kb_id}"


def insert_document(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    text: str,
    text_chunks: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_structured_progress: Callable[[str, int | None, int | None, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = False,
) -> None:
    from app.core.distributed_lock import acquire_distributed_lock

    space_id = knowledge_base.enterprise_space_id
    kb_id = knowledge_base.id
    document_id = document.id
    insert_lock = _insert_lock_for_kb(kb_id)

    def _on_lock_wait() -> None:
        if on_progress:
            on_progress("图知识库另有入库任务进行中，当前文档排队等待…")

    with acquire_distributed_lock(
        _lightrag_kb_lock_key(kb_id),
        ttl_sec=_lightrag_int_setting("lightrag_insert_wait_timeout_sec", 7200),
        wait_sec=1800.0,
        on_wait=_on_lock_wait,
    ):
        insert_lock.acquire()
        try:
            _get_lightrag_runtime().run(
                _insert_document_runtime(
                    space_id,
                    kb_id,
                    document_id,
                    text,
                    text_chunks,
                    on_progress=on_progress,
                    on_structured_progress=on_structured_progress,
                    cancel_event=cancel_event,
                    resume=resume,
                )
            )
        finally:
            insert_lock.release()


def delete_document(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    wait_removed: bool = False,
    lock_wait_sec: float | None = None,
) -> None:
    from app.core.distributed_lock import acquire_distributed_lock

    kb_id = knowledge_base.id
    insert_lock = _insert_lock_for_kb(kb_id)
    wait_sec = (
        float(lock_wait_sec)
        if lock_wait_sec is not None
        else float(_lightrag_int_setting("lightrag_delete_lock_wait_sec", 120))
    )
    last_wait_log = 0.0

    def _on_lock_wait() -> None:
        nonlocal last_wait_log
        now = time.monotonic()
        if now - last_wait_log >= 10.0:
            logger.info(
                "LightRAG delete waiting for kb lock kb_id=%s doc=doc-%s (wait_sec=%s)",
                kb_id,
                document.id,
                int(wait_sec),
            )
            last_wait_log = now

    try:
        with acquire_distributed_lock(
            _lightrag_kb_lock_key(kb_id),
            ttl_sec=_lightrag_int_setting("lightrag_insert_wait_timeout_sec", 7200),
            wait_sec=wait_sec,
            on_wait=_on_lock_wait,
        ):
            insert_lock.acquire()
            try:
                _get_lightrag_runtime().run(
                    _delete_document_runtime(
                        knowledge_base.enterprise_space_id,
                        knowledge_base.id,
                        document.id,
                        wait_removed=wait_removed,
                    )
                )
            finally:
                insert_lock.release()
    except AppError as exc:
        if exc.code != "RESOURCE_BUSY":
            raise
        logger.warning(
            "LightRAG delete lock timeout kb_id=%s doc=doc-%s; purging local state",
            kb_id,
            document.id,
        )
        purge_lightrag_document_local_state(knowledge_base, document)


def query_graph_kb(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    query: str,
    mode: LightRagQueryMode = "mix",
    top_k: int = 5,
    chunk_top_k: int | None = None,
    include_references: bool = True,
) -> dict[str, Any]:
    return _get_lightrag_runtime().run(
        _query_graph_runtime(
            knowledge_base.enterprise_space_id,
            knowledge_base.id,
            query,
            mode=mode,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            include_references=include_references,
        )
    )
