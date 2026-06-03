"""批量 Celery 入队单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

from app.models.knowledge_base import KnowledgeDocumentStatus
from app.services import knowledge_document_service as kds


def test_resolve_batch_process_mode_reindex_for_indexed():
    kb = SimpleNamespace(kb_type="vector")
    doc = SimpleNamespace(status=KnowledgeDocumentStatus.INDEXED.value)
    mode, force = kds._resolve_batch_process_mode_and_force(knowledge_base=kb, document=doc, force=False)
    assert mode == "reindex"
    assert force is False


def test_resolve_batch_process_mode_parse_for_uploaded():
    kb = SimpleNamespace(kb_type="vector")
    doc = SimpleNamespace(status=KnowledgeDocumentStatus.UPLOADED.value)
    mode, force = kds._resolve_batch_process_mode_and_force(knowledge_base=kb, document=doc, force=False)
    assert mode == "parse"
    assert force is False


def test_resolve_batch_process_stuck_in_progress_sets_force():
    kb = SimpleNamespace(kb_type="vector")
    doc = SimpleNamespace(status=KnowledgeDocumentStatus.PARSING.value)
    mode, force = kds._resolve_batch_process_mode_and_force(knowledge_base=kb, document=doc, force=False)
    assert mode == "parse"
    assert force is True
