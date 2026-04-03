from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authentication import create_access_token, verify_password
from app.core.security import get_security_settings
from app.db.session import get_db
from app.models.enterprise_space import User
from app.schemas.enterprise_space import Token, UserCreate, UserLogin, UserResponse

router = APIRouter(tags=["authentication"])


def _get_db() -> Session:
    """获取数据库会话"""
    db = next(get_db())
    try:
        return db
    finally:
        pass


@router.post("/auth/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(_get_db),
) -> Token:
    """
    用户登录
    
    使用用户名和密码登录，成功后返回 Bearer Token
    """
    user = db.execute(select(User).where(User.username == login_data.username)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(user.password_hash, login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})

    return Token(access_token=access_token)


@router.get("/auth/me", response_model=UserResponse)
def get_current_user_info(
    db: Session = Depends(_get_db),
) -> UserResponse:
    """
    获取当前登录用户信息
    
    需要从请求头中获取有效的 Bearer Token
    """
    from app.core.enterprise_space_context import get_current_user

    # 手动调用以获取用户（通过 Depends 机制）
    # 这里需要重新实现以适配普通路由
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="此接口需要通过 Depends 机制获取认证用户",
    )
