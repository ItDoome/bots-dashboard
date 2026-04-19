/** Thin fetch wrapper used by all React Query hooks.
 *
 * Adds CSRF header + Content-Type for mutating methods, sends credentials
 * (so the session cookie is included), and routes 401 back to the landing
 * page so a stale tab doesn't silently fail.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super(`HTTP ${status}: ${body.slice(0, 200)}`);
    this.status = status;
    this.body = body;
  }
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (MUTATING.has(method)) {
    headers.set("X-Dashboard-Request", "1");
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  const resp = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: "include",
  });

  if (resp.status === 401) {
    // Session is gone — back to landing page.
    if (typeof window !== "undefined" && window.location.pathname !== "/") {
      window.location.href = "/";
    }
    throw new ApiError(401, "unauthenticated");
  }

  const text = await resp.text();
  if (!resp.ok) {
    throw new ApiError(resp.status, text);
  }
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  let url = path;
  if (params) {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join("&");
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }
  return apiFetch<T>(url, { method: "GET" });
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
}
