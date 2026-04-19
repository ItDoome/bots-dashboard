"""Telegram Login Widget payload verification.

Protocol (from https://core.telegram.org/widgets/login#checking-authorization):

    1. The widget sends query params: id, first_name, last_name, username,
       photo_url, auth_date, hash.
    2. Compute ``data_check_string``: all fields EXCEPT ``hash``, sorted
       alphabetically by key, joined as ``key=value\\n``.
    3. Secret key = ``sha256(bot_token)``.
    4. Expected hash = ``hmac_sha256(secret_key, data_check_string).hex()``.
    5. Compare expected hash with received hash in constant time.
    6. Verify ``auth_date`` isn't too old.

Implementation uses only the Python stdlib — no extra dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)


class TelegramAuthError(Exception):
    """Any failure during Telegram login verification."""


def verify_telegram_auth(
    params: dict[str, str],
    bot_token: str,
    max_age_sec: int = 900,
    now_ts: int | None = None,
) -> dict[str, str]:
    """Verify a Telegram Login Widget payload.

    Args:
        params: the query params dict from the ``/api/auth/telegram`` request.
            Must include ``hash``, ``auth_date`` and at least ``id``.
        bot_token: the bot's token from @BotFather.
        max_age_sec: reject if ``auth_date`` is older than this many seconds.
        now_ts: override "now" for tests.

    Returns:
        A copy of ``params`` with ``hash`` removed, values normalized to str.

    Raises:
        TelegramAuthError on any verification failure.
    """
    if not bot_token:
        raise TelegramAuthError("bot_token is empty — cannot verify")
    if not params:
        raise TelegramAuthError("empty params")

    # Copy + stringify so we don't mutate caller's dict.
    data = {k: str(v) for k, v in params.items() if v is not None}

    received_hash = data.pop("hash", "")
    if not received_hash:
        raise TelegramAuthError("missing hash")

    # auth_date is required and must be a recent int.
    raw_auth_date = data.get("auth_date", "")
    try:
        auth_date = int(raw_auth_date)
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError(f"auth_date not an integer: {raw_auth_date!r}") from exc

    now = now_ts if now_ts is not None else int(time.time())
    age = now - auth_date
    if age < -60:   # small clock skew allowed
        raise TelegramAuthError(f"auth_date is in the future by {-age}s")
    if age > max_age_sec:
        raise TelegramAuthError(f"auth_date expired ({age}s > {max_age_sec}s)")

    # Build data_check_string: lex-sorted, key=value joined by \n.
    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Constant-time compare.
    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning(
            "telegram auth: hash mismatch for tg_id=%r (expected prefix=%s, got prefix=%s)",
            data.get("id"),
            expected_hash[:8],
            received_hash[:8],
        )
        raise TelegramAuthError("invalid hash")

    # id must be a valid integer.
    try:
        int(data.get("id", ""))
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError(f"id not an integer: {data.get('id')!r}") from exc

    return data
