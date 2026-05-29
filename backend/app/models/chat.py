from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatConversation(Base):
    """对话：其下多会话；模型/知识库等配置挂在对话行上（原独立 chat_configuration 表已合并）。"""

    __tablename__ = "chat_conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="新建对话", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    selected_llm_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"), nullable=True, index=True
    )
    knowledge_base_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    show_citations: Mapped[bool] = mapped_column(default=True, nullable=False)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    lightrag_query_mode: Mapped[str] = mapped_column(String(20), default="mix", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    top_p: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    temperature_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_tokens_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    top_p_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_history_messages: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_history_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refine_multiturn: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opening_greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    empty_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggest_next_questions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    suggest_next_questions_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"), nullable=True, index=True
    )
    suggest_next_questions_prompt_mode: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    suggest_next_questions_custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ChatSession(Base):
    """会话：仅消息历史按会话区分；配置继承自所属对话。"""

    __tablename__ = "chat_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="新会话", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
