from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer, JSON, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class KnowledgeBaseStatus(enum.Enum):
    """知识库状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class KnowledgeBase(Base):
    """知识库 - 用于管理知识集合"""

    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=KnowledgeBaseStatus.ACTIVE.value, nullable=False)
    vector_db_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    graph_db_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    enterprise_space = relationship("EnterpriseSpace", backref="knowledge_bases")
    milvus_connection = relationship("MilvusConnection", back_populates="knowledge_base", uselist=False, cascade="all, delete-orphan")
    neo4j_connection = relationship("Neo4jConnection", back_populates="knowledge_base", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, space_id={self.enterprise_space_id})>"


class MilvusConnection(Base):
    """Milvus 向量数据库连接配置"""

    __tablename__ = "milvus_connection"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    host: Mapped[str] = mapped_column(String(200), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=19530, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 仅写入不回显
    collection_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 自动生成
    dimension: Mapped[int] = mapped_column(Integer, default=1536, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(20), default="COSINE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="milvus_connection")

    def __repr__(self) -> str:
        return f"<MilvusConnection(kb_id={self.knowledge_base_id}, host={self.host})>"


class Neo4jConnection(Base):
    """Neo4j 图数据库连接配置"""

    __tablename__ = "neo4j_connection"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    uri: Mapped[str] = mapped_column(String(500), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 仅写入不回显
    database: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="neo4j_connection")

    def __repr__(self) -> str:
        return f"<Neo4jConnection(kb_id={self.knowledge_base_id}, uri={self.uri})>"
