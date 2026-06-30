"""平台用量埋点事件。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformUsageEvent(Base):
    __tablename__ = "platform_usage_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    knowledge_base_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
