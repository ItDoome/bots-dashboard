import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "./client";
import type {
  ActionResult,
  AuditPage,
  BotSummary,
  DashboardOverview,
  LogsResponse,
  PluginListResponse,
  SessionUser,
  SettingsResponse,
} from "./types";

// Polling intervals — one place to tweak everything.
export const POLL_OVERVIEW_MS = 15_000;
export const POLL_SUMMARY_MS = 10_000;
export const POLL_LOGS_MS = 5_000;

export function useMe() {
  return useQuery<SessionUser>({
    queryKey: ["me"],
    queryFn: () => apiGet<SessionUser>("/api/me"),
    staleTime: 60_000,
    retry: false,
  });
}

export function useDashboardOverview() {
  return useQuery<DashboardOverview>({
    queryKey: ["dashboard", "overview"],
    queryFn: () => apiGet<DashboardOverview>("/api/dashboard/overview"),
    refetchInterval: POLL_OVERVIEW_MS,
    refetchIntervalInBackground: false,
  });
}

export function usePluginList() {
  return useQuery<PluginListResponse>({
    queryKey: ["plugins", "list"],
    queryFn: () => apiGet<PluginListResponse>("/api/plugins"),
    staleTime: 30_000,
  });
}

export function usePluginSummary(slug: string | undefined, enabled = true) {
  return useQuery<BotSummary>({
    queryKey: ["plugins", slug, "summary"],
    queryFn: () => apiGet<BotSummary>(`/api/plugins/${slug}/summary`),
    enabled: Boolean(slug) && enabled,
    refetchInterval: POLL_SUMMARY_MS,
    refetchIntervalInBackground: false,
  });
}

export function usePluginSettings(slug: string | undefined, enabled = true) {
  return useQuery<SettingsResponse>({
    queryKey: ["plugins", slug, "settings"],
    queryFn: () => apiGet<SettingsResponse>(`/api/plugins/${slug}/settings`),
    enabled: Boolean(slug) && enabled,
    staleTime: 30_000,
  });
}

export function useUpdateSettings(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Record<string, unknown>) =>
      apiPut<{ values: Record<string, unknown> }>(
        `/api/plugins/${slug}/settings`,
        patch,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plugins", slug] });
      qc.invalidateQueries({ queryKey: ["dashboard", "overview"] });
    },
  });
}

export function useRunAction(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { actionKey: string; params?: Record<string, unknown> }) =>
      apiPost<ActionResult>(
        `/api/plugins/${slug}/actions/${vars.actionKey}`,
        vars.params || {},
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plugins", slug] });
      qc.invalidateQueries({ queryKey: ["dashboard", "overview"] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export function usePluginLogs(
  slug: string | undefined,
  params: { cursor?: string; limit?: number } = {},
  enabled = true,
) {
  return useQuery<LogsResponse>({
    queryKey: ["plugins", slug, "logs", params.cursor ?? "", params.limit ?? 200],
    queryFn: () =>
      apiGet<LogsResponse>(`/api/plugins/${slug}/logs`, {
        cursor: params.cursor,
        limit: params.limit ?? 200,
      }),
    enabled: Boolean(slug) && enabled,
    refetchInterval: POLL_LOGS_MS,
    refetchIntervalInBackground: false,
  });
}

export function useAuditPage(page = 1, pageSize = 50, pluginSlug?: string) {
  return useQuery<AuditPage>({
    queryKey: ["audit", page, pageSize, pluginSlug ?? ""],
    queryFn: () =>
      apiGet<AuditPage>("/api/audit", {
        page,
        page_size: pageSize,
        plugin_slug: pluginSlug,
      }),
    staleTime: 10_000,
  });
}

export function useLogout() {
  return useMutation({
    mutationFn: () => apiPost("/api/auth/logout"),
    onSuccess: () => {
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    },
  });
}
