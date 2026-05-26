"""用户与企业空间成员权限校验辅助函数。"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import is_bootstrap_admin
from app.core.membership_roles import SPACE_ADMIN, VALID_ROLES
from app.models.enterprise_space import EnterpriseSpace, Membership, User


def count_space_admins(db: Session, space_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.enterprise_space_id == space_id,
            Membership.role == SPACE_ADMIN,
        )
    ).scalar_one()


def validate_role(role: str) -> str:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色 '{role}'，允许值：{', '.join(sorted(VALID_ROLES))}",
        )
    return role


def ensure_not_last_space_admin(db: Session, space_id: int, membership: Membership, *, new_role: str | None = None) -> None:
    """防止移除或降级空间中最后一名 space_admin。"""
    if membership.role != SPACE_ADMIN:
        return
    if new_role == SPACE_ADMIN:
        return
    if count_space_admins(db, space_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="企业空间至少需要保留一名空间管理员",
        )


def user_in_space(db: Session, user_id: int, space_id: int) -> bool:
    existing = db.execute(
        select(Membership.id).where(
            Membership.user_id == user_id,
            Membership.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    return existing is not None


def can_manage_user(
    actor: User,
    target: User,
    db: Session,
    *,
    space: EnterpriseSpace | None = None,
    actor_membership: Membership | None = None,
) -> bool:
    """判断 actor 是否有权管理 target 用户。"""
    if actor.id == target.id:
        return True
    if is_bootstrap_admin(target) and not is_bootstrap_admin(actor):
        return False
    if actor.is_admin:
        return True
    if space is None or actor_membership is None:
        return False
    if actor_membership.role != SPACE_ADMIN:
        return False
    if target.is_admin:
        return False
    return user_in_space(db, target.id, space.id)


def assert_can_manage_user(
    actor: User,
    target: User,
    db: Session,
    *,
    space: EnterpriseSpace | None = None,
    actor_membership: Membership | None = None,
) -> None:
    if not can_manage_user(actor, target, db, space=space, actor_membership=actor_membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权管理该用户",
        )


def assert_can_set_is_admin(actor: User, *, is_admin_value: bool | None) -> None:
    if is_admin_value is None:
        return
    if not is_bootstrap_admin(actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有 bootstrap 管理员可以设置系统管理员权限",
        )


def assert_can_delete_user(actor: User, target: User) -> None:
    if is_bootstrap_admin(target):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除 bootstrap 管理员账号",
        )
    if actor.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号",
        )
