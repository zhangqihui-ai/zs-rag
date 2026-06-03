"""Embed API Key 日配额检查。"""

from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_lock = threading.Lock()
_daily_counts: dict[str, tuple[str, int]] = {}


def _daily_key(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer zs_rag_embed_"):
        return None
    return auth[-24:]


def check_embed_daily_quota(request: Request) -> None:
    settings = get_settings()
    limit = int(settings.embed_api_key_daily_quota or 0)
    if limit <= 0:
        return
    key = _daily_key(request)
    if not key:
        return
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with _lock:
        stored_day, count = _daily_counts.get(key, (day, 0))
        if stored_day != day:
            stored_day, count = day, 0
        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Embed API Key 日调用配额已用尽",
            )
        _daily_counts[key] = (stored_day, count + 1)
