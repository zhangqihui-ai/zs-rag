from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


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


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    is_active: bool | None = None
    is_admin: bool | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


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
