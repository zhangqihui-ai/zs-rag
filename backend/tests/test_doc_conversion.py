"""Tests for legacy .doc → .docx conversion and parse routing."""

from unittest.mock import patch

import pytest

from app.core.doc_conversion import (
    convert_doc_to_docx_bytes,
    detect_doc_container,
    libreoffice_available,
)
from app.core.document_parser import ParsedDocument, UnsupportedDocumentError, parse_document
from app.core.parser_config import ParserOptions


def test_detect_doc_container():
    assert detect_doc_container(b"") == "empty"
    assert detect_doc_container(b"PK\x03\x04") == "docx_zip"
    assert detect_doc_container(bytes.fromhex("d0cf11e0a1b11ae1") + b"x") == "ole"
    assert detect_doc_container(b"{\\rtf1\\ansi") == "rtf"
    assert detect_doc_container(b"<html><body>x</body></html>") == "html"


def test_convert_docx_zip_bypasses_libreoffice():
    fake_docx = b"PK\x03\x04fake-docx"
    with patch("app.core.doc_conversion._find_soffice_binary", return_value="/usr/bin/soffice"):
        out = convert_doc_to_docx_bytes(fake_docx, source_name="sample.doc")
    assert out == fake_docx


def test_convert_doc_lo_load_error_includes_detail():
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "Error: source file could not be loaded\n"
            stderr = "Warning: failed to launch javaldx\n"

        return Result()

    with patch("app.core.doc_conversion._find_soffice_binary", return_value="/usr/bin/soffice"), patch(
        "app.core.doc_conversion.subprocess.run",
        side_effect=fake_run,
    ):
        with pytest.raises(UnsupportedDocumentError, match="source file could not be loaded"):
            convert_doc_to_docx_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"x" * 64, source_name="broken.doc")


def test_libreoffice_missing_raises():
    with patch("app.core.doc_conversion._find_soffice_binary", return_value=None):
        with pytest.raises(UnsupportedDocumentError, match="LibreOffice"):
            convert_doc_to_docx_bytes(b"fake-doc-bytes", source_name="sample.doc")


def test_convert_doc_success_reads_docx_output():
    fake_docx = b"PK\x03\x04fake-docx"

    def fake_run(cmd, **kwargs):
        from pathlib import Path

        outdir = Path(cmd[cmd.index("--outdir") + 1])
        (outdir / "source.docx").write_bytes(fake_docx)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    with patch("app.core.doc_conversion._find_soffice_binary", return_value="/usr/bin/soffice"), patch(
        "app.core.doc_conversion.subprocess.run",
        side_effect=fake_run,
    ):
        out = convert_doc_to_docx_bytes(b"legacy-doc", source_name="sample.doc")

    assert out == fake_docx


def test_parse_document_doc_converts_then_uses_docx_parser():
    parsed = ParsedDocument(
        parser_type="docx",
        text="hello",
        char_count=5,
        segments=[],
        metadata={},
    )
    opts = ParserOptions(
        pdf_engine="opendataloader",
        pdf_hybrid=False,
        docx_engine="python-docx",
        excel_engine="html_table",
        csv_engine="standard",
        text_engine="native",
    )

    with patch("app.core.doc_conversion.convert_doc_to_docx_bytes", return_value=b"converted-docx") as convert_mock, patch(
        "app.core.document_parser._parse_docx",
        return_value=parsed,
    ) as parse_mock:
        doc = parse_document("legacy.doc", b"legacy-bytes", parser_options=opts, log=None)

    convert_mock.assert_called_once()
    parse_mock.assert_called_once_with(b"converted-docx")
    assert doc.parser_type == "doc"
    assert doc.metadata.get("source_format") == "doc"
    assert doc.metadata.get("converted_via") == "libreoffice"
    assert doc.metadata.get("parser_backend") == "python-docx"


@pytest.mark.skipif(not libreoffice_available(), reason="LibreOffice not installed")
def test_convert_doc_integration_minimal():
    """Optional integration test when soffice is present in the environment."""
    assert libreoffice_available()


@pytest.mark.skipif(not libreoffice_available(), reason="LibreOffice not installed")
def test_parse_word_html_doc_integration():
    """Regression: Word 网页导出 .doc（实为 HTML）应能解析出正文标题。"""
    from pathlib import Path

    sample = Path(__file__).resolve().parents[2] / "道路运输车辆燃料消耗量检测和监督管理办法.doc"
    if not sample.is_file():
        pytest.skip("sample .doc not present in repo root")

    opts = ParserOptions(
        pdf_engine="opendataloader",
        pdf_hybrid=False,
        docx_engine="python-docx",
        excel_engine="html_table",
        csv_engine="standard",
        text_engine="native",
    )
    doc = parse_document(sample.name, sample.read_bytes(), parser_options=opts, log=None)
    assert "道路运输车辆燃料消耗量检测和监督管理办法" in doc.text
    assert doc.char_count > 1000
    assert doc.metadata.get("source_format") == "doc"
