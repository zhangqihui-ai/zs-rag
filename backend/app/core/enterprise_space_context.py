from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authentication import decode_access_token
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.services.chat_embed_api_key_service import (
    resolve_embed_api_key_auth,
    resolve_user_via_embed_api_key,
)

# Context variables
current_user_ctx: ContextVar[dict | None] = ContextVar("current_user", default=None)
current_space_ctx: ContextVar[str] = ContextVar("current_space", default="default")
# 嵌入 API Key 鉴权成功后写入，供 get_enterprise_space_from_header 自动选用对应空间
auth_resolved_space_slug_ctx: ContextVar[str | None] = ContextVar("auth_resolved_space_slug", default=None)

# Security scheme
security = HTTPBearer(auto_error=False)


def resolve_authenticated_user(request: Request, raw_token: str, db: Session) -> User | None:
    """JWT 或嵌入 API Key（Bearer）解析为平台用户。"""
    auth_resolved_space_slug_ctx.set(None)

    payload = decode_access_token(raw_token)
    if payload is not None:
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user = db.get(User, int(user_id))
        if user is None or not user.is_active:
            return None
        return user

    # 嵌入 Key：token_hash 全局唯一，可不传 X-Enterprise-Space
    embed_auth = resolve_embed_api_key_auth(raw_token, db)
    if embed_auth is not None:
        user, space = embed_auth
        auth_resolved_space_slug_ctx.set(space.slug)
        return user

    # 兼容旧调用：若显式带了空间头，仍按头内空间校验 Key
    space_slug = request.headers.get("X-Enterprise-Space", "default") or "default"
    space = db.execute(select(EnterpriseSpace).where(EnterpriseSpace.slug == space_slug)).scalar_one_or_none()
    if space is None:
        return None
    return resolve_user_via_embed_api_key(raw_token, space.id, db)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    """获取当前认证用户"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = resolve_authenticated_user(request, credentials.credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    current_user_ctx.set({"id": user.id, "username": user.username, "is_admin": user.is_admin})
    return user


def get_enterprise_space_from_header(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EnterpriseSpace:
    """从请求头获取企业空间；嵌入 API Key 鉴权成功时自动使用 Key 所属空间。"""
    resolved_slug = auth_resolved_space_slug_ctx.get()
    if resolved_slug:
        space_slug = resolved_slug
    else:
        space_slug = request.headers.get("X-Enterprise-Space", "default") or "default"

    space = db.execute(select(EnterpriseSpace).where(EnterpriseSpace.slug == space_slug)).scalar_one_or_none()
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"企业空间 '{space_slug}' 不存在",
        )

    current_space_ctx.set(space_slug)
    return space


def require_membership(
    user: Annotated[User, Depends(get_current_user)],
    space: Annotated[EnterpriseSpace, Depends(get_enterprise_space_from_header)],
    db: Annotated[Session, Depends(get_db)],
) -> Membership:
    """验证用户是否为企业空间成员"""
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.enterprise_space_id == space.id,
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有该企业空间的访问权限",
        )

    return membership


# Dependency shortcuts
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentSpace = Annotated[EnterpriseSpace, Depends(get_enterprise_space_from_header)]
RequireMembership = Annotated[Membership, Depends(require_membership)]


def get_current_user_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User | None:
    """可选的当前用户（用于不需要认证的端点）"""
    if credentials is None:
        return None

    return resolve_authenticated_user(request, credentials.credentials, db)
