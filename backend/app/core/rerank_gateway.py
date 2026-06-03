"""Rerank 模型调用网关：对召回候选做二阶段精排。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.errors import AppError
from app.core.provider_adapter import rerank_documents
from app.models.model_management import AIModel

logger = logging.getLogger(__name__)

RERANK_MAX_DOCUMENT_CHARS = 4096
RERANK_RECALL_FACTOR = 4


@dataclass(frozen=True)
class RerankScore:
    index: int
    score: float


def _ensure_rerank_model(model: AIModel) -> None:
    if model.model_type != "rerank":
        raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="指定模型不是 rerank 模型")
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="指定 rerank 模型尚未启用")
    if model.provider is None:
        raise AppError(status_code=500, code="PROVIDER_NOT_FOUND", message="rerank 模型缺少 Provider 配置")


def _prepare_document(text: str) -> str:
    s = (text or "").replace("\x00", "").strip()
    if not s:
        return " "
    if len(s) > RERANK_MAX_DOCUMENT_CHARS:
        return s[:RERANK_MAX_DOCUMENT_CHARS]
    return s


def rerank_texts(
    model: AIModel,
    *,
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[RerankScore]:
    """调用 rerank API，返回与 documents 下标对应的 relevance 分数（按分数降序）。"""
    _ensure_rerank_model(model)
    if not documents:
        return []

    prepared = [_prepare_document(doc) for doc in documents]
    q = (query or "").strip() or " "
    limit = top_n if top_n is not None else len(prepared)
    limit = max(1, min(limit, len(prepared)))

    timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)
    result = rerank_documents(
        model.provider,
        model.model_name,
        query=q,
        documents=prepared,
        top_n=limit,
        timeout=timeout,
    )
    if not result.success:
        logger.warning("rerank 请求失败，回退原始排序：%s", result.message)
        return [
            RerankScore(index=i, score=float(len(prepared) - i) / max(len(prepared), 1))
            for i in range(len(prepared))
        ]

    raw = result.data
    if not isinstance(raw, list):
        raise AppError(status_code=502, code="RERANK_RESPONSE_INVALID", message="rerank 响应格式无效")

    scores: list[RerankScore] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
            score = float(item.get("score"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(prepared):
            scores.append(RerankScore(index=idx, score=score))
    if not scores:
        raise AppError(status_code=502, code="RERANK_RESPONSE_INVALID", message="rerank 响应无有效结果")
    scores.sort(key=lambda row: row.score, reverse=True)
    return scores
