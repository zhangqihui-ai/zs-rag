"""基于 Redis 的简易分布式锁（无 Redis 时退化为进程内互斥）。"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.config import get_settings
from app.core.errors import AppError

_local_locks: dict[str, threading.Lock] = {}
_local_guard = threading.Lock()


def _local_lock_for(key: str) -> threading.Lock:
    with _local_guard:
        lock = _local_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _local_locks[key] = lock
        return lock


@contextmanager
def acquire_distributed_lock(
    key: str,
    *,
    ttl_sec: int = 7200,
    wait_sec: float = 0.0,
    on_wait: Callable[[], None] | None = None,
) -> Iterator[None]:
    """获取分布式锁；wait_sec=0 时拿不到立即失败。"""
    settings = get_settings()
    redis_url = settings.redis_url
    if not redis_url:
        lock = _local_lock_for(key)
        if wait_sec <= 0:
            if not lock.acquire(blocking=False):
                raise AppError(
                    status_code=409,
                    code="RESOURCE_BUSY",
                    message="资源正被本机其他任务占用，请稍后重试",
                )
        else:
            deadline = time.monotonic() + wait_sec
            while True:
                if lock.acquire(blocking=False):
                    break
                if time.monotonic() >= deadline:
                    raise AppError(
                        status_code=409,
                        code="RESOURCE_BUSY",
                        message="等待资源锁超时，请稍后重试",
                    )
                if on_wait is not None:
                    on_wait()
                time.sleep(1.0)
        try:
            yield
        finally:
            lock.release()
        return

    import redis

    client = redis.from_url(redis_url, socket_connect_timeout=3.0)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, wait_sec)
    acquired = False
    while True:
        if client.set(key, token, nx=True, ex=max(1, int(ttl_sec))):
            acquired = True
            break
        if wait_sec <= 0 or time.monotonic() >= deadline:
            raise AppError(
                status_code=409,
                code="RESOURCE_BUSY",
                message="资源正被其他 worker 占用，请稍后重试",
            )
        if on_wait is not None:
            on_wait()
        time.sleep(1.5)

    try:
        yield
    finally:
        if acquired:
            release_script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            try:
                client.eval(release_script, 1, key, token)
            except Exception:
                pass
