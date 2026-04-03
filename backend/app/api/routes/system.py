from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from fastapi import APIRouter

from app.core.errors import AppError
from app.db.session import engine

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
