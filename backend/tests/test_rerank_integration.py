"""Rerank 配置解析与结果重排单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.rerank_gateway import RerankScore, rerank_texts
from app.models.knowledge_base import KnowledgeBase
from app.services.retrieval_service import (
    _apply_rerank_to_results,
    _resolve_rerank_config,
)


def test_resolve_rerank_config_hybrid_strategy():
    kb = KnowledgeBase(
        id=1,
        enterprise_space_id=1,
        name="kb",
        config={"retrieval": {"hybrid_strategy": "rerank", "rerank_model_id": 9}},
    )
    enabled, model_id = _resolve_rerank_config(kb, "hybrid")
    assert enabled is True
    assert model_id == 9


def test_resolve_rerank_config_vector_enabled():
    kb = KnowledgeBase(
        id=1,
        enterprise_space_id=1,
        name="kb",
        config={"retrieval": {"rerank_enabled": True, "rerank_model_id": 3}},
    )
    enabled, model_id = _resolve_rerank_config(kb, "vector")
    assert enabled is True
    assert model_id == 3


def test_resolve_rerank_config_hybrid_weight_disabled():
    kb = KnowledgeBase(
        id=1,
        enterprise_space_id=1,
        name="kb",
        config={"retrieval": {"hybrid_strategy": "weight", "rerank_model_id": 3}},
    )
    enabled, model_id = _resolve_rerank_config(kb, "hybrid")
    assert enabled is False
    assert model_id is None


@patch("app.services.retrieval_service.rerank_texts")
@patch("app.services.retrieval_service.get_rerank_model_for_knowledge_base")
def test_apply_rerank_to_results_reorders(mock_get_model, mock_rerank):
    mock_get_model.return_value = MagicMock()
    mock_rerank.return_value = [
        RerankScore(index=1, score=0.9),
        RerankScore(index=0, score=0.1),
    ]
    kb = KnowledgeBase(id=1, enterprise_space_id=1, name="kb")
    rows = [
        {"content": "a", "score": 0.2},
        {"content": "b", "score": 0.8},
    ]
    out = _apply_rerank_to_results(
        MagicMock(),
        knowledge_base=kb,
        query="q",
        results=rows,
        rerank_model_id=1,
        top_n=2,
    )
    assert out[0]["content"] == "b"
    assert out[0]["score"] == 0.9


@patch("app.core.rerank_gateway.rerank_documents")
def test_rerank_texts_parses_scores(mock_rerank_documents):
    model = MagicMock()
    model.model_type = "rerank"
    model.is_enabled = True
    model.provider = MagicMock()
    model.model_name = "gte-rerank"
    mock_rerank_documents.return_value = MagicMock(
        success=True,
        data=[{"index": 0, "score": 0.77}],
    )
    scores = rerank_texts(model, query="hello", documents=["doc one"], top_n=1)
    assert len(scores) == 1
    assert scores[0].index == 0
    assert scores[0].score == pytest.approx(0.77)
