import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authentication import hash_password
from app.core.security import get_security_settings
from app.models.enterprise_space import EnterpriseSpace, Membership, User

logger = logging.getLogger(__name__)


def initialize_admin_and_default_space(db: Session) -> None:
    """
    初始化管理员账号和 default 企业空间
    
    幂等保证：
    - 若管理员已存在则不重复创建
    - 若 default 企业空间已存在则不重复创建
    - 若成员关系已存在则不重复创建
    """
    security_settings = get_security_settings()

    # 1. 创建或获取管理员账号
    admin = db.execute(select(User).where(User.username == security_settings.admin_username)).scalar_one_or_none()
    
    if admin is None:
        logger.info("创建管理员账号：%s", security_settings.admin_username)
        admin = User(
            username=security_settings.admin_username,
            email=security_settings.admin_email,
            password_hash=hash_password(security_settings.admin_password),
            is_active=True,
            is_admin=True,
        )
        db.add(admin)
        db.flush()  # 获取 admin.id
    else:
        logger.debug("管理员账号已存在：%s", security_settings.admin_username)

    # 2. 创建或获取 default 企业空间
    default_space = db.execute(select(EnterpriseSpace).where(EnterpriseSpace.slug == "default")).scalar_one_or_none()
    
    if default_space is None:
        logger.info("创建 default 企业空间")
        default_space = EnterpriseSpace(
            name="default",
            slug="default",
            description="默认企业空间",
        )
        db.add(default_space)
        db.flush()  # 获取 default_space.id
    else:
        logger.debug("default 企业空间已存在")

    # 3. 创建或获取成员关系
    existing_membership = db.execute(
        select(Membership).where(
            Membership.user_id == admin.id,
            Membership.enterprise_space_id == default_space.id,
        )
    ).scalar_one_or_none()

    if existing_membership is None:
        logger.info("创建管理员与 default 企业空间的成员关系")
        membership = Membership(
            user_id=admin.id,
            enterprise_space_id=default_space.id,
            role="owner",
        )
        db.add(membership)
    else:
        logger.debug("成员关系已存在")

    db.commit()
    logger.info("企业空间与管理初始化完成")
