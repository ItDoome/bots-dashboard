import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Bot,
  Coins,
  Gamepad2,
  AlertTriangle,
  HelpCircle,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PluginCardData } from "@/api/types";
import { formatRelative } from "@/lib/dates";

const ICONS: Record<string, LucideIcon> = {
  bot: Bot,
  coins: Coins,
  "gamepad-2": Gamepad2,
};

export function BotCard({ data }: { data: PluginCardData }) {
  const Icon = ICONS[data.icon] || Bot;
  const s = data.summary;

  const status: "ok" | "warning" | "error" = !data.available
    ? "error"
    : s?.health === "error"
      ? "error"
      : s?.health === "warning"
        ? "warning"
        : "ok";

  return (
    <Link to={`/bots/${data.slug}`} className="group block">
      <Card className="h-full p-5 transition-shadow hover:shadow-md">
        {/* Header row */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-700">
              <Icon size={18} />
            </div>
            <div>
              <div className="font-semibold text-ink-900">{data.display_name}</div>
              <div className="text-xs text-ink-500">{data.host}</div>
            </div>
          </div>
          <StatusBadge status={status} label={labelFor(status)} />
        </div>

        {/* Message line */}
        <div className="mt-4 min-h-[2.5rem] text-sm text-ink-500">
          {data.available
            ? s?.message || "running"
            : data.error || "agent unavailable"}
        </div>

        {/* Primary metrics grid */}
        {s && s.primary_metrics.length > 0 ? (
          <div className="mt-4 grid grid-cols-3 gap-3">
            {s.primary_metrics.slice(0, 3).map((m, idx) => (
              <div key={idx} className="rounded-lg bg-ink-100/60 p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-500 truncate">
                  {m.label}
                </div>
                <div className="mt-1 text-lg font-semibold text-ink-900">
                  {m.value ?? "—"}
                  {m.unit ? <span className="ml-1 text-xs font-normal text-ink-500">{m.unit}</span> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-ink-200 p-4 text-center text-xs text-ink-500">
            {data.available ? "нет метрик" : "метрики недоступны"}
          </div>
        )}

        {/* Footer */}
        <div className="mt-5 flex items-center justify-between border-t border-ink-200 pt-4 text-xs text-ink-500">
          <span>
            {data.last_successful_at
              ? `обновлено ${formatRelative(data.last_successful_at)}`
              : "—"}
          </span>
          <span className="inline-flex items-center gap-1 text-ink-700 group-hover:text-ink-900">
            View details <ArrowUpRight size={14} />
          </span>
        </div>
      </Card>
    </Link>
  );
}

function labelFor(s: "ok" | "warning" | "error") {
  if (s === "ok") return "running";
  if (s === "warning") return "warning";
  return "error";
}

function StatusBadge({
  status,
  label,
}: {
  status: "ok" | "warning" | "error";
  label: string;
}) {
  if (status === "ok") {
    return (
      <Badge variant="success">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        {label}
      </Badge>
    );
  }
  if (status === "warning") {
    return (
      <Badge variant="warning">
        <AlertTriangle size={12} />
        {label}
      </Badge>
    );
  }
  return (
    <Badge variant="error">
      <HelpCircle size={12} />
      {label}
    </Badge>
  );
}
