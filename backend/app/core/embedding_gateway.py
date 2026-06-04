from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable

import httpx

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


def generate_embeddings(
    model: AIModel,
    texts: list[str],
    *,
    batch_size: int | None = None,
    on_batch_start: Callable[[int, int, int, int], None] | None = None,
    on_progress: Callable[[int, int, float | None], None] | None = None,
) -> list[list[float]]:
    _ensure_embedding_model(model)
    if not texts:
        return []

    total = len(texts)
    chunk_size = batch_size if batch_size is not None else get_settings().embedding_batch_size
    chunk_size = max(1, min(int(chunk_size), 128))
    total_batches = (total + chunk_size - 1) // chunk_size
    vectors: list[list[float]] = []
    for batch_index, start in enumerate(range(0, total, chunk_size), start=1):
        batch = texts[start : start + chunk_size]
        if on_batch_start is not None:
            on_batch_start(batch_index, total_batches, len(batch), start)
        batch_started = time.monotonic()
        vectors.extend(_generate_embeddings_for_batch(model, batch))
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


def generate_query_embedding(model: AIModel, text: str) -> list[float]:
    vectors = generate_embeddings(model, [text])
    if not vectors:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="未返回查询向量")
    return vectors[0]


def probe_embedding_dimension(model: AIModel) -> int:
    """调用 embedding 模型探测实际向量维度（用于 LightRAG / Milvus 对齐）。"""
    vectors = generate_embeddings(model, ["dimension probe"])
    if not vectors or not vectors[0]:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="无法探测 embedding 维度")
    dimension = len(vectors[0])
    if dimension <= 0:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 维度无效")
    return dimension
