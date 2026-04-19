"""Atomic file read/merge/write with advisory locking.

Every state/config file managed by the agent is protected by an fcntl lock
on a sibling ``.lock`` file. The lock is held for the full read→merge→write
sequence, so concurrent callers (and the bot itself, if it also flocks)
never see a half-written file.

Backups of the previous contents are dropped into ``config.BACKUP_DIR`` and
rotated (latest ``BACKUP_KEEP`` kept).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from agent import config

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SEC = 5.0


# fcntl is Linux-only; on Windows during local development we fall back to
# "no locking" which is fine for tests.
try:
    import fcntl  # type: ignore[import-not-found]
    _HAS_FCNTL = True
except ImportError:   # Windows dev
    _HAS_FCNTL = False
    fcntl = None     # type: ignore


class FileLockTimeout(Exception):
    pass


@contextmanager
def file_lock(target: Path) -> Iterator[None]:
    """Acquire an exclusive lock on ``<target>.lock``."""
    lock_path = target.with_suffix(target.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if _HAS_FCNTL:
            deadline = time.monotonic() + LOCK_TIMEOUT_SEC
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        raise FileLockTimeout(f"lock busy: {lock_path}")
                    time.sleep(0.1)
        yield
    finally:
        try:
            if _HAS_FCNTL:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except Exception:
            pass


def _backup(target: Path) -> None:
    if not target.exists():
        return
    try:
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        safe_name = target.name.replace("/", "_")
        dest = config.BACKUP_DIR / f"{ts}-{safe_name}"
        shutil.copy2(target, dest)
        # rotate — keep latest N
        existing = sorted(
            config.BACKUP_DIR.glob(f"*-{safe_name}"),
            reverse=True,
        )
        for old in existing[config.BACKUP_KEEP:]:
            try:
                old.unlink()
            except OSError:
                pass
    except Exception as exc:
        logger.warning("backup failed for %s: %r", target, exc)


def read_json(target: Path) -> Any:
    """Read a JSON file under lock. Returns ``None`` if the file is missing."""
    if not target.exists():
        return None
    with file_lock(target):
        return json.loads(target.read_text(encoding="utf-8"))


def _deep_merge(base: Any, patch: Any) -> Any:
    """Recursively merge ``patch`` into ``base``. Patches win for leaves."""
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    return patch


def patch_json(
    target: Path,
    patch: dict[str, Any],
    *,
    whitelist: set[str] | None = None,
) -> dict[str, Any]:
    """Deep-merge ``patch`` into the JSON file at ``target``.

    If ``whitelist`` is provided, only keys in it may be updated — anything
    else raises ``ValueError``. ``whitelist`` is flat (no nested paths); for
    v1 we keep the schema flat.

    Returns the new full contents as a dict.
    """
    if whitelist is not None:
        bad_keys = set(patch.keys()) - whitelist
        if bad_keys:
            raise ValueError(f"keys not whitelisted: {sorted(bad_keys)}")

    with file_lock(target):
        current: dict[str, Any] = {}
        if target.exists():
            try:
                current = json.loads(target.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError(f"unable to parse current {target}: {exc!r}")
            if not isinstance(current, dict):
                raise RuntimeError(f"{target} is not a JSON object")

        _backup(target)
        merged = _deep_merge(current, patch)

        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, target)

    return merged


def read_text(target: Path, max_bytes: int = 1_000_000) -> str:
    """Read plain text file under lock. Caps size to avoid OOM on huge logs."""
    if not target.exists():
        return ""
    with file_lock(target):
        raw = target.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
        return raw.decode("utf-8", errors="replace")
