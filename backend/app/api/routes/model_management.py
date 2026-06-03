from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, CurrentUser, RequireMembership
from app.core.platform_audit_helper import audit_action
from app.core.errors import AppError
from app.core.provider_adapter import test_provider_connection
from app.core.provider_templates import MODEL_TYPE_SET, get_provider_template
from app.db.session import get_db
from app.models.model_management import AIModelProvider
from app.schemas.model_management import (
    BatchDefaultsUpdateRequest,
    ModelEnabledUpdateRequest,
    ProviderConnectionTestRequest,
    ProviderCreateRequest,
    ProviderUpdateRequest,
    SingleDefaultUpdateRequest,
)
from app.services.model_management import (
    available_provider_templates,
    compact_auth_config,
    ensure_provider_unique,
    get_defaults,
    get_model_detail,
    get_provider_or_error,
    list_models,
    list_provider_summaries,
    save_defaults,
    save_single_default,
    serialize_provider_detail,
    set_model_enabled,
    sync_provider_models,
)

router = APIRouter(prefix="/api/v1/ai-models", tags=["model-management"])


def ok_response(data: Any, *, message: str = "ok", status_code: int = status.HTTP_200_OK) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": 0, "message": message, "data": jsonable_encoder(data)},
    )


@router.get("/provider-templates")
def list_provider_templates(
    model_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> JSONResponse:
    if model_type and model_type not in MODEL_TYPE_SET:
        raise AppError(status_code=400, code="VALIDATION_ERROR", message="不支持的 model_type")
    return ok_response(available_provider_templates(model_type=model_type, keyword=keyword))


@router.get("/providers")
def list_providers(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    keyword: str | None = Query(default=None),
    deployment_type: str | None = Query(default=None),
) -> JSONResponse:
    if deployment_type and deployment_type not in {"public", "private"}:
        raise AppError(status_code=400, code="VALIDATION_ERROR", message="deployment_type 仅支持 public 或 private")
    providers = list_provider_summaries(
        db,
        space_id=current_space.id,
        keyword=keyword,
        deployment_type=deployment_type,
    )
    return ok_response(providers)


@router.post("/providers")
def create_provider(
    payload: ProviderCreateRequest,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    ensure_provider_unique(
        db,
        space_id=current_space.id,
        provider_name=payload.provider_name,
        base_url=payload.base_url,
    )
    template = get_provider_template(payload.provider_code) or {}
    provider = AIModelProvider(
        enterprise_space_id=current_space.id,
        provider_name=payload.provider_name,
        provider_code=payload.provider_code,
        deployment_type=payload.deployment_type,
        base_url=payload.base_url,
        auth_type=payload.auth_type or template.get("auth_type", "bearer"),
        auth_config=compact_auth_config(payload.auth_config),
        remark=payload.remark,
        sync_status="pending",
    )
    db.add(provider)
    db.flush()

    sync_result = {
        "provider_id": provider.id,
        "added": 0,
        "updated": 0,
        "disabled": 0,
        "sync_status": provider.sync_status,
        "model_count": 0,
    }
    if payload.auto_sync_models:
        sync_result = sync_provider_models(db, provider=provider, raise_on_error=False)

    db.commit()
    audit_action(
        db,
        request,
        action="model.provider.create",
        resource_type="ai_model_provider",
        resource_id=provider.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"provider_name": provider.provider_name},
    )
    db.commit()
    return ok_response(
        {
            "provider_id": provider.id,
            "provider_name": provider.provider_name,
            "sync_status": sync_result["sync_status"],
            "model_count": sync_result["model_count"],
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/providers/test-connection")
def test_provider_connection_draft(
    payload: ProviderConnectionTestRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
) -> JSONResponse:
    template = get_provider_template(payload.provider_code) or {}
    provider = AIModelProvider(
        enterprise_space_id=current_space.id,
        provider_name=payload.provider_name,
        provider_code=payload.provider_code,
        deployment_type=payload.deployment_type or template.get("deployment_type", "public"),
        base_url=payload.base_url,
        auth_type=payload.auth_type or template.get("auth_type", "bearer"),
        auth_config=compact_auth_config(payload.auth_config),
        remark=payload.remark,
        sync_status="pending",
    )
    result = test_provider_connection(provider)
    return ok_response(
        {
            "success": result.success,
            "message": result.message,
            "response_time_ms": result.response_time_ms,
            "model_name": result.model_name,
            "model_count": (result.data or {}).get("model_count"),
        }
    )


@router.get("/providers/{provider_id}")
def get_provider_detail(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    provider = get_provider_or_error(db, space_id=current_space.id, provider_id=provider_id)
    return ok_response(serialize_provider_detail(provider))


@router.put("/providers/{provider_id}")
def update_provider(
    provider_id: int,
    payload: ProviderUpdateRequest,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    provider = get_provider_or_error(db, space_id=current_space.id, provider_id=provider_id)

    next_name = payload.provider_name or provider.provider_name
    next_base_url = payload.base_url or provider.base_url
    ensure_provider_unique(
        db,
        space_id=current_space.id,
        provider_name=next_name,
        base_url=next_base_url,
        exclude_provider_id=provider.id,
    )

    if payload.provider_code is not None:
        provider.provider_code = payload.provider_code
        template = get_provider_template(payload.provider_code) or {}
        if payload.deployment_type is None:
            provider.deployment_type = template.get("deployment_type", provider.deployment_type)
        if payload.auth_type is None:
            provider.auth_type = template.get("auth_type", provider.auth_type)
    if payload.provider_name is not None:
        provider.provider_name = payload.provider_name
    if payload.deployment_type is not None:
        provider.deployment_type = payload.deployment_type
    if payload.base_url is not None:
        provider.base_url = payload.base_url
    if payload.auth_type is not None:
        provider.auth_type = payload.auth_type
    if payload.auth_config is not None:
        merged_auth_config = compact_auth_config(provider.auth_config)
        merged_auth_config.update(compact_auth_config(payload.auth_config))
        provider.auth_config = merged_auth_config
    if payload.remark is not None:
        provider.remark = payload.remark

    if payload.auto_sync_models:
        sync_provider_models(db, provider=provider, raise_on_error=False)

    db.commit()
    audit_action(
        db,
        request,
        action="model.provider.update",
        resource_type="ai_model_provider",
        resource_id=provider.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"provider_name": provider.provider_name},
    )
    db.commit()
    refreshed = get_provider_or_error(db, space_id=current_space.id, provider_id=provider.id)
    return ok_response(serialize_provider_detail(refreshed))


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    provider = get_provider_or_error(db, space_id=current_space.id, provider_id=provider_id)
    default_model = next((model for model in provider.models if model.defaults), None)
    if default_model is not None:
        raise AppError(
            status_code=409,
            code="PROVIDER_HAS_DEFAULT_MODEL",
            message="该厂商下仍有模型被设为默认模型，请先修改默认模型",
        )
    provider_name = provider.provider_name
    db.delete(provider)
    audit_action(
        db,
        request,
        action="model.provider.delete",
        resource_type="ai_model_provider",
        resource_id=provider_id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"provider_name": provider_name},
    )
    db.commit()
    return ok_response(True, message="deleted")


@router.post("/providers/{provider_id}/sync")
def sync_provider(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    provider = get_provider_or_error(db, space_id=current_space.id, provider_id=provider_id)
    try:
        result = sync_provider_models(db, provider=provider, raise_on_error=True)
    except AppError:
        db.commit()
        raise
    db.commit()
    return ok_response(result)


@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    provider = get_provider_or_error(db, space_id=current_space.id, provider_id=provider_id)
    result = test_provider_connection(provider)
    return ok_response(
        {
            "success": result.success,
            "message": result.message,
            "response_time_ms": result.response_time_ms,
            "model_name": result.model_name,
            "model_count": (result.data or {}).get("model_count"),
        }
    )


@router.get("/models")
def query_models(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    provider_id: int | None = Query(default=None),
    model_type: str | None = Query(default=None),
    is_enabled: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    view: str = Query(default="grouped"),
) -> JSONResponse:
    if view not in {"grouped", "flat"}:
        raise AppError(status_code=400, code="VALIDATION_ERROR", message="view 仅支持 grouped 或 flat")
    if model_type and model_type not in MODEL_TYPE_SET:
        raise AppError(status_code=400, code="VALIDATION_ERROR", message="不支持的 model_type")
    data = list_models(
        db,
        space_id=current_space.id,
        view=view,
        provider_id=provider_id,
        model_type=model_type,
        is_enabled=is_enabled,
        keyword=keyword,
    )
    return ok_response(data)


@router.get("/models/{model_id}")
def get_model(
    model_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    return ok_response(get_model_detail(db, space_id=current_space.id, model_id=model_id))


@router.patch("/models/{model_id}/enabled")
def update_model_enabled(
    model_id: int,
    payload: ModelEnabledUpdateRequest,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    result = set_model_enabled(db, space_id=current_space.id, model_id=model_id, is_enabled=payload.is_enabled)
    audit_action(
        db,
        request,
        action="model.enabled.update",
        resource_type="ai_model",
        resource_id=model_id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"is_enabled": payload.is_enabled},
    )
    db.commit()
    return ok_response(result)


@router.get("/defaults")
def get_default_models(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    return ok_response(get_defaults(db, space_id=current_space.id))


@router.put("/defaults")
def update_defaults(
    payload: BatchDefaultsUpdateRequest,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    save_defaults(db, space_id=current_space.id, payload=payload.to_mapping())
    audit_action(
        db,
        request,
        action="model.defaults.update",
        resource_type="ai_model_defaults",
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail=payload.to_mapping(),
    )
    db.commit()
    return ok_response(True, message="saved")


@router.put("/defaults/{model_type}")
def update_single_default(
    model_type: str,
    payload: SingleDefaultUpdateRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> JSONResponse:
    if model_type not in MODEL_TYPE_SET:
        raise AppError(status_code=400, code="VALIDATION_ERROR", message="不支持的 model_type")
    result = save_single_default(db, space_id=current_space.id, model_type=model_type, model_id=payload.model_id)
    db.commit()
    return ok_response(result)
