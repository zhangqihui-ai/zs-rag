"""企业空间成员角色常量。"""

SPACE_ADMIN = "space_admin"
MEMBER = "member"

VALID_ROLES = frozenset({SPACE_ADMIN, MEMBER})

DEFAULT_MEMBER_ROLE = MEMBER
