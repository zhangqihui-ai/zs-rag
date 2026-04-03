from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: Any | None = None


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_payload(
    *,
    request: Request,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    payload = ErrorResponse(
        code=code,
        message=message,
        request_id=_request_id(request),
        details=details,
    )
    return payload.model_dump(exclude_none=True)


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request=request,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "SPACE_NOT_FOUND",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request=request,
            code=code_map.get(exc.status_code, "HTTP_ERROR"),
            message=str(exc.detail),
        ),
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request=request,
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            details=exc.errors(),
        ),
    )


async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            request=request,
            code="INTERNAL_ERROR",
            message="服务内部错误",
        ),
    )
