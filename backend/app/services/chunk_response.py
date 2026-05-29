"""KnowledgeChunk API 序列化（避免 knowledge_document_service 被 chunk_edit 间接全量导入）。"""

from __future__ import annotations

from typing import Any

from app.models.knowledge_base import KnowledgeChunk


def serialize_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    kw_raw = meta.get("enrichment_keywords") or []
    q_raw = meta.get("enrichment_questions") or []
    enrichment_keywords = (
        [str(k).strip() for k in kw_raw if str(k).strip()]
        if isinstance(kw_raw, list)
        else []
    )
    enrichment_questions = (
        [str(q).strip() for q in q_raw if str(q).strip()]
        if isinstance(q_raw, list)
        else []
    )
    return {
        "id": chunk.id,
        "chunk_uid": chunk.chunk_uid,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_preview": chunk.content_preview,
        "char_count": chunk.char_count,
        "token_count": chunk.token_count,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "page_no": chunk.page_no,
        "heading_path": chunk.heading_path,
        "vector_status": chunk.vector_status,
        "vector_id": chunk.vector_id,
        "keyword_text": chunk.keyword_text,
        "enrichment_keywords": enrichment_keywords,
        "enrichment_questions": enrichment_questions,
        "metadata": chunk.metadata_json,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }
