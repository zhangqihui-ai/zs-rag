from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authentication import decode_access_token
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User

# Context variables
current_user_ctx: ContextVar[dict | None] = ContextVar("current_user", default=None)
current_space_ctx: ContextVar[str] = ContextVar("current_space", default="default")

# Security scheme
security = HTTPBearer(auto_error=False)


def get_current_user_from_token(token: str, db: Session) -> User:
    """从 token 中解析并获取当前用户"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


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

    user = get_current_user_from_token(credentials.credentials, db)
    current_user_ctx.set({"id": user.id, "username": user.username, "is_admin": user.is_admin})
    return user


def get_enterprise_space_from_header(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EnterpriseSpace:
    """从请求头获取企业空间，默认为 default"""
    space_slug = request.headers.get("X-Enterprise-Space", "default")
    if not space_slug:
        space_slug = "default"

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

    try:
        return get_current_user_from_token(credentials.credentials, db)
    except HTTPException:
        return None
