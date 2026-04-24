from __future__ import annotations

from app.core.errors import AppError
from app.core.provider_adapter import embed_texts
from app.models.model_management import AIModel


EMBEDDING_BATCH_SIZE = 16
EMBEDDING_BATCH_FALLBACK_MESSAGES = ("HTTP 错误：400",)


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


def _generate_embeddings_for_batch(model: AIModel, texts: list[str]) -> list[list[float]]:
    result = embed_texts(model.provider, model.model_name, texts)
    if result.success:
        batch_vectors = _parse_vectors(result.data)
        if len(batch_vectors) != len(texts):
            raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="embedding 响应数量与请求不一致")
        return batch_vectors

    if len(texts) > 1 and any(message in result.message for message in EMBEDDING_BATCH_FALLBACK_MESSAGES):
        middle = max(len(texts) // 2, 1)
        return _generate_embeddings_for_batch(model, texts[:middle]) + _generate_embeddings_for_batch(model, texts[middle:])

    raise AppError(status_code=502, code="EMBEDDING_REQUEST_FAILED", message=result.message)



def generate_embeddings(model: AIModel, texts: list[str]) -> list[list[float]]:
    _ensure_embedding_model(model)
    if not texts:
        return []

    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        vectors.extend(_generate_embeddings_for_batch(model, batch))

    return vectors


def generate_query_embedding(model: AIModel, text: str) -> list[float]:
    vectors = generate_embeddings(model, [text])
    if not vectors:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="未返回查询向量")
    return vectors[0]
