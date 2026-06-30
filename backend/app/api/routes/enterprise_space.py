from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.enterprise_space_context import CurrentSpace, CurrentUser, RequireMembership, RequireSystemAdmin
from app.core.membership_roles import SPACE_ADMIN
from app.core.user_permissions import (
    ensure_not_last_space_admin,
    validate_role,
)
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.schemas.dashboard import DashboardChatTopResponse, DashboardOverviewResponse, DashboardUsageResponse
from app.services.usage_metrics_service import get_usage_timeseries
from app.schemas.enterprise_space import (
    EnterpriseSpaceCreate,
    EnterpriseSpaceResponse,
    EnterpriseSpaceUpdate,
    EnterpriseSpaceWithRoleResponse,
    MembershipResponse,
    MembershipUpdate,
    MembershipWithUserResponse,
    UserResponse,
)

from app.services.dashboard_service import get_space_dashboard_overview, get_top_chat_conversations

router = APIRouter(prefix="/enterprise-spaces", tags=["enterprise-space-management"])


def _get_db() -> Session:
    db = next(get_db())
    try:
        return db
    finally:
        pass


def _membership_with_user(m: Membership) -> MembershipWithUserResponse:
    return MembershipWithUserResponse(
        id=m.id,
        user_id=m.user_id,
        enterprise_space_id=m.enterprise_space_id,
        role=m.role,
        created_at=m.created_at,
        user=UserResponse.model_validate(m.user),
    )


@router.get("", response_model=list[EnterpriseSpaceWithRoleResponse])
def list_enterprise_spaces(
    current_user: CurrentUser,
    db: Any = Depends(_get_db),
) -> list[EnterpriseSpaceWithRoleResponse]:
    """列出当前用户可访问的所有企业空间（含角色）。"""
    memberships = db.execute(
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .join(EnterpriseSpace)
    ).scalars().all()

    return [
        EnterpriseSpaceWithRoleResponse(
            id=m.enterprise_space.id,
            name=m.enterprise_space.name,
            slug=m.enterprise_space.slug,
            description=m.enterprise_space.description,
            created_at=m.enterprise_space.created_at,
            updated_at=m.enterprise_space.updated_at,
            role=m.role,
        )
        for m in memberships
    ]


@router.get("/all", response_model=list[EnterpriseSpaceResponse])
def list_all_enterprise_spaces(
    current_user: RequireSystemAdmin,
    db: Any = Depends(_get_db),
) -> list[EnterpriseSpaceResponse]:
    """列出全部企业空间（仅系统管理员）。"""
    spaces = db.execute(select(EnterpriseSpace).order_by(EnterpriseSpace.id)).scalars().all()
    return spaces


@router.get("/dashboard", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Any = Depends(_get_db),
) -> DashboardOverviewResponse:
    """当前企业空间仪表盘概览（知识库、检索语料、对话、模型、成员）。"""
    return get_space_dashboard_overview(db, space=current_space)


@router.get("/dashboard/usage", response_model=DashboardUsageResponse)
def get_dashboard_usage(
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Any = Depends(_get_db),
    range: str = "24h",
    metric: str = "model_calls",
) -> DashboardUsageResponse:
    """当前企业空间用量时间序列（模型调用 / Token / 对话 API）。"""
    allowed_ranges = {"24h", "7d", "30d"}
    allowed_metrics = {"model_calls", "tokens", "chat_api"}
    range_key = range if range in allowed_ranges else "24h"
    metric_key = metric if metric in allowed_metrics else "model_calls"
    payload = get_usage_timeseries(
        db,
        space_id=current_space.id,
        range_key=range_key,  # type: ignore[arg-type]
        metric=metric_key,  # type: ignore[arg-type]
    )
    return DashboardUsageResponse(
        space_id=current_space.id,
        space_name=current_space.name,
        **payload,
    )


@router.get("/dashboard/chat-top", response_model=DashboardChatTopResponse)
def get_dashboard_chat_top(
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Any = Depends(_get_db),
    range: str = "24h",
) -> DashboardChatTopResponse:
    """当前企业空间最常用对话助手 Top3（会话数 / 消息数）。"""
    allowed_ranges = {"24h", "7d", "30d"}
    range_key = range if range in allowed_ranges else "24h"
    items = get_top_chat_conversations(db, space_id=current_space.id, range_key=range_key, limit=3)
    return DashboardChatTopResponse(
        space_id=current_space.id,
        space_name=current_space.name,
        range=range_key,
        items=items,
    )


@router.post("", response_model=EnterpriseSpaceResponse, status_code=status.HTTP_201_CREATED)
def create_enterprise_space(
    space_data: EnterpriseSpaceCreate,
    current_user: RequireSystemAdmin,
    db: Any = Depends(_get_db),
) -> EnterpriseSpaceResponse:
    """创建新的企业空间（仅系统管理员）。"""
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

    membership = Membership(
        user_id=current_user.id,
        enterprise_space_id=space.id,
        role=SPACE_ADMIN,
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
    """获取指定企业空间详情。"""
    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业空间不存在")

    membership = db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.enterprise_space_id == space.id,
        )
    ).scalar_one_or_none()

    if membership is None and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您没有该企业空间的访问权限")

    return space


@router.patch("/{space_id}", response_model=EnterpriseSpaceResponse)
def update_enterprise_space(
    space_id: int,
    space_data: EnterpriseSpaceUpdate,
    current_user: RequireSystemAdmin,
    db: Any = Depends(_get_db),
) -> EnterpriseSpaceResponse:
    """更新企业空间信息（仅系统管理员）。"""
    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业空间不存在")

    update_data = space_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(space, field, value)

    db.commit()
    db.refresh(space)
    return space


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_enterprise_space(
    space_id: int,
    current_user: RequireSystemAdmin,
    db: Any = Depends(_get_db),
) -> Response:
    """删除企业空间（仅系统管理员，不允许删除 default）。"""
    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业空间不存在")

    if space.slug == "default":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不允许删除 default 企业空间")

    db.delete(space)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{space_id}/members", response_model=list[MembershipWithUserResponse])
def list_members(
    space_id: int,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> list[MembershipWithUserResponse]:
    """列出企业空间的所有成员。"""
    memberships = db.execute(
        select(Membership)
        .options(joinedload(Membership.user))
        .where(Membership.enterprise_space_id == space_id)
        .join(User)
    ).unique().scalars().all()

    return [_membership_with_user(m) for m in memberships]


@router.post("/{space_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    space_id: int,
    user_id: int,
    current_user: CurrentUser,
    membership: RequireMembership,
    role: str = "member",
    db: Any = Depends(_get_db),
) -> MembershipResponse:
    """添加企业空间成员（空间管理员或系统管理员）。"""
    if membership.role != SPACE_ADMIN and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有空间管理员或系统管理员可以添加成员")

    space = db.get(EnterpriseSpace, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="企业空间不存在")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    existing = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已是该企业空间成员")

    validated_role = validate_role(role)
    new_membership = Membership(
        user_id=user_id,
        enterprise_space_id=space_id,
        role=validated_role,
    )
    db.add(new_membership)
    db.commit()
    db.refresh(new_membership)

    return new_membership


@router.patch("/{space_id}/members/{user_id}", response_model=MembershipResponse)
def update_member(
    space_id: int,
    user_id: int,
    body: MembershipUpdate,
    current_user: CurrentUser,
    actor_membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> MembershipResponse:
    """修改成员角色（空间管理员或系统管理员）。"""
    if actor_membership.role != SPACE_ADMIN and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有空间管理员或系统管理员可以修改成员角色")

    target = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")

    new_role = validate_role(body.role)
    ensure_not_last_space_admin(db, space_id, target, new_role=new_role)
    target.role = new_role
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{space_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_member(
    space_id: int,
    user_id: int,
    current_user: CurrentUser,
    actor_membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> Response:
    """移除企业空间成员（空间管理员或系统管理员）。"""
    if actor_membership.role != SPACE_ADMIN and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有空间管理员或系统管理员可以移除成员")

    target = db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")

    ensure_not_last_space_admin(db, space_id, target)
    db.delete(target)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{space_id}/member-count", response_model=dict)
def member_count(
    space_id: int,
    current_user: RequireSystemAdmin,
    db: Any = Depends(_get_db),
) -> dict:
    """获取企业空间成员数量（系统管理员）。"""
    count = db.execute(
        select(func.count()).select_from(Membership).where(Membership.enterprise_space_id == space_id)
    ).scalar_one()
    return {"count": count}
