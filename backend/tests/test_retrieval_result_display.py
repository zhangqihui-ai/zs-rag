"""检索结果序列化与去重。"""

from app.models.knowledge_base import KnowledgeChunk
from app.services.retrieval_service import (
    _chunk_location_label,
    _content_overlap_ratio,
    _content_preview,
    _dedupe_search_results,
    _extract_enrichment,
    _serialize_search_result,
)


def _chunk(**kwargs) -> KnowledgeChunk:
    return KnowledgeChunk(**kwargs)


def test_location_label_prefers_heading_over_page_one():
    chunk = _chunk(
        id=1,
        chunk_uid="u1",
        document_id=1,
        chunk_index=0,
        content="正文",
        page_no=1,
        heading_path="**四、需提供材料**",
        metadata_json={"block": "paragraph", "heading_path": "四、需提供材料"},
    )
    item = _serialize_search_result(chunk=chunk, document_name="test.docx", score=0.8)
    assert item["citation"]["page_no"] is None
    assert item["citation"]["location_label"] == "四、需提供材料"


def test_dedupe_removes_near_duplicate_chunks():
    base = {
        "document_id": 1,
        "score": 0.9,
    }
    long_text = "2. 新生儿出生“一件事”提供引导式申报，请根据实际情况依次回答问题。" * 2
    short_text = long_text[:80]
    results = [
        {**base, "content": long_text, "chunk_uid": "a"},
        {**base, "content": short_text, "chunk_uid": "b"},
        {**base, "content": "完全不同的材料清单", "chunk_uid": "c"},
    ]
    deduped = _dedupe_search_results(results, limit=5)
    assert len(deduped) == 2
    assert deduped[0]["chunk_uid"] == "a"
    assert deduped[1]["chunk_uid"] == "c"


def test_dedupe_prefers_body_chunk_over_image_ocr():
    body = {
        "document_id": 1,
        "score": 0.7,
        "content": "引导式申报" + "正文" * 20,
        "metadata": {"block": "paragraph"},
        "chunk_uid": "body",
    }
    ocr = {
        "document_id": 1,
        "score": 0.95,
        "content": body["content"][:100],
        "metadata": {"block": "image"},
        "chunk_uid": "ocr",
    }
    deduped = _dedupe_search_results([ocr, body], limit=5)
    assert len(deduped) == 1
    assert deduped[0]["chunk_uid"] == "body"


def test_content_preview_truncates():
    text = "a" * 300
    assert len(_content_preview(text)) <= 240


def test_enrichment_fields_serialized():
    chunk = _chunk(
        id=2,
        chunk_uid="u2",
        document_id=1,
        chunk_index=3,
        content="正文",
        metadata_json={
            "enrichment_keywords": ["关键词A"],
            "enrichment_questions": ["问题A？"],
        },
    )
    item = _serialize_search_result(chunk=chunk, document_name="test.docx", score=0.5)
    assert item["enrichment_keywords"] == ["关键词A"]
    assert item["enrichment_questions"] == ["问题A？"]


def test_overlap_ratio_detects_substring_duplicate():
    long_text = "引导式申报" + "正文内容" * 20
    short_text = long_text[:120]
    assert _content_overlap_ratio(long_text, short_text) >= 0.72
