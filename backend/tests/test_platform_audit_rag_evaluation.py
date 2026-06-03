"""平台审计、限流、空间配额与 RAG 配置单元测试。"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.embed_quota import check_embed_daily_quota
from app.core.rate_limit import check_rate_limit
from app.core.space_quota import assert_space_upload_quota
from app.models.knowledge_base import KnowledgeBase
from app.services.platform_audit_service import record_platform_audit
from app.services.retrieval_service import _resolve_rerank_config


def test_resolve_rerank_vector_mode():
    kb = KnowledgeBase(
        id=1,
        enterprise_space_id=1,
        name="kb",
        config={"retrieval": {"rerank_enabled": True, "rerank_model_id": 2}},
    )
    enabled, model_id = _resolve_rerank_config(kb, "vector")
    assert enabled is True
    assert model_id == 2


def test_rate_limit_blocks_burst():
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"X-Enterprise-Space": "default", "Authorization": ""}
    scope = "test_scope_unique"
    for _ in range(3):
        check_rate_limit(request, scope=scope, limit_per_minute=3)
    with pytest.raises(HTTPException) as exc:
        check_rate_limit(request, scope=scope, limit_per_minute=3)
    assert exc.value.status_code == 429


def test_record_platform_audit_model_fields():
    db = MagicMock()
    row = record_platform_audit(
        db,
        action="auth.login",
        resource_type="user",
        resource_id=1,
        user_id=1,
    )
    assert row.action == "auth.login"
    assert row.resource_type == "user"
    db.add.assert_called_once()


def test_embed_daily_quota_blocks(monkeypatch):
    from app.core import embed_quota as eq

    monkeypatch.setattr(eq, "get_settings", lambda: MagicMock(embed_api_key_daily_quota=2))
    request = MagicMock()
    request.headers = {"Authorization": "Bearer zs_rag_embed_abc123"}
    check_embed_daily_quota(request)
    check_embed_daily_quota(request)
    with pytest.raises(HTTPException) as exc:
        check_embed_daily_quota(request)
    assert exc.value.status_code == 429


def test_list_platform_audit_events_filters_and_total():
    from app.services.platform_audit_service import list_platform_audit_events

    event = MagicMock()
    event.id = 1
    event.enterprise_space_id = 10
    event.user_id = 2
    event.action = "auth.login"
    event.resource_type = "user"
    event.resource_id = "2"
    event.request_id = None
    event.ip_address = "127.0.0.1"
    event.detail = None
    event.message = "login"
    event.created_at = MagicMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [(event, "alice", "Default Space")]

    db = MagicMock()
    db.execute.side_effect = [count_result, rows_result]

    items, total = list_platform_audit_events(
        db,
        enterprise_space_id=10,
        user_id=2,
        skip=0,
        limit=20,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].username == "alice"
    assert items[0].space_name == "Default Space"
    assert items[0].action == "auth.login"


def test_space_document_quota(monkeypatch):
    from app.core.errors import AppError
    from app.core import space_quota as sq

    monkeypatch.setattr(
        sq,
        "get_settings",
        lambda: MagicMock(space_max_documents=1, space_max_storage_bytes=0),
    )
    db = MagicMock()
    db.execute.return_value.one.return_value = (1, 0)
    with pytest.raises(AppError) as exc:
        assert_space_upload_quota(db, space_id=1, additional_bytes=100, is_new_document=True)
    assert exc.value.code == "SPACE_DOCUMENT_QUOTA_EXCEEDED"
