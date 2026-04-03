from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="unknown")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next):
        header_name = self.settings.request_id_header
        request_id = request.headers.get(header_name) or str(uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        response.headers[header_name] = request_id
        return response


def get_request_id() -> str:
    return request_id_ctx.get()
