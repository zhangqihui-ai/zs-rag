from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from sqlalchemy.orm import Session

from app.core import embedding_cache
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.provider_adapter import ProviderResponse, embed_texts
from app.models.model_management import AIModel

logger = logging.getLogger(__name__)

# 通义 text-embedding-v4 等模型对单条 input 有长度上限；批量过大也易触发 400
EMBEDDING_BATCH_SIZE = 8
EMBEDDING_MAX_INPUT_CHARS = 8192
EMBEDDING_BATCH_FALLBACK_MESSAGES = (
    "HTTP 错误：400",
    "HTTP 错误：413",
    "HTTP 错误：422",
    "请求过于频繁",
)

# 账户/鉴权类错误重试截断无意义，应直接失败并提示用户处理
EMBEDDING_NON_RETRYABLE_MARKERS = (
    "账户欠费",
    "Arrearage",
    "认证失败",
    "API Key 无效",
    "额度不足",
    "insufficient_quota",
    "无权调用",
)

EMBEDDING_RETRYABLE_MARKERS = (
    "timed out",
    "Timeout",
    "ConnectTimeout",
    "ReadTimeout",
    "WriteTimeout",
    "连接测试失败",
    "Connection reset",
    "Connection refused",
    "RemoteProtocolError",
)

_QUERY_EMBEDDING_CACHE_MAX = 256
_query_embedding_cache: OrderedDict[tuple[int, str], list[float]] = OrderedDict()
_query_embedding_cache_lock = threading.Lock()


def _ensure_embedding_model(model: AIModel) -> None:
    if model.model_type != "embedding":
        raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="指定模型不是 embedding 模型")
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="指定 embedding 模型尚未启用")
    if model.provider is None:
        raise AppError(status_code=500, code="PROVIDER_NOT_FOUND", message="embedding 模型缺少 Provider 配置")


def _parse_vectors(data: object) -> list[list[float]]:
    if not isinstance(data, list):
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 响应格式无效")

    vectors: list[list[float]] = []
    for item in data:
        if not isinstance(item, list):
            raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 响应格式无效")
        vectors.append([float(value) for value in item])
    return vectors


def prepare_text_for_embedding(text: str, *, max_chars: int = EMBEDDING_MAX_INPUT_CHARS) -> str:
    """清洗并截断送入 embedding API 的文本，避免 NUL/过长/空串导致厂商 400。"""
    if not text:
        return " "
    s = text.replace("\x00", "")
    # 去掉不可见控制字符（保留换行、制表）
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    s = s.strip()
    if not s:
        return " "
    if len(s) > max_chars:
        s = s[:max_chars]
    return s


def _is_non_retryable_embedding_error(message: str) -> bool:
    return any(token in message for token in EMBEDDING_NON_RETRYABLE_MARKERS)


def _should_split_batch_on_error(message: str) -> bool:
    if _is_non_retryable_embedding_error(message):
        return False
    return any(token in message for token in EMBEDDING_BATCH_FALLBACK_MESSAGES)


def _is_retryable_embedding_error(message: str) -> bool:
    if _is_non_retryable_embedding_error(message):
        return False
    return any(token in message for token in EMBEDDING_RETRYABLE_MARKERS)


def _embedding_request_timeout() -> httpx.Timeout:
    read_sec = float(get_settings().embedding_timeout_sec)
    return httpx.Timeout(connect=30.0, read=read_sec, write=30.0, pool=30.0)


def _raise_embedding_failed(message: str | None) -> None:
    raise AppError(
        status_code=502,
        code="EMBEDDING_REQUEST_FAILED",
        message=message or "embedding 请求失败",
    )


def _embed_prepared_batch(model: AIModel, texts: list[str]) -> ProviderResponse:
    settings = get_settings()
    timeout = _embedding_request_timeout()
    max_retries = max(1, int(settings.embedding_max_retries))
    last_result: ProviderResponse | None = None
    for attempt in range(max_retries):
        last_result = embed_texts(model.provider, model.model_name, texts, timeout=timeout)
        if last_result.success:
            return last_result
        message = last_result.message or ""
        if _is_non_retryable_embedding_error(message):
            break
        if attempt + 1 >= max_retries or not _is_retryable_embedding_error(message):
            break
        logger.warning(
            "embedding batch retry %s/%s (batch_size=%s): %s",
            attempt + 1,
            max_retries,
            len(texts),
            message,
        )
        time.sleep(min(2**attempt, 8))
    assert last_result is not None
    return last_result


def _generate_single_with_truncation_fallback(model: AIModel, text: str) -> list[float]:
    """单条仍 400 时逐级缩短文本；最后退化为占位符 embedding。"""
    limits = (
        EMBEDDING_MAX_INPUT_CHARS,
        4096,
        2048,
        1024,
        512,
        256,
        64,
    )
    seen: set[str] = set()
    for limit in limits:
        candidate = prepare_text_for_embedding(text, max_chars=limit)
        if candidate in seen:
            continue
        seen.add(candidate)
        result = _embed_prepared_batch(model, [candidate])
        if result.success:
            batch_vectors = _parse_vectors(result.data)
            if batch_vectors:
                if limit < EMBEDDING_MAX_INPUT_CHARS:
                    logger.warning(
                        "embedding 单条降级成功（截断至 %s 字符，原长 %s）",
                        limit,
                        len(text),
                    )
                return batch_vectors[0]
        if _is_non_retryable_embedding_error(result.message or ""):
            _raise_embedding_failed(result.message)

    placeholder = prepare_text_for_embedding(" ", max_chars=8)
    result = _embed_prepared_batch(model, [placeholder])
    if result.success:
        batch_vectors = _parse_vectors(result.data)
        if batch_vectors:
            logger.warning(
                "embedding 单条使用占位向量（原长 %s，末次错误需查厂商配置）",
                len(text),
            )
            return batch_vectors[0]

    _raise_embedding_failed(result.message)


def _generate_embeddings_for_batch(model: AIModel, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    prepared = [prepare_text_for_embedding(t) for t in texts]
    result = _embed_prepared_batch(model, prepared)
    if result.success:
        batch_vectors = _parse_vectors(result.data)
        if len(batch_vectors) != len(prepared):
            raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 响应数量与请求不一致")
        return batch_vectors

    if len(prepared) > 1 and _should_split_batch_on_error(result.message):
        middle = max(len(prepared) // 2, 1)
        return _generate_embeddings_for_batch(model, prepared[:middle]) + _generate_embeddings_for_batch(
            model, prepared[middle:]
        )

    if _is_non_retryable_embedding_error(result.message or ""):
        _raise_embedding_failed(result.message)

    if len(prepared) == 1:
        return [_generate_single_with_truncation_fallback(model, texts[0])]

    _raise_embedding_failed(result.message)


EMBEDDING_CONCURRENCY_HARD_LIMIT = 16


def resolve_embedding_concurrency(config: object) -> int:
    """解析知识库级 embedding 并发度（embedding concurrency）。

    优先读取 ``config["embedding_concurrency"]``（知识库配置页可覆盖），
    缺省回落到全局 ``settings.embedding_max_concurrency``。结果统一夹在
    ``[1, EMBEDDING_CONCURRENCY_HARD_LIMIT]`` 区间，避免并发过高拖垮后端。
    """
    settings = get_settings()
    fallback = max(
        1, min(int(settings.embedding_max_concurrency), EMBEDDING_CONCURRENCY_HARD_LIMIT)
    )
    if isinstance(config, dict):
        raw = config.get("embedding_concurrency")
        if raw is not None:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return fallback
            return max(1, min(value, EMBEDDING_CONCURRENCY_HARD_LIMIT))
    return fallback


def _estimate_embedding_tokens(texts: list[str]) -> int:
    total = 0
    for text in texts:
        s = text or ""
        if not s.strip():
            continue
        total += max(1, len(s) // 4)
    return total


def _record_embedding_batch_usage(
    model: AIModel,
    *,
    usage_db: Session | None,
    batch: list[str],
    usage_source: str | None,
    usage_user_id: int | None,
) -> None:
    batch_len = len(batch)
    if usage_db is None or batch_len <= 0:
        return
    space_id = getattr(model, "enterprise_space_id", None)
    if space_id is None:
        return
    from app.services.usage_metrics_service import record_usage_event

    record_usage_event(
        usage_db,
        enterprise_space_id=int(space_id),
        event_type="embedding_call",
        model_type="embedding",
        model_id=model.id,
        source=usage_source or "embedding",
        user_id=usage_user_id,
        tokens_in=_estimate_embedding_tokens(batch),
        result_count=batch_len,
    )


def generate_embeddings(
    model: AIModel,
    texts: list[str],
    *,
    batch_size: int | None = None,
    max_concurrency: int | None = None,
    on_batch_start: Callable[[int, int, int, int], None] | None = None,
    on_progress: Callable[[int, int, float | None], None] | None = None,
    on_cache_stats: Callable[[int, int], None] | None = None,
    usage_db: Session | None = None,
    usage_source: str | None = None,
    usage_user_id: int | None = None,
) -> list[list[float]]:
    """生成向量；命中持久化 embedding 缓存的段不再调用 GPU 计算。

    ``on_cache_stats(hit_count, total)`` 在使用缓存时回调，便于上层展示复用进度。
    """
    _ensure_embedding_model(model)
    if not texts:
        return []

    total = len(texts)
    use_cache = bool(getattr(get_settings(), "embedding_cache_enabled", True)) and embedding_cache.is_enabled()

    cached_vectors: list[list[float] | None] = [None] * total
    text_hashes: list[str | None] = [None] * total
    miss_indices: list[int]
    if use_cache:
        prepared = [prepare_text_for_embedding(t) for t in texts]
        hashes = [embedding_cache.make_hash(model.model_name, p) for p in prepared]
        hits = embedding_cache.get_many(model.id, hashes)
        miss_indices = []
        for i, h in enumerate(hashes):
            text_hashes[i] = h
            vec = hits.get(h)
            if vec is not None:
                cached_vectors[i] = vec
            else:
                miss_indices.append(i)
        if hits:
            logger.info(
                "embedding cache hit %s/%s (model_id=%s)", len(hits), total, model.id
            )
    else:
        miss_indices = list(range(total))

    hit_count = total - len(miss_indices)
    if on_cache_stats is not None and use_cache:
        on_cache_stats(hit_count, total)

    # 全部命中：直接返回，进度直接补满
    if not miss_indices:
        if on_progress is not None:
            on_progress(total, total, 0.0)
        return [vec for vec in cached_vectors if vec is not None]

    miss_texts = [texts[i] for i in miss_indices]

    wrapped_progress: Callable[[int, int, float | None], None] | None = None
    if on_progress is not None:
        def wrapped_progress(done_miss: int, _total_miss: int, elapsed: float | None) -> None:
            on_progress(min(hit_count + done_miss, total), total, elapsed)

    miss_vectors = _compute_embeddings(
        model,
        miss_texts,
        batch_size=batch_size,
        max_concurrency=max_concurrency,
        on_batch_start=on_batch_start,
        on_progress=wrapped_progress,
        usage_db=usage_db,
        usage_source=usage_source,
        usage_user_id=usage_user_id,
    )

    if use_cache and miss_vectors:
        dim = len(miss_vectors[0]) if miss_vectors[0] else None
        to_put: dict[str, list[float]] = {}
        for local_idx, global_idx in enumerate(miss_indices):
            h = text_hashes[global_idx]
            if h is not None and local_idx < len(miss_vectors):
                to_put[h] = miss_vectors[local_idx]
        embedding_cache.put_many(model.id, to_put, dim=dim)

    result: list[list[float]] = []
    miss_iter = iter(miss_vectors)
    for i in range(total):
        cached = cached_vectors[i]
        result.append(cached if cached is not None else next(miss_iter))
    return result


def _compute_embeddings(
    model: AIModel,
    texts: list[str],
    *,
    batch_size: int | None,
    max_concurrency: int | None,
    on_batch_start: Callable[[int, int, int, int], None] | None,
    on_progress: Callable[[int, int, float | None], None] | None,
    usage_db: Session | None = None,
    usage_source: str | None = None,
    usage_user_id: int | None = None,
) -> list[list[float]]:
    """实际计算向量（不经缓存）：根据并发度走串行或有界并发批处理。"""
    total = len(texts)
    chunk_size = batch_size if batch_size is not None else get_settings().embedding_batch_size
    chunk_size = max(1, min(int(chunk_size), 128))
    total_batches = (total + chunk_size - 1) // chunk_size

    if max_concurrency is None:
        concurrency = max(1, min(int(get_settings().embedding_max_concurrency), EMBEDDING_CONCURRENCY_HARD_LIMIT))
    else:
        concurrency = max(1, min(int(max_concurrency), EMBEDDING_CONCURRENCY_HARD_LIMIT))
    concurrency = min(concurrency, total_batches)

    if concurrency <= 1:
        return _generate_embeddings_serial(
            model,
            texts,
            chunk_size=chunk_size,
            total=total,
            total_batches=total_batches,
            on_batch_start=on_batch_start,
            on_progress=on_progress,
            usage_db=usage_db,
            usage_source=usage_source,
            usage_user_id=usage_user_id,
        )

    return _generate_embeddings_concurrent(
        model,
        texts,
        chunk_size=chunk_size,
        total=total,
        total_batches=total_batches,
        concurrency=concurrency,
        on_batch_start=on_batch_start,
        on_progress=on_progress,
        usage_db=usage_db,
        usage_source=usage_source,
        usage_user_id=usage_user_id,
    )


def _generate_embeddings_serial(
    model: AIModel,
    texts: list[str],
    *,
    chunk_size: int,
    total: int,
    total_batches: int,
    on_batch_start: Callable[[int, int, int, int], None] | None,
    on_progress: Callable[[int, int, float | None], None] | None,
    usage_db: Session | None = None,
    usage_source: str | None = None,
    usage_user_id: int | None = None,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for batch_index, start in enumerate(range(0, total, chunk_size), start=1):
        batch = texts[start : start + chunk_size]
        if on_batch_start is not None:
            on_batch_start(batch_index, total_batches, len(batch), start)
        batch_started = time.monotonic()
        vectors.extend(_generate_embeddings_for_batch(model, batch))
        _record_embedding_batch_usage(
            model,
            usage_db=usage_db,
            batch=batch,
            usage_source=usage_source,
            usage_user_id=usage_user_id,
        )
        batch_elapsed = time.monotonic() - batch_started
        done = min(start + len(batch), total)
        if on_progress is not None:
            on_progress(done, total, batch_elapsed)
        logger.info(
            "embedding batch %s/%s done (%s/%s texts, %.1fs)",
            batch_index,
            total_batches,
            done,
            total,
            batch_elapsed,
        )

    return vectors


def _generate_embeddings_concurrent(
    model: AIModel,
    texts: list[str],
    *,
    chunk_size: int,
    total: int,
    total_batches: int,
    concurrency: int,
    on_batch_start: Callable[[int, int, int, int], None] | None,
    on_progress: Callable[[int, int, float | None], None] | None,
    usage_db: Session | None = None,
    usage_source: str | None = None,
    usage_user_id: int | None = None,
) -> list[list[float]]:
    """多实例 Embedding 后端下的有界并发向量化；保持返回顺序与原文一致。"""
    batches = [texts[start : start + chunk_size] for start in range(0, total, chunk_size)]
    results: list[list[list[float]] | None] = [None] * len(batches)
    done_lock = threading.Lock()
    done_count = 0

    # 并发模式下逐批播报开始信息会刷屏，这里仅在首批播报一次以提示"请求已发出"。
    if on_batch_start is not None:
        on_batch_start(1, total_batches, len(batches[0]), 0)

    def _work(index: int) -> tuple[int, list[list[float]], float, int]:
        started = time.monotonic()
        vecs = _generate_embeddings_for_batch(model, batches[index])
        return index, vecs, time.monotonic() - started, len(batches[index])

    logger.info(
        "embedding concurrent start: %s texts in %s batches, concurrency=%s",
        total,
        total_batches,
        concurrency,
    )
    executor = ThreadPoolExecutor(max_workers=concurrency)
    try:
        futures = [executor.submit(_work, i) for i in range(len(batches))]
        for future in as_completed(futures):
            index, vecs, batch_elapsed, batch_len = future.result()
            results[index] = vecs
            _record_embedding_batch_usage(
                model,
                usage_db=usage_db,
                batch=batches[index],
                usage_source=usage_source,
                usage_user_id=usage_user_id,
            )
            with done_lock:
                done_count += batch_len
                done_now = done_count
            if on_progress is not None:
                on_progress(done_now, total, batch_elapsed)
            logger.info(
                "embedding batch done (%s/%s texts, %.1fs)",
                done_now,
                total,
                batch_elapsed,
            )
    except BaseException:
        # 取消或异常：尽快放弃尚未开始的批次，避免无谓的 GPU 调用。
        for pending in futures:
            pending.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    vectors: list[list[float]] = []
    for batch_vecs in results:
        if batch_vecs is None:
            raise AppError(
                status_code=502,
                code="EMBEDDING_RESPONSE_INVALID",
                message="并发向量化存在缺失批次",
            )
        vectors.extend(batch_vecs)
    return vectors


def generate_query_embedding(model: AIModel, text: str) -> list[float]:
    """检索用查询向量；同模型 + 同文本在进程内缓存，避免重复调用慢速 Embedding API。"""
    _ensure_embedding_model(model)
    prepared = prepare_text_for_embedding(text)
    cache_key = (int(model.id), prepared)
    with _query_embedding_cache_lock:
        cached = _query_embedding_cache.get(cache_key)
        if cached is not None:
            _query_embedding_cache.move_to_end(cache_key)
            return cached

    vectors = generate_embeddings(model, [text])
    if not vectors:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="未返回查询向量")
    vector = vectors[0]
    with _query_embedding_cache_lock:
        _query_embedding_cache[cache_key] = vector
        _query_embedding_cache.move_to_end(cache_key)
        while len(_query_embedding_cache) > _QUERY_EMBEDDING_CACHE_MAX:
            _query_embedding_cache.popitem(last=False)
    return vector


def probe_embedding_dimension(model: AIModel) -> int:
    """调用 embedding 模型探测实际向量维度（用于 LightRAG / Milvus 对齐）。"""
    vectors = generate_embeddings(model, ["dimension probe"])
    if not vectors or not vectors[0]:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="无法探测 embedding 维度")
    dimension = len(vectors[0])
    if dimension <= 0:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 维度无效")
    return dimension
