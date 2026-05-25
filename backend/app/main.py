import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    handle_app_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)
from app.core.initialization import initialize_admin_and_default_space
from app.core.request_context import RequestContextMiddleware
from app.db.session import SessionLocal

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.normalized_cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, handle_app_error)
app.add_exception_handler(HTTPException, handle_http_exception)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(Exception, handle_unexpected_error)
app.include_router(api_router)


@app.on_event("startup")
def startup_event():
    """应用启动时执行初始化（数据库未就绪时短暂重试，避免 compose 启动竞态）"""
    logger.info(
        "MinerU 配置：enabled=%s base_url=%s",
        settings.mineru_enabled,
        settings.mineru_base_url,
    )
    delay_sec = 1.0
    max_attempts = 12
    last_error: OperationalError | None = None
    for attempt in range(1, max_attempts + 1):
        db = SessionLocal()
        try:
            initialize_admin_and_default_space(db)
            if attempt > 1:
                logger.info("数据库初始化在第 %s 次重试后成功", attempt)
            return
        except OperationalError as exc:
            last_error = exc
            db.rollback()
            if attempt >= max_attempts:
                break
            logger.warning(
                "数据库暂不可用（%s/%s），%ss 后重试: %s",
                attempt,
                max_attempts,
                delay_sec,
                exc,
            )
            time.sleep(delay_sec)
            delay_sec = min(delay_sec * 1.5, 5.0)
        finally:
            db.close()
    if last_error is not None:
        raise last_error
