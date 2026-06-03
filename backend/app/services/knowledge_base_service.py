from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.embedding_gateway import probe_embedding_dimension
from app.core.errors import AppError
from app.core.kb_type import KB_TYPE_LIGHTRAG
from app.models.knowledge_base import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, Neo4jConnection
from app.models.model_management import AIModel, AIModelDefault

# 历史遗留占位：OpenAI text-embedding-ada-002 等常见模型维度；新建库应通过 embedding 探测写入。
FALLBACK_MILVUS_DIMENSION = 1536


def build_collection_name(space_id: int, kb_id: int) -> str:
    return f"kb_{space_id}_{kb_id}_chunks"


def get_knowledge_base_or_error(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    include_deleted: bool = False,
) -> KnowledgeBase:
    stmt = (
        select(KnowledgeBase)
        .options(
            selectinload(KnowledgeBase.neo4j_connection),
            selectinload(KnowledgeBase.embedding_model).selectinload(AIModel.provider),
        )
        .where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == space_id,
        )
    )
    if not include_deleted:
        stmt = stmt.where(KnowledgeBase.status != "deleted")
    knowledge_base = db.execute(stmt).scalar_one_or_none()
    if knowledge_base is None:
        raise AppError(status_code=404, code="KNOWLEDGE_BASE_NOT_FOUND", message="知识库不存在")
    return knowledge_base


def ensure_knowledge_base_name_unique(
    db: Session,
    *,
    space_id: int,
    name: str,
    exclude_kb_id: int | None = None,
) -> None:
    stmt = select(KnowledgeBase).where(
        KnowledgeBase.enterprise_space_id == space_id,
        KnowledgeBase.name == name,
        KnowledgeBase.status != "deleted",
    )
    if exclude_kb_id is not None:
        stmt = stmt.where(KnowledgeBase.id != exclude_kb_id)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        raise AppError(status_code=409, code="KNOWLEDGE_BASE_ALREADY_EXISTS", message="同名知识库已存在")


def build_deleted_knowledge_base_name(original: str, kb_id: int) -> str:
    """软删除时给名称加归档后缀，避免唯一约束阻塞重建同名知识库。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = f"__deleted__{kb_id}__{stamp}"
    base = (original or "").strip() or "knowledge_base"
    max_len = 200
    keep = max_len - len(suffix)
    if keep < 1:
        return suffix[-max_len:]
    return f"{base[:keep]}{suffix}"


def resolve_knowledge_base_milvus_dimension(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    persist: bool = True,
) -> int:
    """按知识库绑定（或企业空间默认）的 embedding 模型探测向量维度。"""
    model = get_embedding_model_for_knowledge_base(db, knowledge_base=knowledge_base)
    dimension = probe_embedding_dimension(model)
    if knowledge_base.milvus_dimension != dimension:
        knowledge_base.milvus_dimension = dimension
        if persist:
            db.commit()
            db.refresh(knowledge_base)
        else:
            db.flush()
    return dimension


def ensure_knowledge_base_milvus_fields(db: Session, knowledge_base: KnowledgeBase) -> None:
    if not knowledge_base.milvus_collection_name:
        knowledge_base.milvus_collection_name = build_collection_name(
            knowledge_base.enterprise_space_id,
            knowledge_base.id,
        )
    if not knowledge_base.milvus_metric_type:
        knowledge_base.milvus_metric_type = "COSINE"
    needs_dimension = (
        not knowledge_base.milvus_dimension or knowledge_base.milvus_dimension <= 0
    )
    if needs_dimension and (
        knowledge_base.vector_db_enabled or knowledge_base.kb_type == KB_TYPE_LIGHTRAG
    ):
        try:
            resolve_knowledge_base_milvus_dimension(
                db,
                knowledge_base=knowledge_base,
                persist=False,
            )
        except AppError:
            knowledge_base.milvus_dimension = FALLBACK_MILVUS_DIMENSION
    elif needs_dimension:
        knowledge_base.milvus_dimension = FALLBACK_MILVUS_DIMENSION


def get_neo4j_connection_or_error(db: Session, *, knowledge_base_id: int) -> Neo4jConnection:
    connection = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == knowledge_base_id)
    ).scalar_one_or_none()
    if connection is None:
        raise AppError(status_code=404, code="NEO4J_CONNECTION_NOT_FOUND", message="Neo4j 连接不存在")
    return connection


def get_embedding_model_for_knowledge_base(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    override_model_id: int | None = None,
) -> AIModel:
    model_id = override_model_id or knowledge_base.embedding_model_id
    if model_id is None:
        default_binding = db.execute(
            select(AIModelDefault)
            .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
            .where(
                AIModelDefault.enterprise_space_id == knowledge_base.enterprise_space_id,
                AIModelDefault.model_type == "embedding",
            )
        ).scalar_one_or_none()
        if default_binding is not None and default_binding.model is not None:
            model = default_binding.model
            if not model.is_enabled:
                raise AppError(status_code=400, code="MODEL_DISABLED", message="默认 embedding 模型尚未启用")
            return model
        raise AppError(status_code=400, code="EMBEDDING_MODEL_NOT_CONFIGURED", message="当前企业空间尚未配置默认 embedding 模型")

    model = db.execute(
        select(AIModel)
        .options(selectinload(AIModel.provider))
        .where(
            AIModel.id == model_id,
            AIModel.enterprise_space_id == knowledge_base.enterprise_space_id,
        )
    ).scalar_one_or_none()
    if model is None:
        raise AppError(status_code=404, code="MODEL_NOT_FOUND", message="embedding 模型不存在")
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="指定 embedding 模型尚未启用")
    if model.model_type != "embedding":
        raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="指定模型不是 embedding 模型")
    return model


def get_rerank_model_for_knowledge_base(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    override_model_id: int | None = None,
) -> AIModel:
    model_id = override_model_id
    if model_id is None:
        stored = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
        retrieval = stored.get("retrieval") if isinstance(stored.get("retrieval"), dict) else {}
        raw_id = retrieval.get("rerank_model_id")
        if raw_id is not None:
            try:
                model_id = int(raw_id)
            except (TypeError, ValueError):
                model_id = None
    if model_id is None:
        default_binding = db.execute(
            select(AIModelDefault)
            .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
            .where(
                AIModelDefault.enterprise_space_id == knowledge_base.enterprise_space_id,
                AIModelDefault.model_type == "rerank",
            )
        ).scalar_one_or_none()
        if default_binding is not None and default_binding.model is not None:
            model = default_binding.model
            if not model.is_enabled:
                raise AppError(status_code=400, code="MODEL_DISABLED", message="默认 rerank 模型尚未启用")
            return model
        raise AppError(status_code=400, code="RERANK_MODEL_NOT_CONFIGURED", message="当前知识库未配置 rerank 模型")

    model = db.execute(
        select(AIModel)
        .options(selectinload(AIModel.provider))
        .where(
            AIModel.id == model_id,
            AIModel.enterprise_space_id == knowledge_base.enterprise_space_id,
        )
    ).scalar_one_or_none()
    if model is None:
        raise AppError(status_code=404, code="MODEL_NOT_FOUND", message="rerank 模型不存在")
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="指定 rerank 模型尚未启用")
    if model.model_type != "rerank":
        raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="指定模型不是 rerank 模型")
    return model


def format_ai_model_for_log(model: AIModel, *, role: str) -> str:
    """生成解析/入库日志中展示的模型一行说明。"""
    prov_name = ""
    if model.provider is not None:
        prov_name = (
            getattr(model.provider, "provider_name", None)
            or getattr(model.provider, "provider_code", None)
            or ""
        )
    label = (model.model_name or model.model_code or "").strip() or f"id={model.id}"
    if prov_name:
        return f"{role}：{label}（{prov_name}）"
    return f"{role}：{label}"


def get_knowledge_base_stats(db: Session, *, knowledge_base: KnowledgeBase) -> dict[str, int]:
    document_total = db.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.status != "deleted",
        )
    ).scalar_one()
    indexed_document_total = db.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.status.in_(("indexed", "graph_indexed")),
        )
    ).scalar_one()
    failed_document_total = db.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.status.in_(("failed", "graph_failed")),
        )
    ).scalar_one()
    chunk_total = db.execute(
        select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.knowledge_base_id == knowledge_base.id)
    ).scalar_one()

    return {
        "knowledge_base_id": knowledge_base.id,
        "document_total": int(document_total or 0),
        "indexed_document_total": int(indexed_document_total or 0),
        "chunk_total": int(chunk_total or 0),
        "failed_document_total": int(failed_document_total or 0),
    }
