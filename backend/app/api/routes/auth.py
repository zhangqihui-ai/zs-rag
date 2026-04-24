from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authentication import create_access_token, verify_password
from app.core.enterprise_space_context import CurrentUser
from app.db.session import get_db
from app.models.enterprise_space import User
from app.schemas.enterprise_space import Token, UserLogin, UserResponse

router = APIRouter(tags=["authentication"])


@router.post("/auth/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db),
) -> Token:
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
def get_current_user_info(current_user: CurrentUser) -> User:
    return current_user
