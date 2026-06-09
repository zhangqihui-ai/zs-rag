"""持久化 embedding 缓存（embedding cache）。

按"模型 + 文本内容哈希"缓存已计算的向量，使重解析 / 续传 / 重建索引时
无需再次调用 GPU 计算向量（向量化 vectorization 不重做）。

存储后端使用 Redis（栈内已部署，Celery 多进程 prefork 友好，自带 TTL）。
Redis 不可用时静默降级为"不缓存"，绝不影响主流程。
"""

from __future__ import annotations

import hashlib
import logging
import threading

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "emb"
# float32 序列化；与 generate_embeddings 返回的 np.float32 保持一致
_DTYPE = np.float32

_client_lock = threading.Lock()
_client_cache: tuple[str, object] | None = None
_warned_unavailable = False


def _effective_redis_url() -> str | None:
    settings = get_settings()
    if not getattr(settings, "embedding_cache_enabled", True):
        return None
    return settings.redis_url or "redis://redis:6379/0"


def _get_client():
    """返回可用的 Redis 客户端；不可用时返回 None（降级）。"""
    global _client_cache, _warned_unavailable
    url = _effective_redis_url()
    if not url:
        return None
    with _client_lock:
        if _client_cache is not None and _client_cache[0] == url:
            return _client_cache[1]
        try:
            import redis

            client = redis.from_url(url, socket_connect_timeout=2.0, socket_timeout=2.0)
            client.ping()
            _client_cache = (url, client)
            _warned_unavailable = False
            return client
        except Exception as exc:  # noqa: BLE001 - 降级而非报错
            if not _warned_unavailable:
                logger.warning("embedding 缓存不可用，降级为不缓存：%s", exc)
                _warned_unavailable = True
            _client_cache = None
            return None


def is_enabled() -> bool:
    return _get_client() is not None


def make_hash(model_name: str, prepared_text: str) -> str:
    """以模型名 + 预处理后文本计算稳定哈希，作为缓存键的一部分。"""
    digest = hashlib.sha256()
    digest.update((model_name or "").encode("utf-8"))
    digest.update(b"\x00")
    digest.update((prepared_text or "").encode("utf-8"))
    return digest.hexdigest()


def _redis_key(model_id: int, text_hash: str) -> str:
    return f"{_KEY_PREFIX}:{int(model_id)}:{text_hash}"


def get_many(model_id: int, hashes: list[str], *, dim: int | None = None) -> dict[str, list[float]]:
    """批量取缓存向量；返回 {hash: vector}，未命中的键不在结果中。"""
    if not hashes:
        return {}
    client = _get_client()
    if client is None:
        return {}
    keys = [_redis_key(model_id, h) for h in hashes]
    try:
        raw_values = client.mget(keys)
    except Exception as exc:  # noqa: BLE001
        logger.debug("embedding 缓存读取失败，降级：%s", exc)
        return {}

    result: dict[str, list[float]] = {}
    for text_hash, raw in zip(hashes, raw_values):
        if not raw:
            continue
        try:
            vector = np.frombuffer(raw, dtype=_DTYPE)
        except (TypeError, ValueError):
            continue
        if dim is not None and vector.shape[0] != dim:
            # 维度不一致（模型/配置变更）视为未命中，避免污染
            continue
        result[text_hash] = vector.tolist()
    return result


def put_many(
    model_id: int,
    mapping: dict[str, list[float]],
    *,
    dim: int | None = None,
) -> None:
    """批量写入缓存向量；写入失败静默降级。"""
    if not mapping:
        return
    client = _get_client()
    if client is None:
        return
    settings = get_settings()
    ttl = max(60, int(getattr(settings, "embedding_cache_ttl_sec", 1_209_600)))
    try:
        pipe = client.pipeline(transaction=False)
        for text_hash, vector in mapping.items():
            arr = np.asarray(vector, dtype=_DTYPE)
            if dim is not None and arr.shape[0] != dim:
                continue
            pipe.set(_redis_key(model_id, text_hash), arr.tobytes(), ex=ttl)
        pipe.execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("embedding 缓存写入失败，降级：%s", exc)
