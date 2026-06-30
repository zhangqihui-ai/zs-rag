from __future__ import annotations

ROUTE_PROMPT = (
    "你是企业知识库问答系统的检索路由器。请判断用户问题是否需要检索已选知识库。\n"
    "输入中会提供：用户问题、已选知识库的名称/描述/文档标题范围，以及可选的预检索试探片段。\n"
    "决策规则：\n"
    "1）问候、闲聊、模型身份、通用常识，或与已选知识库名称/描述/文档主题明显无关 → direct\n"
    "2）问题需要企业制度、流程、表单、文档事实，或与已选知识库范围相关 → retrieve\n"
    "3）若提供预检索片段：score 较高且片段能支撑回答 → retrieve；0 条且问题像通用对话 → direct\n"
    "4）不确定时 confidence 设为 low，但仍需给出 decision\n"
    "仅输出 JSON："
    '{"decision":"retrieve|direct","reason":"简短原因","confidence":"high|low"}'
)

GRADE_PROMPT = (
    "你是 RAG 检索结果相关性评估器。请根据用户问题，逐条判断片段是否能帮助回答。\n"
    "评分标准：2=直接相关且含答案依据；1=部分相关或可辅助；0=不相关。\n"
    "仅输出 JSON 数组，每项格式：{\"index\":1,\"relevant\":true,\"score\":2,\"reason\":\"简短原因\"}。"
)

REWRITE_PROMPT = (
    "你是 RAG 查询改写器。当前检索结果不足，请把用户问题改写成更适合企业知识库检索的查询。\n"
    "要求：\n"
    "1）保留用户真实意图，补充关键实体、流程、材料、政策等检索词；不要编造事实\n"
    "2）若最新问题是对上一轮追问、补充或省略主语/宾语，必须结合「最近用户问题」还原完整检索意图\n"
    "3）输出应为可独立理解的完整问句，不得丢弃上一轮核心主题\n"
    "只输出改写后的查询文本。"
)

CONTEXTUALIZE_QUERY_PROMPT = (
    "根据下面的 prior 用户问题与当前最新问题，将当前问题改写为完整、可独立理解的检索查询。"
    "若当前问题已完整，可轻微润色但不得改变意图；若当前问题是补充/追问，必须合并 prior 用户问题中的核心主题。"
    "只输出改写后的查询文本，不要解释或加引号。"
)

GENERAL_DIRECT_PROMPT = (
    "你是一个企业知识助手。当前问题不需要检索知识库文档内容，请结合常识与对话目标直接、简洁地回答。"
)


def build_direct_generate_system_prompt(*, kb_context: str) -> str:
    from app.services.agentic_rag.kb_route_context import format_kb_binding_for_generate

    binding = format_kb_binding_for_generate(kb_context)
    if binding:
        return f"{GENERAL_DIRECT_PROMPT}\n\n{binding}"
    return GENERAL_DIRECT_PROMPT
