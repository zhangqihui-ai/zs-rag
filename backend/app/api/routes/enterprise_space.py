from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentUser, CurrentSpace, RequireMembership
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.schemas.enterprise_space import (
    EnterpriseSpaceCreate,
    EnterpriseSpaceResponse,
    EnterpriseSpaceUpdate,
    MembershipResponse,
    UserResponse,
)

router = APIRouter(prefix="/enterprise-spaces", tags=["enterprise-space-management"])


def _get_db() -> Session:
    """获取数据库会话"""
    db = next(get_db())
    try:
        return db
    finally:
        pass


@router.get("", response_model=list[EnterpriseSpaceResponse])
def list_enterprise_spaces(
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> list[EnterpriseSpaceResponse]:
    """列出当前用户可访问的所有企业空间"""
    memberships = db.execute(
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .join(EnterpriseSpace)
    ).scalars().all()
    
    spaces = [m.enterprise_space for m in memberships]
    return spaces


@router.post("", response_model=EnterpriseSpaceResponse, status_code=status.HTTP_201_CREATED)
def create_enterprise_space(
    space_data: EnterpriseSpaceCreate,
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> EnterpriseSpaceResponse:
    """创建新的企业空间（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以创建企业空间",
        )

    # 检查 slug 是否已存在
    existing = db.execute(
        select(EnterpriseSpace).where(EnterpriseSpace.slug == space_data.slug)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"企业空间标识 '{space_data.slug}' 已存在",
        )

    space = EnterpriseSpace(
        name=space_data.name,
        slug=space_data.slug,
        description=space_data.description,
    )
    db.add(space)
    db.flush()

    # 创建管理员与该企业空间的成员关系
    membership = Membership(
        user_id=current_user.id,
        enterprise_space_id=space.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(space)

    return space


@router.get("/{space_id}", response_model=EnterpriseSpaceResponse)
def get_enterprise_space(
    space_id: int,
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> EnterpriseSpaceResponse:
    """获取指定企业空间详情"""
    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="企业空间不存在",
        )

    # 检查权限
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.enterprise_space_id == space.id,
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有该企业空间的访问权限",
        )

    return space


@router.patch("/{space_id}", response_model=EnterpriseSpaceResponse)
def update_enterprise_space(
    space_id: int,
    space_data: EnterpriseSpaceUpdate,
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> EnterpriseSpaceResponse:
    """更新企业空间信息（仅管理员）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以更新企业空间",
        )

    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="企业空间不存在",
        )

    update_data = space_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(space, field, value)

    db.commit()
    db.refresh(space)
    return space


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_enterprise_space(
    space_id: int,
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> Response:
    """删除企业空间（仅管理员，不允许删除 default）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以删除企业空间",
        )

    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="企业空间不存在",
        )

    if space.slug == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许删除 default 企业空间",
        )

    db.delete(space)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{space_id}/members", response_model=list[MembershipResponse])
def list_members(
    space_id: int,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> list[MembershipResponse]:
    """列出企业空间的所有成员"""
    memberships = db.execute(
        select(Membership)
        .where(Membership.enterprise_space_id == space_id)
        .join(User)
    ).scalars().all()

    return memberships


@router.post("/{space_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    space_id: int,
    user_id: int,
    current_user: CurrentUser,
    membership: RequireMembership,
    role: str = "member",
    db: Any = Depends(_get_db),
) -> MembershipResponse:
    """添加企业空间成员（仅 owner 或管理员）"""
    if membership.role != "owner" and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有 owner 或管理员可以添加成员",
        )

    # 检查企业空间是否存在
    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="企业空间不存在",
        )

    # 检查用户是否存在
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 检查成员关系是否已存在
    existing = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已是该企业空间成员",
        )

    new_membership = Membership(
        user_id=user_id,
        enterprise_space_id=space_id,
        role=role,
    )
    db.add(new_membership)
    db.commit()
    db.refresh(new_membership)

    return new_membership
