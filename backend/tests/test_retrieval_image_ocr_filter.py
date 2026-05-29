"""独立 block=image OCR 切片检索过滤。"""

from app.models.knowledge_base import KnowledgeChunk, KnowledgeBase
from app.schemas.retrieval import KnowledgeSearchRequest
from app.services.retrieval_service import (
    _apply_chunk_role_filters,
    _dedupe_search_results,
    _is_standalone_image_ocr_chunk,
    _query_wants_image_ocr,
    _resolve_image_ocr_retrieval,
    _result_is_standalone_image_ocr,
)


def _chunk(**kwargs) -> KnowledgeChunk:
    return KnowledgeChunk(**kwargs)


def _kb(**kwargs) -> KnowledgeBase:
    defaults = {
        "id": 1,
        "enterprise_space_id": 1,
        "name": "test",
        "default_retrieval_mode": "hybrid",
        "default_top_k": 5,
        "config": {},
    }
    defaults.update(kwargs)
    return KnowledgeBase(**defaults)


def test_is_standalone_image_ocr_chunk():
    image = _chunk(
        id=1,
        chunk_uid="img",
        document_id=1,
        chunk_index=0,
        content="OCR",
        metadata_json={"block": "image"},
    )
    attached = _chunk(
        id=2,
        chunk_uid="para",
        document_id=1,
        chunk_index=1,
        content="正文",
        metadata_json={"block": "paragraph", "image_ocr_attached": 1},
    )
    assert _is_standalone_image_ocr_chunk(image)
    assert not _is_standalone_image_ocr_chunk(attached)


def test_query_wants_image_ocr():
    assert _query_wants_image_ocr("豫事办如何选择办理地区")
    assert _query_wants_image_ocr("App 界面怎么操作")
    assert not _query_wants_image_ocr("新生儿需要哪些材料")


def test_apply_chunk_role_filters_excludes_by_default():
    body = {
        "content": "四、需提供材料",
        "score": 0.9,
        "metadata": {"block": "paragraph"},
    }
    ocr = {
        "content": "申报须知 OCR",
        "score": 0.95,
        "metadata": {"block": "image"},
    }
    out = _apply_chunk_role_filters([ocr, body], include_image_ocr=False, image_ocr_score_factor=0.55)
    assert len(out) == 1
    assert out[0]["content"] == "四、需提供材料"


def test_apply_chunk_role_filters_downweights_when_included():
    ocr = {
        "content": "截图 OCR",
        "score": 1.0,
        "metadata": {"block": "image"},
    }
    out = _apply_chunk_role_filters([ocr], include_image_ocr=True, image_ocr_score_factor=0.55)
    assert len(out) == 1
    assert out[0]["score"] == 0.55


def test_resolve_image_ocr_auto_ui_query():
    kb = _kb(config={"retrieval": {"include_image_ocr": False, "auto_image_ocr_on_ui_query": True}})
    include, factor, exclude = _resolve_image_ocr_retrieval(
        kb,
        KnowledgeSearchRequest(query="豫事办界面怎么选地区"),
        "豫事办界面怎么选地区",
    )
    assert include is True
    assert exclude is False
    assert factor == 0.55


def test_resolve_image_ocr_respects_kb_config():
    kb = _kb(config={"retrieval": {"include_image_ocr": True}})
    include, _, exclude = _resolve_image_ocr_retrieval(
        kb,
        KnowledgeSearchRequest(query="需要哪些材料"),
        "需要哪些材料",
    )
    assert include is True
    assert exclude is False


def test_dedupe_prefers_body_over_image():
    body = {
        "document_id": 1,
        "content": "引导式申报" + "正文" * 30,
        "score": 0.7,
        "metadata": {"block": "paragraph"},
        "chunk_uid": "body",
    }
    ocr = {
        "document_id": 1,
        "content": body["content"][:100],
        "score": 0.95,
        "metadata": {"block": "image"},
        "chunk_uid": "ocr",
    }
    deduped = _dedupe_search_results([ocr, body], limit=5)
    assert len(deduped) == 1
    assert deduped[0]["chunk_uid"] == "body"


def test_result_is_standalone_image_ocr_from_citation():
    item = {
        "content": "x",
        "metadata": None,
        "citation": {"block": "image"},
    }
    assert _result_is_standalone_image_ocr(item)


def test_document_filters_exclude_image_ocr_compiles():
    from app.services.retrieval_service import _document_filters

    filters = _document_filters(1, None, exclude_standalone_image_ocr=True)
    assert len(filters) == 3


def test_hybrid_cross_domain_guard_allows_newborn_keyword_hit():
    from app.services.retrieval_service import _hybrid_cross_domain_guard

    keyword_candidates = [{"keyword_score": 3.0, "chunk": object()}]
    merged = {"u1": {"vector_score": None, "keyword_score": 3.0}}
    assert _hybrid_cross_domain_guard(
        keyword_candidates=keyword_candidates,
        vector_candidates=[{"vector_score": 0.42}],
        merged=merged,
    )
