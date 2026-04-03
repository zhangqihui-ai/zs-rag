from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EnterpriseSpace(Base):
    """企业空间 - 系统唯一租户标识"""

    __tablename__ = "enterprise_space"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    members = relationship("Membership", back_populates="enterprise_space", cascade="all, delete-orphan")
    # providers relationship will be added in model_management.py
    # knowledge_bases relationship will be added in knowledge_base.py

    def __repr__(self) -> str:
        return f"<EnterpriseSpace(id={self.id}, name={self.name}, slug={self.slug})>"


class User(Base):
    """用户账号"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Membership(Base):
    """用户 - 企业空间成员关系"""

    __tablename__ = "membership"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    enterprise_space_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_space.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="memberships")
    enterprise_space = relationship("EnterpriseSpace", back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "enterprise_space_id", name="uq_membership_user_space"),
    )

    def __repr__(self) -> str:
        return f"<Membership(user_id={self.user_id}, space_id={self.enterprise_space_id}, role={self.role})>"
