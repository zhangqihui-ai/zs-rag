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
from app.core.knowledge_retrieval_defaults import DEFAULT_VECTOR_WEIGHT
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

# 全文路加权分低于此值视为「仅命中泛词」，不参与混合融合（如单独命中「需要」「对方」）
MIN_KEYWORD_RELEVANCE_SCORE = 1.5
# 混合检索全文路：低于此加权分视为跨库/跨主题弱命中（如「正当」+「需要」凑分），不进入融合
MIN_KEYWORD_HYBRID_SCORE = 3.0
# 全文无有效命中时，向量路 Top1 分数低于此值则不强行向量兜底
MIN_VECTOR_FALLBACK_SCORE = 0.45

# 问句二字滑窗产生的跨词边界片段，参与匹配但不计分
_NOISE_BIGRAMS: frozenset[str] = frozenset(
    {
        "卫不",
        "不小",
        "小心",
        "心杀",
        "了对",
        "方需",
        "要判",
        "刑吗",
        "正当",  # 常由「正当防卫」拆出；正文「正当权益」等与问句主题无关
        "当防",
        "卫杀",
        "人需",
        "刑吗",
    }
)

# 法律/公文高频词，单独命中不代表与用户问题相关
_LOW_VALUE_KEYWORD_TERMS: frozenset[str] = frozenset(
    {
        "对方",
        "需要",
        "可以",
        "应当",
        "进行",
        "规定",
        "下列",
        "以下",
        "其中",
        "之一",
        "或者",
        "以及",
        "并且",
        "根据",
        "按照",
        "予以",
        "对于",
        "依法",
        "之一",
        "情形",
        "以下",
    }
)

# 问句词在正文中的近义/同主题表达
_KEYWORD_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "杀了": ("杀人", "杀害", "致死", "死亡"),
    "判刑": ("有期徒刑", "刑罚", "刑事责任", "处刑"),
    "防卫": ("正当防卫", "防卫过当"),
    "防御": ("正当防卫", "防卫过当", "防卫"),
}

# 口语/非规范表述 → 法条常用语（检索前整句替换，向量化与全文共用）
_QUERY_COLLOQUIAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("被动防御", "正当防卫"),
    ("被动防卫", "正当防卫"),
    ("自我防御", "正当防卫"),
    ("自我防卫", "正当防卫"),
)


def _expand_colloquial_query(query: str) -> str:
    q = query.strip()
    if not q:
        return q
    for src, dst in _QUERY_COLLOQUIAL_REPLACEMENTS:
        q = q.replace(src, dst)
    return q


def _keyword_term_weight(term: str) -> float:
    if term in _NOISE_BIGRAMS:
        return 0.0
    if term in _LOW_VALUE_KEYWORD_TERMS:
        return 0.35
    if len(term) >= 4 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 2.5
    if len(term) == 3 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 2.0
    if len(term) == 2 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 1.5
    if re.search(r"[A-Za-z0-9]", term):
        return 1.2
    return 1.0


def _keyword_term_hits(text: str, term: str) -> bool:
    if not text or not term:
        return False
    if term in text:
        return True
    for alias in _KEYWORD_TERM_ALIASES.get(term, ()):
        if alias in text:
            return True
    return False


def _keyword_match_score(text: str, terms: list[str]) -> float:
    if not text or not terms:
        return 0.0
    score = 0.0
    for term in terms:
        weight = _keyword_term_weight(term)
        if weight <= 0:
            continue
        if _keyword_term_hits(text, term):
            score += weight
    return score


def _rescore_keyword_candidates(
    candidates: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    terms = _keyword_fallback_ilike_terms(query)
    if not terms:
        terms = [query.strip()]
    for item in candidates:
        text = item["chunk"].keyword_text or item["chunk"].content or ""
        item["keyword_score"] = _keyword_match_score(text, terms)
    candidates.sort(
        key=lambda item: (-float(item["keyword_score"] or 0), item["chunk"].id),
    )
    return candidates[:limit]


def _vector_boost_eligible(
    *,
    vector_rank: int,
    vector_total: int,
    raw_score: float,
    top_score: float,
) -> bool:
    """仅对向量路头部且分数接近最优的命中参与混合加权，避免弱向量误抬升关键词噪声。"""
    if vector_total <= 0 or raw_score <= 0 or top_score <= 0:
        return False
    if vector_rank > max(3, vector_total // 4):
        return False
    return raw_score >= top_score * 0.55


def _filter_hybrid_channel_candidates(
    candidates: list[dict[str, Any]],
    *,
    score_key: str,
    score_threshold: float | None,
    channel: str,
) -> list[dict[str, Any]]:
    """
    混合检索融合前，按单路分数过滤候选。
    - 用户开启 score_threshold：该路 min-max 归一化后 >= 阈值才进入融合池。
    - 未开启：关键词路默认保留 >= max*45% 且 >= 2.0；向量路仅保留头部且接近最优的命中。
    """
    if not candidates:
        return []

    if channel == "keyword" and _max_channel_score(candidates, score_key) < MIN_KEYWORD_HYBRID_SCORE:
        return []

    flat_below = MIN_KEYWORD_HYBRID_SCORE if channel == "keyword" else None

    if score_threshold is not None:
        keyed = {item["chunk"].chunk_uid: float(item.get(score_key) or 0) for item in candidates}
        normed = _normalize_scores(keyed, zero_if_flat_below=flat_below)
        kept = [
            item
            for item in candidates
            if normed.get(item["chunk"].chunk_uid, 0.0) >= score_threshold
        ]
        return kept

    if channel == "keyword":
        max_score = _max_channel_score(candidates, score_key)
        if max_score <= 0:
            return []
        floor = max(max_score * 0.45, MIN_KEYWORD_HYBRID_SCORE)
        return [item for item in candidates if float(item.get(score_key) or 0) >= floor]

    top_score = _max_channel_score(candidates, score_key)
    kept = []
    for rank, item in enumerate(candidates, start=1):
        raw = float(item.get(score_key) or 0)
        if _vector_boost_eligible(
            vector_rank=rank,
            vector_total=len(candidates),
            raw_score=raw,
            top_score=top_score,
        ):
            kept.append(item)
    return kept


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


def _normalize_scores(
    values: dict[str, float],
    *,
    zero_if_flat_below: float | None = None,
) -> dict[str, float]:
    if not values:
        return {}
    scores = list(values.values())
    maximum = max(scores)
    minimum = min(scores)
    if maximum == minimum:
        if zero_if_flat_below is not None and maximum < zero_if_flat_below:
            return {key: 0.0 for key in values}
        return {key: (1.0 if maximum > 0 else 0.0) for key in values}
    return {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}


def _max_channel_score(candidates: list[dict[str, Any]], score_key: str) -> float:
    if not candidates:
        return 0.0
    return max(float(item.get(score_key) or 0) for item in candidates)


def _vector_fallback_allowed(vector_candidates: list[dict[str, Any]]) -> bool:
    """全文无有效命中时，仅当向量路头部置信度足够高才兜底召回。"""
    return _max_channel_score(vector_candidates, "vector_score") >= MIN_VECTOR_FALLBACK_SCORE


def _hybrid_cross_domain_guard(
    *,
    keyword_candidates: list[dict[str, Any]],
    vector_candidates: list[dict[str, Any]],
    merged: dict[str, dict[str, Any]],
) -> bool:
    """
    混合检索：向量路整体置信不足且全文仅弱命中时，视为跨库/跨主题误召回，应返回空。
    例如医保库问「正当防卫判刑吗」——全文仅「正当权益+需要」凑 1.85 分。
    """
    if not keyword_candidates or not merged:
        return True
    top_vector = _max_channel_score(vector_candidates, "vector_score")
    max_keyword = _max_channel_score(keyword_candidates, "keyword_score")
    has_vector_boost = any(item.get("vector_score") is not None for item in merged.values())
    if has_vector_boost:
        return True
    if top_vector >= MIN_VECTOR_FALLBACK_SCORE and max_keyword >= MIN_KEYWORD_HYBRID_SCORE:
        return True
    if max_keyword >= MIN_KEYWORD_HYBRID_SCORE + 1.5:
        return True
    return False


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
            .limit(max(limit * 6, 30))
        ).all()
        candidates = [
            {
                "chunk": chunk,
                "document_name": document_name,
                "keyword_score": float(keyword_score or 0),
            }
            for chunk, document_name, keyword_score in rows
        ]
        return _rescore_keyword_candidates(candidates, query=query, limit=limit)
    candidates = [
        {
            "chunk": chunk,
            "document_name": document_name,
            "keyword_score": float(keyword_score or 0),
        }
        for chunk, document_name, keyword_score in rows
    ]
    return _rescore_keyword_candidates(candidates, query=query, limit=limit)


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
            candidates = opensearch_chunk_service.keyword_search_candidates(
                db,
                enterprise_space_id=enterprise_space_id,
                knowledge_base_id=knowledge_base_id,
                query=query,
                limit=limit,
                document_ids=document_ids,
            )
            if candidates:
                return _rescore_keyword_candidates(candidates, query=query, limit=limit)
            logger.debug("OpenSearch 关键词检索无命中，回退 PostgreSQL：query=%r", query)
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

    ensure_knowledge_base_milvus_fields(db, knowledge_base)
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
    query = _expand_colloquial_query(payload.query)

    if mode == "keyword":
        keyword_candidates = _keyword_candidates(
            db,
            enterprise_space_id=knowledge_base.enterprise_space_id,
            knowledge_base_id=knowledge_base.id,
            query=query,
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
            query=query,
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
            query=query,
            limit=top_k * 4,
            document_ids=document_ids,
        )
        keyword_candidates = _keyword_candidates(
            db,
            enterprise_space_id=knowledge_base.enterprise_space_id,
            knowledge_base_id=knowledge_base.id,
            query=query,
            limit=top_k * 4,
            document_ids=document_ids,
        )
        vector_candidates = _filter_hybrid_channel_candidates(
            vector_candidates,
            score_key="vector_score",
            score_threshold=score_threshold,
            channel="vector",
        )
        keyword_candidates = _filter_hybrid_channel_candidates(
            keyword_candidates,
            score_key="keyword_score",
            score_threshold=score_threshold,
            channel="keyword",
        )
        keyword_scores = {
            item["chunk"].chunk_uid: item["keyword_score"]
            for item in keyword_candidates
        }

        w_vector = DEFAULT_VECTOR_WEIGHT
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
            # 全文无有效命中：仅向量置信度足够高时兜底（避免跨领域问句误召回）
            if vector_candidates and _vector_fallback_allowed(vector_candidates):
                for item in vector_candidates:
                    chunk = item["chunk"]
                    merged[chunk.chunk_uid] = {
                        "chunk": chunk,
                        "document_name": item["document_name"],
                        "vector_score": item["vector_score"],
                        "keyword_score": None,
                    }
        else:
            vector_rank_map: dict[str, tuple[int, float]] = {}
            top_vector_score = 0.0
            for rank, item in enumerate(vector_candidates, start=1):
                uid = item["chunk"].chunk_uid
                raw = float(item["vector_score"] or 0)
                vector_rank_map[uid] = (rank, raw)
                top_vector_score = max(top_vector_score, raw)

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
                rank, raw = vector_rank_map.get(uid, (999, 0.0))
                if uid not in merged:
                    continue
                if _vector_boost_eligible(
                    vector_rank=rank,
                    vector_total=len(vector_candidates),
                    raw_score=raw,
                    top_score=top_vector_score,
                ):
                    merged[uid]["vector_score"] = raw

        eligible_vector_scores = {
            uid: float(item["vector_score"])
            for uid, item in merged.items()
            if item.get("vector_score") is not None
        }
        if w_keyword <= 0.0:
            normalized_vector = _normalize_scores(
                {
                    item["chunk"].chunk_uid: float(item["vector_score"] or 0)
                    for item in vector_candidates
                }
            )
        elif not keyword_candidates:
            normalized_vector = _normalize_scores(
                {
                    item["chunk"].chunk_uid: float(item["vector_score"] or 0)
                    for item in vector_candidates
                }
            )
        else:
            normalized_vector = _normalize_scores(eligible_vector_scores)
        normalized_keyword = _normalize_scores(keyword_scores, zero_if_flat_below=MIN_KEYWORD_HYBRID_SCORE)

        if not _hybrid_cross_domain_guard(
            keyword_candidates=keyword_candidates,
            vector_candidates=vector_candidates,
            merged=merged,
        ):
            results = []
        else:
            ranked: list[dict[str, Any]] = []
            for chunk_uid, item in merged.items():
                vector_score = item["vector_score"]
                keyword_score = item["keyword_score"]
                v_norm = normalized_vector.get(chunk_uid, 0.0) if vector_score is not None else 0.0
                k_norm = normalized_keyword.get(chunk_uid, 0.0)
                final_score = w_vector * v_norm + w_keyword * k_norm
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
