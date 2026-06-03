"""Celery 文档解析分发单元测试。"""

from app.services import document_background_task_service as bg


def test_try_dispatch_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(bg, "celery_enabled", lambda: False)
    assert (
        bg.try_dispatch_celery_index_task(
            task_uid="abc",
            space_id=1,
            kb_id=2,
            document_id=3,
            mode="parse",
            embedding_model_id=None,
            user_id=1,
            batch_uid=None,
            force=False,
        )
        is None
    )


def test_celery_enabled_requires_redis(monkeypatch):
    monkeypatch.setattr(
        bg,
        "get_settings",
        lambda: type("S", (), {"celery_enabled": True, "redis_url": None})(),
    )
    assert bg.celery_enabled() is False
