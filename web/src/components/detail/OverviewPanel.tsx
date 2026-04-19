import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MonopolyCard } from "./MonopolyCard";
import { ValshopCard } from "./ValshopCard";
import type { BotSummary, HealthStatus, MetricValue, MonopolyData, ServiceState, ValshopData } from "@/api/types";

const HEALTH_BADGE: Record<
  HealthStatus,
  { variant: "success" | "warning" | "error" | "muted"; label: string }
> = {
  ok: { variant: "success", label: "OK" },
  warning: { variant: "warning", label: "WARN" },
  error: { variant: "error", label: "ERROR" },
  unknown: { variant: "muted", label: "?" },
};

const STATE_BADGE: Record<
  ServiceState,
  { variant: "success" | "warning" | "error" | "muted"; label: string }
> = {
  active: { variant: "success", label: "active" },
  inactive: { variant: "muted", label: "inactive" },
  activating: { variant: "warning", label: "activating" },
  deactivating: { variant: "warning", label: "deactivating" },
  failed: { variant: "error", label: "failed" },
  unknown: { variant: "muted", label: "?" },
};

function MetricTile({ metric }: { metric: MetricValue }) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="text-[11px] uppercase tracking-wider text-ink-500">
        {metric.label}
      </div>
      <div className="mt-1 flex items-baseline gap-1 font-display">
        <span className="text-2xl font-semibold text-ink-900">
          {metric.value == null ? "—" : metric.value}
        </span>
        {metric.unit && (
          <span className="text-sm text-ink-500">{metric.unit}</span>
        )}
      </div>
      {metric.trend_delta != null && (
        <div className="mt-1 text-xs text-ink-500">{metric.trend_delta}</div>
      )}
    </div>
  );
}

interface OverviewPanelProps {
  summary: BotSummary;
}

export function OverviewPanel({ summary }: OverviewPanelProps) {
  const healthStyle = HEALTH_BADGE[summary.health];
  const stateStyle = STATE_BADGE[summary.status];
  const primary = summary.primary_metrics ?? [];
  const secondary = summary.secondary_metrics ?? [];
  const monopoly = (summary.extra as Record<string, unknown> | null)?.monopoly as MonopolyData | undefined;
  const valshop = (summary.extra as Record<string, unknown> | null)?.valshop as ValshopData | undefined;
  // Skip primary metrics grid when a dedicated rich card (valshop/monopoly)
  // already shows the same data — avoids duplicate wallet tiles on mobile.
  const hideGenericPrimary = !!(valshop || monopoly);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Статус</CardTitle>
              {summary.message && (
                <CardDescription>{summary.message}</CardDescription>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={stateStyle.variant}>{stateStyle.label}</Badge>
              <Badge variant={healthStyle.variant}>{healthStyle.label}</Badge>
            </div>
          </div>
        </CardHeader>
        {!hideGenericPrimary && primary.length > 0 && (
          <CardContent>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3">
              {primary.map((m, idx) => (
                <MetricTile key={`${m.label}-${idx}`} metric={m} />
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      {monopoly && <MonopolyCard data={monopoly} />}

      {valshop && <ValshopCard data={valshop} />}

      {secondary.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Дополнительно</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-2 sm:gap-3 md:grid-cols-3">
              {secondary.map((m, idx) => (
                <MetricTile key={`${m.label}-${idx}`} metric={m} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
