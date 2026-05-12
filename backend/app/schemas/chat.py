from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatStreamRequest(BaseModel):
    content: str = Field(..., min_length=1, description="用户本轮输入（纯文本）")


class OpenAICompatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsRequest(BaseModel):
    """对齐 OpenAI Chat Completions 的常用字段，并扩展本系统的 chat_id / session_id / question。"""

    model_config = ConfigDict(extra="ignore")

    chat_id: str = Field(..., min_length=1)
    session_id: str | None = None
    stream: bool = False
    messages: list[OpenAICompatMessage] | None = None
    question: str | None = None

    @model_validator(mode="after")
    def need_messages_or_question(self) -> Self:
        has_m_raw = bool(self.messages and len(self.messages) > 0)
        has_q = bool(self.question and str(self.question).strip())
        if not has_m_raw and not has_q:
            raise ValueError("必须提供 messages（至少一条）或 question")
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
        default=8,
        ge=1,
        le=50,
        description=(
            "与「知识检索」多库一致：合并后按分数取 Top K 条注入上下文；"
            "各库内会先按该值放大召回候选再全局排序（见 search_knowledge_bases_multi）。"
        ),
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2000, ge=1)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    system_prompt: str | None = Field(
        default=None,
        max_length=100_000,
        description="系统提示词；可用 {knowledge} 占位。为空时使用服务端默认模板。",
    )


class ChatConfigurationUpdate(ChatConfigurationBase):
    pass


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
    retrieval_top_k: int = 8

    class Config:
        from_attributes = True
