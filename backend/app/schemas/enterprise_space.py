import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_optional_email(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("邮箱格式不正确")
    trimmed = value.strip()
    if not trimmed:
        return None
    if not EMAIL_PATTERN.fullmatch(trimmed):
        raise ValueError("邮箱格式不正确")
    return trimmed


class EnterpriseSpaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="企业空间名称")
    slug: str = Field(..., min_length=1, max_length=100, description="企业空间标识")
    description: str | None = Field(None, max_length=500, description="企业空间描述")


class EnterpriseSpaceCreate(EnterpriseSpaceBase):
    pass


class EnterpriseSpaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class EnterpriseSpaceResponse(EnterpriseSpaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class EnterpriseSpaceWithRoleResponse(EnterpriseSpaceResponse):
    role: str


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255, description="邮箱（可选）")

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return normalize_optional_email(value)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class SpaceAssignment(BaseModel):
    enterprise_space_id: int
    role: str = Field(default="member", min_length=1, max_length=50)


class UserCreateRequest(UserCreate):
    is_admin: bool | None = None
    space_assignments: list[SpaceAssignment] | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, max_length=255)
    is_active: bool | None = None
    is_admin: bool | None = None
    password: str | None = Field(None, min_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return normalize_optional_email(value)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class MembershipSummary(BaseModel):
    enterprise_space_id: int
    role: str
    space: EnterpriseSpaceResponse


class UserDetailResponse(UserResponse):
    memberships: list[MembershipSummary] = Field(default_factory=list)
    is_bootstrap_admin: bool = False


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MembershipBase(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)


class MembershipCreate(MembershipBase):
    user_id: int
    enterprise_space_id: int


class MembershipResponse(MembershipBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    enterprise_space_id: int
    created_at: datetime


class MembershipWithUserResponse(MembershipResponse):
    user: UserResponse


class MembershipUpdate(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)


class UserMembershipAssign(BaseModel):
    assignments: list[SpaceAssignment]
