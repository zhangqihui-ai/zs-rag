from app.services.agentic_rag.nodes import generate_node, route_node


def test_route_node_skips_retrieval_without_knowledge_bases() -> None:
    result = route_node({"question": "你好", "knowledge_base_ids": [], "trace": []})
    assert result["route_decision"] == "direct"
    assert "未绑定知识库" in str(result["route_reason"])


def test_generate_node_uses_general_prompt_without_knowledge_bases() -> None:
    class _Provider:
        def chat_stream_chunks(self, *_args, **_kwargs):
            yield "你好"

    state = {
        "question": "你好",
        "knowledge_base_ids": [],
        "relevant_docs": [],
        "chat_history": [],
        "llm_provider": _Provider(),
        "llm_model_name": "test-model",
        "trace": [],
    }
    result = generate_node(state)
    assert result["answer"] == "你好"
    assert result["citations"] == []
