"""仪表盘聚合与用量埋点单元测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.dashboard_service import _aggregate_document_pipeline, _aggregate_knowledge_usage, get_top_chat_conversations
from app.services.usage_metrics_service import (
    _aggregate_rows,
    _build_time_buckets,
    _coerce_shanghai,
    _metric_total,
    record_usage_event,
)


def test_build_time_buckets_7d():
    now = _coerce_shanghai(datetime(2026, 6, 10, 15, 30))
    buckets = _build_time_buckets(now, "7d")
    assert len(buckets) == 7
    assert buckets[-1][1] == "06-10"


def test_build_time_buckets_24h():
    now = _coerce_shanghai(datetime(2026, 6, 10, 15, 30))
    buckets = _build_time_buckets(now, "24h")
    assert len(buckets) == 24


def test_build_time_buckets_24h_uses_shanghai_timezone():
    # UTC 2026-06-10 16:00 == CST 2026-06-11 00:00
    now = _coerce_shanghai(datetime(2026, 6, 10, 16, 0))
    buckets = _build_time_buckets(now, "24h")
    assert buckets[-1][1] == "00:00"


def test_build_time_buckets_7d_uses_shanghai_date():
    now = _coerce_shanghai(datetime(2026, 6, 10, 16, 0))
    buckets = _build_time_buckets(now, "7d")
    assert buckets[-1][1] == "06-11"


def test_aggregate_model_calls_series():
    now = _coerce_shanghai(datetime(2026, 6, 10, 12, 0))
    buckets = _build_time_buckets(now, "24h")
    rows = [
        SimpleNamespace(event_type="llm_call", model_type="llm", tokens_in=10, tokens_out=5, created_at=datetime(2026, 6, 10, 12, 0)),
        SimpleNamespace(
            event_type="embedding_call",
            model_type="embedding",
            tokens_in=0,
            tokens_out=0,
            created_at=datetime(2026, 6, 10, 11, 0),
        ),
    ]
    series = _aggregate_rows(rows, buckets, "24h", "model_calls")
    assert len(series) == 2
    assert series[0]["key"] == "llm"
    assert sum(p["v"] for p in series[0]["points"]) == 1
    assert _metric_total(rows, "model_calls") == 2


def test_aggregate_tokens_series():
    now = _coerce_shanghai(datetime(2026, 6, 10, 12, 0))
    buckets = _build_time_buckets(now, "7d")
    rows = [
        SimpleNamespace(event_type="llm_call", tokens_in=100, tokens_out=40, created_at=datetime(2026, 6, 10, 12, 0)),
        SimpleNamespace(
            event_type="embedding_call",
            tokens_in=80,
            tokens_out=0,
            result_count=2,
            created_at=datetime(2026, 6, 10, 12, 0),
        ),
        SimpleNamespace(event_type="chat_api", tokens_in=0, tokens_out=0, created_at=datetime(2026, 6, 10, 12, 0)),
    ]
    series = _aggregate_rows(rows, buckets, "7d", "tokens")
    assert len(series) == 2
    assert series[0]["key"] == "llm"
    assert series[1]["key"] == "embedding"
    assert sum(p["v"] for p in series[0]["points"]) == 140
    assert sum(p["v"] for p in series[1]["points"]) == 80
    assert _metric_total(rows, "tokens") == 220


def test_record_usage_event_swallows_errors():
    db_instance = MagicMock()
    db_instance.commit.side_effect = RuntimeError("db down")
    session_factory = MagicMock(return_value=db_instance)

    import app.services.usage_metrics_service as svc

    original = None
    from app.db import session as session_mod

    session_mod.SessionLocal = session_factory
    try:
        record_usage_event(enterprise_space_id=1, event_type="llm_call")
    finally:
        pass

    db_instance.add.assert_called_once()
    db_instance.rollback.assert_called_once()
    db_instance.close.assert_called_once()


def test_aggregate_knowledge_usage_from_db_rows():
    db = MagicMock()
    call_idx = {"n": 0}

    def execute_side_effect(_stmt):
        call_idx["n"] += 1
        result = MagicMock()
        if call_idx["n"] == 1:
            result.scalars.return_value.all.return_value = [[1, 2], [1]]
        elif call_idx["n"] == 2:
            result.scalars.return_value.all.return_value = [
                [{"knowledge_base_id": 1}, {"knowledge_base_id": 1}],
            ]
        elif call_idx["n"] == 3:
            result.all.return_value = [(1, "Alpha"), (2, "Beta")]
        elif call_idx["n"] == 4:
            result.all.return_value = [("pdf", 3), ("docx", 1)]
        else:
            result.all.return_value = []
        return result

    db.execute.side_effect = execute_side_effect
    payload = _aggregate_knowledge_usage(db, space_id=10)

    assert payload["top_knowledge_bases"][0]["kb_name"] == "Alpha"
    assert payload["top_knowledge_bases"][0]["recall_count"] == 2
    assert payload["top_knowledge_bases"][0]["conversation_bind_count"] == 2
    ext = {item["file_ext"]: item["count"] for item in payload["file_ext_distribution"]}
    assert ext["pdf"] == 3


def test_get_top_chat_conversations_merges_counts():
    db = MagicMock()
    call_idx = {"n": 0}

    def execute_side_effect(_stmt):
        call_idx["n"] += 1
        result = MagicMock()
        if call_idx["n"] == 1:
            result.all.return_value = [("conv-a", 3), ("conv-b", 1)]
        elif call_idx["n"] == 2:
            result.all.return_value = [("conv-a", 12), ("conv-c", 5)]
        elif call_idx["n"] == 3:
            result.all.return_value = [
                ("conv-a", "助手 A"),
                ("conv-b", "助手 B"),
                ("conv-c", "助手 C"),
            ]
        else:
            result.all.return_value = []
        return result

    db.execute.side_effect = execute_side_effect
    items = get_top_chat_conversations(db, space_id=1, range_key="24h", limit=3)

    assert len(items) == 3
    assert items[0]["conversation_id"] == "conv-a"
    assert items[0]["session_count"] == 3
    assert items[0]["message_count"] == 12


def test_aggregate_document_pipeline_counts():
    db = MagicMock()
    values = iter([2, 5, 1])

    def scalar_one():
        return next(values)

    db.execute.return_value.scalar_one = scalar_one
    payload = _aggregate_document_pipeline(db, space_id=1)
    assert payload == {"parsing": 2, "indexed": 5, "failed": 1}
