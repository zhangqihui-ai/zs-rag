from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.enterprise_space_context import RequireSystemAdmin
from app.core.errors import AppError
from app.db.session import engine
from app.schemas.system_components import ServiceComponentsStatusResponse
from app.services.system_component_service import collect_status

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
    return {
        "mineru": {
            "enabled": settings.mineru_enabled,
            "formats": formats,
        },
    }


@router.get("/system/components/status", response_model=ServiceComponentsStatusResponse)
def service_components_status(_user: RequireSystemAdmin) -> ServiceComponentsStatusResponse:
    return collect_status()
