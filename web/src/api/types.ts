// These match shared/models.py on the backend. Keep in sync manually for v1.

export type HealthStatus = "ok" | "warning" | "error" | "unknown";
export type ServiceState =
  | "active"
  | "inactive"
  | "activating"
  | "deactivating"
  | "failed"
  | "unknown";
export type DangerLevel = "low" | "medium" | "high";
export type LogLevel = "debug" | "info" | "warning" | "error" | "critical";
export type AuditStatus = "queued" | "running" | "ok" | "error" | "timeout";

export interface MetricValue {
  label: string;
  value: string | number | null;
  unit?: string | null;
  trend_delta?: string | number | null;
  tooltip?: string | null;
}

export interface BotSummary {
  slug: string;
  status: ServiceState;
  health: HealthStatus;
  uptime_sec?: number | null;
  last_heartbeat?: string | null;
  primary_metrics: MetricValue[];
  secondary_metrics: MetricValue[];
  message?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface ValshopData {
  ok: boolean;
  tg_user_id?: number;
  riot_username?: string | null;
  region?: string;
  error?: string;
  wallet?: { vp: number; rad: number; kc: number };
  daily?: {
    remaining_sec: number;
    items: { name: string; tier: string; cost_vp: number; icon: string | null; owned: boolean }[];
  };
  bundle?: {
    name: string; base: number; discounted: number; pct: number; remaining_sec: number;
    icon: string | null;
    items?: { name: string; icon: string | null; kind: string; qty: number; base: number; discounted: number; pct: number; tier?: string }[];
  };
  plugins?: { base: number; discounted: number; pct: number; items: number }[];
  accessories?: {
    remaining_sec: number;
    items: { name: string; kind: string; qty: number; cost_kc: number; icon?: string | null }[];
  };
  night_market?: {
    remaining_sec: number;
    items: { name: string; base: number; discounted: number; pct: number; icon: string | null }[];
  };
  inventory?: {
    total: number;
    unique_skins?: number;
    total_levels?: number;
    estimated_vp: number;
    known_prices_count?: number;
    tiers: Record<string, number>;
    recent: { name: string; icon: string; tier: string; vp: number; vp_actual?: boolean; is_bp?: boolean; is_contract?: boolean; is_melee?: boolean; is_bundle?: boolean; bundle_group?: string | null }[];
    all?: { name: string; icon: string; tier: string; vp: number; vp_actual?: boolean; is_bp?: boolean; is_contract?: boolean; is_melee?: boolean; is_bundle?: boolean; bundle_group?: string | null }[];
  };
  collection?: {
    sprays: { total: number; items: { uuid: string; name: string; icon: string | null }[] };
    buddies: { total: number; items: { uuid: string; name: string; icon: string | null }[] };
    cards: {
      total: number;
      items: {
        uuid: string; name: string; icon: string | null;
        large?: string | null; wide?: string | null;
      }[];
    };
    titles: { total: number; items: { uuid: string; name: string; text: string }[] };
  };
  history?: {
    date: string;
    items: { name: string; tier: string; cost_vp: number; icon: string | null }[];
  }[];
}

export interface MonopolyData {
  share_pct: number;
  my_count: number;
  total_count: number;
  mayo_count: number;
  mayo_oldest_days: number;
  price_distribution: Record<string, number>;
  sellers: Record<string, number>;
  new_competitors_7d: Record<string, number>;
  sold_24h: number;
  revenue_24h: number;
  sold_7d_avg: number;
  revenue_7d: number;
}

export interface PluginCardData {
  slug: string;
  display_name: string;
  icon: string;
  host: string;
  available: boolean;
  summary?: BotSummary | null;
  error?: string | null;
  last_successful_at?: string | null;
}

export interface DashboardOverview {
  generated_at: string;
  bots: PluginCardData[];
  totals: Record<string, number>;
}

export interface AdapterCapabilities {
  key: string;
  display_name: string;
  icon?: string | null;
  supports_summary: boolean;
  supports_settings: boolean;
  supports_actions: boolean;
  supports_logs: boolean;
  action_keys: string[];
  actions: ActionDescriptor[];
}

export interface PluginListItem {
  slug: string;
  display_name: string;
  icon: string;
  host: string;
  adapter_key: string;
  available: boolean;
  last_error?: string | null;
  capabilities?: AdapterCapabilities | null;
}

export interface PluginListResponse {
  plugins: PluginListItem[];
  hosts: Record<
    string,
    {
      available: boolean;
      last_seen_at: number;
      last_error: string | null;
      agent_version: string | null;
    }
  >;
}

export interface SettingField {
  path: string;
  label: string;
  type: "string" | "integer" | "number" | "boolean" | "enum" | "json";
  default?: unknown;
  help?: string | null;
  enum_values?: string[] | null;
  minimum?: number | null;
  maximum?: number | null;
  required?: boolean;
  secret?: boolean;
}

export interface SettingsSection {
  title: string;
  description?: string | null;
  fields: SettingField[];
}

export interface SettingsSchema {
  sections: SettingsSection[];
}

export interface SettingsValues {
  values: Record<string, unknown>;
}

export interface SettingsResponse {
  schema: SettingsSchema;
  values: SettingsValues;
}

export interface ActionDescriptor {
  key: string;
  label: string;
  description?: string | null;
  danger_level: DangerLevel;
  confirm_prompt?: string | null;
  params_schema?: Record<string, unknown> | null;
  estimated_duration_sec?: number | null;
}

export interface ActionResult {
  ok: boolean;
  message?: string | null;
  output?: string | null;
  error?: string | null;
  duration_sec?: number | null;
}

export interface LogEntry {
  ts: string;
  level: LogLevel;
  message: string;
  source?: string | null;
}

export interface LogsResponse {
  entries: LogEntry[];
  next_cursor?: string | null;
  has_more: boolean;
}

export interface SessionUser {
  tg_id: number;
  username?: string | null;
  first_name?: string | null;
  photo_url?: string | null;
  session_created_at: string;
  session_expires_at: string;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor_tg_id: number;
  actor_username?: string | null;
  plugin_slug?: string | null;
  action: string;
  params_json?: string | null;
  status: AuditStatus;
  result_json?: string | null;
  error_summary?: string | null;
  remote_host?: string | null;
  duration_sec?: number | null;
}

export interface AuditPage {
  entries: AuditEntry[];
  page: number;
  total: number;
  page_size: number;
}
