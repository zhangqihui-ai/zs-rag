from __future__ import annotations

from app.services.kb_process_audit_service import _infer_item_outcome_from_document


class _Doc:
    def __init__(self, status: str, error_message: str | None = None) -> None:
        self.status = status
        self.error_message = error_message


def test_infer_outcome_indexed():
    assert _infer_item_outcome_from_document(_Doc("indexed")) == "success"
    assert _infer_item_outcome_from_document(_Doc("graph_indexed")) == "success"


def test_infer_outcome_failed():
    assert _infer_item_outcome_from_document(_Doc("failed", "err")) == "failed"


def test_infer_outcome_still_processing():
    assert _infer_item_outcome_from_document(_Doc("parsing")) is None
