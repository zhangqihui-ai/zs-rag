import threading

import pytest

from app.core.distributed_lock import acquire_distributed_lock
from app.core.errors import AppError


def test_local_distributed_lock_serializes_access() -> None:
    order: list[int] = []

    def worker(value: int) -> None:
        with acquire_distributed_lock("test-lock", wait_sec=5.0):
            order.append(value)

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert sorted(order) == [1, 2]


def test_local_distributed_lock_fails_fast_when_busy() -> None:
    with acquire_distributed_lock("test-lock-busy", wait_sec=0.0):
        with pytest.raises(AppError) as exc:
            with acquire_distributed_lock("test-lock-busy", wait_sec=0.0):
                pass
    assert exc.value.code == "RESOURCE_BUSY"
