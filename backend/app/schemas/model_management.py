from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProviderConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Provider 名称")
    provider_type: str = Field(..., min_length=1, max_length=50, description="Provider 类型")
    base_url: str = Field(..., min_length=1, max_length=500, description="API 基础 URL")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    description: str | None = Field(None, max_length=1000, description="描述")


class ProviderConfigCreate(ProviderConfigBase):
    api_key: str = Field(..., min_length=1, description="API 密钥")
    config: dict | None = None


class ProviderConfigUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    base_url: str | None = Field(None, min_length=1, max_length=500)
    api_key: str | None = Field(None, min_length=1)  # 仅用于更新
    is_active: bool | None = None
    timeout_seconds: int | None = Field(None, ge=1, le=300)
    max_retries: int | None = Field(None, ge=0, le=10)
    config: dict | None = None
    description: str | None = Field(None, max_length=1000)


class ProviderConfigResponse(ProviderConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enterprise_space_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Note: api_key is never returned in responses for security


class ModelRefBase(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=200, description="模型名称")
    display_name: str | None = Field(None, max_length=200, description="显示名称")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    default_params: dict | None = None
    description: str | None = Field(None, max_length=1000, description="描述")


class ModelRefCreate(ModelRefBase):
    provider_id: int


class ModelRefUpdate(BaseModel):
    model_name: str | None = Field(None, min_length=1, max_length=200)
    display_name: str | None = Field(None, max_length=200)
    capabilities: list[str] | None = None
    is_active: bool | None = None
    default_params: dict | None = None
    description: str | None = Field(None, max_length=1000)


class ModelRefResponse(ModelRefBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enterprise_space_id: int
    provider_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProviderTestRequest(BaseModel):
    provider_id: int
    model_name: str | None = None
    prompt: str = Field(default="Hello", description="测试提示词")


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    response_time_ms: float | None = None
    model_name: str | None = None
