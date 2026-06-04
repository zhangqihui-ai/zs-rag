from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.models.knowledge_base import (
    KbProcessBatch,
    KbProcessBatchItem,
    KbProcessBatchItemStatus,
    KbProcessBatchStatus,
)
from app.services.kb_process_audit_service import (
    _action_label,
    _batch_duration_seconds,
    _build_summary,
    _maybe_record_platform_audit,
    format_duration_label,
)


def test_action_label_batch_parse():
    assert _action_label("parse", total_count=50) == "批量解析"


def test_action_label_force_reparse():
    assert _action_label("parse", total_count=1, force=True) == "重新解析"
    assert _action_label("reindex", total_count=3, force=True) == "批量重新解析"


def test_build_summary_delete():
    assert _build_summary(username="admin", action="delete", total_count=1) == "admin 删除了 1 个文档"


def test_build_summary_batch_upload():
    assert _build_summary(username="admin", action="upload", total_count=6) == "admin 批量上传 6 个文档"


def test_format_duration_label():
    assert format_duration_label(None) == "—"
    assert format_duration_label(None, running=True) == "进行中"
    assert format_duration_label(0.4) == "不足 1 秒"
    assert format_duration_label(65) == "1 分 5 秒"
    assert format_duration_label(3661) == "1 小时 1 分 1 秒"


def test_batch_duration_seconds_completed():
    batch = KbProcessBatch(
        batch_uid="u1",
        enterprise_space_id=1,
        knowledge_base_id=1,
        action="parse",
        status=KbProcessBatchStatus.SUCCESS.value,
        started_at=datetime(2026, 6, 3, 9, 0, 0),
        finished_at=datetime(2026, 6, 3, 9, 2, 30),
    )
    assert _batch_duration_seconds(batch) == 150.0


def test_batch_duration_seconds_prefers_item_timestamps():
    batch = KbProcessBatch(
        batch_uid="u1",
        enterprise_space_id=1,
        knowledge_base_id=1,
        action="parse",
        status=KbProcessBatchStatus.SUCCESS.value,
        started_at=datetime(2026, 6, 3, 9, 0, 0),
        finished_at=datetime(2026, 6, 3, 9, 0, 1),
    )
    items = [
        KbProcessBatchItem(
            batch_id=1,
            document_id=10,
            file_name="a.pdf",
            status=KbProcessBatchItemStatus.SUCCESS.value,
            started_at=datetime(2026, 6, 3, 9, 0, 0),
            finished_at=datetime(2026, 6, 3, 9, 1, 5),
        ),
    ]
    assert _batch_duration_seconds(batch, items) == 65.0


def test_batch_duration_seconds_ignores_item_timestamps_when_batch_running():
    batch = KbProcessBatch(
        batch_uid="u1",
        enterprise_space_id=1,
        knowledge_base_id=1,
        action="parse",
        status=KbProcessBatchStatus.RUNNING.value,
        started_at=datetime(2026, 6, 3, 9, 0, 0),
        finished_at=None,
    )
    items = [
        KbProcessBatchItem(
            batch_id=1,
            document_id=10,
            file_name="a.pdf",
            status=KbProcessBatchItemStatus.RUNNING.value,
            started_at=datetime(2026, 6, 3, 9, 0, 0),
            finished_at=None,
        ),
    ]
    with patch("app.services.kb_process_audit_service._utcnow", return_value=datetime(2026, 6, 3, 9, 2, 0)):
        assert _batch_duration_seconds(batch, items) == 120.0


def test_maybe_record_platform_audit_once():
    batch = KbProcessBatch(
        id=10,
        batch_uid="u1",
        enterprise_space_id=1,
        knowledge_base_id=2,
        user_id=3,
        action="parse",
        status=KbProcessBatchStatus.SUCCESS.value,
        total_count=15,
        success_count=15,
        failed_count=0,
        started_at=datetime(2026, 6, 3, 9, 0, 0),
        finished_at=datetime(2026, 6, 3, 9, 1, 0),
        summary="admin 批量解析 15 个文档",
        metadata_json={"username": "admin", "force": False},
    )
    db = MagicMock()
    db.get.return_value = MagicMock(username="admin")

    with patch("app.services.kb_process_audit_service.record_platform_audit") as record:
        _maybe_record_platform_audit(db, batch)
        assert record.call_count == 1
        assert record.call_args.kwargs["action"] == "knowledge_document.batch.parse"
        assert record.call_args.kwargs["resource_type"] == "knowledge_document"
        assert "耗时" in record.call_args.kwargs["message"]
        assert batch.metadata_json["platform_audit_recorded"] is True

        _maybe_record_platform_audit(db, batch)
        assert record.call_count == 1
