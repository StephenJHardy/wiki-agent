from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

ResultT = TypeVar("ResultT")


def retry_call(
    func: Callable[[], ResultT],
    *,
    attempts: int = 2,
    backoff_seconds: float = 0.5,
) -> ResultT:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(backoff_seconds * attempt)
    assert last_error is not None
    raise last_error
