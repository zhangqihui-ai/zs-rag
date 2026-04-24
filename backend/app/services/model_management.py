from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.provider_adapter import fetch_provider_models
from app.core.provider_templates import MODEL_TYPE_ORDER, MODEL_TYPE_SET, get_provider_template, list_provider_templates
from app.models.model_management import AIModel, AIModelDefault, AIModelProvider
from app.schemas.model_management import (
    DefaultsResponse,
    ModelItemResponse,
    ProviderDetailResponse,
    ProviderModelsGroupResponse,
    ProviderSummaryResponse,
    ProviderSyncResponse,
)


def compact_auth_config(auth_config: dict[str, Any] | None) -> dict[str, Any]:
    auth_config = auth_config or {}
    return {
        key: value
        for key, value in auth_config.items()
        if value not in (None, "")
    }


def ensure_provider_unique(
    db: Session,
    *,
    space_id: int,
    provider_name: str,
    base_url: str,
    exclude_provider_id: int | None = None,
) -> None:
    stmt = select(AIModelProvider).where(
        AIModelProvider.enterprise_space_id == space_id,
        AIModelProvider.provider_name == provider_name,
        AIModelProvider.base_url == base_url,
    )
    if exclude_provider_id is not None:
        stmt = stmt.where(AIModelProvider.id != exclude_provider_id)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            status_code=409,
            code="PROVIDER_ALREADY_EXISTS",
            message="相同名称和地址的厂商配置已存在",
        )


def get_provider_or_error(db: Session, *, space_id: int, provider_id: int) -> AIModelProvider:
    provider = db.execute(
        select(AIModelProvider)
        .options(selectinload(AIModelProvider.models))
        .where(
            AIModelProvider.id == provider_id,
            AIModelProvider.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if provider is None:
        raise AppError(status_code=404, code="PROVIDER_NOT_FOUND", message="厂商配置不存在")
    return provider


def get_model_or_error(db: Session, *, space_id: int, model_id: int) -> AIModel:
    model = db.execute(
        select(AIModel)
        .options(selectinload(AIModel.provider))
        .where(
            AIModel.id == model_id,
            AIModel.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if model is None:
        raise AppError(status_code=404, code="MODEL_NOT_FOUND", message="模型不存在")
    return model


def _sorted_model_types(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return sorted(
        unique_values,
        key=lambda item: MODEL_TYPE_ORDER.index(item) if item in MODEL_TYPE_ORDER else len(MODEL_TYPE_ORDER),
    )


def _provider_supported_types(provider: AIModelProvider) -> list[str]:
    model_types = [model.model_type for model in provider.models if model.model_type in MODEL_TYPE_SET]
    if model_types:
        return _sorted_model_types(model_types)
    template = get_provider_template(provider.provider_code) or {}
    return _sorted_model_types(list(template.get("supported_types", [])))


def serialize_provider_summary(provider: AIModelProvider) -> dict[str, Any]:
    model_total = len(provider.models)
    enabled_model_total = len([model for model in provider.models if model.is_enabled])
    payload = ProviderSummaryResponse(
        id=provider.id,
        provider_code=provider.provider_code,
        provider_name=provider.provider_name,
        deployment_type=provider.deployment_type,
        base_url=provider.base_url,
        supported_types=_provider_supported_types(provider),
        sync_status=provider.sync_status,
        last_sync_at=provider.last_sync_at,
        last_sync_error=provider.last_sync_error,
        model_total=model_total,
        enabled_model_total=enabled_model_total,
        remark=provider.remark,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )
    return payload.model_dump()


def serialize_provider_detail(provider: AIModelProvider) -> dict[str, Any]:
    summary = serialize_provider_summary(provider)
    auth_fields = (get_provider_template(provider.provider_code) or {}).get("auth_fields", [])
    payload = ProviderDetailResponse(
        **summary,
        auth_type=provider.auth_type,
        auth_fields=auth_fields,
        has_auth_config=bool(provider.auth_config),
    )
    return payload.model_dump()


def list_provider_summaries(
    db: Session,
    *,
    space_id: int,
    keyword: str | None = None,
    deployment_type: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(AIModelProvider)
        .options(selectinload(AIModelProvider.models))
        .where(AIModelProvider.enterprise_space_id == space_id)
        .order_by(AIModelProvider.created_at.desc())
    )
    if keyword:
        stmt = stmt.where(
            or_(
                AIModelProvider.provider_name.ilike(f"%{keyword}%"),
                AIModelProvider.provider_code.ilike(f"%{keyword}%"),
            )
        )
    if deployment_type:
        stmt = stmt.where(AIModelProvider.deployment_type == deployment_type)
    providers = db.execute(stmt).scalars().all()
    return [serialize_provider_summary(provider) for provider in providers]


def serialize_model(model: AIModel, *, is_default: bool = False) -> dict[str, Any]:
    provider = model.provider
    payload = ModelItemResponse(
        id=model.id,
        provider_id=model.provider_id,
        provider_name=provider.provider_name,
        provider_code=provider.provider_code,
        model_code=model.model_code,
        model_name=model.model_name,
        model_type=model.model_type,
        is_enabled=model.is_enabled,
        capabilities=model.capabilities or [],
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        is_default=is_default,
        raw_payload=model.raw_payload,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
    return payload.model_dump()


def list_models(
    db: Session,
    *,
    space_id: int,
    view: str,
    provider_id: int | None = None,
    model_type: str | None = None,
    is_enabled: bool | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(AIModel)
        .join(AIModelProvider, AIModelProvider.id == AIModel.provider_id)
        .options(selectinload(AIModel.provider))
        .where(
            AIModel.enterprise_space_id == space_id,
            AIModelProvider.enterprise_space_id == space_id,
        )
        .order_by(AIModel.created_at.desc())
    )
    if provider_id is not None:
        stmt = stmt.where(AIModel.provider_id == provider_id)
    if model_type:
        stmt = stmt.where(AIModel.model_type == model_type)
    if is_enabled is not None:
        stmt = stmt.where(AIModel.is_enabled == is_enabled)
    if keyword:
        stmt = stmt.where(
            or_(
                AIModel.model_name.ilike(f"%{keyword}%"),
                AIModel.model_code.ilike(f"%{keyword}%"),
            )
        )

    models = db.execute(stmt).scalars().all()
    default_model_ids = set(
        db.execute(
            select(AIModelDefault.model_id).where(AIModelDefault.enterprise_space_id == space_id)
        ).scalars().all()
    )

    if view == "flat":
        return [serialize_model(model, is_default=model.id in default_model_ids) for model in models]

    grouped: dict[int, dict[str, Any]] = {}
    for model in models:
        provider = model.provider
        if provider.id not in grouped:
            grouped[provider.id] = {
                "provider_id": provider.id,
                "provider_name": provider.provider_name,
                "provider_code": provider.provider_code,
                "deployment_type": provider.deployment_type,
                "supported_types": _provider_supported_types(provider),
                "sync_status": provider.sync_status,
                "last_sync_at": provider.last_sync_at,
                "last_sync_error": provider.last_sync_error,
                "model_total": len(provider.models),
                "enabled_model_total": len([item for item in provider.models if item.is_enabled]),
                "models": [],
            }
        grouped[provider.id]["models"].append(serialize_model(model, is_default=model.id in default_model_ids))

    return [ProviderModelsGroupResponse(**item).model_dump() for item in grouped.values()]


def get_model_detail(db: Session, *, space_id: int, model_id: int) -> dict[str, Any]:
    model = get_model_or_error(db, space_id=space_id, model_id=model_id)
    is_default = db.execute(
        select(AIModelDefault).where(
            AIModelDefault.enterprise_space_id == space_id,
            AIModelDefault.model_id == model.id,
        )
    ).scalar_one_or_none() is not None
    return serialize_model(model, is_default=is_default)


def set_model_enabled(db: Session, *, space_id: int, model_id: int, is_enabled: bool) -> dict[str, Any]:
    model = get_model_or_error(db, space_id=space_id, model_id=model_id)
    if not is_enabled:
        default_binding = db.execute(
            select(AIModelDefault).where(
                AIModelDefault.enterprise_space_id == space_id,
                AIModelDefault.model_id == model.id,
            )
        ).scalar_one_or_none()
        if default_binding is not None:
            raise AppError(
                status_code=409,
                code="MODEL_IS_DEFAULT",
                message="该模型已被设为默认模型，请先调整默认模型后再禁用",
            )
    model.is_enabled = is_enabled
    db.flush()
    return {"id": model.id, "is_enabled": model.is_enabled}


def get_defaults(db: Session, *, space_id: int) -> dict[str, Any]:
    result = {model_type: None for model_type in MODEL_TYPE_ORDER}
    bindings = db.execute(
        select(AIModelDefault)
        .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
        .where(AIModelDefault.enterprise_space_id == space_id)
    ).scalars().all()

    for binding in bindings:
        if binding.model_type not in MODEL_TYPE_SET or binding.model is None:
            continue
        result[binding.model_type] = {
            "model_id": binding.model.id,
            "model_name": binding.model.model_name,
            "provider_name": binding.model.provider.provider_name,
        }
    return DefaultsResponse(**result).model_dump()


def _validate_default_target(db: Session, *, space_id: int, model_type: str, model_id: int | None) -> AIModel | None:
    if model_id is None:
        return None
    model = get_model_or_error(db, space_id=space_id, model_id=model_id)
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="只能将已启用模型设置为默认模型")
    if model.model_type != model_type:
        raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="默认模型类型与模型类型不匹配")
    return model


def save_defaults(db: Session, *, space_id: int, payload: dict[str, int | None]) -> None:
    existing = {
        item.model_type: item
        for item in db.execute(
            select(AIModelDefault).where(AIModelDefault.enterprise_space_id == space_id)
        ).scalars().all()
    }

    for model_type, model_id in payload.items():
        if model_type not in MODEL_TYPE_SET:
            continue
        _validate_default_target(db, space_id=space_id, model_type=model_type, model_id=model_id)
        current = existing.get(model_type)
        if model_id is None:
            if current is not None:
                db.delete(current)
            continue
        if current is None:
            db.add(AIModelDefault(enterprise_space_id=space_id, model_type=model_type, model_id=model_id))
        else:
            current.model_id = model_id

    db.flush()


def save_single_default(db: Session, *, space_id: int, model_type: str, model_id: int | None) -> dict[str, Any]:
    save_defaults(db, space_id=space_id, payload={model_type: model_id})
    return {"model_type": model_type, "model_id": model_id}


def sync_provider_models(
    db: Session,
    *,
    provider: AIModelProvider,
    raise_on_error: bool = True,
) -> dict[str, Any]:
    try:
        discovered_models = fetch_provider_models(provider)
    except Exception as exc:
        provider.sync_status = "failed"
        provider.last_sync_at = datetime.utcnow()
        provider.last_sync_error = str(exc)[:500]
        if raise_on_error:
            raise AppError(status_code=502, code="PROVIDER_SYNC_FAILED", message="同步模型失败，请检查厂商地址和认证信息") from exc
        return ProviderSyncResponse(
            provider_id=provider.id,
            added=0,
            updated=0,
            disabled=0,
            sync_status=provider.sync_status,
            model_count=0,
        ).model_dump()

    existing_models = {
        model.model_code: model
        for model in db.execute(
            select(AIModel).where(AIModel.provider_id == provider.id)
        ).scalars().all()
    }
    default_model_ids = set(
        db.execute(
            select(AIModelDefault.model_id).where(AIModelDefault.enterprise_space_id == provider.enterprise_space_id)
        ).scalars().all()
    )

    added = 0
    updated = 0
    disabled = 0
    discovered_codes: set[str] = set()

    for discovered in discovered_models:
        discovered_codes.add(discovered.model_code)
        current = existing_models.get(discovered.model_code)
        if current is None:
            current = AIModel(
                enterprise_space_id=provider.enterprise_space_id,
                provider_id=provider.id,
                model_code=discovered.model_code,
                model_name=discovered.model_name,
                model_type=discovered.model_type,
                capabilities=discovered.capabilities,
                is_enabled=False,
                context_window=discovered.context_window,
                max_output_tokens=discovered.max_output_tokens,
                raw_payload=discovered.raw_payload,
            )
            db.add(current)
            added += 1
        else:
            current.model_name = discovered.model_name
            current.model_type = discovered.model_type
            current.capabilities = discovered.capabilities
            current.context_window = discovered.context_window
            current.max_output_tokens = discovered.max_output_tokens
            current.raw_payload = discovered.raw_payload
            updated += 1

    for current in existing_models.values():
        if current.model_code in discovered_codes:
            continue
        if current.id in default_model_ids:
            continue
        if current.is_enabled:
            current.is_enabled = False
            disabled += 1

    provider.sync_status = "success"
    provider.last_sync_at = datetime.utcnow()
    provider.last_sync_error = None

    return ProviderSyncResponse(
        provider_id=provider.id,
        added=added,
        updated=updated,
        disabled=disabled,
        sync_status=provider.sync_status,
        model_count=len(discovered_models),
    ).model_dump()


def available_provider_templates(*, model_type: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
    return list_provider_templates(model_type=model_type, keyword=keyword)
