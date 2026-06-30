from unittest.mock import MagicMock, patch

from app.services.agentic_rag.nodes import (
    _build_rewrite_user_message,
    _contextualize_query_with_history,
    _format_chat_history_block,
    _format_user_questions_block,
    _grade_question_text,
    _resolve_query_for_retrieval,
    retrieve_node,
)
from app.services.chat_service import _clamp_agentic_context_user_turns


def _state_with_history(**overrides):
    base = {
        "question": "但是我才10岁",
        "context_user_turns": 3,
        "chat_history": [
            {"role": "user", "content": "杀人判多少年"},
            {"role": "assistant", "content": "根据刑法..."},
        ],
        "llm_provider": MagicMock(),
        "llm_model_name": "test",
    }
    base.update(overrides)
    return base


def test_format_user_questions_block_prior_user_only() -> None:
    block = _format_user_questions_block(_state_with_history())
    assert block == "- 杀人判多少年"
    assert "助手" not in block
    assert "但是我才10岁" not in block


def test_format_user_questions_block_respects_context_user_turns() -> None:
    history = [{"role": "user", "content": f"问题{i}"} for i in range(1, 6)]
    block = _format_user_questions_block(_state_with_history(chat_history=history, context_user_turns=3))
    lines = block.splitlines()
    assert len(lines) == 3
    assert lines[0] == "- 问题3"
    assert lines[-1] == "- 问题5"


def test_format_chat_history_block_includes_assistant() -> None:
    block = _format_chat_history_block(_state_with_history())
    assert "用户：杀人判多少年" in block
    assert "助手：根据刑法..." in block


def test_build_rewrite_user_message_includes_prior_user_questions() -> None:
    message = _build_rewrite_user_message(
        _state_with_history(),
        question="但是我才10岁",
        current_query="但是我才10岁",
        snippets="无",
    )
    assert "原始问题：但是我才10岁" in message
    assert "最近用户问题：" in message
    assert "杀人判多少年" in message


def test_grade_question_text_uses_current_query_and_history() -> None:
    text = _grade_question_text(
        _state_with_history(current_query="10岁未成年人杀人如何量刑"),
    )
    assert "10岁未成年人杀人如何量刑" in text
    assert "杀人判多少年" in text


@patch("app.services.agentic_rag.nodes._chat_once")
def test_contextualize_query_with_history(mock_chat_once) -> None:
    mock_chat_once.return_value = "10岁未成年人杀人如何量刑"
    result = _contextualize_query_with_history(_state_with_history())
    assert result == "10岁未成年人杀人如何量刑"
    user_content = mock_chat_once.call_args[0][1][1]["content"]
    assert "但是我才10岁" in user_content
    assert "杀人判多少年" in user_content


@patch("app.services.agentic_rag.nodes._chat_once")
def test_resolve_query_for_retrieval_uses_cache(mock_chat_once) -> None:
    state = _state_with_history(resolved_query="已补全的 query")
    assert _resolve_query_for_retrieval(state) == "已补全的 query"
    mock_chat_once.assert_not_called()


@patch("app.services.agentic_rag.nodes.search_knowledge_bases_multi")
@patch("app.services.agentic_rag.nodes._chat_once")
def test_retrieve_node_first_iteration_contextualizes_query(mock_chat_once, mock_search) -> None:
    mock_chat_once.return_value = "10岁未成年人杀人如何量刑"
    mock_search.return_value = {"results": []}
    state = _state_with_history(
        iterations=0,
        knowledge_base_ids=[1],
        enterprise_space_id=1,
        db=MagicMock(),
    )
    result = retrieve_node(state)
    retrieve_trace = next(row for row in result["trace"] if row["step"] == "retrieve")
    assert retrieve_trace["query"] == "10岁未成年人杀人如何量刑"
    assert result["current_query"] == "10岁未成年人杀人如何量刑"
    assert result["resolved_query"] == "10岁未成年人杀人如何量刑"


def test_clamp_agentic_context_user_turns() -> None:
    assert _clamp_agentic_context_user_turns(None) == 3
    assert _clamp_agentic_context_user_turns(0) == 1
    assert _clamp_agentic_context_user_turns(11) == 10
    assert _clamp_agentic_context_user_turns("5") == 5
    assert _clamp_agentic_context_user_turns("bad") == 3
