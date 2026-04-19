"""Redact sensitive values before writing to audit log or returning to UI.

Any dict key matching SENSITIVE_KEY_PATTERN has its value replaced with the
redaction marker. Walk is recursive but depth-limited to protect against
pathological inputs.

Usage:
    >>> redact({'password': 'secret123', 'login': 'admin'})
    {'password': '***REDACTED***', 'login': 'admin'}

The ``redact_text`` helper also masks Telegram bot tokens found anywhere in a
string — useful when a subprocess stack trace bleeds a token into the message.
"""
from __future__ import annotations

import re
from typing import Any

REDACTION_MARKER = "***REDACTED***"

# Match keys like: password, api_key, access-token, cookie, secret_key, authorization, ...
SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[-_ ]?key|authorization|cookie|session|"
    r"dsn|database[-_ ]?url|proxy[-_ ]?password|private[-_ ]?key|bearer|hash)",
    re.IGNORECASE,
)

# Telegram bot token shape: <digits>:<alnum_underscore_dash>+ of length > 25
TG_TOKEN_PATTERN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")

# Generic bearer/api-key hex-ish blobs longer than 32 chars
LONG_HEX_TOKEN_PATTERN = re.compile(r"\b[A-Fa-f0-9]{32,}\b")

MAX_RECURSION_DEPTH = 8


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    return bool(SENSITIVE_KEY_PATTERN.search(key))


def redact(value: Any, depth: int = 0) -> Any:
    """Return a deep-copied version of ``value`` with sensitive fields masked.

    Dicts: keys matching ``SENSITIVE_KEY_PATTERN`` have values replaced.
    Lists/tuples: recurse into elements.
    Strings: masks embedded Telegram tokens.
    Other scalars: passed through unchanged.
    """
    if depth > MAX_RECURSION_DEPTH:
        return "<truncated: depth limit>"

    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                if v is None or v == "":
                    out[k] = v
                else:
                    out[k] = REDACTION_MARKER
            else:
                out[k] = redact(v, depth + 1)
        return out

    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value]

    if isinstance(value, tuple):
        return tuple(redact(item, depth + 1) for item in value)

    if isinstance(value, str):
        return redact_text(value)

    return value


def redact_text(s: str) -> str:
    """Mask Telegram bot tokens / long hex blobs embedded in freeform text."""
    if not s:
        return s
    s = TG_TOKEN_PATTERN.sub(REDACTION_MARKER, s)
    # Only mask long hex if it looks like a token (isolated word). Skip if the
    # surrounding context suggests it's a hash intentionally being displayed
    # (e.g. git SHAs, which are shorter).
    s = LONG_HEX_TOKEN_PATTERN.sub(REDACTION_MARKER, s)
    return s


def redact_error_message(exc: BaseException) -> str:
    """Get a safe short representation of an exception.

    Uses the type name + str(exc) with text-level redaction. Never includes
    the traceback — those belong in journalctl only.
    """
    msg = f"{type(exc).__name__}: {exc}"
    return redact_text(msg)[:500]
