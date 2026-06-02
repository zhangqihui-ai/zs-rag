from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

TaskKey = tuple[int, int, int]


class DocumentProcessCancelled(Exception):
    """用户取消文档解析/重建时抛出。"""


@dataclass
class DocumentProcessTask:
    cancel_event: threading.Event
    thread: threading.Thread | None
    started_at: datetime
    key: TaskKey


_lock = threading.Lock()
_tasks: dict[TaskKey, DocumentProcessTask] = {}


def make_task_key(space_id: int, kb_id: int, document_id: int) -> TaskKey:
    return (space_id, kb_id, document_id)


def register_task(key: TaskKey, *, thread: threading.Thread, cancel_event: threading.Event | None = None) -> threading.Event:
    event = cancel_event or threading.Event()
    with _lock:
        _tasks[key] = DocumentProcessTask(
            cancel_event=event,
            thread=thread,
            started_at=datetime.now(timezone.utc),
            key=key,
        )
    return event


def unregister_task(key: TaskKey) -> None:
    with _lock:
        _tasks.pop(key, None)


def get_task(key: TaskKey) -> DocumentProcessTask | None:
    with _lock:
        return _tasks.get(key)


def request_cancel(key: TaskKey) -> bool:
    with _lock:
        task = _tasks.get(key)
        if task is None:
            return False
        task.cancel_event.set()
        return True


def wait_task_finished(key: TaskKey, *, timeout_sec: float = 5.0) -> bool:
    with _lock:
        task = _tasks.get(key)
        if task is None or task.thread is None:
            return True
        thread = task.thread
    thread.join(timeout=timeout_sec)
    with _lock:
        still = _tasks.get(key)
        if still is None:
            return True
        if still.thread is not None and still.thread.is_alive():
            return False
    return True


def cancel_force_and_wait(key: TaskKey, *, timeout_sec: float = 5.0) -> None:
    request_cancel(key)
    wait_task_finished(key, timeout_sec=timeout_sec)
    unregister_task(key)


def check_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DocumentProcessCancelled()


# 全局解析并发闸门：限制同时执行的解析/重建任务数，保护 CPU/内存与 DB 连接池。
_parse_semaphore_lock = threading.Lock()
_parse_semaphore: threading.BoundedSemaphore | None = None


def _get_parse_semaphore() -> threading.BoundedSemaphore:
    global _parse_semaphore
    if _parse_semaphore is not None:
        return _parse_semaphore
    with _parse_semaphore_lock:
        if _parse_semaphore is None:
            from app.core.config import get_settings

            limit = max(1, int(get_settings().doc_parse_max_concurrency))
            _parse_semaphore = threading.BoundedSemaphore(value=limit)
    return _parse_semaphore


def acquire_parse_slot(
    cancel_event: threading.Event | None,
    *,
    on_wait: Callable[[], None] | None = None,
    poll_interval: float = 1.0,
) -> None:
    """获取一个解析名额；满了则排队等待，期间可被取消。

    返回前需保证已获取名额；调用方务必在 finally 中调用 release_parse_slot()。
    """
    sem = _get_parse_semaphore()
    if sem.acquire(blocking=False):
        return
    if on_wait is not None:
        on_wait()
    while True:
        check_cancelled(cancel_event)
        if sem.acquire(timeout=poll_interval):
            return


def release_parse_slot() -> None:
    sem = _get_parse_semaphore()
    try:
        sem.release()
    except ValueError:
        # 释放次数多于获取次数时 BoundedSemaphore 会抛错，吞掉以免影响清理。
        pass
