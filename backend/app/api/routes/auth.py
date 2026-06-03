from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.authentication import create_access_token, verify_password
from app.core.platform_audit_helper import audit_action
from app.core.enterprise_space_context import CurrentUser, is_bootstrap_admin
from app.db.session import get_db
from app.models.enterprise_space import Membership, User
from app.schemas.enterprise_space import MembershipSummary, Token, UserDetailResponse, UserLogin

router = APIRouter(tags=["authentication"])


@router.post("/auth/login", response_model=Token)
def login(
    login_data: UserLogin,
    request: Request,
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
    audit_action(
        db,
        request,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        user_id=user.id,
        message=f"用户 {user.username} 登录成功",
    )
    db.commit()
    return Token(access_token=access_token)


@router.get("/auth/me", response_model=UserDetailResponse)
def get_current_user_info(current_user: CurrentUser, db: Session = Depends(get_db)) -> UserDetailResponse:
    user = db.execute(
        select(User)
        .options(joinedload(User.memberships).joinedload(Membership.enterprise_space))
        .where(User.id == current_user.id)
    ).unique().scalar_one()

    memberships = [
        MembershipSummary(
            enterprise_space_id=m.enterprise_space_id,
            role=m.role,
            space=m.enterprise_space,
        )
        for m in user.memberships
    ]
    return UserDetailResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        memberships=memberships,
        is_bootstrap_admin=is_bootstrap_admin(user),
    )
