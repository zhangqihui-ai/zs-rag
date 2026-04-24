from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

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
    """应用启动时执行初始化"""
    db = SessionLocal()
    try:
        initialize_admin_and_default_space(db)
    finally:
        db.close()
