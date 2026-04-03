from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProviderConfig(Base):
    """模型 Provider 配置 - 用于管理不同厂商的模型服务"""

    __tablename__ = "provider_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)  # openai-compatible, bailian, deepseek, zhipu, kimi
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)  # 仅写入不回显
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 额外配置
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    enterprise_space = relationship("EnterpriseSpace", backref="providers")
    models = relationship("ModelRef", back_populates="provider", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ProviderConfig(id={self.id}, name={self.name}, type={self.provider_type})>"


class ModelRef(Base):
    """模型引用 - 用于管理 Provider 下的具体模型"""

    __tablename__ = "model_ref"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider_config.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)  # ["chat", "embedding", "rerank"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 默认参数如 temperature, max_tokens
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    provider = relationship("ProviderConfig", back_populates="models")
    enterprise_space = relationship("EnterpriseSpace")

    def __repr__(self) -> str:
        return f"<ModelRef(id={self.id}, model_name={self.model_name}, provider_id={self.provider_id})>"
