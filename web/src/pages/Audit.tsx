import { useState } from "react";
import { Shell } from "@/components/layout/Shell";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuditPage } from "@/api/hooks";
import { formatRelative } from "@/lib/dates";

export default function Audit() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAuditPage(page, 50);

  return (
    <Shell>
      <h1 className="font-display text-3xl font-semibold text-ink-900">
        Audit log
      </h1>
      <p className="mt-1 text-sm text-ink-500">
        Каждое изменение и каждое действие — с редактированными секретами.
      </p>

      <Card className="mt-6">
        <CardContent className="p-0">
          {isLoading && <div className="p-6 text-sm text-ink-500">loading…</div>}
          {error && <div className="p-6 text-sm text-red-700">error: {String(error)}</div>}
          {data && (
            <table className="w-full text-sm">
              <thead className="border-b border-ink-200 bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Plugin</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((e) => (
                  <tr
                    key={e.id}
                    className="border-b border-ink-100 last:border-0"
                  >
                    <td className="px-4 py-3 whitespace-nowrap text-ink-500">
                      {formatRelative(e.ts)}
                    </td>
                    <td className="px-4 py-3 font-medium text-ink-900">
                      {e.actor_username || e.actor_tg_id}
                    </td>
                    <td className="px-4 py-3 text-ink-700">
                      {e.plugin_slug || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <code className="rounded bg-ink-100 px-1.5 py-0.5 text-xs">
                        {e.action}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-500">
                      {e.error_summary ? (
                        <span className="text-red-700">
                          {e.error_summary.slice(0, 100)}
                        </span>
                      ) : e.duration_sec != null ? (
                        <>{e.duration_sec.toFixed(1)}s</>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
                {data.entries.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-ink-500">
                      Пусто
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-between text-sm text-ink-500">
          <span>
            {(data.page - 1) * data.page_size + 1}–
            {Math.min(data.page * data.page_size, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              disabled={data.page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-full border border-ink-200 px-3 py-1 text-xs hover:bg-ink-100 disabled:opacity-50"
            >
              Prev
            </button>
            <button
              disabled={data.page * data.page_size >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-full border border-ink-200 px-3 py-1 text-xs hover:bg-ink-100 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}

function StatusBadge({
  status,
}: {
  status: "queued" | "running" | "ok" | "error" | "timeout";
}) {
  if (status === "ok")
    return (
      <Badge variant="success">
        ok
      </Badge>
    );
  if (status === "error" || status === "timeout")
    return <Badge variant="error">{status}</Badge>;
  if (status === "running") return <Badge variant="warning">{status}</Badge>;
  return <Badge variant="muted">{status}</Badge>;
}
