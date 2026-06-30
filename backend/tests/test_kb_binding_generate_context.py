from app.services.agentic_rag.kb_route_context import format_kb_binding_for_generate
from app.services.agentic_rag.nodes import generate_node
from app.services.agentic_rag.prompts import build_direct_generate_system_prompt
from app.services.chat_service import _effective_system_prompt


def test_format_kb_binding_for_generate_includes_instruction_and_context() -> None:
    kb_context = "共 2 个知识库：\n【医保知识库（图）】（图知识库）"
    text = format_kb_binding_for_generate(kb_context)
    assert "不要声称未绑定" in text
    assert "已绑定知识库" in text
    assert "医保知识库（图）" in text


def test_format_kb_binding_for_generate_empty_when_no_context() -> None:
    assert format_kb_binding_for_generate("") == ""
    assert format_kb_binding_for_generate("   ") == ""


def test_build_direct_generate_system_prompt_appends_binding() -> None:
    prompt = build_direct_generate_system_prompt(kb_context="【测试库】（向量知识库）")
    assert "不需要检索知识库文档内容" in prompt
    assert "测试库" in prompt
    assert "不要声称未绑定" in prompt


def test_effective_system_prompt_uses_bound_direct_template() -> None:
    binding = format_kb_binding_for_generate("【测试库】（向量知识库）")
    prompt = _effective_system_prompt(None, kb_binding_context="【测试库】（向量知识库）")
    assert binding in prompt
    assert "未选择知识库" not in prompt


def test_effective_system_prompt_prefers_retrieved_knowledge_block() -> None:
    prompt = _effective_system_prompt(
        None,
        knowledge_block="[1] 《文档A》\n内容",
        kb_binding_context="【测试库】（向量知识库）",
    )
    assert "[1] 《文档A》" in prompt
    assert "不要声称未绑定" not in prompt


def test_generate_node_injects_kb_binding_when_direct_with_knowledge_bases() -> None:
    captured: dict[str, object] = {}

    class _Provider:
        def chat_stream_chunks(self, _model, messages, **_kwargs):
            captured["messages"] = messages
            yield "已绑定 2 个知识库。"

    state = {
        "question": "你现在绑定了哪几个知识库？",
        "knowledge_base_ids": [1, 2],
        "kb_context": "共 2 个知识库：\n【医保知识库（图）】（图知识库）\n\n【医保知识库用pdf】（向量知识库）",
        "relevant_docs": [],
        "chat_history": [],
        "llm_provider": _Provider(),
        "llm_model_name": "test-model",
        "trace": [],
    }
    result = generate_node(state)
    assert result["answer"] == "已绑定 2 个知识库。"
    messages = captured["messages"]
    assert isinstance(messages, list)
    system_prompt = str(messages[0]["content"])
    assert "医保知识库（图）" in system_prompt
    assert "不要声称未绑定" in system_prompt
