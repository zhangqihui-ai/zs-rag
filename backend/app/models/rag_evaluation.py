"""RAG 评估 benchmark 与评测运行记录。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RagBenchmark(Base):
    __tablename__ = "rag_benchmark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_base_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    items: Mapped[list["RagBenchmarkItem"]] = relationship(
        "RagBenchmarkItem", back_populates="benchmark", cascade="all, delete-orphan"
    )


class RagBenchmarkItem(Base):
    __tablename__ = "rag_benchmark_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        ForeignKey("rag_benchmark.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    benchmark: Mapped[RagBenchmark] = relationship("RagBenchmark", back_populates="items")


class RagEvaluationRun(Base):
    __tablename__ = "rag_evaluation_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        ForeignKey("rag_benchmark.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    retrieval_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    results: Mapped[list["RagEvaluationResult"]] = relationship(
        "RagEvaluationResult", back_populates="run", cascade="all, delete-orphan"
    )


class RagEvaluationResult(Base):
    __tablename__ = "rag_evaluation_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("rag_evaluation_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    benchmark_item_id: Mapped[int] = mapped_column(
        ForeignKey("rag_benchmark_item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped[RagEvaluationRun] = relationship("RagEvaluationRun", back_populates="results")
