import { Shell } from "@/components/layout/Shell";
import { BotCard } from "@/components/dashboard/BotCard";
import { Card } from "@/components/ui/card";
import { useDashboardOverview } from "@/api/hooks";
import { formatRelative } from "@/lib/dates";
import { AlertCircle } from "lucide-react";

export default function Dashboard() {
  const { data, error, isLoading } = useDashboardOverview();

  return (
    <Shell>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink-900">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Все твои боты — один взгляд.
          </p>
        </div>
        {data && (
          <div className="text-xs text-ink-500">
            обновлено {formatRelative(data.generated_at)}
          </div>
        )}
      </div>

      {/* Top stat tiles */}
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Всего ботов" value={data?.totals.total_bots ?? "—"} />
        <StatTile label="Доступно" value={data?.totals.available ?? "—"} />
        <StatTile
          label="С ошибками"
          value={data?.totals.errors ?? "—"}
          tone={data && Number(data.totals.errors) > 0 ? "error" : "muted"}
        />
        <StatTile
          label="Серверов"
          value={data ? new Set(data.bots.map((b) => b.host)).size : "—"}
        />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mt-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          <AlertCircle size={18} />
          <div>
            <div className="font-semibold">Не удалось загрузить overview</div>
            <div className="mt-1 text-red-800/80">{String(error)}</div>
          </div>
        </div>
      )}

      {/* Bot grid */}
      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {isLoading && !data
          ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
          : data?.bots.map((b) => <BotCard key={b.slug} data={b} />)}
      </div>
    </Shell>
  );
}

function StatTile({
  label,
  value,
  tone = "muted",
}: {
  label: string;
  value: string | number;
  tone?: "muted" | "error";
}) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">
        {label}
      </div>
      <div
        className={
          tone === "error"
            ? "mt-1 text-2xl font-semibold text-red-700"
            : "mt-1 text-2xl font-semibold text-ink-900"
        }
      >
        {value}
      </div>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <Card className="h-48 animate-pulse">
      <div className="h-full rounded-2xl bg-ink-100/50" />
    </Card>
  );
}
