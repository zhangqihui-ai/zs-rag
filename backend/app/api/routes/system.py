from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.enterprise_space_context import RequireSystemAdmin
from app.core.errors import AppError
from app.db.session import engine
from app.schemas.system_components import ComponentStatus, ServiceComponentsStatusResponse
from app.services.system_component_service import _probe_odl_hybrid, collect_status

router = APIRouter(tags=["system"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise AppError(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="数据库连接不可用",
        ) from exc

    return {
        "status": "ok",
        "database": "ok",
    }


@router.get("/system/parser-capabilities")
def parser_capabilities() -> dict[str, dict[str, object]]:
    settings = get_settings()
    formats = sorted(settings.mineru_format_set)
    # 探测 odl-hybrid sidecar 实时可用性，供前端决定是否允许勾选 Hybrid 模式
    hybrid_status, hybrid_message, _ = _probe_odl_hybrid(settings)
    hybrid_available = hybrid_status == ComponentStatus.alive
    return {
        "mineru": {
            "enabled": settings.mineru_enabled,
            "formats": formats,
        },
        "opendataloader": {
            "hybrid_available": hybrid_available,
            "hybrid_message": hybrid_message,
        },
    }


@router.get("/system/components/status", response_model=ServiceComponentsStatusResponse)
def service_components_status(_user: RequireSystemAdmin) -> ServiceComponentsStatusResponse:
    return collect_status()
