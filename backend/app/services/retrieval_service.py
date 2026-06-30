from __future__ import annotations

import logging
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embedding_gateway import generate_query_embedding
from app.core.errors import AppError
from app.services.usage_metrics_service import record_usage_event
from app.core.milvus_client import search_vectors
from app.core.knowledge_retrieval_defaults import (
    DEFAULT_AUTO_IMAGE_OCR_ON_UI_QUERY,
    DEFAULT_FUSION_METHOD,
    DEFAULT_IMAGE_OCR_SCORE_FACTOR,
    DEFAULT_INCLUDE_IMAGE_OCR,
    DEFAULT_RRF_K,
    DEFAULT_VECTOR_WEIGHT,
)
from app.core.rerank_gateway import RERANK_RECALL_FACTOR, rerank_texts
from app.models.knowledge_base import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus
from app.schemas.retrieval import KnowledgeSearchRequest
from app.db.session import SessionLocal
from app.services.knowledge_base_service import (
    ensure_knowledge_base_milvus_fields,
    get_embedding_model_for_knowledge_base,
    get_knowledge_base_or_error,
    get_rerank_model_for_knowledge_base,
)
from app.services import opensearch_chunk_service

settings = get_settings()
logger = logging.getLogger(__name__)

# 全文路加权分低于此值视为「仅命中泛词」，不参与混合融合（如单独命中「需要」「对方」）
MIN_KEYWORD_RELEVANCE_SCORE = 1.5
# 混合检索全文路：低于此加权分视为跨库/跨主题弱命中（如「正当」+「需要」凑分），不进入融合
MIN_KEYWORD_HYBRID_SCORE = 3.0
# 事项编码等长字母数字串：全文精确命中权重须能过混合门槛
MIN_KEYWORD_HYBRID_SCORE_IDENTIFIER = 1.0
IDENTIFIER_QUERY_MIN_LEN = 6
# 全文无有效命中时，向量路 Top1 分数低于此值则不强行向量兜底
MIN_VECTOR_FALLBACK_SCORE = 0.45
# RRF 平滑常数（加权倒数排名融合）
RRF_K = DEFAULT_RRF_K

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

# 问句模板词：不参与强锚点，辅助层也极低权重
_QUERY_TEMPLATE_TERMS: frozenset[str] = frozenset(
    {
        "如何",
        "怎么",
        "怎样",
        "咋样",
        "哪些",
        "什么",
        "是否",
        "能否",
        "可不可以",
        "有没有",
        "干嘛",
        "请问",
        "哪儿",
        "哪里",
        "多少",
        "为啥",
        "为什么",
        "办理",
        "申请",
        "查询",
        "相关",
        "有哪些",
        "是什么",
        "什么意思",
        "指的是",
        "一下",
        "帮我",
        "告诉",
        "能否",
        "可不可以",
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


@dataclass(frozen=True)
class QueryTermLayers:
    """问句词项分层：强锚点（2~8 字实体）+ 二字滑窗辅助。"""

    anchors: tuple[str, ...]
    specific_anchors: tuple[str, ...]
    auxiliaries: tuple[str, ...]


def _dominant_identifier_in_query(query: str) -> str | None:
    """问句主体为事项编码/业务单号等字母数字串时返回该 token。"""
    q = query.strip()
    if not q:
        return None
    for tok in re.split(r"[\s\u3000]+", q):
        t = tok.strip()
        if len(t) >= IDENTIFIER_QUERY_MIN_LEN and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", t):
            return t
    if len(q) >= IDENTIFIER_QUERY_MIN_LEN and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", q):
        return q
    return None


def _min_keyword_hybrid_score_for_query(query: str) -> float:
    if _dominant_identifier_in_query(query):
        return MIN_KEYWORD_HYBRID_SCORE_IDENTIFIER
    return MIN_KEYWORD_HYBRID_SCORE


def _dedupe_terms(terms: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in terms:
        t = raw.strip()
        if len(t) < 2 or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return tuple(out)


def _entity_parts_from_query(query: str) -> list[str]:
    """从连续中文块中剥离问句模板词，得到实体片段（2~8 字）。"""
    parts: list[str] = []
    for run in re.finditer(r"[\u4e00-\u9fff]{2,}", query):
        block = run.group(0)
        peeled = block
        for template in sorted(_QUERY_TEMPLATE_TERMS, key=len, reverse=True):
            peeled = peeled.replace(template, "|")
        for piece in peeled.split("|"):
            piece = piece.strip()
            if len(piece) >= 2 and piece not in _QUERY_TEMPLATE_TERMS:
                parts.append(piece)
    return parts


def _expand_anchors_from_part(part: str) -> list[str]:
    anchors = [part]
    n = len(part)
    if n >= 4:
        anchors.append(part[:3])
        anchors.append(part[-2:])
        if n == 4:
            anchors.append(part[:2])
    elif n == 3:
        anchors.append(part[:2])
        anchors.append(part[1:3])
    return anchors


def _required_anchor_satisfied(text: str, entity_parts: tuple[str, ...]) -> bool:
    """按实体片段长度决定必达锚点，避免「新生儿医保」问句仅命中「医保」过线。"""
    if not entity_parts:
        return True
    for part in entity_parts:
        if len(part) >= 5:
            if _keyword_term_hits(text, part) or _keyword_term_hits(text, part[:3]):
                return True
        elif len(part) == 4:
            if (
                _keyword_term_hits(text, part)
                or _keyword_term_hits(text, part[:2])
                or _keyword_term_hits(text, part[-2:])
            ):
                return True
        elif len(part) == 3:
            if _keyword_term_hits(text, part) or _keyword_term_hits(text, part[:2]):
                return True
        elif _keyword_term_hits(text, part):
            return True
    return False


def _extract_query_term_layers(query: str) -> QueryTermLayers:
    """
    强锚点：问句实体（2~8 字，含「医保」「落户」等二字领域词）；
    辅助项：二字滑窗，仅用于 recall/加分，不作必达。
    """
    q = query.strip()
    entity_parts = _dedupe_terms(_entity_parts_from_query(q))
    anchor_candidates: list[str] = list(entity_parts)
    for part in entity_parts:
        anchor_candidates.extend(_expand_anchors_from_part(part))
    for tok in re.split(r"[\s\u3000]+", q):
        tok = tok.strip()
        if len(tok) >= 2 and re.search(r"[A-Za-z0-9]", tok) and tok not in _QUERY_TEMPLATE_TERMS:
            anchor_candidates.append(tok)

    anchors = _dedupe_terms([a for a in anchor_candidates if a not in _QUERY_TEMPLATE_TERMS])
    specific = entity_parts if entity_parts else anchors

    auxiliaries: list[str] = []
    for run in re.finditer(r"[\u4e00-\u9fff]{2,}", q):
        text = run.group(0)
        if len(text) == 2:
            auxiliaries.append(text)
        else:
            auxiliaries.extend(text[i : i + 2] for i in range(len(text) - 1))
    anchor_set = set(anchors)
    auxiliaries = [
        t
        for t in auxiliaries
        if t not in anchor_set
        and t not in _QUERY_TEMPLATE_TERMS
        and t not in _NOISE_BIGRAMS
        and t not in _LOW_VALUE_KEYWORD_TERMS
    ]
    return QueryTermLayers(
        anchors=anchors,
        specific_anchors=specific,
        auxiliaries=_dedupe_terms(auxiliaries),
    )


def _anchor_term_weight(term: str) -> float:
    if term in _QUERY_TEMPLATE_TERMS or term in _NOISE_BIGRAMS:
        return 0.0
    if len(term) >= 5 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 3.0
    if len(term) == 4 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 2.5
    if len(term) == 3 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 2.0
    if len(term) == 2 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 1.5
    if re.search(r"[A-Za-z0-9]", term):
        if len(term) >= IDENTIFIER_QUERY_MIN_LEN:
            return 4.0
        return 1.2
    return 1.0


def _auxiliary_term_weight(term: str) -> float:
    if term in _QUERY_TEMPLATE_TERMS or term in _NOISE_BIGRAMS:
        return 0.0
    if term in _LOW_VALUE_KEYWORD_TERMS:
        return 0.15
    if len(term) == 2 and re.fullmatch(r"[\u4e00-\u9fff]+", term):
        return 0.45
    if re.search(r"[A-Za-z0-9]", term):
        return 0.35
    return 0.25


def _layered_keyword_match_score(text: str, layers: QueryTermLayers) -> float:
    if not text or not layers.anchors:
        return 0.0

    if not _required_anchor_satisfied(text, layers.specific_anchors):
        return 0.0

    anchor_score = 0.0
    for anchor in layers.anchors:
        if _keyword_term_hits(text, anchor):
            anchor_score += _anchor_term_weight(anchor)

    aux_score = 0.0
    for term in layers.auxiliaries:
        if _keyword_term_hits(text, term):
            aux_score += _auxiliary_term_weight(term)

    return anchor_score + aux_score


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
    """兼容旧测试：按扁平词项列表打分（无锚点必达）。"""
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
    layers = _extract_query_term_layers(query)
    for item in candidates:
        text = item["chunk"].keyword_text or item["chunk"].content or ""
        item["keyword_score"] = _layered_keyword_match_score(text, layers)
    candidates = [item for item in candidates if float(item.get("keyword_score") or 0) > 0]
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
    chunk_text: str = "",
    query: str = "",
) -> bool:
    """仅对向量路头部且分数接近最优的命中参与混合加权，避免弱向量误抬升关键词噪声。"""
    ident = _dominant_identifier_in_query(query)
    if ident and ident in chunk_text:
        return raw_score > 0
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
    query: str = "",
) -> list[dict[str, Any]]:
    """
    混合检索融合前，按单路分数过滤候选。
    - 用户开启 score_threshold：该路 min-max 归一化后 >= 阈值才进入融合池。
    - 未开启：关键词路默认保留 >= max*45% 且 >= 2.0；向量路仅保留头部且接近最优的命中。
    """
    if not candidates:
        return []

    min_hybrid = _min_keyword_hybrid_score_for_query(query)

    if channel == "keyword" and _max_channel_score(candidates, score_key) < min_hybrid:
        return []

    flat_below = min_hybrid if channel == "keyword" else None

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
        floor = max(max_score * 0.45, min_hybrid)
        return [item for item in candidates if float(item.get(score_key) or 0) >= floor]

    top_score = _max_channel_score(candidates, score_key)
    kept = []
    for rank, item in enumerate(candidates, start=1):
        raw = float(item.get(score_key) or 0)
        text = item["chunk"].keyword_text or item["chunk"].content or ""
        if _vector_boost_eligible(
            vector_rank=rank,
            vector_total=len(candidates),
            raw_score=raw,
            top_score=top_score,
            chunk_text=text,
            query=query,
        ):
            kept.append(item)
    return kept


def _escape_for_ilike(s: str) -> str:
    """避免用户输入中的 %、_ 被当作 SQL ILIKE 通配符。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _keyword_fallback_ilike_terms(query: str) -> list[str]:
    """
    从问句中提取若干子串，用作 ILIKE 的 OR 后备检索。
    优先强锚点短语，再补二字滑窗辅助 recall。
    """
    q = query.strip()
    if not q:
        return []
    layers = _extract_query_term_layers(q)
    terms: list[str] = list(layers.anchors) + list(layers.auxiliaries)
    for tok in re.split(r"[\s\u3000]+", q):
        t = tok.strip()
        if len(t) >= 2 and re.search(r"[A-Za-z0-9]", t):
            terms.append(t)
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
    return chunk.content or ""


def _content_preview(text: str, *, max_chars: int = 240) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max_chars - 1].rstrip() + "…"


def _extract_enrichment(meta: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    if not isinstance(meta, dict):
        return [], []
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
    return keywords, questions


def _chunk_block_type(meta: dict[str, Any] | None) -> str | None:
    if not isinstance(meta, dict):
        return None
    block = meta.get("block")
    return str(block).strip() if block else None


def _chunk_location_label(chunk: KnowledgeChunk) -> str | None:
    from app.core.heading_match import normalize_heading_match_text

    meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    heading = (chunk.heading_path or meta.get("heading_path") or "").strip()
    if heading:
        parts = [p.strip() for p in heading.split(" / ") if p.strip()]
        if parts:
            return normalize_heading_match_text(parts[-1])
    block = meta.get("block")
    if block == "image":
        return "图片 OCR"
    if block == "document_preamble":
        return "文前"
    if block == "table":
        return "表格"
    if chunk.page_no is not None and chunk.page_no > 1:
        return f"第 {chunk.page_no} 页"
    return None


def _citation_page_no(chunk: KnowledgeChunk) -> int | None:
    """Word/MinerU 单页文档 page_no 常为 1，不在引文中展示无区分度的页码。"""
    if chunk.page_no is None or chunk.page_no <= 1:
        return None
    return chunk.page_no


def _normalize_content_for_dedup(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _content_overlap_ratio(a: str, b: str) -> float:
    na = _normalize_content_for_dedup(a)
    nb = _normalize_content_for_dedup(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if shorter in longer:
        return len(shorter) / max(len(longer), 1)
    prefix_len = min(len(shorter), 120)
    if prefix_len >= 40 and shorter[:prefix_len] == longer[:prefix_len]:
        return prefix_len / max(len(longer), 1)
    return 0.0


_UI_IMAGE_OCR_QUERY_RE = re.compile(
    r"(界面|截图|页面|App|小程序|按钮|点击|屏幕|图片|豫事办|支付宝)",
    re.IGNORECASE,
)


def _chunk_metadata_dict(chunk: KnowledgeChunk) -> dict[str, Any]:
    meta = chunk.metadata_json
    return meta if isinstance(meta, dict) else {}


def _is_standalone_image_ocr_chunk(chunk: KnowledgeChunk) -> bool:
    meta = _chunk_metadata_dict(chunk)
    return meta.get("block") == "image" and not meta.get("image_ocr_attached")


def _result_is_standalone_image_ocr(item: dict[str, Any]) -> bool:
    meta = item.get("metadata")
    if not isinstance(meta, dict):
        cite = item.get("citation")
        if isinstance(cite, dict) and cite.get("block") == "image":
            return True
        return False
    return meta.get("block") == "image" and not meta.get("image_ocr_attached")


def _query_wants_image_ocr(query: str) -> bool:
    return bool(_UI_IMAGE_OCR_QUERY_RE.search((query or "").strip()))


def _resolve_rerank_config(knowledge_base: KnowledgeBase, mode: str) -> tuple[bool, int | None]:
    """与前端 retrieval-form 对齐：hybrid+rerank 策略，或 vector/keyword 下 rerank_enabled。"""
    stored = _stored_retrieval_config(knowledge_base)
    raw_id = stored.get("rerank_model_id")
    model_id: int | None
    try:
        model_id = int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        model_id = None
    if not model_id:
        return False, None
    if mode == "hybrid":
        if stored.get("hybrid_strategy") == "rerank":
            return True, model_id
        return False, None
    if bool(stored.get("rerank_enabled")):
        return True, model_id
    return False, None


def _apply_rerank_to_results(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    query: str,
    results: list[dict[str, Any]],
    rerank_model_id: int,
    top_n: int,
) -> list[dict[str, Any]]:
    if not results:
        return results
    try:
        model = get_rerank_model_for_knowledge_base(
            db,
            knowledge_base=knowledge_base,
            override_model_id=rerank_model_id,
        )
        documents = [str(item.get("content") or "") for item in results]
        scores = rerank_texts(
            model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
        )
        reranked: list[dict[str, Any]] = []
        for row in scores:
            item = dict(results[row.index])
            item["score"] = float(row.score)
            reranked.append(item)
        return reranked
    except AppError:
        logger.exception("rerank 失败，回退原始排序 kb_id=%s", knowledge_base.id)
        return results[:top_n]


def _stored_retrieval_config(knowledge_base: KnowledgeBase) -> dict[str, Any]:
    cfg = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
    raw = cfg.get("retrieval")
    return raw if isinstance(raw, dict) else {}


def _resolve_image_ocr_retrieval(
    knowledge_base: KnowledgeBase,
    payload: KnowledgeSearchRequest,
    query: str,
) -> tuple[bool, float, bool]:
    """返回 (allow_standalone_image_ocr, score_factor, exclude_at_engine)."""
    stored = _stored_retrieval_config(knowledge_base)
    include = (
        payload.include_image_ocr
        if payload.include_image_ocr is not None
        else bool(stored.get("include_image_ocr", DEFAULT_INCLUDE_IMAGE_OCR))
    )
    auto_ui = bool(stored.get("auto_image_ocr_on_ui_query", DEFAULT_AUTO_IMAGE_OCR_ON_UI_QUERY))
    if not include and auto_ui and _query_wants_image_ocr(query):
        include = True
    try:
        factor = float(stored.get("image_ocr_score_factor", DEFAULT_IMAGE_OCR_SCORE_FACTOR))
    except (TypeError, ValueError):
        factor = DEFAULT_IMAGE_OCR_SCORE_FACTOR
    if not math.isfinite(factor) or factor <= 0:
        factor = DEFAULT_IMAGE_OCR_SCORE_FACTOR
    exclude_at_engine = not include
    return include, factor, exclude_at_engine


def _apply_chunk_role_filters(
    results: list[dict[str, Any]],
    *,
    include_image_ocr: bool,
    image_ocr_score_factor: float,
) -> list[dict[str, Any]]:
    if not results:
        return results
    out: list[dict[str, Any]] = []
    for item in results:
        if not include_image_ocr and _result_is_standalone_image_ocr(item):
            continue
        row = dict(item)
        if include_image_ocr and _result_is_standalone_image_ocr(row):
            row["score"] = float(row.get("score") or 0) * image_ocr_score_factor
        out.append(row)
    if include_image_ocr:
        out.sort(key=lambda row: float(row.get("score") or 0), reverse=True)
    return out


def _result_identity_key(item: dict[str, Any]) -> str:
    kb_id = item.get("knowledge_base_id")
    chunk_id = item.get("chunk_id")
    if chunk_id is not None:
        return f"chunk:{kb_id}:{chunk_id}"
    doc_id = item.get("document_id")
    chunk_index = item.get("chunk_index")
    content = str(item.get("content") or "")[:80]
    return f"fallback:{kb_id}:{doc_id}:{chunk_index}:{content}"


def _apply_merge_scores(rows: list[dict[str, Any]]) -> None:
    """按知识库内 min-max 归一化，写入 merge_score。"""
    by_kb: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        raw_kb = row.get("knowledge_base_id")
        if raw_kb is None:
            continue
        kid = int(raw_kb)
        by_kb.setdefault(kid, []).append(row)
    for kb_rows in by_kb.values():
        scores = [float(item.get("score") or 0.0) for item in kb_rows]
        min_s = min(scores) if scores else 0.0
        max_s = max(scores) if scores else 0.0
        for item in kb_rows:
            raw = float(item.get("score") or 0.0)
            if max_s > min_s:
                item["merge_score"] = (raw - min_s) / (max_s - min_s)
            else:
                item["merge_score"] = 1.0


def _row_kb_type(row: dict[str, Any]) -> str:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source = str(meta.get("source") or row.get("source") or "")
    return "lightrag" if source == "lightrag" else "classic"


def _summarize_path_candidates(
    rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
    preview_chars: int = 120,
) -> list[dict[str, Any]]:
    cap = len(rows) if limit is None else min(len(rows), max(int(limit), 0))
    summaries: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:cap], start=1):
        content = str(row.get("content") or "").strip()
        preview = content if len(content) <= preview_chars else content[: preview_chars - 1] + "…"
        summaries.append(
            {
                "index": index,
                "document_name": str(row.get("document_name") or "文献"),
                "score": round(float(row.get("score") or 0.0), 4),
                "merge_score": round(float(row.get("merge_score") or row.get("score") or 0.0), 4),
                "preview": preview,
            }
        )
    return summaries


def _merge_multi_kb_results_fair(
    merged_rows: list[dict[str, Any]],
    *,
    kb_ids: list[int],
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """多库公平合并：分库归一化 + 每库/每类型保底 + merge_score 补齐 + 去重。"""
    if not merged_rows:
        return [], {
            "strategy": "auto_fair",
            "merge_top_k": limit,
            "pre_merge_total": 0,
            "post_merge_total": 0,
            "dedupe_dropped": 0,
            "type_breakdown": {"classic": 0, "lightrag": 0},
            "merge_phases": [],
        }

    rows = [dict(item) for item in merged_rows]
    _apply_merge_scores(rows)
    pre_merge_total = len(rows)
    sorted_rows = sorted(rows, key=lambda x: float(x.get("merge_score") or 0.0), reverse=True)
    merge_phases: list[dict[str, Any]] = []

    if len(kb_ids) <= 1:
        before = len(sorted_rows)
        deduped = _dedupe_search_results(sorted_rows, limit=limit)
        type_breakdown = {"classic": 0, "lightrag": 0}
        for item in deduped:
            kb_type = _row_kb_type(item)
            type_breakdown[kb_type] = type_breakdown.get(kb_type, 0) + 1
        return deduped, {
            "strategy": "auto_fair",
            "merge_top_k": limit,
            "pre_merge_total": pre_merge_total,
            "post_merge_total": len(deduped),
            "dedupe_dropped": max(0, min(before, limit) - len(deduped)),
            "type_breakdown": type_breakdown,
            "merge_phases": [{"phase": "dedupe", "count": len(deduped)}],
        }

    by_kb: dict[int, list[dict[str, Any]]] = {int(kid): [] for kid in kb_ids}
    for row in sorted_rows:
        raw_kb = row.get("knowledge_base_id")
        if raw_kb is None:
            continue
        kid = int(raw_kb)
        if kid in by_kb:
            by_kb[kid].append(row)

    selected: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    type_counts: dict[str, int] = {"classic": 0, "lightrag": 0}

    def try_add(row: dict[str, Any]) -> bool:
        if len(selected) >= limit:
            return False
        key = _result_identity_key(row)
        if key in used_keys:
            return False
        used_keys.add(key)
        selected.append(row)
        kb_type = _row_kb_type(row)
        type_counts[kb_type] = type_counts.get(kb_type, 0) + 1
        return True

    active_kb_ids = [kid for kid in kb_ids if by_kb.get(int(kid))]
    reserve_count = 0
    for kid in active_kb_ids:
        kb_rows = by_kb.get(int(kid), [])
        if kb_rows and try_add(kb_rows[0]):
            reserve_count += 1
    if reserve_count:
        merge_phases.append({"phase": "reserve_per_kb", "count": reserve_count})

    types_present = { _row_kb_type(row) for row in rows }
    type_floor = max(1, int(limit * 0.3)) if len(types_present) >= 2 else 0
    if type_floor > 0:
        type_reserve = 0
        for row in sorted_rows:
            kb_type = _row_kb_type(row)
            if type_counts.get(kb_type, 0) >= type_floor:
                continue
            if try_add(row):
                type_reserve += 1
        if type_reserve:
            merge_phases.append({"phase": "type_floor", "count": type_reserve, "floor": type_floor})

    fill_before = len(selected)
    for row in sorted_rows:
        if len(selected) >= limit:
            break
        try_add(row)
    fill_added = len(selected) - fill_before
    if fill_added:
        merge_phases.append({"phase": "fill_by_merge_score", "count": fill_added})

    selected.sort(key=lambda x: float(x.get("merge_score") or 0.0), reverse=True)
    before_dedupe = len(selected)
    deduped = _dedupe_search_results(selected, limit=limit)
    dedupe_dropped = max(0, before_dedupe - len(deduped))
    if dedupe_dropped:
        merge_phases.append({"phase": "dedupe", "dropped": dedupe_dropped, "count": len(deduped)})

    type_breakdown = {"classic": 0, "lightrag": 0}
    for item in deduped:
        kb_type = _row_kb_type(item)
        type_breakdown[kb_type] = type_breakdown.get(kb_type, 0) + 1

    return deduped, {
        "strategy": "auto_fair",
        "merge_top_k": limit,
        "pre_merge_total": pre_merge_total,
        "post_merge_total": len(deduped),
        "dedupe_dropped": dedupe_dropped,
        "type_breakdown": type_breakdown,
        "merge_phases": merge_phases,
    }


def _merge_multi_kb_results(
    merged_rows: list[dict[str, Any]],
    *,
    kb_ids: list[int],
    limit: int,
) -> list[dict[str, Any]]:
    """多库检索合并：每个库先保留至少 1 条（若有命中），再按分数补齐至 limit。"""
    if not merged_rows:
        return []
    sorted_rows = sorted(merged_rows, key=lambda x: float(x.get("score") or 0.0), reverse=True)
    if len(kb_ids) <= 1:
        return _dedupe_search_results(sorted_rows, limit=limit)

    by_kb: dict[int, list[dict[str, Any]]] = {int(kid): [] for kid in kb_ids}
    for row in sorted_rows:
        raw_kb = row.get("knowledge_base_id")
        if raw_kb is None:
            continue
        kid = int(raw_kb)
        if kid in by_kb:
            by_kb[kid].append(row)

    selected: list[dict[str, Any]] = []
    used_keys: set[str] = set()

    def try_add(row: dict[str, Any]) -> bool:
        if len(selected) >= limit:
            return False
        key = _result_identity_key(row)
        if key in used_keys:
            return False
        used_keys.add(key)
        selected.append(row)
        return True

    active_kb_ids = [kid for kid in kb_ids if by_kb.get(int(kid))]
    for kid in active_kb_ids:
        rows = by_kb.get(int(kid), [])
        if rows:
            try_add(rows[0])

    for row in sorted_rows:
        if len(selected) >= limit:
            break
        try_add(row)

    selected.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return _dedupe_search_results(selected, limit=limit)


def _dedupe_search_results(results: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """去掉同文档内高度重叠的切片，避免检索列表看起来重复。"""
    kept: list[dict[str, Any]] = []
    for item in results:
        content = str(item.get("content") or "")
        document_id = item.get("document_id")
        handled = False
        for i, prev in enumerate(kept):
            if prev.get("document_id") != document_id:
                continue
            if _content_overlap_ratio(content, str(prev.get("content") or "")) < 0.72:
                continue
            item_is_image = _result_is_standalone_image_ocr(item)
            prev_is_image = _result_is_standalone_image_ocr(prev)
            if item_is_image and not prev_is_image:
                handled = True
                break
            if prev_is_image and not item_is_image:
                kept[i] = item
                handled = True
                break
            handled = True
            break
        if not handled:
            kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def _serialize_search_result(
    *,
    chunk: KnowledgeChunk,
    document_name: str,
    score: float,
    vector_score: float | None = None,
    keyword_score: float | None = None,
) -> dict[str, Any]:
    meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    enrichment_keywords, enrichment_questions = _extract_enrichment(meta)
    content = _render_result_content(chunk)
    heading_path = chunk.heading_path or (
        str(meta.get("heading_path")).strip() if meta.get("heading_path") else None
    )
    block = _chunk_block_type(meta)
    location_label = _chunk_location_label(chunk)
    return {
        "chunk_id": chunk.id,
        "chunk_uid": chunk.chunk_uid,
        "document_id": chunk.document_id,
        "document_name": document_name,
        "chunk_index": chunk.chunk_index,
        "content": content,
        "content_preview": _content_preview(content),
        "char_count": chunk.char_count,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "heading_path": heading_path,
        "enrichment_keywords": enrichment_keywords,
        "enrichment_questions": enrichment_questions,
        "score": float(score),
        "vector_score": float(vector_score) if vector_score is not None else None,
        "keyword_score": float(keyword_score) if keyword_score is not None else None,
        "metadata": chunk.metadata_json,
        "citation": {
            "document_name": document_name,
            "page_no": _citation_page_no(chunk),
            "chunk_index": chunk.chunk_index,
            "heading_path": heading_path,
            "location_label": location_label,
            "block": block,
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


def _resolve_fusion_method(
    knowledge_base: KnowledgeBase,
    payload: KnowledgeSearchRequest,
) -> str:
    """混合检索通道融合方式：payload 优先 > 知识库 config.retrieval.fusion_method > 默认 weighted。"""
    val = getattr(payload, "fusion_method", None)
    if val in ("weighted", "rrf"):
        return val
    stored = _stored_retrieval_config(knowledge_base)
    sv = stored.get("fusion_method")
    if sv in ("weighted", "rrf"):
        return sv
    return DEFAULT_FUSION_METHOD


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


def _normalize_scores_relative(
    values: dict[str, float],
    *,
    zero_if_flat_below: float | None = None,
) -> dict[str, float]:
    """按最大值归一化（top=1.0），不像 min-max 那样把批次最小值强制压到 0。

    min-max 归一化会让每批结果里最弱的一条恒为 0.0，从而：
    - 真正相关、只是略弱于头部的切片被显示成 0 分、并可能被 score_threshold 误过滤；
    - 阈值在不同 query 间不可比（末位永远 0、首位永远 1）。

    本函数保留各通道分数与头部的相对比例（value / max），让弱于头部的相关命中
    仍有与其绝对分相称的非零分；仅用于融合排序/展示，不参与召回门控预过滤。
    """
    if not values:
        return {}
    scores = list(values.values())
    maximum = max(scores)
    minimum = min(scores)
    if maximum <= 0:
        return {key: 0.0 for key in values}
    if maximum == minimum:
        if zero_if_flat_below is not None and maximum < zero_if_flat_below:
            return {key: 0.0 for key in values}
        return {key: 1.0 for key in values}
    return {key: max(0.0, value) / maximum for key, value in values.items()}


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
    query: str = "",
) -> bool:
    """
    混合检索：向量路整体置信不足且全文仅弱命中时，视为跨库/跨主题误召回，应返回空。
    例如医保库问「正当防卫判刑吗」——全文仅「正当权益+需要」凑 1.85 分。

    已通过关键词路 MIN_KEYWORD_HYBRID_SCORE（默认 3.0）门槛的命中视为同库有效召回，
    避免如「新生儿如何办理」仅命中「新生+生儿」时被误判为空结果。
    """
    if not merged:
        return True
    if not keyword_candidates:
        return True

    min_hybrid = _min_keyword_hybrid_score_for_query(query)
    max_keyword = _max_channel_score(keyword_candidates, "keyword_score")
    if max_keyword >= min_hybrid:
        return True

    has_vector_boost = any(item.get("vector_score") is not None for item in merged.values())
    if has_vector_boost:
        return True
    top_vector = _max_channel_score(vector_candidates, "vector_score")
    if top_vector >= MIN_VECTOR_FALLBACK_SCORE and max_keyword >= MIN_KEYWORD_RELEVANCE_SCORE:
        return True
    return False


def _document_filters(
    kb_id: int,
    document_ids: list[int] | None,
    *,
    exclude_standalone_image_ocr: bool = False,
) -> list[Any]:
    filters: list[Any] = [
        KnowledgeChunk.knowledge_base_id == kb_id,
        KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED.value,
    ]
    if document_ids:
        filters.append(KnowledgeChunk.document_id.in_(document_ids))
    if exclude_standalone_image_ocr:
        meta_block = KnowledgeChunk.metadata_json["block"].as_string()
        meta_attached = KnowledgeChunk.metadata_json["image_ocr_attached"].as_string()
        filters.append(
            or_(
                meta_block.is_(None),
                meta_block != "image",
                meta_attached.isnot(None),
            )
        )
    return filters


def _keyword_candidates_postgres(
    db: Session,
    *,
    knowledge_base_id: int,
    query: str,
    limit: int,
    document_ids: list[int] | None,
    exclude_standalone_image_ocr: bool = False,
) -> list[dict[str, Any]]:
    filters = _document_filters(
        knowledge_base_id,
        document_ids,
        exclude_standalone_image_ocr=exclude_standalone_image_ocr,
    )
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
    exclude_standalone_image_ocr: bool = False,
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
                exclude_standalone_image_ocr=exclude_standalone_image_ocr,
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
        exclude_standalone_image_ocr=exclude_standalone_image_ocr,
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


def _hybrid_channel_candidates(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    query: str,
    limit: int,
    document_ids: list[int] | None,
    exclude_standalone_image_ocr: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    混合检索双路召回：向量路（含 Embedding）与关键词路并行，缩短总耗时。
    每路使用独立 DB Session（SQLAlchemy Session 非线程安全）。
    """
    kb_id = knowledge_base.id
    space_id = knowledge_base.enterprise_space_id

    def _vector_job() -> list[dict[str, Any]]:
        session = SessionLocal()
        try:
            kb = get_knowledge_base_or_error(session, space_id=space_id, kb_id=kb_id)
            return _vector_candidates(
                session,
                knowledge_base=kb,
                query=query,
                limit=limit,
                document_ids=document_ids,
            )
        finally:
            session.close()

    def _keyword_job() -> list[dict[str, Any]]:
        session = SessionLocal()
        try:
            return _keyword_candidates(
                session,
                enterprise_space_id=space_id,
                knowledge_base_id=kb_id,
                query=query,
                limit=limit,
                document_ids=document_ids,
                exclude_standalone_image_ocr=exclude_standalone_image_ocr,
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        vector_future = pool.submit(_vector_job)
        keyword_future = pool.submit(_keyword_job)
        return vector_future.result(), keyword_future.result()


def search_knowledge_base(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    payload: KnowledgeSearchRequest,
) -> dict[str, Any]:
    search_started = time.perf_counter()
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    mode = payload.mode or knowledge_base.default_retrieval_mode
    top_k = payload.top_k or knowledge_base.default_top_k
    score_threshold = payload.score_threshold
    if score_threshold is None and knowledge_base.default_score_threshold is not None:
        score_threshold = float(knowledge_base.default_score_threshold)
    document_ids = payload.document_ids or None
    query = _expand_colloquial_query(payload.query)
    include_image_ocr, image_ocr_score_factor, exclude_image_ocr = _resolve_image_ocr_retrieval(
        knowledge_base,
        payload,
        query,
    )

    use_rerank, rerank_model_id = _resolve_rerank_config(knowledge_base, mode)
    stored_retrieval = _stored_retrieval_config(knowledge_base)
    hybrid_strategy = str(stored_retrieval.get("hybrid_strategy") or "weight")
    recall_limit = max(top_k * (RERANK_RECALL_FACTOR if use_rerank else 3), top_k)
    hybrid_recall_limit = max(top_k * (RERANK_RECALL_FACTOR if use_rerank else 4), top_k)

    def _finalize_results(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = _apply_chunk_role_filters(
            raw,
            include_image_ocr=include_image_ocr,
            image_ocr_score_factor=image_ocr_score_factor,
        )
        return _dedupe_search_results(filtered, limit=top_k)

    def _post_process_results(raw: list[dict[str, Any]], *, apply_threshold: bool) -> list[dict[str, Any]]:
        rows = list(raw)
        if use_rerank and rerank_model_id and rows:
            rows = _apply_rerank_to_results(
                db,
                knowledge_base=knowledge_base,
                query=query,
                results=rows,
                rerank_model_id=rerank_model_id,
                top_n=max(recall_limit, top_k),
            )
        if apply_threshold and score_threshold is not None:
            rows = [item for item in rows if float(item.get("score") or 0) >= score_threshold]
        return _finalize_results(rows)

    if mode == "keyword":
        keyword_candidates = _keyword_candidates(
            db,
            enterprise_space_id=knowledge_base.enterprise_space_id,
            knowledge_base_id=knowledge_base.id,
            query=query,
            limit=recall_limit,
            document_ids=document_ids,
            exclude_standalone_image_ocr=exclude_image_ocr,
        )
        results = _post_process_results(
            [
                _serialize_search_result(
                    chunk=item["chunk"],
                    document_name=item["document_name"],
                    score=item["keyword_score"],
                    keyword_score=item["keyword_score"],
                )
                for item in keyword_candidates
            ],
            apply_threshold=True,
        )
    elif mode == "vector":
        vector_candidates = _vector_candidates(
            db,
            knowledge_base=knowledge_base,
            query=query,
            limit=recall_limit,
            document_ids=document_ids,
        )
        results = _post_process_results(
            [
                _serialize_search_result(
                    chunk=item["chunk"],
                    document_name=item["document_name"],
                    score=item["vector_score"],
                    vector_score=item["vector_score"],
                )
                for item in vector_candidates
            ],
            apply_threshold=True,
        )
    elif use_rerank and hybrid_strategy == "rerank":
        vector_candidates, keyword_candidates = _hybrid_channel_candidates(
            db,
            knowledge_base=knowledge_base,
            query=query,
            limit=hybrid_recall_limit,
            document_ids=document_ids,
            exclude_standalone_image_ocr=exclude_image_ocr,
        )
        merged_hybrid: dict[str, dict[str, Any]] = {}
        for item in vector_candidates:
            uid = item["chunk"].chunk_uid
            merged_hybrid[uid] = {
                "chunk": item["chunk"],
                "document_name": item["document_name"],
                "vector_score": item["vector_score"],
                "keyword_score": None,
            }
        for item in keyword_candidates:
            uid = item["chunk"].chunk_uid
            if uid in merged_hybrid:
                merged_hybrid[uid]["keyword_score"] = item["keyword_score"]
            else:
                merged_hybrid[uid] = {
                    "chunk": item["chunk"],
                    "document_name": item["document_name"],
                    "vector_score": None,
                    "keyword_score": item["keyword_score"],
                }
        preliminary = [
            _serialize_search_result(
                chunk=entry["chunk"],
                document_name=entry["document_name"],
                score=float(entry.get("vector_score") or entry.get("keyword_score") or 0),
                vector_score=entry.get("vector_score"),
                keyword_score=entry.get("keyword_score"),
            )
            for entry in merged_hybrid.values()
        ]
        results = _post_process_results(preliminary, apply_threshold=True)
    else:
        vector_candidates, keyword_candidates = _hybrid_channel_candidates(
            db,
            knowledge_base=knowledge_base,
            query=query,
            limit=hybrid_recall_limit,
            document_ids=document_ids,
            exclude_standalone_image_ocr=exclude_image_ocr,
        )
        vector_candidates = _filter_hybrid_channel_candidates(
            vector_candidates,
            score_key="vector_score",
            score_threshold=score_threshold,
            channel="vector",
            query=query,
        )
        keyword_candidates = _filter_hybrid_channel_candidates(
            keyword_candidates,
            score_key="keyword_score",
            score_threshold=score_threshold,
            channel="keyword",
            query=query,
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
        fusion_method = _resolve_fusion_method(knowledge_base, payload)

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
                    chunk_text=item["chunk"].keyword_text or item["chunk"].content or "",
                    query=query,
                ):
                    merged[uid]["vector_score"] = raw

        eligible_vector_scores = {
            uid: float(item["vector_score"])
            for uid, item in merged.items()
            if item.get("vector_score") is not None
        }
        if w_keyword <= 0.0:
            normalized_vector = _normalize_scores_relative(
                {
                    item["chunk"].chunk_uid: float(item["vector_score"] or 0)
                    for item in vector_candidates
                }
            )
        elif not keyword_candidates:
            normalized_vector = _normalize_scores_relative(
                {
                    item["chunk"].chunk_uid: float(item["vector_score"] or 0)
                    for item in vector_candidates
                }
            )
        else:
            normalized_vector = _normalize_scores_relative(eligible_vector_scores)
        normalized_keyword = _normalize_scores_relative(
            keyword_scores,
            zero_if_flat_below=_min_keyword_hybrid_score_for_query(query),
        )

        if not _hybrid_cross_domain_guard(
            keyword_candidates=keyword_candidates,
            vector_candidates=vector_candidates,
            merged=merged,
            query=query,
        ):
            results = []
        else:
            # 加权 RRF：按各通道名次融合，对量纲不可比、单路异常分更稳健；
            # 仅对 merged 内（已过护栏/预过滤）的命中重排，不改变召回成员，再归一化到 0~1。
            keyword_rank_map = {
                item["chunk"].chunk_uid: rank
                for rank, item in enumerate(keyword_candidates, start=1)
            }
            vector_rank_map_full = {
                item["chunk"].chunk_uid: rank
                for rank, item in enumerate(vector_candidates, start=1)
            }
            display_scores: dict[str, float] = {}
            if fusion_method == "rrf":
                rrf_raw: dict[str, float] = {}
                for chunk_uid, item in merged.items():
                    score = 0.0
                    if item["vector_score"] is not None and chunk_uid in vector_rank_map_full:
                        score += w_vector * (1.0 / (RRF_K + vector_rank_map_full[chunk_uid]))
                    if item["keyword_score"] is not None and chunk_uid in keyword_rank_map:
                        score += w_keyword * (1.0 / (RRF_K + keyword_rank_map[chunk_uid]))
                    rrf_raw[chunk_uid] = score
                display_scores = _normalize_scores_relative(rrf_raw)
            else:
                for chunk_uid, item in merged.items():
                    vector_score = item["vector_score"]
                    v_norm = normalized_vector.get(chunk_uid, 0.0) if vector_score is not None else 0.0
                    k_norm = normalized_keyword.get(chunk_uid, 0.0)
                    display_scores[chunk_uid] = w_vector * v_norm + w_keyword * k_norm

            ranked: list[dict[str, Any]] = []
            for chunk_uid, item in merged.items():
                vector_score = item["vector_score"]
                keyword_score = item["keyword_score"]
                final_score = display_scores.get(chunk_uid, 0.0)
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
            results = _post_process_results(ranked, apply_threshold=False)

    elapsed = time.perf_counter() - search_started
    if elapsed >= 5.0:
        logger.info(
            "knowledge search slow kb_id=%s mode=%s hits=%s elapsed=%.2fs query=%r",
            kb_id,
            mode,
            len(results),
            elapsed,
            (query or "")[:120],
        )

    return {
        "query": payload.query,
        "mode": mode,
        "total": len(results),
        "results": results,
    }


def _lightrag_chunk_score_map(chunks: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        raw_score = chunk.get("score")
        if raw_score is None:
            raw_score = chunk.get("similarity")
        if raw_score is None:
            raw_score = chunk.get("distance")
        if raw_score is not None:
            try:
                scores[chunk_id] = float(raw_score)
                continue
            except (TypeError, ValueError):
                pass
        scores[chunk_id] = max(0.1, 1.0 - index * 0.05)
    return scores


def _serialize_lightrag_search_results(
    *,
    knowledge_base: KnowledgeBase,
    graph_data: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    citations = graph_data.get("citations") or []
    chunks = graph_data.get("chunks") or []
    chunk_items = [item for item in chunks if isinstance(item, dict)]
    score_by_chunk = _lightrag_chunk_score_map(chunk_items)

    cite_by_chunk_id: dict[str, dict[str, Any]] = {}
    for cite in citations:
        if not isinstance(cite, dict):
            continue
        chunk_id_str = str(cite.get("chunk_id") or "").strip()
        if chunk_id_str:
            cite_by_chunk_id[chunk_id_str] = cite

    rows: list[dict[str, Any]] = []

    def _append_chunk_row(index: int, chunk: dict[str, Any]) -> None:
        content = str(chunk.get("content") or "").strip()
        if not content:
            return
        chunk_id_str = str(chunk.get("chunk_id") or "").strip()
        cite = cite_by_chunk_id.get(chunk_id_str) if chunk_id_str else None
        file_path = str(chunk.get("file_path") or "").split("|||")[0].strip()
        document_name = str(
            (cite or {}).get("document_name")
            or (file_path.rsplit("/", 1)[-1] if file_path else "")
            or "文献"
        )
        raw_document_id = (cite or {}).get("document_id")
        document_id = int(raw_document_id) if raw_document_id is not None else 0
        score = score_by_chunk.get(chunk_id_str, max(0.5, 1.0 - index * 0.05))
        rows.append(
            {
                "chunk_id": document_id if document_id > 0 else -(index + 1),
                "chunk_uid": f"lightrag:{knowledge_base.id}:{chunk_id_str or index + 1}",
                "document_id": document_id,
                "document_name": document_name,
                "chunk_index": index,
                "content": content,
                "content_preview": _content_preview(content),
                "char_count": len(content),
                "start_offset": None,
                "end_offset": None,
                "heading_path": None,
                "enrichment_keywords": [],
                "enrichment_questions": [],
                "score": float(score),
                "vector_score": None,
                "keyword_score": None,
                "metadata": {"source": "lightrag", "lightrag_chunk_id": chunk_id_str or None},
                "citation": {
                    "document_name": document_name,
                    "page_no": None,
                    "chunk_index": index,
                    "heading_path": None,
                    "location_label": None,
                    "block": None,
                },
                "knowledge_base_id": knowledge_base.id,
                "knowledge_base_name": knowledge_base.name,
            }
        )

    if chunk_items:
        for index, chunk in enumerate(chunk_items):
            _append_chunk_row(index, chunk)
            if len(rows) >= limit:
                break
        return rows

    for index, cite in enumerate(citations):
        if not isinstance(cite, dict):
            continue
        content = str(cite.get("content") or "").strip()
        if not content:
            continue
        document_name = str(cite.get("document_name") or "文献")
        raw_document_id = cite.get("document_id")
        document_id = int(raw_document_id) if raw_document_id is not None else 0
        chunk_id_str = str(cite.get("chunk_id") or "").strip()
        ref = int(cite.get("ref") or (index + 1))
        score = score_by_chunk.get(chunk_id_str, max(0.5, 1.0 - index * 0.05))
        rows.append(
            {
                "chunk_id": document_id if document_id > 0 else -ref,
                "chunk_uid": f"lightrag:{knowledge_base.id}:{chunk_id_str or ref}",
                "document_id": document_id,
                "document_name": document_name,
                "chunk_index": max(0, ref - 1),
                "content": content,
                "content_preview": _content_preview(content),
                "char_count": len(content),
                "start_offset": None,
                "end_offset": None,
                "heading_path": None,
                "enrichment_keywords": [],
                "enrichment_questions": [],
                "score": float(score),
                "vector_score": None,
                "keyword_score": None,
                "metadata": {"source": "lightrag", "lightrag_chunk_id": chunk_id_str or None},
                "citation": {
                    "document_name": document_name,
                    "page_no": None,
                    "chunk_index": max(0, ref - 1),
                    "heading_path": None,
                    "location_label": None,
                    "block": None,
                },
                "knowledge_base_id": knowledge_base.id,
                "knowledge_base_name": knowledge_base.name,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def search_knowledge_bases_multi(
    db: Session,
    *,
    space_id: int,
    knowledge_base_ids: list[int],
    payload: KnowledgeSearchRequest,
    vector_top_k: int | None = None,
    lightrag_top_k: int | None = None,
    merge_top_k: int | None = None,
    lightrag_query_mode: str | None = None,
    lightrag_chunk_top_k: int | None = None,
) -> dict[str, Any]:
    """
    在多个知识库上执行检索：经典库与图库按各自 Top K 召回，再公平合并至 merge_top_k。
    单库失败时跳过并记录日志。
    """
    from app.core.kb_type import is_lightrag_kb
    from app.core.knowledge_retrieval_defaults import (
        DEFAULT_LIGHTRAG_RETRIEVAL_TOP_K,
        DEFAULT_MERGE_TOP_K,
        DEFAULT_VECTOR_RETRIEVAL_TOP_K,
    )
    from app.services.lightrag_engine import get_default_query_mode, query_graph_kb

    ordered_unique: list[int] = []
    for kid in knowledge_base_ids:
        if kid not in ordered_unique:
            ordered_unique.append(kid)
    kb_ids = ordered_unique
    if not kb_ids:
        raise AppError(status_code=400, code="KB_IDS_REQUIRED", message="请至少选择一个知识库")

    first_kb = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_ids[0])
    mode_str = str(payload.mode or first_kb.default_retrieval_mode)
    resolved_merge_top = merge_top_k if merge_top_k is not None else (payload.top_k or first_kb.default_top_k)
    resolved_merge_top = min(max(int(resolved_merge_top or DEFAULT_MERGE_TOP_K), 1), 50)
    resolved_vector_top = min(max(int(vector_top_k or DEFAULT_VECTOR_RETRIEVAL_TOP_K), 1), 50)
    resolved_lightrag_top = min(max(int(lightrag_top_k or DEFAULT_LIGHTRAG_RETRIEVAL_TOP_K), 1), 50)

    merged_rows: list[dict[str, Any]] = []
    path_results: list[dict[str, Any]] = []
    for kb_id in kb_ids:
        kb = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)

        if is_lightrag_kb(kb):
            path_top = resolved_lightrag_top
            kb_type = "lightrag"
            try:
                graph_mode = lightrag_query_mode or get_default_query_mode(kb)
                if graph_mode not in ("naive", "local", "global", "hybrid", "mix"):
                    graph_mode = get_default_query_mode(kb)
                graph_data = query_graph_kb(
                    db,
                    knowledge_base=kb,
                    query=payload.query,
                    mode=graph_mode,  # type: ignore[arg-type]
                    top_k=path_top,
                    chunk_top_k=lightrag_chunk_top_k,
                    include_references=True,
                )
                path_rows = _serialize_lightrag_search_results(
                    knowledge_base=kb,
                    graph_data=graph_data,
                    limit=path_top,
                )
                merged_rows.extend(path_rows)
                _apply_merge_scores(path_rows)
                path_results.append(
                    {
                        "knowledge_base_id": kb.id,
                        "knowledge_base_name": kb.name,
                        "kb_type": kb_type,
                        "mode": graph_mode,
                        "path_top_k": path_top,
                        "recalled_count": len(path_rows),
                        "candidates": _summarize_path_candidates(path_rows, limit=len(path_rows)),
                        "error": None,
                    }
                )
            except AppError as exc:
                logger.warning("多库检索跳过图知识库 kb_id=%s：%s", kb_id, exc)
                path_results.append(
                    {
                        "knowledge_base_id": kb.id,
                        "knowledge_base_name": kb.name,
                        "kb_type": kb_type,
                        "mode": lightrag_query_mode or get_default_query_mode(kb),
                        "path_top_k": path_top,
                        "recalled_count": 0,
                        "candidates": [],
                        "error": str(exc.message if hasattr(exc, "message") else exc),
                    }
                )
            continue

        path_top = resolved_vector_top
        kb_type = "classic"
        inner = KnowledgeSearchRequest(
            query=payload.query,
            mode=payload.mode,
            top_k=path_top,
            score_threshold=payload.score_threshold,
            vector_weight=payload.vector_weight,
            document_ids=payload.document_ids,
            include_image_ocr=payload.include_image_ocr,
        )
        try:
            one = search_knowledge_base(db, space_id=space_id, kb_id=kb_id, payload=inner)
        except AppError as exc:
            logger.warning("多库检索跳过知识库 kb_id=%s：%s", kb_id, exc)
            path_results.append(
                {
                    "knowledge_base_id": kb.id,
                    "knowledge_base_name": kb.name,
                    "kb_type": kb_type,
                    "mode": str(payload.mode or kb.default_retrieval_mode),
                    "path_top_k": path_top,
                    "recalled_count": 0,
                    "candidates": [],
                    "error": str(exc.message if hasattr(exc, "message") else exc),
                }
            )
            continue
        mode_str = str(one.get("mode") or mode_str)
        path_rows: list[dict[str, Any]] = []
        for item in one["results"]:
            row = dict(item)
            row["knowledge_base_id"] = kb.id
            row["knowledge_base_name"] = kb.name
            path_rows.append(row)
            merged_rows.append(row)
        _apply_merge_scores(path_rows)
        path_results.append(
            {
                "knowledge_base_id": kb.id,
                "knowledge_base_name": kb.name,
                "kb_type": kb_type,
                "mode": mode_str,
                "path_top_k": path_top,
                "recalled_count": len(path_rows),
                "candidates": _summarize_path_candidates(path_rows, limit=len(path_rows)),
                "error": None,
            }
        )

    merged_rows, merge_meta = _merge_multi_kb_results_fair(
        merged_rows,
        kb_ids=kb_ids,
        limit=resolved_merge_top,
    )
    merge_meta["vector_top_k"] = resolved_vector_top
    merge_meta["lightrag_top_k"] = resolved_lightrag_top

    kb_result_counts: dict[int, int] = defaultdict(int)
    for row in merged_rows:
        kb_id = row.get("knowledge_base_id")
        if kb_id is not None:
            kb_result_counts[int(kb_id)] += 1
    for kb_id in kb_ids:
        record_usage_event(
            db,
            enterprise_space_id=space_id,
            event_type="retrieval_call",
            source="retrieval",
            knowledge_base_id=kb_id,
            result_count=kb_result_counts.get(kb_id, 0),
        )

    return {
        "query": payload.query,
        "mode": mode_str,
        "knowledge_base_ids": kb_ids,
        "total": len(merged_rows),
        "results": merged_rows,
        "merge_meta": merge_meta,
        "path_results": path_results,
    }
