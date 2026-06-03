from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.authentication import hash_password
from app.core.enterprise_space_context import (
    CurrentSpace,
    CurrentUser,
    RequireSystemAdmin,
    get_membership,
    is_bootstrap_admin,
)
from app.core.membership_roles import DEFAULT_MEMBER_ROLE, SPACE_ADMIN
from app.core.platform_audit_helper import audit_action
from app.core.user_permissions import (
    assert_can_delete_user,
    assert_can_manage_user,
    assert_can_set_is_admin,
    validate_role,
)
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace, Membership, User
from app.schemas.enterprise_space import (
    MembershipResponse,
    MembershipSummary,
    UserCreateRequest,
    UserDetailResponse,
    UserMembershipAssign,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["user-management"])


def _build_user_detail(user: User) -> UserDetailResponse:
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


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.execute(
        select(User)
        .options(joinedload(User.memberships).joinedload(Membership.enterprise_space))
        .where(User.id == user_id)
    ).unique().scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


def _require_space_admin_or_system(
    current_user: User,
    current_space: EnterpriseSpace,
    db: Session,
) -> Membership | None:
    """系统管理员直接放行；否则要求当前空间 space_admin。"""
    if current_user.is_admin:
        return get_membership(current_user, current_space, db)
    membership = get_membership(current_user, current_space, db)
    if membership is None or membership.role != SPACE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有企业空间管理员或系统管理员可以执行此操作",
        )
    return membership


@router.get("", response_model=list[UserDetailResponse])
def list_users(
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="按用户名或邮箱搜索"),
) -> list[UserDetailResponse]:
    """列出用户：系统管理员返回全部；空间管理员返回当前空间成员。"""
    actor_membership = _require_space_admin_or_system(current_user, current_space, db)

    query = select(User).options(
        joinedload(User.memberships).joinedload(Membership.enterprise_space)
    )

    if not current_user.is_admin:
        query = query.join(Membership).where(Membership.enterprise_space_id == current_space.id)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    users = db.execute(query.order_by(User.id)).unique().scalars().all()
    return [_build_user_detail(u) for u in users]


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    request: Request,
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """创建用户。空间管理员创建的用户自动加入当前企业空间。"""
    actor_membership = _require_space_admin_or_system(current_user, current_space, db)

    if body.is_admin is not None:
        assert_can_set_is_admin(current_user, is_admin_value=body.is_admin)

    existing_username = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    existing_email = None
    if body.email:
        existing_email = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已存在")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        is_active=True,
        is_admin=bool(body.is_admin) if body.is_admin is not None and is_bootstrap_admin(current_user) else False,
    )
    db.add(user)
    db.flush()

    if current_user.is_admin and body.space_assignments:
        for assignment in body.space_assignments:
            space = db.get(EnterpriseSpace, assignment.enterprise_space_id)
            if space is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"企业空间 {assignment.enterprise_space_id} 不存在",
                )
            role = validate_role(assignment.role)
            db.add(
                Membership(
                    user_id=user.id,
                    enterprise_space_id=space.id,
                    role=role,
                )
            )
    elif not current_user.is_admin:
        db.add(
            Membership(
                user_id=user.id,
                enterprise_space_id=current_space.id,
                role=DEFAULT_MEMBER_ROLE,
            )
        )

    db.commit()
    audit_action(
        db,
        request,
        action="admin.user.create",
        resource_type="user",
        resource_id=user.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"username": user.username},
    )
    db.commit()
    return _build_user_detail(_get_user_or_404(db, user.id))


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: int,
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    actor_membership = _require_space_admin_or_system(current_user, current_space, db)
    target = _get_user_or_404(db, user_id)
    assert_can_manage_user(
        current_user,
        target,
        db,
        space=current_space,
        actor_membership=actor_membership,
    )
    return _build_user_detail(target)


@router.patch("/{user_id}", response_model=UserDetailResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    actor_membership = _require_space_admin_or_system(current_user, current_space, db)
    target = _get_user_or_404(db, user_id)
    assert_can_manage_user(
        current_user,
        target,
        db,
        space=current_space,
        actor_membership=actor_membership,
    )

    if body.is_admin is not None:
        assert_can_set_is_admin(current_user, is_admin_value=body.is_admin)

    update_data = body.model_dump(exclude_unset=True)
    password = update_data.pop("password", None)
    if password:
        target.password_hash = hash_password(password)

    if "email" in update_data:
        new_email = update_data.pop("email")
        if new_email != target.email:
            if new_email:
                conflict = db.execute(
                    select(User).where(User.email == new_email, User.id != target.id)
                ).scalar_one_or_none()
                if conflict:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已存在")
            target.email = new_email

    for field, value in update_data.items():
        if field == "is_admin" and not is_bootstrap_admin(current_user):
            continue
        setattr(target, field, value)

    if body.username and body.username != target.username:
        conflict = db.execute(
            select(User).where(User.username == body.username, User.id != target.id)
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    db.commit()
    audit_action(
        db,
        request,
        action="admin.user.update",
        resource_type="user",
        resource_id=target.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"username": target.username},
    )
    db.commit()
    return _build_user_detail(_get_user_or_404(db, target.id))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    current_user: CurrentUser,
    current_space: CurrentSpace,
    db: Session = Depends(get_db),
) -> None:
    actor_membership = _require_space_admin_or_system(current_user, current_space, db)
    target = _get_user_or_404(db, user_id)
    assert_can_manage_user(
        current_user,
        target,
        db,
        space=current_space,
        actor_membership=actor_membership,
    )
    assert_can_delete_user(current_user, target)
    username = target.username
    db.delete(target)
    audit_action(
        db,
        request,
        action="admin.user.delete",
        resource_type="user",
        resource_id=user_id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"username": username},
    )
    db.commit()


@router.get("/{user_id}/memberships", response_model=list[MembershipResponse])
def get_user_memberships(
    user_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[MembershipResponse]:
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该用户的成员关系")

    memberships = db.execute(
        select(Membership).where(Membership.user_id == user_id).order_by(Membership.id)
    ).scalars().all()
    return memberships


@router.put("/{user_id}/memberships", response_model=UserDetailResponse)
def set_user_memberships(
    user_id: int,
    body: UserMembershipAssign,
    request: Request,
    current_user: RequireSystemAdmin,
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    target = _get_user_or_404(db, user_id)
    if is_bootstrap_admin(target) and not is_bootstrap_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理 bootstrap 管理员")

    seen_space_ids: set[int] = set()
    for assignment in body.assignments:
        if assignment.enterprise_space_id in seen_space_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"企业空间 {assignment.enterprise_space_id} 重复分配",
            )
        seen_space_ids.add(assignment.enterprise_space_id)
        space = db.get(EnterpriseSpace, assignment.enterprise_space_id)
        if space is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"企业空间 {assignment.enterprise_space_id} 不存在",
            )
        validate_role(assignment.role)

    existing = db.execute(select(Membership).where(Membership.user_id == user_id)).scalars().all()
    for m in existing:
        db.delete(m)
    db.flush()

    for assignment in body.assignments:
        db.add(
            Membership(
                user_id=user_id,
                enterprise_space_id=assignment.enterprise_space_id,
                role=validate_role(assignment.role),
            )
        )

    db.commit()
    audit_action(
        db,
        request,
        action="admin.user.memberships.update",
        resource_type="user",
        resource_id=user_id,
        user_id=current_user.id,
        detail={"assignments": [a.model_dump() for a in body.assignments]},
    )
    db.commit()
    return _build_user_detail(_get_user_or_404(db, user_id))
