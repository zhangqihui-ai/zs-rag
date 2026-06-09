from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument
from app.services.lightrag_engine import (
    _lightrag_doc_status_path,
    purge_lightrag_document_local_state,
    wait_lightrag_kb_lock_released,
)


def _make_kb_doc(tmp_path: Path, *, kb_id: int = 18, doc_id: int = 2731) -> tuple[KnowledgeBase, KnowledgeDocument]:
    kb = KnowledgeBase(
        id=kb_id,
        enterprise_space_id=1,
        name="graph-kb",
        kb_type="lightrag",
        config={},
    )
    doc = KnowledgeDocument(
        id=doc_id,
        knowledge_base_id=kb_id,
        file_name="demo.xls",
        status="graph_indexing",
    )
    return kb, doc


def test_purge_lightrag_document_local_state_removes_doc_status(tmp_path: Path, monkeypatch) -> None:
    kb, doc = _make_kb_doc(tmp_path)
    storage_root = tmp_path / "lightrag"
    workspace = "space_1_kb_18"
    status_dir = storage_root / workspace
    status_dir.mkdir(parents=True)
    status_path = status_dir / "kv_store_doc_status.json"
    status_path.write_text(
        json.dumps(
            {
                "doc-2731": {
                    "status": "processing",
                    "chunks_count": 2,
                    "chunks_list": ["chunk-a", "chunk-b"],
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.lightrag_engine._working_dir_for",
        lambda _kb: storage_root,
    )
    monkeypatch.setattr(
        "app.services.lightrag_engine.build_lightrag_workspace",
        lambda _space_id, _kb_id: workspace,
    )

    purge_lightrag_document_local_state(kb, doc)

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert "doc-2731" not in payload


def test_wait_lightrag_kb_lock_released_without_redis() -> None:
    with patch("app.services.lightrag_engine.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = ""
        assert wait_lightrag_kb_lock_released(99, timeout_sec=0.1) is True


def test_delete_lightrag_in_progress_skips_adelete(monkeypatch) -> None:
    from app.models.knowledge_base import KnowledgeDocument
    from app.services import knowledge_document_service as kds

    kb = KnowledgeBase(id=18, enterprise_space_id=1, name="g", kb_type="lightrag", config={})
    doc = KnowledgeDocument(
        id=99,
        knowledge_base_id=18,
        file_name="a.xls",
        status="graph_indexing",
    )
    calls: list[str] = []

    monkeypatch.setattr(
        kds,
        "_prepare_lightrag_document_for_delete",
        lambda *args, **kwargs: calls.append("prepare"),
    )
    monkeypatch.setattr(
        "app.services.lightrag_engine.purge_lightrag_document_local_state",
        lambda *_args, **_kwargs: calls.append("purge"),
    )
    monkeypatch.setattr(
        "app.services.lightrag_engine.delete_document",
        lambda *_args, **_kwargs: calls.append("adelete") or (_ for _ in ()).throw(AssertionError("should not call")),
    )

    kds._delete_lightrag_graph_document(
        None,  # type: ignore[arg-type]
        space_id=1,
        knowledge_base=kb,
        document=doc,
    )
    assert calls == ["prepare", "purge"]


def test_lightrag_doc_status_path_layout(tmp_path: Path, monkeypatch) -> None:
    kb, _doc = _make_kb_doc(tmp_path)
    storage_root = tmp_path / "storage"
    monkeypatch.setattr("app.services.lightrag_engine._working_dir_for", lambda _kb: storage_root)
    path = _lightrag_doc_status_path(kb)
    assert path.name == "kv_store_doc_status.json"
    assert "space_1_kb_18" in str(path)
