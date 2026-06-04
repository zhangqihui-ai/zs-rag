"""parse_log 中的 embedding 进度持久化与恢复。"""

from unittest.mock import MagicMock

from app.services.knowledge_document_service import (
    _build_parse_log_payload,
    _progress_from_parse_log,
)


def test_progress_from_parse_log_uses_stored_embedding_progress():
    db = MagicMock()
    log_payload = {
        "phase": "running",
        "progress": {
            "type": "progress",
            "phase": "embedding",
            "percent": 42.5,
            "current": 500,
            "total": 1371,
            "message": "向量生成进度 500/1371",
        },
    }
    payload = _progress_from_parse_log(
        db,
        space_id=1,
        kb_id=2,
        document_id=3,
        log_payload=log_payload,
    )
    assert payload["phase"] == "embedding"
    assert payload["current"] == 500
    assert payload["total"] == 1371
    assert payload["percent"] == 42.5
    db.execute.assert_not_called()


def test_build_parse_log_payload_includes_progress():
    progress = {"phase": "embedding", "current": 8, "total": 100, "percent": 28.6, "message": "x"}
    payload = _build_parse_log_payload("parse", "running", [], progress=progress)
    assert payload["progress"] == progress


def test_compute_phase_percent_without_ratio_uses_phase_start():
    from app.services.knowledge_document_service import _compute_phase_percent

    assert _compute_phase_percent("indexing") == 70.0
    assert _compute_phase_percent("embedding") == 25.0
    assert _compute_phase_percent("done") == 100.0


def test_should_flush_embedding_progress_on_first_tick():
    from app.services.knowledge_document_service import _should_flush_embedding_progress

    state: dict[str, object] = {"last_done": -1, "last_ts": 0.0}
    assert _should_flush_embedding_progress(state, current=0, total=1371) is True
    state["last_done"] = 0
    state["last_ts"] = __import__("time").monotonic()
    assert _should_flush_embedding_progress(state, current=16, total=1371) is False


def test_infer_progress_phase_from_log_lines():
    from app.services.knowledge_document_service import _infer_progress_phase_from_log_lines

    assert _infer_progress_phase_from_log_lines([{"text": "向量生成批次 1/86 请求中（本批 16 条）…"}]) == "embedding"
    assert _infer_progress_phase_from_log_lines([{"text": "正在生成向量，文本段数 100"}]) == "embedding"
    assert _infer_progress_phase_from_log_lines([{"text": "正在写入 Milvus：100 条"}]) == "indexing"
