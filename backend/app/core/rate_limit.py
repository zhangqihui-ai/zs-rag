"""简单滑动窗口限流（进程内；多实例需 Redis 扩展）。"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.embed_quota import check_embed_daily_quota
from app.core.config import get_settings

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, *, scope: str) -> str:
    client = request.client.host if request.client else "unknown"
    space = request.headers.get("X-Enterprise-Space", "default")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer zs_rag_embed_"):
        return f"{scope}:embed:{auth[-12:]}"
    return f"{scope}:space:{space}:{client}"


def check_rate_limit(request: Request, *, scope: str, limit_per_minute: int) -> None:
    if limit_per_minute <= 0:
        return
    key = _client_key(request, scope=scope)
    now = time.time()
    window_start = now - 60.0
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )
        bucket.append(now)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next):
        if self.settings.rate_limit_enabled:
            path = request.url.path
            if path.startswith("/api/v1/chat/completions") or path.startswith("/api/v1/openai/"):
                check_embed_daily_quota(request)
                check_rate_limit(
                    request,
                    scope="chat_api",
                    limit_per_minute=self.settings.chat_api_rate_limit_per_minute,
                )
            elif path.startswith("/auth/login"):
                check_rate_limit(
                    request,
                    scope="auth_login",
                    limit_per_minute=self.settings.auth_login_rate_limit_per_minute,
                )
        return await call_next(request)
