"""Shared pydantic DTOs used by both central app and agent.

These models define the wire format between the central dashboard app and
bot-specific agents. Both sides import from here to guarantee compatibility.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────
# Health and status
# ──────────────────────────────────────────────────────────────────────


class HealthStatus(str, Enum):
    ok = "ok"
    warning = "warning"
    error = "error"
    unknown = "unknown"


class ServiceState(str, Enum):
    active = "active"
    inactive = "inactive"
    activating = "activating"
    deactivating = "deactivating"
    failed = "failed"
    unknown = "unknown"


# ──────────────────────────────────────────────────────────────────────
# Metrics — flexible key-value pairs with optional formatting hints
# ──────────────────────────────────────────────────────────────────────


class MetricValue(BaseModel):
    """A single metric rendered on a BotCard or BotDetail page.

    Frontend picks the display based on ``unit`` and ``trend_delta``.
    """

    label: str
    value: str | int | float | None
    unit: str | None = None            # "R", "%", "items", "sec", ...
    trend_delta: str | int | float | None = None  # "+5", "-12%", etc.
    tooltip: str | None = None


# ──────────────────────────────────────────────────────────────────────
# Summary — what a BotCard on /dashboard shows
# ──────────────────────────────────────────────────────────────────────


class BotSummary(BaseModel):
    """Top-level summary returned by an adapter's ``summary()`` method."""

    slug: str
    status: ServiceState = ServiceState.unknown
    health: HealthStatus = HealthStatus.unknown
    uptime_sec: int | None = None
    last_heartbeat: str | None = None   # ISO-8601 or None
    primary_metrics: list[MetricValue] = Field(default_factory=list)  # shown on card
    secondary_metrics: list[MetricValue] = Field(default_factory=list)  # shown on detail only
    message: str | None = None          # short human-readable status blurb
    extra: dict[str, Any] | None = None  # adapter-specific structured data


# ──────────────────────────────────────────────────────────────────────
# Settings schema — describes editable fields for a bot
# ──────────────────────────────────────────────────────────────────────


class SettingFieldType(str, Enum):
    string = "string"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    enum = "enum"
    json = "json"


class SettingField(BaseModel):
    """One editable setting field. Maps 1:1 to a form control on the frontend.

    ``path`` is dot-notation into the underlying config file,
    e.g. ``"autosell_enabled"`` or ``"rate_limiter.working_limit_rpm"``.
    """

    path: str
    label: str
    type: SettingFieldType
    default: Any = None
    help: str | None = None
    enum_values: list[str] | None = None  # only for type=enum
    minimum: float | None = None          # only for integer/number
    maximum: float | None = None
    required: bool = False
    secret: bool = False                  # if True, never sent back to UI after save


class SettingsSection(BaseModel):
    """Group of related setting fields (e.g., "Autosell", "Autobuy")."""

    title: str
    description: str | None = None
    fields: list[SettingField]


class SettingsSchema(BaseModel):
    """Full schema describing editable settings for one bot."""

    sections: list[SettingsSection] = Field(default_factory=list)


class SettingsValues(BaseModel):
    """Current values of settings, keyed by path."""

    values: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Actions — explicit triggerable operations (restart, claim_now, etc.)
# ──────────────────────────────────────────────────────────────────────


class DangerLevel(str, Enum):
    low = "low"         # no confirmation needed
    medium = "medium"   # confirm dialog
    high = "high"       # confirm dialog + typed-word confirmation


class ActionDescriptor(BaseModel):
    """Describes a single action that can be triggered via the UI."""

    key: str                              # e.g. "restart_service", "claim_all_now"
    label: str                            # e.g. "Restart lolz-bot"
    description: str | None = None
    danger_level: DangerLevel = DangerLevel.low
    confirm_prompt: str | None = None     # extra text in confirm dialog
    params_schema: dict[str, Any] | None = None  # JSON schema for body (optional)
    estimated_duration_sec: int | None = None


class ActionResult(BaseModel):
    """Result of running an action."""

    ok: bool
    message: str | None = None
    output: str | None = None             # stdout / structured summary
    error: str | None = None              # redacted error message
    duration_sec: float | None = None


# ──────────────────────────────────────────────────────────────────────
# Logs
# ──────────────────────────────────────────────────────────────────────


class LogLevel(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class LogEntry(BaseModel):
    ts: str                 # ISO-8601
    level: LogLevel = LogLevel.info
    message: str
    source: str | None = None   # e.g. "systemd", "watcher", "autosell"


class LogsResponse(BaseModel):
    entries: list[LogEntry]
    next_cursor: str | None = None   # pass back to get older entries
    has_more: bool = False


# ──────────────────────────────────────────────────────────────────────
# Agent capabilities — what an agent can do (returned by /agent/capabilities)
# ──────────────────────────────────────────────────────────────────────


class AdapterCapabilities(BaseModel):
    """Describes what a specific adapter on an agent supports."""

    key: str                    # adapter_key, e.g. "lolz_bot"
    display_name: str
    icon: str | None = None
    supports_summary: bool = True
    supports_settings: bool = False
    supports_actions: bool = False
    supports_logs: bool = False
    action_keys: list[str] = Field(default_factory=list)   # legacy / quick list
    actions: list[ActionDescriptor] = Field(default_factory=list)   # full descriptors


class AgentCapabilities(BaseModel):
    """Top-level response from GET /agent/capabilities on each agent."""

    agent_id: str               # "server-a", "server-b"
    version: str                # git SHA or semver
    hostname: str | None = None
    adapters: list[AdapterCapabilities] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# Dashboard overview — aggregation of all plugins
# ──────────────────────────────────────────────────────────────────────


class PluginCardData(BaseModel):
    """Data shown on a single BotCard on /dashboard."""

    slug: str
    display_name: str
    icon: str
    host: str
    available: bool              # False if agent/plugin is currently unreachable
    summary: BotSummary | None = None
    error: str | None = None     # populated when available=False
    last_successful_at: str | None = None  # ISO-8601 of last good summary


class DashboardOverview(BaseModel):
    """Response shape for GET /api/dashboard/overview."""

    generated_at: str            # ISO-8601
    bots: list[PluginCardData]
    totals: dict[str, int | float] = Field(default_factory=dict)
    # totals examples: {"total_bots": 3, "errors": 0, "events_24h": 42}


# ──────────────────────────────────────────────────────────────────────
# Audit log
# ──────────────────────────────────────────────────────────────────────


class AuditStatus(str, Enum):
    queued = "queued"
    running = "running"
    ok = "ok"
    error = "error"
    timeout = "timeout"


class AuditEntry(BaseModel):
    id: int
    ts: str
    actor_tg_id: int
    actor_username: str | None = None
    plugin_slug: str | None = None
    action: str
    params_json: str | None = None   # redacted JSON string
    status: AuditStatus
    result_json: str | None = None   # redacted JSON string
    error_summary: str | None = None
    remote_host: str | None = None
    duration_sec: float | None = None


class AuditPage(BaseModel):
    entries: list[AuditEntry]
    page: int
    total: int
    page_size: int


# ──────────────────────────────────────────────────────────────────────
# Session / me
# ──────────────────────────────────────────────────────────────────────


class SessionUser(BaseModel):
    tg_id: int
    username: str | None = None
    first_name: str | None = None
    photo_url: str | None = None
    session_created_at: str
    session_expires_at: str


# ──────────────────────────────────────────────────────────────────────
# Error envelope
# ──────────────────────────────────────────────────────────────────────


class ApiError(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
