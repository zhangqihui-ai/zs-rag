"""Tests for MinerU routing in document_parser."""

from unittest.mock import MagicMock, patch

from app.core.document_parser import ParsedDocument, parse_document
from app.core.mineru_gateway import MineruResult
from app.core.parser_config import ParserOptions


def test_docx_engine_mineru_routes_to_gateway():
    fake_result = MineruResult(
        content_list=[{"type": "text", "text": "Hello", "page_idx": 0}],
        markdown="# Hello",
        source_file_name="sample.docx",
    )
    mock_gw = MagicMock()
    mock_gw.is_enabled.return_value = True
    mock_gw.should_handle.return_value = True
    mock_gw.backend = "pipeline"
    mock_gw.lang = "ch"
    mock_gw.parse.return_value = fake_result

    opts = ParserOptions(
        pdf_engine="opendataloader",
        pdf_hybrid=False,
        docx_engine="mineru",
        excel_engine="html_table",
        csv_engine="standard",
        text_engine="native",
    )

    with patch("app.core.mineru_gateway.get_mineru_gateway", return_value=mock_gw):
        doc = parse_document(
            "sample.docx",
            b"fake-docx-bytes",
            parser_options=opts,
        )

    assert doc.parser_type == "docx"
    assert doc.metadata.get("parser_backend") == "mineru"
    assert doc.metadata.get("_parse_markdown") == "# Hello"
    assert len(doc.metadata.get("_parse_content_list") or []) == 1
    mock_gw.parse.assert_called_once()


def test_docx_engine_mineru_skips_format_whitelist():
    fake_result = MineruResult(
        content_list=[{"type": "text", "text": "Hi", "page_idx": 0}],
        markdown="# Hi",
        source_file_name="a.docx",
    )
    mock_gw = MagicMock()
    mock_gw.is_enabled.return_value = True
    mock_gw.should_handle.return_value = False
    mock_gw.backend = "pipeline"
    mock_gw.lang = "ch"
    mock_gw.parse.return_value = fake_result

    opts = ParserOptions(
        pdf_engine="opendataloader",
        pdf_hybrid=False,
        docx_engine="mineru",
        excel_engine="html_table",
        csv_engine="standard",
        text_engine="native",
    )

    with patch("app.core.mineru_gateway.get_mineru_gateway", return_value=mock_gw):
        doc = parse_document("a.docx", b"bytes", parser_options=opts)

    assert doc.metadata.get("parser_backend") == "mineru"
    mock_gw.parse.assert_called_once()
