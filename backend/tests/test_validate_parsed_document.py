"""索引前解析质量校验。"""

import pytest

from app.core.document_parser import (
    MAX_INDEXABLE_DOCUMENT_CHARS,
    MAX_INDEXABLE_EXCEL_CHARS,
    ParsedDocument,
    UnsupportedDocumentError,
    validate_parsed_document_for_indexing,
)


def test_large_structured_excel_passes_validation():
    doc = ParsedDocument(
        parser_type="xls",
        text="事项" * 4_000_000,
        char_count=8_000_000,
        segments=[{"text": "row"}] * 100,  # type: ignore[list-item]
        metadata={"excel_engine": "html_table", "sheet_count": 3},
    )
    validate_parsed_document_for_indexing(doc)


def test_oversized_structured_excel_rejected():
    doc = ParsedDocument(
        parser_type="xls",
        text="x" * (MAX_INDEXABLE_EXCEL_CHARS + 1),
        char_count=MAX_INDEXABLE_EXCEL_CHARS + 1,
        segments=[],
        metadata={"excel_engine": "html_table"},
    )
    with pytest.raises(UnsupportedDocumentError, match="Excel 解析文本过长"):
        validate_parsed_document_for_indexing(doc)


def test_large_pdf_still_rejected():
    doc = ParsedDocument(
        parser_type="pdf",
        text="x" * (MAX_INDEXABLE_DOCUMENT_CHARS + 1),
        char_count=MAX_INDEXABLE_DOCUMENT_CHARS + 1,
        segments=[],
        metadata={"parser_backend": "pypdf_fallback"},
    )
    with pytest.raises(UnsupportedDocumentError, match="疑似误提取"):
        validate_parsed_document_for_indexing(doc)
