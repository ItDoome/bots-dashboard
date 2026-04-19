import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { usePluginLogs } from "@/api/hooks";
import type { LogEntry, LogLevel } from "@/api/types";
import { cn } from "@/lib/cn";

const LEVEL_COLORS: Record<LogLevel, string> = {
  debug: "text-ink-400",
  info: "text-ink-700",
  warning: "text-amber-700",
  error: "text-red-700",
  critical: "text-red-900 font-semibold",
};

interface LogPanelProps {
  slug: string;
  active: boolean;   // only poll when this tab is actually visible
}

export function LogPanel({ slug, active }: LogPanelProps) {
  const [sinceSec, setSinceSec] = useState<number>(600);  // last 10 minutes
  const { data, isFetching, error, refetch } = usePluginLogs(
    slug,
    { cursor: String(sinceSec), limit: 300 },
    active,
  );

  const entries: LogEntry[] = useMemo(() => data?.entries ?? [], [data]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle>Логи</CardTitle>
            <CardDescription>
              Хвост journalctl, обновляется каждые 5 сек
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={sinceSec}
              onChange={(e) => setSinceSec(Number(e.target.value))}
              className="h-9 rounded-lg border border-ink-200 bg-white px-2 text-xs text-ink-900 focus:border-ink-900 focus:outline-none"
            >
              <option value={300}>Последние 5 мин</option>
              <option value={600}>Последние 10 мин</option>
              <option value={1800}>Последние 30 мин</option>
              <option value={3600}>Последний час</option>
              <option value={21600}>Последние 6 часов</option>
              <option value={86400}>Последние 24 часа</option>
            </select>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw
                size={14}
                className={cn(isFetching && "animate-spin")}
              />
              {isFetching ? "…" : "Обновить"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900">
            Ошибка: {String(error)}
          </div>
        )}
        {entries.length === 0 && !error && !isFetching && (
          <div className="rounded-lg border border-dashed border-ink-200 px-3 py-8 text-center text-xs text-ink-500">
            Нет записей за выбранный промежуток
          </div>
        )}
        {entries.length > 0 && (
          <div className="max-h-[520px] overflow-auto rounded-lg border border-ink-200 bg-ink-50 font-mono text-[11px] leading-5">
            {entries.map((e, idx) => (
              <div
                key={`${e.ts}-${idx}`}
                className={cn(
                  "flex gap-3 whitespace-pre-wrap px-3 py-1 border-b border-ink-100 last:border-0",
                  LEVEL_COLORS[e.level] ?? "text-ink-700",
                )}
              >
                <span className="shrink-0 text-ink-400">
                  {e.ts.length > 19 ? e.ts.slice(0, 19) : e.ts}
                </span>
                {e.source && (
                  <Badge variant="muted" className="shrink-0 h-5">
                    {e.source}
                  </Badge>
                )}
                <span className="min-w-0 break-words">{e.message}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
