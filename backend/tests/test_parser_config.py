"""Tests for parser_config resolution."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import AppError
from app.core.parser_config import DEFAULT_PARSERS, resolve_enrichment, resolve_parsers, validate_parsers_patch


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


def test_resolve_parsers_mineru_office_engines():
    opts = resolve_parsers(
        {
            "parsers": {
                "docx": {"engine": "mineru"},
                "excel": {"engine": "mineru"},
                "csv": {"engine": "mineru"},
                "text": {"engine": "mineru"},
            }
        }
    )
    assert opts.docx_engine == "mineru"
    assert opts.excel_engine == "mineru"
    assert opts.csv_engine == "mineru"
    assert opts.text_engine == "mineru"


def test_validate_parsers_patch_rejects_mineru_when_disabled():
    mock_settings = MagicMock()
    mock_settings.mineru_enabled = False
    with patch("app.core.config.get_settings", return_value=mock_settings):
        with pytest.raises(AppError) as exc_info:
            validate_parsers_patch({"docx": {"engine": "mineru"}})
    assert exc_info.value.code == "MINERU_NOT_ENABLED"


def test_validate_parsers_patch_allows_mineru_when_enabled():
    mock_settings = MagicMock()
    mock_settings.mineru_enabled = True
    with patch("app.core.config.get_settings", return_value=mock_settings):
        validate_parsers_patch({"docx": {"engine": "mineru"}, "excel": {"engine": "mineru"}})


def test_resolve_enrichment_default_off():
    opts = resolve_enrichment(None)
    assert opts.enabled is False
    assert opts.max_questions == 3
