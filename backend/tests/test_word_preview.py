"""Tests for legacy .doc Word preview conversion path."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.knowledge_document_service import (
    WORD_PREVIEW_DOCX_FILENAME,
    _persist_parse_view_artifacts,
    resolve_word_preview_docx_path,
)


def test_persist_parse_view_artifacts_includes_doc_parser_type(tmp_path: Path) -> None:
    from app.core.document_parser import ParsedDocument, ParsedSegment

    text = "第一章 总则"
    parsed = ParsedDocument(
        text=text,
        char_count=len(text),
        parser_type="doc",
        segments=[ParsedSegment(text=text, start_offset=0, end_offset=len(text), metadata={"block": "text"})],
        metadata={"parser_backend": "python-docx"},
    )
    file_path = tmp_path / "original.doc"
    file_path.write_bytes(b"legacy")
    _persist_parse_view_artifacts(parsed=parsed, file_path=file_path)
    assert (tmp_path / "docx_markdown.md").is_file()
    assert (tmp_path / "docx_content_list.json").is_file()


def test_resolve_word_preview_docx_path_caches_converted_doc(tmp_path: Path) -> None:
    original = tmp_path / "original.doc"
    original.write_bytes(b"legacy-doc-bytes")
    fake_docx = b"PK\x03\x04fake-docx"

    document = MagicMock()
    document.file_ext = "doc"
    document.file_name = "sample.doc"

    with patch(
        "app.services.knowledge_document_service.resolve_original_file_path",
        return_value=original,
    ), patch(
        "app.core.doc_conversion.convert_doc_to_docx_bytes",
        return_value=fake_docx,
    ) as convert_mock:
        path = resolve_word_preview_docx_path(document)

    assert path == tmp_path / WORD_PREVIEW_DOCX_FILENAME
    assert path.read_bytes() == fake_docx
    convert_mock.assert_called_once()

    with patch(
        "app.services.knowledge_document_service.resolve_original_file_path",
        return_value=original,
    ), patch("app.core.doc_conversion.convert_doc_to_docx_bytes") as convert_mock_again:
        path_again = resolve_word_preview_docx_path(document)

    assert path_again == path
    convert_mock_again.assert_not_called()


def test_resolve_word_preview_docx_path_returns_original_for_docx(tmp_path: Path) -> None:
    original = tmp_path / "original.docx"
    original.write_bytes(b"docx-bytes")
    document = MagicMock()
    document.file_ext = "docx"
    document.file_name = "sample.docx"

    with patch(
        "app.services.knowledge_document_service.resolve_original_file_path",
        return_value=original,
    ):
        assert resolve_word_preview_docx_path(document) == original
