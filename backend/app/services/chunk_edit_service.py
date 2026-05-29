"""单切片 enrichment（关键词/假设问题）编辑与增量重索引。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embedding_gateway import generate_embeddings
from app.core.errors import AppError
from app.core.milvus_client import create_collection_if_not_exists, delete_vectors, insert_vectors
from app.core.parser_config import resolve_enrichment
from app.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkVectorStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.services.chunk_enrichment_service import (
    build_keyword_text,
    enrich_chunk_with_llm,
)
from app.services.chunk_enrichment_service import _resolve_enrichment_llm  # noqa: PLC2701
from app.services.knowledge_base_service import (
    ensure_knowledge_base_milvus_fields,
    get_embedding_model_for_knowledge_base,
    get_knowledge_base_or_error,
)
from app.services import opensearch_chunk_service
from app.services.chunk_response import serialize_chunk

_NON_EDITABLE_CHUNK_SOURCES = frozenset({"mineru_graph_preview", "lightrag_text_chunk"})
_MAX_KEYWORDS = 12
_MAX_QUESTIONS = 5


def _normalize_string_list(values: list[str] | None, *, max_items: int) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        item = str(raw).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= max_items:
            break
    return out


def _enrichment_lists_from_metadata(meta: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    meta = meta or {}
    kw_raw = meta.get("enrichment_keywords") or []
    q_raw = meta.get("enrichment_questions") or []
    keywords = (
        [str(k).strip() for k in kw_raw if str(k).strip()]
        if isinstance(kw_raw, list)
        else []
    )
    questions = (
        [str(q).strip() for q in q_raw if str(q).strip()]
        if isinstance(q_raw, list)
        else []
    )
    return keywords[:_MAX_KEYWORDS], questions[:_MAX_QUESTIONS]


def chunk_enrichment_editable(chunk: KnowledgeChunk) -> bool:
    meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    source = str(meta.get("source") or "")
    return source not in _NON_EDITABLE_CHUNK_SOURCES


def get_chunk_for_edit(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    chunk_id: int,
) -> KnowledgeChunk:
    get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=False)
    chunk = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.id == chunk_id,
            KnowledgeChunk.enterprise_space_id == space_id,
            KnowledgeChunk.knowledge_base_id == kb_id,
        )
    ).scalar_one_or_none()
    if chunk is None:
        raise AppError(status_code=404, code="CHUNK_NOT_FOUND", message="切片不存在或无权访问")
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == chunk.document_id,
            KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
        )
    ).scalar_one_or_none()
    if document is None:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    return chunk


def _ensure_chunk_editable(chunk: KnowledgeChunk) -> None:
    if not chunk_enrichment_editable(chunk):
        raise AppError(
            status_code=400,
            code="CHUNK_ENRICHMENT_NOT_EDITABLE",
            message="该切片不支持编辑关键词与假设问题",
        )


def _reindex_single_chunk_vector(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    chunk: KnowledgeChunk,
    document: KnowledgeDocument,
) -> None:
    settings = get_settings()
    if not knowledge_base.vector_db_enabled:
        return

    ensure_knowledge_base_milvus_fields(db, knowledge_base)
    embedding_model = get_embedding_model_for_knowledge_base(db, knowledge_base=knowledge_base)
    text = (chunk.keyword_text or chunk.content or "").strip()
    if not text:
        return

    vectors = generate_embeddings(embedding_model, [text])
    if not vectors or len(vectors[0]) <= 0:
        raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="未返回有效向量")

    vector_dimension = len(vectors[0])
    if knowledge_base.milvus_dimension and knowledge_base.milvus_dimension != vector_dimension:
        raise AppError(
            status_code=400,
            code="MILVUS_DIMENSION_MISMATCH",
            message=f"Milvus 配置维度为 {knowledge_base.milvus_dimension}，但 embedding 结果维度为 {vector_dimension}",
        )
    if not knowledge_base.milvus_dimension:
        knowledge_base.milvus_dimension = vector_dimension
        db.flush()

    create_result = create_collection_if_not_exists(
        host=settings.milvus_host,
        port=settings.milvus_port,
        collection_name=knowledge_base.milvus_collection_name,
        dimension=knowledge_base.milvus_dimension,
        metric_type=knowledge_base.milvus_metric_type,
        username=settings.milvus_username,
        password=settings.milvus_password,
    )
    if not create_result.success:
        raise AppError(status_code=502, code="MILVUS_COLLECTION_FAILED", message=create_result.message)

    delete_result = delete_vectors(
        host=settings.milvus_host,
        port=settings.milvus_port,
        collection_name=knowledge_base.milvus_collection_name,
        chunk_uids=[chunk.chunk_uid],
        username=settings.milvus_username,
        password=settings.milvus_password,
    )
    if not delete_result.success:
        raise AppError(status_code=502, code="MILVUS_DELETE_FAILED", message=delete_result.message)

    metadata = [
        {
            "chunk_uid": chunk.chunk_uid,
            "enterprise_space_id": chunk.enterprise_space_id,
            "knowledge_base_id": chunk.knowledge_base_id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "page_no": chunk.page_no,
            "heading_path": chunk.heading_path,
        }
    ]
    insert_result = insert_vectors(
        host=settings.milvus_host,
        port=settings.milvus_port,
        collection_name=knowledge_base.milvus_collection_name,
        vectors=vectors,
        metadata=metadata,
        username=settings.milvus_username,
        password=settings.milvus_password,
    )
    if not insert_result.success:
        raise AppError(status_code=502, code="MILVUS_INSERT_FAILED", message=insert_result.message)

    chunk.vector_status = KnowledgeChunkVectorStatus.INDEXED.value
    chunk.vector_id = chunk.chunk_uid

    if opensearch_chunk_service.is_enabled():
        opensearch_chunk_service.bulk_upsert_chunks(
            document_name=document.document_name or document.file_name,
            chunks=[chunk],
        )


def update_chunk_enrichment(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    chunk_id: int,
    keywords: list[str],
    questions: list[str],
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=False)
    chunk = get_chunk_for_edit(db, space_id=space_id, kb_id=kb_id, chunk_id=chunk_id)
    _ensure_chunk_editable(chunk)
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == chunk.document_id,
            KnowledgeDocument.enterprise_space_id == space_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
        )
    ).scalar_one_or_none()
    if document is None:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")

    norm_keywords = _normalize_string_list(keywords, max_items=_MAX_KEYWORDS)
    norm_questions = _normalize_string_list(questions, max_items=_MAX_QUESTIONS)

    meta = dict(chunk.metadata_json or {})
    meta["enrichment_keywords"] = norm_keywords
    meta["enrichment_questions"] = norm_questions
    meta["enrichment_source"] = "manual"

    chunk.metadata_json = meta
    chunk.keyword_text = build_keyword_text(
        chunk.content or "",
        keywords=norm_keywords,
        questions=norm_questions,
    )

    _reindex_single_chunk_vector(db, knowledge_base=knowledge_base, chunk=chunk, document=document)
    db.commit()
    db.refresh(chunk)
    return serialize_chunk(chunk)


def regenerate_chunk_enrichment(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    chunk_id: int,
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=False)
    chunk = get_chunk_for_edit(db, space_id=space_id, kb_id=kb_id, chunk_id=chunk_id)
    _ensure_chunk_editable(chunk)

    cfg = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
    options = resolve_enrichment(cfg)
    if not options.enabled:
        raise AppError(
            status_code=400,
            code="ENRICHMENT_DISABLED",
            message="知识库未启用入库增强，请先在设置中开启",
        )
    if not options.generate_keywords and not options.generate_questions:
        raise AppError(
            status_code=400,
            code="ENRICHMENT_TASKS_EMPTY",
            message="入库增强未配置关键词或假设问题生成项",
        )

    model = _resolve_enrichment_llm(db, knowledge_base=knowledge_base, llm_id=options.llm_id)
    result = enrich_chunk_with_llm(
        content=chunk.content or "",
        heading_path=chunk.heading_path,
        model=model,
        options=options,
    )
    if result is None:
        raise AppError(
            status_code=502,
            code="ENRICHMENT_LLM_FAILED",
            message="LLM 未能生成有效的关键词或假设问题",
        )
    return {
        "keywords": result.keywords,
        "questions": result.questions,
    }
