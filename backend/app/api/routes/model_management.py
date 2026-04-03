from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.core.provider_adapter import test_provider_connection
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace
from app.models.model_management import ModelRef, ProviderConfig
from app.schemas.model_management import (
    ModelRefCreate,
    ModelRefResponse,
    ModelRefUpdate,
    ProviderConfigCreate,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    ProviderTestResponse,
)

router = APIRouter(prefix="/providers", tags=["model-management"])


def _get_db() -> Session:
    """获取数据库会话"""
    db = next(get_db())
    try:
        return db
    finally:
        pass


@router.get("", response_model=list[ProviderConfigResponse])
def list_providers(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> list[ProviderConfigResponse]:
    """列出当前企业空间下的所有 Provider 配置"""
    providers = db.execute(
        select(ProviderConfig)
        .where(ProviderConfig.enterprise_space_id == current_space.id)
        .order_by(ProviderConfig.created_at.desc())
    ).scalars().all()

    return providers


@router.post("", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    provider_data: ProviderConfigCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ProviderConfigResponse:
    """创建新的 Provider 配置"""
    # 检查名称是否已存在
    existing = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.name == provider_data.name,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider_data.name}' 已存在",
        )

    provider = ProviderConfig(
        enterprise_space_id=current_space.id,
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        base_url=provider_data.base_url,
        api_key=provider_data.api_key,
        is_active=True,
        timeout_seconds=provider_data.timeout_seconds,
        max_retries=provider_data.max_retries,
        config=provider_data.config,
        description=provider_data.description,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    return provider


@router.get("/{provider_id}", response_model=ProviderConfigResponse)
def get_provider(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ProviderConfigResponse:
    """获取指定 Provider 配置详情"""
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    return provider


@router.patch("/{provider_id}", response_model=ProviderConfigResponse)
def update_provider(
    provider_id: int,
    provider_data: ProviderConfigUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ProviderConfigResponse:
    """更新 Provider 配置"""
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    update_data = provider_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(provider, field, value)

    db.commit()
    db.refresh(provider)

    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> None:
    """删除 Provider 配置"""
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    db.delete(provider)
    db.commit()


# Model Ref CRUD endpoints

@router.get("/{provider_id}/models", response_model=list[ModelRefResponse])
def list_models(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> list[ModelRefResponse]:
    """列出指定 Provider 下的所有模型"""
    # 验证 Provider 属于当前企业空间
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    models = db.execute(
        select(ModelRef)
        .where(ModelRef.provider_id == provider_id)
        .order_by(ModelRef.created_at.desc())
    ).scalars().all()

    return models


@router.post("/{provider_id}/models", response_model=ModelRefResponse, status_code=status.HTTP_201_CREATED)
def create_model(
    provider_id: int,
    model_data: ModelRefCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ModelRefResponse:
    """创建新的模型引用"""
    # 验证 Provider 属于当前企业空间
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    # 检查模型名称是否已存在
    existing = db.execute(
        select(ModelRef).where(
            ModelRef.model_name == model_data.model_name,
            ModelRef.provider_id == provider_id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"模型 '{model_data.model_name}' 已存在于该 Provider",
        )

    model = ModelRef(
        enterprise_space_id=current_space.id,
        provider_id=provider_id,
        model_name=model_data.model_name,
        display_name=model_data.display_name,
        capabilities=model_data.capabilities,
        is_active=True,
        default_params=model_data.default_params,
        description=model_data.description,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    return model


@router.patch("/{provider_id}/models/{model_id}", response_model=ModelRefResponse)
def update_model(
    provider_id: int,
    model_id: int,
    model_data: ModelRefUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ModelRefResponse:
    """更新模型配置"""
    model = db.execute(
        select(ModelRef).where(
            ModelRef.id == model_id,
            ModelRef.provider_id == provider_id,
            ModelRef.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在或不属于当前企业空间",
        )

    update_data = model_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)

    db.commit()
    db.refresh(model)

    return model


@router.delete("/{provider_id}/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    provider_id: int,
    model_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> None:
    """删除模型引用"""
    model = db.execute(
        select(ModelRef).where(
            ModelRef.id == model_id,
            ModelRef.provider_id == provider_id,
            ModelRef.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在或不属于当前企业空间",
        )

    db.delete(model)
    db.commit()


@router.post("/test", response_model=ProviderTestResponse)
def test_provider(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ProviderTestResponse:
    """测试 Provider 连接"""
    provider = db.execute(
        select(ProviderConfig).where(
            ProviderConfig.id == provider_id,
            ProviderConfig.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider 不存在或不属于当前企业空间",
        )

    result = test_provider_connection(provider)

    return ProviderTestResponse(
        success=result.success,
        message=result.message,
        response_time_ms=result.response_time_ms,
        model_name=result.model_name,
    )
