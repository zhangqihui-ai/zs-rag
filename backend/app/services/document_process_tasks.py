from __future__ import annotations

import threading
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
