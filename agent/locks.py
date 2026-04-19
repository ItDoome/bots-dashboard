"""Per-action asyncio locks — prevent double-execution of mutating actions.

This only guards against concurrency INSIDE a single Python process. The
single-worker invariant (see plan §Security §7) is the reason it's enough
for v1. Break that invariant and these locks silently become useless.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict


class ActionBusy(Exception):
    """Raised when the same adapter+action is already running."""


_locks: dict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


def try_lock(adapter_key: str, action_key: str) -> asyncio.Lock:
    """Return the lock object for a given adapter+action combo.

    Caller should ``if lock.locked(): raise ActionBusy`` before ``await lock.acquire()``
    so the UI gets a clean 409 Conflict on double-click instead of queueing.
    """
    return _locks[(adapter_key, action_key)]
