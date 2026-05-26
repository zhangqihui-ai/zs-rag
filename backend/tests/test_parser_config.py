"""Tests for parser_config resolution."""

from app.core.parser_config import DEFAULT_PARSERS, resolve_enrichment, resolve_parsers


def test_resolve_parsers_defaults():
    opts = resolve_parsers(None)
    assert opts.pdf_engine in {"opendataloader", "mineru", "pypdf"}
    assert opts.excel_engine == "html_table"
    assert opts.docx_engine == "python-docx"


def test_resolve_parsers_legacy_pdf():
    opts = resolve_parsers({"pdf_parser": "mineru"})
    assert opts.pdf_engine == "mineru"


def test_resolve_parsers_structured():
    opts = resolve_parsers(
        {
            "parsers": {
                "pdf": {"engine": "mineru", "hybrid": False},
                "excel": {"engine": "tsv"},
            }
        }
    )
    assert opts.pdf_engine == "mineru"
    assert opts.excel_engine == "tsv"


def test_resolve_enrichment_default_off():
    opts = resolve_enrichment(None)
    assert opts.enabled is False
    assert opts.max_questions == 3
