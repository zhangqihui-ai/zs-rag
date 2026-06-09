"""OpenSearch 切片索引：BM25 全文检索与 Upsert/删除。"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus

logger = logging.getLogger(__name__)
settings = get_settings()

# 单次 _bulk 条数过大易触发 OpenSearch circuit breaker（429）
OPENSEARCH_BULK_BATCH_SIZE = 40
OPENSEARCH_BULK_MAX_RETRIES = 5
OPENSEARCH_BULK_RETRY_BASE_SEC = 2.0

# 问句里高频、单独命中会污染结果的中文词（不要求命中）
_CN_QUERY_NOISE: frozenset[str] = frozenset(
    {
        "什么",
        "怎么",
        "为啥",
        "为什么",
        "哪里",
        "哪儿",
        "如何",
        "是否",
        "多少",
        "哪些",
        "啥意思",
        "请问",
        "有没有",
        "能不能",
        "可不可以",
        "干嘛",
        "怎样",
        "咋样",
    }
)


def _strip_query_decorators(raw: str) -> str:
    """去掉句尾「是什么」「有哪些」等模板，保留实体/专名。"""
    s = raw.strip()
    for pat in (
        r"是什么[？?！!。.\s]*$",
        r"是啥[？?！!。.\s]*$",
        r"什么意思[？?！!。.\s]*$",
        r"指的是什么[？?！!。.\s]*$",
        r"是什么意思[？?！!。.\s]*$",
        r"有哪些[？?！!。.\s]*$",
        r"^[请请]问[，,、：:\s]+",
    ):
        s = re.sub(pat, "", s).strip()
    return s


def _substantive_terms(q: str) -> list[str]:
    """
    从问句中提取应参与 AND 的词：连续汉字(≥2) + 英文数字词；
    过滤常见虚问词。若无结果则用去掉模板后的整段（便于短语匹配）。
    """
    base = _strip_query_decorators(q)
    if not base.strip():
        base = q.strip()
    terms: list[str] = []
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", base):
        t = m.group(0)
        if t in _CN_QUERY_NOISE:
            continue
        terms.append(t)
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9._\\-]{1,}", base):
        terms.append(m.group(0))

    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        key = t.lower() if re.match(r"^[A-Za-z]", t) else t
        if key in seen:
            continue
        seen.add(key)
        out.append(t)

    if not out and base.strip() and len(base.strip()) <= 64:
        if base.strip() not in _CN_QUERY_NOISE:
            out.append(base.strip())
    return out


def _expand_search_terms(terms: list[str]) -> list[str]:
    """
    长中文片段整段 phrase 几乎无法命中法条正文；拆成二字片段做 should 召回。
    短词（≤4 字）保留原样以便精确匹配专名。
    """
    expanded: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if re.fullmatch(r"[\u4e00-\u9fff]+", term) and len(term) > 4:
            for i in range(len(term) - 1):
                piece = term[i : i + 2]
                if piece not in seen:
                    seen.add(piece)
                    expanded.append(piece)
        elif term not in seen:
            seen.add(term)
            expanded.append(term)
    return expanded


def _minimum_should_match(term_count: int) -> int:
    if term_count <= 2:
        return 1
    return min(3, max(2, term_count // 4))


def _keyword_query_bool(
    *,
    query: str,
    knowledge_base_id: int,
    enterprise_space_id: int,
    document_ids: list[int] | None,
    limit: int,
    exclude_standalone_image_ocr: bool = False,
) -> dict[str, Any]:
    filter_q: list[dict[str, Any]] = [
        {"term": {"knowledge_base_id": knowledge_base_id}},
        {"term": {"enterprise_space_id": enterprise_space_id}},
    ]
    if document_ids:
        filter_q.append({"terms": {"document_id": document_ids}})

    terms = _substantive_terms(query)
    if not terms:
        bool_query: dict[str, Any] = {
            "must": [
                {
                    "multi_match": {
                        "query": query.strip(),
                        "fields": ["keyword_text^2", "content", "document_name"],
                        "type": "phrase",
                    }
                }
            ],
            "filter": filter_q,
        }
    else:
        search_terms = _expand_search_terms(terms)
        should = [
            {
                "multi_match": {
                    "query": term,
                    "fields": ["keyword_text^2", "content", "document_name"],
                    "type": "phrase" if len(term) >= 2 else "best_fields",
                }
            }
            for term in search_terms
        ]
        bool_query = {
            "should": should,
            "minimum_should_match": _minimum_should_match(len(search_terms)),
            "filter": filter_q,
        }

    if exclude_standalone_image_ocr:
        must_not = bool_query.setdefault("must_not", [])
        must_not.append({"term": {"block": "image"}})

    return {
        "size": max(1, min(limit, 100)),
        "_source": ["chunk_uid", "chunk_id"],
        "query": {"bool": bool_query},
    }


_INDEX_BODY: dict[str, Any] = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "chunk_uid": {"type": "keyword"},
            "chunk_id": {"type": "long"},
            "enterprise_space_id": {"type": "integer"},
            "knowledge_base_id": {"type": "integer"},
            "document_id": {"type": "integer"},
            "document_name": {"type": "text"},
            "chunk_index": {"type": "integer"},
            "page_no": {"type": "integer"},
            "keyword_text": {"type": "text"},
            "content": {"type": "text"},
            "block": {"type": "keyword"},
            "chunk_role": {"type": "keyword"},
        }
    },
}


def _base_url() -> str:
    raw = settings.opensearch_url
    if raw is None:
        return ""
    return str(raw).strip().rstrip("/")


def is_enabled() -> bool:
    return bool(_base_url())


def _index_name() -> str:
    return settings.opensearch_index_chunks.strip() or "zs_rag_chunks"


def _client(timeout: float = 60.0) -> httpx.Client:
    return httpx.Client(base_url=_base_url(), timeout=timeout, headers={"Content-Type": "application/json"})


def ensure_chunk_index(*, client: httpx.Client | None = None) -> None:
    idx = _index_name()
    own = client is None
    c = client or _client(timeout=30.0)
    try:
        r = c.head(f"/{idx}")
        if r.status_code == 200:
            return
        if r.status_code not in (404,):
            r.raise_for_status()
        put = c.put(f"/{idx}", content=json.dumps(_INDEX_BODY, ensure_ascii=False).encode("utf-8"))
        put.raise_for_status()
    finally:
        if own:
            c.close()


def delete_by_document_id(
    document_id: int,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> None:
    delete_by_document_ids([document_id], client=client, timeout=timeout)


def delete_by_document_ids(
    document_ids: list[int],
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
) -> None:
    ids = sorted({int(i) for i in document_ids if i is not None})
    if not ids or not is_enabled():
        return
    idx = _index_name()
    own = client is None
    c = client or _client(timeout=timeout)
    try:
        ensure_chunk_index(client=c)
        body = {"query": {"terms": {"document_id": ids}}}
        r = c.post(f"/{idx}/_delete_by_query?conflicts=proceed&refresh=false", json=body)
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("OpenSearch delete_by_document_ids failed doc_ids=%s: %s", ids, e)
    finally:
        if own:
            c.close()


def delete_by_knowledge_base_id(knowledge_base_id: int, *, client: httpx.Client | None = None) -> None:
    if not is_enabled():
        return
    idx = _index_name()
    own = client is None
    c = client or _client()
    try:
        ensure_chunk_index(client=c)
        body = {"query": {"term": {"knowledge_base_id": knowledge_base_id}}}
        r = c.post(f"/{idx}/_delete_by_query?conflicts=proceed&refresh=true", json=body)
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("OpenSearch delete_by_knowledge_base_id failed kb_id=%s: %s", knowledge_base_id, e)
    finally:
        if own:
            c.close()


def _chunk_bulk_doc(*, idx: str, document_name: str, ch: KnowledgeChunk) -> tuple[str, str]:
    action = json.dumps({"index": {"_index": idx, "_id": ch.chunk_uid}}, ensure_ascii=False)
    kw = (ch.keyword_text or ch.content or "").strip()
    chunk_meta = ch.metadata_json if isinstance(ch.metadata_json, dict) else {}
    doc_body: dict[str, Any] = {
        "chunk_uid": ch.chunk_uid,
        "chunk_id": int(ch.id),
        "enterprise_space_id": int(ch.enterprise_space_id),
        "knowledge_base_id": int(ch.knowledge_base_id),
        "document_id": int(ch.document_id),
        "document_name": document_name,
        "chunk_index": int(ch.chunk_index),
        "page_no": int(ch.page_no) if ch.page_no is not None else None,
        "keyword_text": kw,
        "content": (ch.content or "")[:200_000],
    }
    block = chunk_meta.get("block")
    if block:
        doc_body["block"] = str(block)
    chunk_role = chunk_meta.get("chunk_role")
    if chunk_role:
        doc_body["chunk_role"] = str(chunk_role)
    if doc_body["page_no"] is None:
        del doc_body["page_no"]
    return action, json.dumps(doc_body, ensure_ascii=False)


def _post_bulk_ndjson(client: httpx.Client, lines: list[str]) -> None:
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    last_response: httpx.Response | None = None
    for attempt in range(OPENSEARCH_BULK_MAX_RETRIES):
        r = client.post(
            "/_bulk",
            content=payload,
            headers={"Content-Type": "application/x-ndjson"},
        )
        last_response = r
        if r.status_code == 429:
            if attempt < OPENSEARCH_BULK_MAX_RETRIES - 1:
                wait = OPENSEARCH_BULK_RETRY_BASE_SEC * (2**attempt)
                logger.warning(
                    "OpenSearch bulk 429，%ss 后重试 (%s/%s)",
                    wait,
                    attempt + 1,
                    OPENSEARCH_BULK_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            break
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            for item in data.get("items") or []:
                err = item.get("index", {}).get("error")
                if err:
                    logger.warning("OpenSearch bulk item error: %s", err)
                    break
        return
    if last_response is not None:
        last_response.raise_for_status()


def bulk_upsert_chunks(
    *,
    document_name: str,
    chunks: list[KnowledgeChunk],
    client: httpx.Client | None = None,
) -> None:
    if not is_enabled() or not chunks:
        return
    idx = _index_name()
    own = client is None
    c = client or _client(timeout=120.0)
    try:
        ensure_chunk_index(client=c)
        batch_size = max(1, OPENSEARCH_BULK_BATCH_SIZE)
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            lines: list[str] = []
            for ch in batch:
                action, doc_line = _chunk_bulk_doc(idx=idx, document_name=document_name, ch=ch)
                lines.extend([action, doc_line])
            _post_bulk_ndjson(c, lines)
    except httpx.HTTPError as e:
        logger.warning("OpenSearch bulk_upsert_chunks failed: %s", e)
    finally:
        if own:
            c.close()


def sync_document_after_index(
    db: Session,
    *,
    document_id: int,
    document_name: str,
) -> None:
    """索引成功后：将文档下切片写入 OpenSearch（失败仅打日志，不抛错）。"""
    if not is_enabled():
        return
    try:
        chunks = list(
            db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id).order_by(KnowledgeChunk.chunk_index)
            ).scalars().all()
        )
        if chunks:
            bulk_upsert_chunks(document_name=document_name, chunks=chunks)
    except Exception as exc:
        logger.warning("OpenSearch sync_document_after_index doc_id=%s: %s", document_id, exc)


def keyword_search_candidates(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_id: int,
    query: str,
    limit: int,
    document_ids: list[int] | None,
    exclude_standalone_image_ocr: bool = False,
) -> list[dict[str, Any]]:
    """
    返回与 _keyword_candidates（PG）相同结构：chunk, document_name, keyword_score。
    """
    if not is_enabled():
        raise RuntimeError("OpenSearch not configured")

    idx = _index_name()
    q = (query or "").strip()
    if not q:
        return []

    body = _keyword_query_bool(
        query=q,
        knowledge_base_id=knowledge_base_id,
        enterprise_space_id=enterprise_space_id,
        document_ids=document_ids,
        limit=limit,
        exclude_standalone_image_ocr=exclude_standalone_image_ocr,
    )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "OpenSearch keyword: raw=%r substantives=%r",
            q,
            _substantive_terms(q),
        )

    with _client(timeout=30.0) as c:
        ensure_chunk_index(client=c)
        r = c.post(f"/{idx}/_search", json=body)
        r.raise_for_status()
        data = r.json()

    hits = (data.get("hits") or {}).get("hits") or []
    if not hits:
        return []

    order: list[str] = []
    scores: dict[str, float] = {}
    for h in hits:
        src = h.get("_source") or {}
        uid = str(src.get("chunk_uid") or "")
        if not uid:
            continue
        order.append(uid)
        scores[uid] = float(h.get("_score") or 0.0)

    uids = list(dict.fromkeys(order))
    if not uids:
        return []

    rows = db.execute(
        select(KnowledgeChunk, KnowledgeDocument.document_name)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeChunk.chunk_uid.in_(uids),
            KnowledgeChunk.knowledge_base_id == knowledge_base_id,
            KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED.value,
        )
    ).all()
    by_uid = {chunk.chunk_uid: (chunk, document_name) for chunk, document_name in rows}

    out: list[dict[str, Any]] = []
    for uid in order:
        row = by_uid.get(uid)
        if row is None:
            continue
        chunk, document_name = row
        out.append(
            {
                "chunk": chunk,
                "document_name": document_name,
                "keyword_score": scores.get(uid, 0.0),
            }
        )
    return out
