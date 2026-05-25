"""嵌入对话 API Key：生成、哈希校验、吊销。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chat_embed_api_key import ChatEmbedApiKey
from app.models.enterprise_space import EnterpriseSpace, User

EMBED_KEY_PREFIX = "zs_rag_embed_"


def hash_embed_api_key(raw: str) -> str:
    settings = get_settings()
    pepper = (settings.embed_api_key_pepper or settings.jwt_secret).encode("utf-8")
    return hashlib.sha256(pepper + b":" + raw.encode("utf-8")).hexdigest()


def generate_embed_api_key_plaintext() -> str:
    return EMBED_KEY_PREFIX + secrets.token_urlsafe(32)


def _resolve_embed_api_key_row(raw_token: str, db: Session) -> ChatEmbedApiKey | None:
    if not raw_token.startswith(EMBED_KEY_PREFIX):
        return None
    th = hash_embed_api_key(raw_token)
    return db.execute(
        select(ChatEmbedApiKey).where(
            ChatEmbedApiKey.token_hash == th,
            ChatEmbedApiKey.revoked_at.is_(None),
        )
    ).scalar_one_or_none()


def resolve_embed_api_key_auth(raw_token: str, db: Session) -> tuple[User, EnterpriseSpace] | None:
    """按 token_hash 全局解析嵌入 Key（无需 X-Enterprise-Space），返回用户与所属企业空间。"""
    row = _resolve_embed_api_key_row(raw_token, db)
    if row is None:
        return None
    user = db.get(User, row.created_by_user_id)
    if user is None or not user.is_active:
        return None
    space = db.get(EnterpriseSpace, row.enterprise_space_id)
    if space is None:
        return None
    return user, space


def resolve_user_via_embed_api_key(raw_token: str, enterprise_space_id: int, db: Session) -> User | None:
    """兼容：在指定企业空间内校验嵌入 Key（与请求头 X-Enterprise-Space 一致时使用）。"""
    row = _resolve_embed_api_key_row(raw_token, db)
    if row is None or row.enterprise_space_id != enterprise_space_id:
        return None
    user = db.get(User, row.created_by_user_id)
    if user is None or not user.is_active:
        return None
    return user


def list_active_embed_keys(db: Session, enterprise_space_id: int) -> list[ChatEmbedApiKey]:
    res = db.execute(
        select(ChatEmbedApiKey).where(
            ChatEmbedApiKey.enterprise_space_id == enterprise_space_id,
            ChatEmbedApiKey.revoked_at.is_(None),
        )
    )
    return list(res.scalars().all())


def revoke_all_active_for_space(db: Session, enterprise_space_id: int) -> None:
    now = datetime.utcnow()
    db.execute(
        update(ChatEmbedApiKey)
        .where(
            ChatEmbedApiKey.enterprise_space_id == enterprise_space_id,
            ChatEmbedApiKey.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def create_embed_api_key_row(
    db: Session,
    *,
    enterprise_space_id: int,
    created_by_user_id: int,
    conversation_id: str | None = None,
) -> tuple[str, ChatEmbedApiKey]:
    raw = generate_embed_api_key_plaintext()
    row = ChatEmbedApiKey(
        enterprise_space_id=enterprise_space_id,
        conversation_id=conversation_id,
        created_by_user_id=created_by_user_id,
        token_hash=hash_embed_api_key(raw),
        key_prefix=raw[:24],
    )
    db.add(row)
    db.flush()
    return raw, row


def list_active_embed_keys_for_conversation(
    db: Session, enterprise_space_id: int, conversation_id: str
) -> list[ChatEmbedApiKey]:
    res = db.execute(
        select(ChatEmbedApiKey).where(
            ChatEmbedApiKey.enterprise_space_id == enterprise_space_id,
            ChatEmbedApiKey.conversation_id == conversation_id,
            ChatEmbedApiKey.revoked_at.is_(None),
        )
    )
    return list(res.scalars().all())


def revoke_active_embed_keys_for_conversation(db: Session, enterprise_space_id: int, conversation_id: str) -> None:
    now = datetime.utcnow()
    db.execute(
        update(ChatEmbedApiKey)
        .where(
            ChatEmbedApiKey.enterprise_space_id == enterprise_space_id,
            ChatEmbedApiKey.conversation_id == conversation_id,
            ChatEmbedApiKey.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def revoke_embed_key_by_id(db: Session, *, key_id: int, enterprise_space_id: int) -> bool:
    row = db.get(ChatEmbedApiKey, key_id)
    if row is None or row.enterprise_space_id != enterprise_space_id:
        return False
    if row.revoked_at is not None:
        return True
    row.revoked_at = datetime.utcnow()
    db.flush()
    return True
