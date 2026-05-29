"""切片 enrichment 编辑服务单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import AppError
from app.services.chunk_edit_service import (
    _normalize_string_list,
    chunk_enrichment_editable,
    regenerate_chunk_enrichment,
    update_chunk_enrichment,
)
from app.services.chunk_enrichment_service import build_keyword_text
from app.services.chunk_response import serialize_chunk


def test_build_keyword_text_includes_keywords_and_questions():
    text = build_keyword_text(
        "正文内容",
        keywords=["医保", "结算"],
        questions=["如何办理即时结算？"],
    )
    assert "正文内容" in text
    assert "关键词：医保；结算" in text
    assert "问题：如何办理即时结算？" in text


def test_normalize_string_list_dedupes_and_trims():
    assert _normalize_string_list([" 医保 ", "医保", "结算", ""], max_items=5) == ["医保", "结算"]


def test_chunk_enrichment_editable():
    editable = MagicMock()
    editable.metadata_json = {}
    assert chunk_enrichment_editable(editable) is True

    preview = MagicMock()
    preview.metadata_json = {"source": "mineru_graph_preview"}
    assert chunk_enrichment_editable(preview) is False

    lightrag = MagicMock()
    lightrag.metadata_json = {"source": "lightrag_text_chunk"}
    assert chunk_enrichment_editable(lightrag) is False


def test_serialize_chunk_exposes_enrichment_fields():
    chunk = MagicMock()
    chunk.id = 1
    chunk.chunk_uid = "uid-1"
    chunk.document_id = 10
    chunk.chunk_index = 0
    chunk.content = "hello"
    chunk.content_preview = "hello"
    chunk.char_count = 5
    chunk.token_count = None
    chunk.start_offset = 0
    chunk.end_offset = 5
    chunk.page_no = 1
    chunk.heading_path = None
    chunk.vector_status = "indexed"
    chunk.vector_id = "uid-1"
    chunk.keyword_text = "hello\n关键词：医保"
    chunk.metadata_json = {
        "enrichment_keywords": ["医保"],
        "enrichment_questions": ["问题一"],
    }
    chunk.created_at = chunk.updated_at = None

    data = serialize_chunk(chunk)
    assert data["enrichment_keywords"] == ["医保"]
    assert data["enrichment_questions"] == ["问题一"]
    assert data["keyword_text"] == "hello\n关键词：医保"


def _mock_chunk(*, metadata: dict | None = None) -> MagicMock:
    chunk = MagicMock()
    chunk.id = 42
    chunk.chunk_uid = "doc-1-0"
    chunk.document_id = 10
    chunk.document_name = "test.pdf"
    chunk.chunk_index = 0
    chunk.content = "切片正文"
    chunk.heading_path = "第一章"
    chunk.page_no = 1
    chunk.enterprise_space_id = 1
    chunk.knowledge_base_id = 2
    chunk.metadata_json = metadata or {}
    chunk.keyword_text = "切片正文"
    chunk.vector_status = "indexed"
    chunk.vector_id = "doc-1-0"
    return chunk


def _mock_kb(*, vector_db_enabled: bool = False) -> MagicMock:
    kb = MagicMock()
    kb.vector_db_enabled = vector_db_enabled
    kb.config = {"enrichment": {"enabled": True, "generate_keywords": True, "generate_questions": True}}
    kb.milvus_collection_name = "kb_test"
    kb.milvus_dimension = 4
    kb.milvus_metric_type = "COSINE"
    return kb


def _mock_document() -> MagicMock:
    doc = MagicMock()
    doc.document_name = "政策.pdf"
    doc.file_name = "政策.pdf"
    return doc


@patch("app.services.chunk_edit_service._reindex_single_chunk_vector")
@patch("app.services.chunk_edit_service.get_chunk_for_edit")
@patch("app.services.chunk_edit_service.get_knowledge_base_or_error")
def test_update_chunk_enrichment_persists_metadata(
    mock_get_kb,
    mock_get_chunk,
    mock_reindex,
):
    chunk = _mock_chunk()
    document = _mock_document()
    mock_get_kb.return_value = _mock_kb(vector_db_enabled=False)
    mock_get_chunk.return_value = chunk
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = document

    result = update_chunk_enrichment(
        db,
        space_id=1,
        kb_id=2,
        chunk_id=42,
        keywords=["关键词A"],
        questions=["问题A？"],
    )

    assert chunk.metadata_json["enrichment_keywords"] == ["关键词A"]
    assert chunk.metadata_json["enrichment_questions"] == ["问题A？"]
    assert chunk.metadata_json["enrichment_source"] == "manual"
    assert "关键词A" in chunk.keyword_text
    mock_reindex.assert_called_once()
    db.commit.assert_called_once()
    assert result["enrichment_keywords"] == ["关键词A"]


@patch("app.services.chunk_edit_service.enrich_chunk_with_llm")
@patch("app.services.chunk_edit_service._resolve_enrichment_llm")
@patch("app.services.chunk_edit_service.get_chunk_for_edit")
@patch("app.services.chunk_edit_service.get_knowledge_base_or_error")
def test_regenerate_chunk_enrichment_returns_llm_result(
    mock_get_kb,
    mock_get_chunk,
    mock_resolve_llm,
    mock_enrich,
):
    chunk = _mock_chunk()
    mock_get_kb.return_value = _mock_kb()
    mock_get_chunk.return_value = chunk
    mock_resolve_llm.return_value = MagicMock(model_name="test-llm")

    result_obj = MagicMock()
    result_obj.keywords = ["k1"]
    result_obj.questions = ["q1?"]
    mock_enrich.return_value = result_obj

    out = regenerate_chunk_enrichment(db=MagicMock(), space_id=1, kb_id=2, chunk_id=42)
    assert out == {"keywords": ["k1"], "questions": ["q1?"]}


@patch("app.services.chunk_edit_service.get_chunk_for_edit")
@patch("app.services.chunk_edit_service.get_knowledge_base_or_error")
def test_regenerate_fails_when_enrichment_disabled(mock_get_kb, mock_get_chunk):
    chunk = _mock_chunk()
    kb = _mock_kb()
    kb.config = {"enrichment": {"enabled": False}}
    mock_get_kb.return_value = kb
    mock_get_chunk.return_value = chunk

    with pytest.raises(AppError) as exc:
        regenerate_chunk_enrichment(db=MagicMock(), space_id=1, kb_id=2, chunk_id=42)
    assert exc.value.code == "ENRICHMENT_DISABLED"
