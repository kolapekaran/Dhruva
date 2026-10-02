"""Small process-local single-flight/cache helpers for expensive read-only computations."""
from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from typing import Callable, TypeVar

T = TypeVar("T")
_lock = threading.Lock()
_cache: dict[tuple, tuple[float, object]] = {}
_inflight: dict[tuple, Future] = {}


def get_or_compute(key: tuple, compute: Callable[[], T], ttl_seconds: float = 10.0) -> T:
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < ttl_seconds:
            return cached[1]  # type: ignore[return-value]
        future = _inflight.get(key)
        if future is None:
            future = Future()
            _inflight[key] = future
            owner = True
        else:
            owner = False

    if not owner:
        return future.result()

    try:
        value = compute()
        with _lock:
            _cache[key] = (time.monotonic(), value)
            _inflight.pop(key, None)
            future.set_result(value)
        return value
    except Exception as exc:
        with _lock:
            _inflight.pop(key, None)
            future.set_exception(exc)
        raise
