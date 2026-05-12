from __future__ import annotations

import logging
import math
import re
from typing import Any

from sqlalchemy import desc, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embedding_gateway import generate_query_embedding
from app.core.errors import AppError
from app.core.milvus_client import search_vectors
from app.models.knowledge_base import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus
from app.schemas.retrieval import KnowledgeSearchRequest
from app.services.knowledge_base_service import (
    ensure_knowledge_base_milvus_fields,
    get_embedding_model_for_knowledge_base,
    get_knowledge_base_or_error,
)
from app.services import opensearch_chunk_service

settings = get_settings()
logger = logging.getLogger(__name__)


def _escape_for_ilike(s: str) -> str:
    """避免用户输入中的 %、_ 被当作 SQL ILIKE 通配符。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _keyword_fallback_ilike_terms(query: str) -> list[str]:
    """
    从问句中提取若干子串，用作 ILIKE 的 OR 后备检索。
    解决：中文问句整句较少连续出现在切片中，plainto_tsquery(simple) 又常匹配不到，导致全文检索恒为 0 条。
    """
    q = query.strip()
    if not q:
        return []
    terms: list[str] = []
    for tok in re.split(r"[\s\u3000]+", q):
        t = tok.strip()
        if len(t) >= 2 and re.search(r"[A-Za-z0-9]", t):
            terms.append(t)
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", q):
        run = m.group(0)
        if len(run) == 2:
            terms.append(run)
        else:
            terms.extend(run[i : i + 2] for i in range(0, len(run) - 1))
    if len(q) == 1 and "\u4e00" <= q <= "\u9fff":
        terms.append(q)
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        t = t.strip()
        if len(t) < 1 or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= 24:
            break
    return out


def _render_result_content(chunk: KnowledgeChunk) -> str:
    meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    if meta.get("chunking_mode") == "parent_child":
        parent_preview = meta.get("parent_preview")
        if isinstance(parent_preview, str) and parent_preview.strip():
            child = chunk.content or ""
            if child.strip():
                return f"{parent_preview.rstrip()}\n\n—— 命中片段 ——\n{child.strip()}"
            return parent_preview.strip()
    return chunk.content


def _serialize_search_result(
    *,
    chunk: KnowledgeChunk,
    document_name: str,
    score: float,
    vector_score: float | None = None,
    keyword_score: float | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "chunk_uid": chunk.chunk_uid,
        "document_id": chunk.document_id,
        "document_name": document_name,
        "chunk_index": chunk.chunk_index,
        "content": _render_result_content(chunk),
        "score": float(score),
        "vector_score": float(vector_score) if vector_score is not None else None,
        "keyword_score": float(keyword_score) if keyword_score is not None else None,
        "metadata": chunk.metadata_json,
        "citation": {
            "document_name": document_name,
            "page_no": chunk.page_no,
            "chunk_index": chunk.chunk_index,
        },
    }


def _stored_vector_weight(knowledge_base: KnowledgeBase) -> float | None:
    """与前端 `config.retrieval.vector_weight` 对齐；仅用于混合检索缺省权重。"""
    cfg = knowledge_base.config if isinstance(knowledge_base.config, dict) else None
    if not cfg:
        return None
    raw_retrieval = cfg.get("retrieval")
    if not isinstance(raw_retrieval, dict):
        return None
    w = raw_retrieval.get("vector_weight")
    try:
        f = float(w)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or not (0.0 <= f <= 1.0):
        return None
    return f


def _normalize_scores(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    scores = list(values.values())
    maximum = max(scores)
    minimum = min(scores)
    if maximum == minimum:
        return {key: (1.0 if maximum > 0 else 0.0) for key in values}
    return {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}


def _document_filters(kb_id: int, document_ids: list[int] | None) -> list[Any]:
    filters: list[Any] = [
        KnowledgeChunk.knowledge_base_id == kb_id,
        KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED.value,
    ]
    if document_ids:
        filters.append(KnowledgeChunk.document_id.in_(document_ids))
    return filters


def _keyword_candidates_postgres(
    db: Session,
    *,
    knowledge_base_id: int,
    query: str,
    limit: int,
    document_ids: list[int] | None,
) -> list[dict[str, Any]]:
    filters = _document_filters(knowledge_base_id, document_ids)
    tsquery = func.plainto_tsquery("simple", query)
    score = func.ts_rank_cd(KnowledgeChunk.search_vector, tsquery).label("keyword_score")
    rows = db.execute(
        select(KnowledgeChunk, KnowledgeDocument.document_name, score)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(*filters)
        .where(KnowledgeChunk.search_vector.op("@@")(tsquery))
        .order_by(desc(score), KnowledgeChunk.id.asc())
        .limit(limit)
    ).all()
    if not rows and query.strip():
        fallback_score = literal(1.0).label("keyword_score")
        terms = _keyword_fallback_ilike_terms(query)
        if not terms:
            terms = [query.strip()]
        ilike_conds = [
            KnowledgeChunk.keyword_text.ilike(f"%{_escape_for_ilike(t)}%", escape="\\") for t in terms
        ]
        rows = db.execute(
            select(KnowledgeChunk, KnowledgeDocument.document_name, fallback_score)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(*filters)
            .where(or_(*ilike_conds))
            .order_by(KnowledgeChunk.id.asc())
            .limit(limit)
        ).all()
    return [
        {
            "chunk": chunk,
            "document_name": document_name,
            "keyword_score": float(keyword_score or 0),
        }
        for chunk, document_name, keyword_score in rows
    ]


def _keyword_candidates(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_id: int,
    query: str,
    limit: int,
    document_ids: list[int] | None,
) -> list[dict[str, Any]]:
    if opensearch_chunk_service.is_enabled():
        try:
            return opensearch_chunk_service.keyword_search_candidates(
                db,
                enterprise_space_id=enterprise_space_id,
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
                document_ids=document_ids,
            )
        except Exception as exc:
            logger.warning("OpenSearch 关键词检索失败，回退 PostgreSQL：%s", exc)
    return _keyword_candidates_postgres(
        db,
        knowledge_base_id=knowledge_base_id,
        query=query,
        limit=limit,
        document_ids=document_ids,
    )


def _vector_candidates(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    query: str,
    limit: int,
    document_ids: list[int] | None,
) -> list[dict[str, Any]]:
    if not knowledge_base.vector_db_enabled:
        raise AppError(status_code=400, code="VECTOR_SEARCH_DISABLED", message="当前知识库未启用向量检索")

    ensure_knowledge_base_milvus_fields(knowledge_base)
    embedding_model = get_embedding_model_for_knowledge_base(db, knowledge_base=knowledge_base)
    query_vector = generate_query_embedding(embedding_model, query)
    result = search_vectors(
        host=settings.milvus_host,
        port=settings.milvus_port,
        collection_name=knowledge_base.milvus_collection_name,
        query_vector=query_vector,
        top_k=limit,
        username=settings.milvus_username,
        password=settings.milvus_password,
    )
    if not result.success:
        raise AppError(status_code=502, code="MILVUS_SEARCH_FAILED", message=result.message)

    hits = result.data if isinstance(result.data, list) else []
    chunk_uids = [str(item.get("chunk_uid")) for item in hits if item.get("chunk_uid")]
    if not chunk_uids:
        return []

    rows = db.execute(
        select(KnowledgeChunk, KnowledgeDocument.document_name)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(*_document_filters(knowledge_base.id, document_ids))
        .where(KnowledgeChunk.chunk_uid.in_(chunk_uids))
    ).all()
    chunk_map = {chunk.chunk_uid: (chunk, document_name) for chunk, document_name in rows}

    candidates: list[dict[str, Any]] = []
    for hit in hits:
        chunk_uid = str(hit.get("chunk_uid") or "")
        if not chunk_uid or chunk_uid not in chunk_map:
            continue
        chunk, document_name = chunk_map[chunk_uid]
        candidates.append(
            {
                "chunk": chunk,
                "document_name": document_name,
                "vector_score": float(hit.get("score") or 0),
            }
        )
    return candidates


def search_knowledge_base(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    payload: KnowledgeSearchRequest,
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    mode = payload.mode or knowledge_base.default_retrieval_mode
    top_k = payload.top_k or knowledge_base.default_top_k
    score_threshold = payload.score_threshold
    if score_threshold is None and knowledge_base.default_score_threshold is not None:
        score_threshold = float(knowledge_base.default_score_threshold)
    document_ids = payload.document_ids or None

    if mode == "keyword":
        keyword_candidates = _keyword_candidates(
            db,
            enterprise_space_id=knowledge_base.enterprise_space_id,
            knowledge_base_id=knowledge_base.id,
            query=payload.query,
            limit=top_k,
            document_ids=document_ids,
        )
        results = [
            _serialize_search_result(
                chunk=item["chunk"],
                document_name=item["document_name"],
                score=item["keyword_score"],
                keyword_score=item["keyword_score"],
            )
            for item in keyword_candidates
        ]
    elif mode == "vector":
        vector_candidates = _vector_candidates(
            db,
            knowledge_base=knowledge_base,
            query=payload.query,
            limit=top_k,
            document_ids=document_ids,
        )
        results = [
            _serialize_search_result(
                chunk=item["chunk"],
                document_name=item["document_name"],
                score=item["vector_score"],
                vector_score=item["vector_score"],
            )
            for item in vector_candidates
        ]
    else:
        vector_candidates = _vector_candidates(
            db,
            knowledge_base=knowledge_base,
            query=payload.query,
            limit=top_k * 4,
            document_ids=document_ids,
        )
        keyword_candidates = _keyword_candidates(
            db,
            enterprise_space_id=knowledge_base.enterprise_space_id,
            knowledge_base_id=knowledge_base.id,
            query=payload.query,
            limit=top_k * 4,
            document_ids=document_ids,
        )
        vector_scores = {
            item["chunk"].chunk_uid: item["vector_score"]
            for item in vector_candidates
        }
        keyword_scores = {
            item["chunk"].chunk_uid: item["keyword_score"]
            for item in keyword_candidates
        }
        normalized_vector = _normalize_scores(vector_scores)
        normalized_keyword = _normalize_scores(keyword_scores)

        w_vector = 0.5
        if payload.vector_weight is not None:
            w_vector = float(payload.vector_weight)
        else:
            stored_w = _stored_vector_weight(knowledge_base)
            if stored_w is not None:
                w_vector = stored_w
        w_keyword = 1.0 - w_vector

        merged: dict[str, dict[str, Any]] = {}
        if w_keyword <= 0.0:
            for item in vector_candidates:
                chunk = item["chunk"]
                merged[chunk.chunk_uid] = {
                    "chunk": chunk,
                    "document_name": item["document_name"],
                    "vector_score": item["vector_score"],
                    "keyword_score": None,
                }
            for item in keyword_candidates:
                chunk = item["chunk"]
                current = merged.setdefault(
                    chunk.chunk_uid,
                    {
                        "chunk": chunk,
                        "document_name": item["document_name"],
                        "vector_score": None,
                        "keyword_score": None,
                    },
                )
                current["keyword_score"] = item["keyword_score"]
        elif not keyword_candidates:
            merged = {}
        else:
            for item in keyword_candidates:
                chunk = item["chunk"]
                merged[chunk.chunk_uid] = {
                    "chunk": chunk,
                    "document_name": item["document_name"],
                    "vector_score": None,
                    "keyword_score": item["keyword_score"],
                }
            for item in vector_candidates:
                uid = item["chunk"].chunk_uid
                if uid in merged:
                    merged[uid]["vector_score"] = item["vector_score"]

        ranked: list[dict[str, Any]] = []
        for chunk_uid, item in merged.items():
            vector_score = item["vector_score"]
            keyword_score = item["keyword_score"]
            final_score = w_vector * normalized_vector.get(chunk_uid, 0) + w_keyword * normalized_keyword.get(
                chunk_uid, 0
            )
            ranked.append(
                _serialize_search_result(
                    chunk=item["chunk"],
                    document_name=item["document_name"],
                    score=final_score,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                )
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)
        if score_threshold is not None:
            ranked = [item for item in ranked if item["score"] >= score_threshold]
        results = ranked[:top_k]

    if score_threshold is not None and mode != "hybrid":
        results = [item for item in results if item["score"] >= score_threshold]

    return {
        "query": payload.query,
        "mode": mode,
        "total": len(results),
        "results": results,
    }


def search_knowledge_bases_multi(
    db: Session,
    *,
    space_id: int,
    knowledge_base_ids: list[int],
    payload: KnowledgeSearchRequest,
) -> dict[str, Any]:
    """
    在多个知识库上执行相同检索策略，按 score 全局合并排序后截取 top_k。
    某一库检索失败（如未开向量）时跳过该库并记录日志，其余库结果仍返回。
    """
    ordered_unique: list[int] = []
    for kid in knowledge_base_ids:
        if kid not in ordered_unique:
            ordered_unique.append(kid)
    kb_ids = ordered_unique
    if not kb_ids:
        raise AppError(status_code=400, code="KB_IDS_REQUIRED", message="请至少选择一个知识库")

    first_kb = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_ids[0])
    mode_str = str(payload.mode or first_kb.default_retrieval_mode)
    final_top = payload.top_k or first_kb.default_top_k
    final_top = min(max(int(final_top), 1), 50)
    inner_top = min(50, final_top * max(2, len(kb_ids)))

    merged_rows: list[dict[str, Any]] = []
    for kb_id in kb_ids:
        kb = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
        inner = KnowledgeSearchRequest(
            query=payload.query,
            mode=payload.mode,
            top_k=inner_top,
            score_threshold=payload.score_threshold,
            vector_weight=payload.vector_weight,
            document_ids=payload.document_ids,
        )
        try:
            one = search_knowledge_base(db, space_id=space_id, kb_id=kb_id, payload=inner)
        except AppError as exc:
            logger.warning("多库检索跳过知识库 kb_id=%s：%s", kb_id, exc)
            continue
        mode_str = str(one.get("mode") or mode_str)
        for item in one["results"]:
            row = dict(item)
            row["knowledge_base_id"] = kb.id
            row["knowledge_base_name"] = kb.name
            merged_rows.append(row)

    merged_rows.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    merged_rows = merged_rows[:final_top]

    return {
        "query": payload.query,
        "mode": mode_str,
        "knowledge_base_ids": kb_ids,
        "total": len(merged_rows),
        "results": merged_rows,
    }
