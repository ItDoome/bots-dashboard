"""HTTP client used by central app to call agents.

One pooled ``httpx.AsyncClient`` per host (looked up via ``config.AGENT_URLS``).
All mutations from central go through these methods — they attach the bearer
token, enforce short timeouts, and surface errors as typed exceptions that
the plugin layer can translate into UI-friendly responses.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app import config

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Something went wrong talking to or inside an agent."""
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AgentUnavailable(AgentError):
    """Agent is configured but unreachable / times out."""


class AgentClient:
    def __init__(self) -> None:
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    async def _client_for(self, host: str) -> httpx.AsyncClient:
        async with self._lock:
            existing = self._clients.get(host)
            if existing is not None and not existing.is_closed:
                return existing
            url = config.AGENT_URLS.get(host)
            if not url:
                raise AgentError(f"no AGENT_URL configured for host={host}")
            token = config.AGENT_TOKENS.get(host, "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            client = httpx.AsyncClient(
                base_url=url,
                headers=headers,
                timeout=httpx.Timeout(
                    connect=3.0,
                    read=float(config.AGENT_HTTP_TIMEOUT_SEC),
                    write=5.0,
                    pool=None,
                ),
            )
            self._clients[host] = client
            return client

    async def close(self) -> None:
        async with self._lock:
            for c in self._clients.values():
                try:
                    await c.aclose()
                except Exception:
                    pass
            self._clients.clear()

    # ──────────────────────────────────────────────────────────────
    # Primitive HTTP
    # ──────────────────────────────────────────────────────────────

    async def get(self, host: str, path: str, **kwargs: Any) -> Any:
        client = await self._client_for(host)
        try:
            resp = await client.get(path, **kwargs)
        except httpx.HTTPError as exc:
            raise AgentUnavailable(f"GET {host}{path}: {exc!r}") from exc
        return self._decode(resp, f"GET {host}{path}")

    async def put(self, host: str, path: str, json: Any = None, **kwargs: Any) -> Any:
        client = await self._client_for(host)
        try:
            resp = await client.put(path, json=json, **kwargs)
        except httpx.HTTPError as exc:
            raise AgentUnavailable(f"PUT {host}{path}: {exc!r}") from exc
        return self._decode(resp, f"PUT {host}{path}")

    async def post(self, host: str, path: str, json: Any = None, **kwargs: Any) -> Any:
        client = await self._client_for(host)
        try:
            resp = await client.post(path, json=json, **kwargs)
        except httpx.HTTPError as exc:
            raise AgentUnavailable(f"POST {host}{path}: {exc!r}") from exc
        return self._decode(resp, f"POST {host}{path}")

    @staticmethod
    def _decode(resp: httpx.Response, context: str) -> Any:
        if 200 <= resp.status_code < 300:
            try:
                return resp.json()
            except Exception as exc:
                raise AgentError(
                    f"{context} returned non-JSON body ({resp.status_code}): {exc!r}",
                    status=resp.status_code,
                )
        body_preview = (resp.text or "")[:300]
        if resp.status_code == 409:
            raise AgentError(f"{context}: conflict — {body_preview}", status=409)
        raise AgentError(
            f"{context} failed http={resp.status_code}: {body_preview}",
            status=resp.status_code,
        )


# Singleton used across the process (single-worker invariant).
_client_singleton: AgentClient | None = None


def get_client() -> AgentClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AgentClient()
    return _client_singleton
