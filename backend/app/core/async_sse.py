"""将同步阻塞的 SSE 事件迭代卸到后台线程，避免长时间占用 asyncio 事件循环。"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

SyncEventIteratorFactory = Callable[[Session], Iterator[dict[str, Any]]]
AfterStreamHook = Callable[[Session], None]
ErrorEventBuilder = Callable[[Exception], dict[str, Any]]


def _sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def iter_sse_from_sync_iterator(
    request: Request | None,
    build_sync_iter: SyncEventIteratorFactory,
    *,
    after_stream: AfterStreamHook | None = None,
    trailing_chunks: list[bytes] | None = None,
    error_event_builder: ErrorEventBuilder | None = None,
) -> AsyncIterator[bytes]:
    """在独立线程中消费 build_sync_iter(db)，主协程仅 await 队列事件并写出 SSE。"""
    event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
    stop_event = threading.Event()

    def worker() -> None:
        db = SessionLocal()
        try:
            for event in build_sync_iter(db):
                if stop_event.is_set():
                    return
                event_queue.put(("event", event))
            if after_stream is not None:
                after_stream(db)
            event_queue.put(("done", None))
        except Exception as exc:
            event_queue.put(("error", exc))
        finally:
            db.close()

    threading.Thread(target=worker, daemon=True, name="sse-sync-worker").start()
    loop = asyncio.get_running_loop()
    try:
        while True:
            if request is not None and await request.is_disconnected():
                stop_event.set()
                break
            kind, payload = await loop.run_in_executor(None, event_queue.get)
            if kind == "done":
                break
            if kind == "error":
                event = (
                    error_event_builder(payload)
                    if error_event_builder is not None
                    else {"type": "error", "message": str(payload)}
                )
                err = json.dumps(event, ensure_ascii=False)
                yield f"data: {err}\n\n".encode("utf-8")
                break
            line = json.dumps(payload, ensure_ascii=False)
            yield f"data: {line}\n\n".encode("utf-8")
    finally:
        stop_event.set()

    for chunk in trailing_chunks or []:
        yield chunk


__all__ = ["_sse_headers", "iter_sse_from_sync_iterator"]
