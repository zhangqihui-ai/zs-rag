from datetime import datetime
from unittest.mock import MagicMock

from app.services.knowledge_document_service import _document_last_parsed_at


def test_last_parsed_at_from_success_parse_log():
    doc = MagicMock()
    doc.status = "indexed"
    doc.parse_log_json = {
        "phase": "success",
        "updated_at": "2026-05-27T04:30:00Z",
    }
    doc.updated_at = datetime(2026, 5, 27, 4, 27, 40)

    assert _document_last_parsed_at(doc) == datetime(2026, 5, 27, 4, 30, 0)


def test_last_parsed_at_none_for_uploaded():
    doc = MagicMock()
    doc.status = "uploaded"
    doc.parse_log_json = None
    doc.updated_at = datetime(2026, 5, 27, 4, 27, 40)

    assert _document_last_parsed_at(doc) is None
