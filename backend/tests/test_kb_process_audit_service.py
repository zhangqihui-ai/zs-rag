from __future__ import annotations

from app.services.kb_process_audit_service import _action_label, _build_summary


def test_action_label_batch_parse():
    assert _action_label("parse", total_count=50) == "批量解析"


def test_action_label_force_reparse():
    assert _action_label("parse", total_count=1, force=True) == "重新解析"
    assert _action_label("reindex", total_count=3, force=True) == "批量重新解析"


def test_build_summary_delete():
    assert _build_summary(username="admin", action="delete", total_count=1) == "admin 删除了 1 个文档"


def test_build_summary_batch_upload():
    assert _build_summary(username="admin", action="upload", total_count=6) == "admin 批量上传 6 个文档"
