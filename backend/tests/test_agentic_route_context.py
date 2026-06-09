from unittest.mock import MagicMock, patch

from app.services.agentic_rag.kb_route_context import build_kb_route_context
from app.services.agentic_rag.nodes import (
    _merge_candidates_by_chunk_id,
    _parse_route_response,
    route_node,
)


def test_build_kb_route_context_empty_ids() -> None:
    assert build_kb_route_context(MagicMock(), enterprise_space_id=1, knowledge_base_ids=[]) == ""


def test_parse_route_response_defaults() -> None:
    decision, reason, confidence = _parse_route_response("")
    assert decision == "retrieve"
    assert reason == "默认进入知识库检索"
    assert confidence == "high"


def test_parse_route_response_direct_low_confidence() -> None:
    raw = '{"decision":"direct","reason":"通用常识","confidence":"low"}'
    decision, reason, confidence = _parse_route_response(raw)
    assert decision == "direct"
    assert reason == "通用常识"
    assert confidence == "low"


def test_merge_candidates_dedupes_by_chunk_id() -> None:
    pre = [{"chunk_id": 1, "document_name": "A", "content": "alpha", "score": 0.9}]
    main = [
        {"chunk_id": 1, "document_name": "A", "content": "alpha", "score": 0.8},
        {"chunk_id": 2, "document_name": "B", "content": "beta", "score": 0.7},
    ]
    merged = _merge_candidates_by_chunk_id(main, pre)
    assert len(merged) == 2
    assert merged[0]["chunk_id"] == 1
    assert merged[0]["score"] == 0.9
    assert merged[1]["chunk_id"] == 2


@patch("app.services.agentic_rag.nodes._run_pre_retrieve")
@patch("app.services.agentic_rag.nodes._call_route_llm")
def test_route_node_pre_retrieve_on_retrieve_decision(mock_route_llm, mock_pre_retrieve) -> None:
    mock_route_llm.side_effect = [
        ("retrieve", "可能需要制度文档", "high"),
        ("direct", "预检索无相关片段", "high"),
    ]
    mock_pre_retrieve.return_value = []

    result = route_node(
        {
            "question": "报销流程是什么？",
            "knowledge_base_ids": [1],
            "kb_context": "【财务制度】描述：报销规范",
            "route_pre_retrieve_enabled": True,
            "trace": [],
            "llm_provider": MagicMock(),
            "llm_model_name": "test",
        }
    )

    assert result["route_decision"] == "direct"
    assert result["route_reason"] == "预检索无相关片段"
    assert mock_pre_retrieve.called
    steps = [row["step"] for row in result["trace"]]
    assert steps == ["route", "route_refine"]


@patch("app.services.agentic_rag.nodes._call_route_llm")
def test_route_node_direct_skips_pre_retrieve(mock_route_llm) -> None:
    mock_route_llm.return_value = ("direct", "询问模型能力，无需知识库检索", "high")

    result = route_node(
        {
            "question": "你是什么模型？",
            "knowledge_base_ids": [1],
            "kb_context": "【刑法】描述：法律条文",
            "route_pre_retrieve_enabled": True,
            "trace": [],
            "llm_provider": MagicMock(),
            "llm_model_name": "test",
        }
    )

    assert result["route_decision"] == "direct"
    assert len(result["trace"]) == 1
    assert result["trace"][0]["step"] == "route"
