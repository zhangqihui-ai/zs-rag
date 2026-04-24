from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.provider_templates import MODEL_TYPE_SET, SUPPORTED_PROVIDER_CODES, get_provider_template, normalize_provider_code


class AuthFieldResponse(BaseModel):
    key: str
    label: str
    type: str
    required: bool


class ProviderTemplateResponse(BaseModel):
    provider_code: str
    provider_name: str
    deployment_type: str
    default_base_url: str
    supported_types: list[str]
    auth_type: str
    auth_fields: list[AuthFieldResponse]


class ProviderRequestBase(BaseModel):
    provider_code: str = Field(..., min_length=1, max_length=50)
    provider_name: str = Field(..., min_length=1, max_length=100)
    deployment_type: str = Field(default="public")
    base_url: str = Field(..., min_length=1, max_length=500)
    auth_type: str = Field(default="bearer", min_length=1, max_length=30)
    remark: str | None = Field(default=None, max_length=255)

    @field_validator("provider_code")
    @classmethod
    def validate_provider_code(cls, value: str) -> str:
        normalized = normalize_provider_code(value)
        if normalized not in SUPPORTED_PROVIDER_CODES and get_provider_template(value) is None:
            raise ValueError("不支持的 provider_code")
        return normalized

    @field_validator("deployment_type")
    @classmethod
    def validate_deployment_type(cls, value: str) -> str:
        if value not in {"public", "private"}:
            raise ValueError("deployment_type 仅支持 public 或 private")
        return value


class ProviderCreateRequest(ProviderRequestBase):
    auth_config: dict[str, Any] = Field(default_factory=dict)
    auto_sync_models: bool = True


class ProviderConnectionTestRequest(ProviderRequestBase):
    auth_config: dict[str, Any] = Field(default_factory=dict)


class ProviderUpdateRequest(BaseModel):
    provider_code: str | None = Field(default=None, min_length=1, max_length=50)
    provider_name: str | None = Field(default=None, min_length=1, max_length=100)
    deployment_type: str | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    auth_type: str | None = Field(default=None, min_length=1, max_length=30)
    auth_config: dict[str, Any] | None = None
    remark: str | None = Field(default=None, max_length=255)
    auto_sync_models: bool | None = None

    @field_validator("provider_code")
    @classmethod
    def validate_provider_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_provider_code(value)
        if normalized not in SUPPORTED_PROVIDER_CODES and get_provider_template(value) is None:
            raise ValueError("不支持的 provider_code")
        return normalized

    @field_validator("deployment_type")
    @classmethod
    def validate_deployment_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"public", "private"}:
            raise ValueError("deployment_type 仅支持 public 或 private")
        return value


class ProviderSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_code: str
    provider_name: str
    deployment_type: str
    base_url: str
    supported_types: list[str]
    sync_status: str
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None
    model_total: int
    enabled_model_total: int
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderDetailResponse(ProviderSummaryResponse):
    auth_type: str
    auth_fields: list[AuthFieldResponse]
    has_auth_config: bool


class ProviderSyncResponse(BaseModel):
    provider_id: int
    added: int
    updated: int
    disabled: int
    sync_status: str
    model_count: int


class ModelItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    provider_name: str
    provider_code: str
    model_code: str
    model_name: str
    model_type: str
    is_enabled: bool
    capabilities: list[str]
    context_window: int | None = None
    max_output_tokens: int | None = None
    is_default: bool = False
    raw_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ProviderModelsGroupResponse(BaseModel):
    provider_id: int
    provider_name: str
    provider_code: str
    deployment_type: str
    supported_types: list[str]
    sync_status: str
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None
    model_total: int
    enabled_model_total: int
    models: list[ModelItemResponse]


class ModelEnabledUpdateRequest(BaseModel):
    is_enabled: bool


class DefaultModelOptionResponse(BaseModel):
    model_id: int
    model_name: str
    provider_name: str


class DefaultsResponse(BaseModel):
    llm: DefaultModelOptionResponse | None = None
    embedding: DefaultModelOptionResponse | None = None
    rerank: DefaultModelOptionResponse | None = None
    tts: DefaultModelOptionResponse | None = None
    asr: DefaultModelOptionResponse | None = None
    vlm: DefaultModelOptionResponse | None = None
    moderation: DefaultModelOptionResponse | None = None
    ocr: DefaultModelOptionResponse | None = None


class BatchDefaultsUpdateRequest(BaseModel):
    llm: int | None = None
    embedding: int | None = None
    rerank: int | None = None
    tts: int | None = None
    asr: int | None = None
    vlm: int | None = None
    moderation: int | None = None
    ocr: int | None = None

    def to_mapping(self) -> dict[str, int | None]:
        return self.model_dump()


class SingleDefaultUpdateRequest(BaseModel):
    model_id: int | None = None


class ModelTypePath(BaseModel):
    model_type: str

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, value: str) -> str:
        if value not in MODEL_TYPE_SET:
            raise ValueError("不支持的 model_type")
        return value
