"""Simple progress heartbeat for long handbook parse runs."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def heartbeat(
    say: Callable[[str], None],
    label: str,
    *,
    interval_s: float = 30.0,
) -> Iterator[None]:
    """Call ``say(label + ' still running…')`` every ``interval_s`` until exit."""
    stop = threading.Event()

    def _loop() -> None:
        while not stop.wait(interval_s):
            say(f"{label} still running…")

    thread = threading.Thread(target=_loop, name=f"heartbeat:{label}", daemon=True)
    thread.start()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1.0)
        _ = t0
