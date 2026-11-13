"""Simple progress heartbeat for long handbook parse runs."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


@contextmanager
def heartbeat(
    say: Callable[[str], None],
    label: str,
    *,
    interval_s: float = 30.0,
) -> Iterator[None]:
    """Print ``label still running (Ns)…`` every ``interval_s`` until the block exits."""
    stop = threading.Event()
    started = time.perf_counter()

    def _loop() -> None:
        while not stop.wait(interval_s):
            elapsed = time.perf_counter() - started
            say(f"{label} still running ({elapsed:.0f}s)…")

    thread = threading.Thread(target=_loop, name=f"heartbeat:{label}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1.0)
