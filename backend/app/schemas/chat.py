from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.knowledge_retrieval_defaults import (
    DEFAULT_LIGHTRAG_RETRIEVAL_TOP_K,
    DEFAULT_MERGE_TOP_K,
    DEFAULT_TOP_K,
    DEFAULT_VECTOR_RETRIEVAL_TOP_K,
)

DEFAULT_OPENING_GREETING = "你好，我是你的智能助手，有什么需要帮助的吗？"


class ChatStreamRequest(BaseModel):
    content: str = Field(..., min_length=1, description="用户本轮输入（纯文本）")


class OpenAICompatMessage(BaseModel):
    """与 OpenAI Chat Completions messages 项对齐；content 可为字符串或多模态数组。"""

    model_config = ConfigDict(extra="ignore")

    role: str
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None


class ChatCompletionsRequest(BaseModel):
    """
    OpenAI Chat Completions 请求体（并扩展本系统字段）。

    - 标准字段：model、messages、stream、temperature、max_tokens、top_p 等
    - 扩展：chat_id（也可放在 URL 路径）、session_id（或 extra_body.session_id）、question（兼容旧客户端）
    - extra_body：与 OpenAI Python SDK 一致，可携带 session_id 等扩展
    """

    model_config = ConfigDict(extra="ignore")

    chat_id: str | None = Field(default=None, description="对话 ID；路径型接口可省略")
    session_id: str | None = Field(default=None, description="会话 ID；省略时在仅 chat_id 时自动建会话")
    model: str | None = Field(default=None, description="请求中的模型名（回显用；实际推理以对话配置为准）")
    messages: list[OpenAICompatMessage] | None = None
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    question: str | None = Field(default=None, description="兼容字段：无 messages 时与历史合并")
    extra_body: dict[str, Any] | None = Field(
        default=None,
        description="扩展参数（如 session_id、reference 等），与 OpenAI SDK extra_body 一致",
    )

    @model_validator(mode="after")
    def need_messages_or_question(self) -> Self:
        has_m_raw = bool(self.messages and len(self.messages) > 0)
        has_q = bool(self.question and str(self.question).strip())
        if not has_m_raw and not has_q:
            raise ValueError("messages is required (at least one message) or provide question")
        return self


class ChatMessageBase(BaseModel):
    role: str = Field(..., description="system, user, assistant")
    content: str


class ChatMessageResponse(ChatMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    created_at: datetime
    citations: list[dict[str, Any]] | None = None
    agent_trace: list[dict[str, Any]] | None = None


class ChatConfigurationBase(BaseModel):
    model_provider: str | None = None
    model_name: str | None = None
    model_id: int | None = None
    knowledge_base_ids: list[int] = Field(default_factory=list)
    show_citations: bool = Field(
        default=True,
        description="是否在问答中展示引文角标与来源列表（知识库检索开启时生效）。",
    )
    retrieval_top_k: int = Field(
        default=DEFAULT_MERGE_TOP_K,
        ge=1,
        le=50,
        description="多路检索合并排序、去重后写入上下文的上限（合并最终 Top K）。",
    )
    vector_retrieval_top_k: int = Field(
        default=DEFAULT_VECTOR_RETRIEVAL_TOP_K,
        ge=1,
        le=50,
        description="经典/向量知识库单路召回 Top K。",
    )
    lightrag_retrieval_top_k: int = Field(
        default=DEFAULT_LIGHTRAG_RETRIEVAL_TOP_K,
        ge=1,
        le=50,
        description="图知识库 LightRAG top_k（实体/关系/片段预算）。",
    )
    lightrag_query_mode: str = Field(
        default="mix",
        description="图知识库 LightRAG 检索模式：naive/local/global/hybrid/mix",
    )
    lightrag_chunk_top_k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="图知识库召回的文档片段数（chunk_top_k）；为空时沿用 LightRAG 默认（20）。",
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2000, ge=1)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    temperature_enabled: bool = Field(
        default=False,
        description="为 true 时向模型传入 temperature；为 false 时使用模型/厂商默认。",
    )
    max_tokens_enabled: bool = Field(
        default=False,
        description="为 true 时向模型传入 max_tokens；为 false 时使用模型/厂商默认。",
    )
    top_p_enabled: bool = Field(
        default=False,
        description="为 true 时向模型传入 top_p；为 false 时使用模型/厂商默认。",
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=100_000,
        description="系统提示词；可用 {knowledge} 占位。为空时使用服务端默认模板。",
    )
    max_history_messages: int = Field(
        default=20,
        ge=0,
        le=100,
        description="发给大模型的最近消息条数；0 表示单轮、不使用历史。",
    )
    max_history_tokens: int | None = Field(
        default=None,
        ge=1,
        le=128_000,
        description="可选：历史消息 token 上限（字符估算）；与 max_history_messages 取更严限制。",
    )
    refine_multiturn: bool = Field(
        default=False,
        description="多轮 query 改写：结合历史将省略问句补全后再检索知识库。",
    )
    opening_greeting: str | None = Field(
        default=DEFAULT_OPENING_GREETING,
        max_length=10_000,
        description="新建会话时的开场白（以助手消息写入）。",
    )
    empty_response: str | None = Field(
        default=None,
        max_length=10_000,
        description="已选知识库但检索无命中时的固定回复；为空则仍走大模型。",
    )
    suggest_next_questions_enabled: bool = Field(
        default=True,
        description="是否在助手回复后生成下一步问题建议。",
    )
    suggest_next_questions_model_id: int | None = Field(
        default=None,
        description="生成建议所用模型；为空则使用对话主模型。",
    )
    suggest_next_questions_prompt_mode: str = Field(
        default="system",
        description="提示词模式：system（内置）或 custom（自定义）。",
    )
    suggest_next_questions_custom_prompt: str | None = Field(
        default=None,
        max_length=10_000,
        description="自定义下一步问题生成提示词；prompt_mode=custom 时生效。",
    )
    rag_mode: Literal["classic", "agentic"] = Field(
        default="classic",
        description="检索模式：classic=单次 RAG；agentic=智能体多轮检索（创建后不可修改）。",
    )
    agentic_max_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Agentic 模式最大检索/改写轮数。",
    )
    agentic_min_relevant_docs: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Agentic 模式判定检索足够的最少相关片段数。",
    )
    agentic_context_user_turns: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Agentic 检索/改写时纳入的 prior 用户问题条数。",
    )


class ChatConfigurationUpdate(ChatConfigurationBase):
    rag_mode: Literal["classic", "agentic"] | None = Field(default=None, exclude=True)


class ChatConfigurationResponse(ChatConfigurationBase):
    """与对话（chat）行一一对应。"""

    id: str
    chat_id: str


class ChatSessionCreate(BaseModel):
    title: str = Field("新会话", max_length=255)


class ChatSessionUpdate(BaseModel):
    title: str = Field(..., max_length=255)


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    chat_id: str = Field(validation_alias="conversation_id")
    user_id: int
    enterprise_space_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatConversationCreate(BaseModel):
    title: str = Field("新建对话", max_length=255)
    configuration: ChatConfigurationBase | None = None


class ChatConversationUpdate(BaseModel):
    title: str = Field(..., max_length=255)


class ChatConversationResponse(BaseModel):
    id: str
    user_id: int
    enterprise_space_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    model_provider: str | None = None
    model_name: str | None = None
    model_id: int | None = None
    knowledge_base_ids: list[int] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    system_prompt: str | None = None
    show_citations: bool = True
    retrieval_top_k: int = DEFAULT_TOP_K
    max_history_messages: int = 20
    max_history_tokens: int | None = None
    refine_multiturn: bool = False
    opening_greeting: str | None = None
    empty_response: str | None = None
    suggest_next_questions_enabled: bool = True
    suggest_next_questions_model_id: int | None = None
    suggest_next_questions_prompt_mode: str = "system"
    suggest_next_questions_custom_prompt: str | None = None
    rag_mode: str = "classic"
    agentic_max_iterations: int = 2
    agentic_min_relevant_docs: int = 1
    agentic_context_user_turns: int = 3

    class Config:
        from_attributes = True


class ChatEmbedApiKeyCreateBody(BaseModel):
    """生成或轮换嵌入用 API Key。"""

    regenerate: bool = Field(default=False, description="为 True 时吊销目标范围内已有密钥并签发新密钥")
    conversation_id: str | None = Field(
        default=None,
        description="对话 ID；嵌入分享按对话签发独立密钥，便于复制即用",
        max_length=36,
    )
    issue_new_for_share: bool = Field(
        default=False,
        description="为 True 时吊销该对话已有嵌入密钥并立即签发新密钥（用于再次获得可复制明文）",
    )

    @model_validator(mode="after")
    def _issue_share_requires_conversation(self) -> Self:
        if self.issue_new_for_share and not (self.conversation_id or "").strip():
            raise ValueError("issue_new_for_share 必须提供 conversation_id")
        return self


class ChatEmbedApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key_prefix: str
    created_at: datetime
    conversation_id: str | None = None


class ChatEmbedApiKeyCreateResponse(BaseModel):
    created: bool = Field(description="本次是否新创建了密钥（轮换时也视为 True）")
    api_key: str | None = Field(default=None, description="明文密钥，仅创建/轮换当次返回")
    keys: list[ChatEmbedApiKeyOut] = Field(default_factory=list)
    message: str | None = None
