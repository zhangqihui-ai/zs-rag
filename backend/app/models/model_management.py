from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIModelProvider(Base):
    """企业空间下接入的模型厂商配置"""

    __tablename__ = "ai_model_provider"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_space_id",
            "provider_name",
            "base_url",
            name="uq_ai_model_provider_space_name_base_url",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    deployment_type: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), default="bearer", nullable=False)
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    enterprise_space = relationship("EnterpriseSpace", backref="ai_model_providers")
    models = relationship("AIModel", back_populates="provider", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AIModelProvider(id={self.id}, provider_code={self.provider_code}, provider_name={self.provider_name})>"


class AIModel(Base):
    """企业空间下可用模型"""

    __tablename__ = "ai_model"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_code", name="uq_ai_model_provider_model_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("ai_model_provider.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_code: Mapped[str] = mapped_column(String(200), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_type: Mapped[str] = mapped_column(String(30), nullable=False, default="llm")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    provider = relationship("AIModelProvider", back_populates="models")
    enterprise_space = relationship("EnterpriseSpace")
    defaults = relationship("AIModelDefault", back_populates="model", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AIModel(id={self.id}, model_code={self.model_code}, provider_id={self.provider_id})>"


class AIModelDefault(Base):
    """企业空间默认模型配置"""

    __tablename__ = "ai_model_default"
    __table_args__ = (
        UniqueConstraint("enterprise_space_id", "model_type", name="uq_ai_model_default_space_model_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("ai_model.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    enterprise_space = relationship("EnterpriseSpace")
    model = relationship("AIModel", back_populates="defaults")

    def __repr__(self) -> str:
        return f"<AIModelDefault(id={self.id}, model_type={self.model_type}, model_id={self.model_id})>"
