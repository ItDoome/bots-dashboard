import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { MonopolyData } from "@/api/types";
import { cn } from "@/lib/cn";

// ─────────────────────────────────────────────────────────────
// Color palette for sellers
// ─────────────────────────────────────────────────────────────

const SELLER_COLORS: Record<string, { bar: string; text: string; bg: string }> = {
  caratel: { bar: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50" },
  Mayo:    { bar: "bg-amber-500",   text: "text-amber-700",   bg: "bg-amber-50" },
};

const FALLBACK_COLORS = [
  { bar: "bg-violet-400",  text: "text-violet-700",  bg: "bg-violet-50" },
  { bar: "bg-sky-400",     text: "text-sky-700",     bg: "bg-sky-50" },
  { bar: "bg-rose-400",    text: "text-rose-700",    bg: "bg-rose-50" },
  { bar: "bg-orange-400",  text: "text-orange-700",  bg: "bg-orange-50" },
  { bar: "bg-teal-400",    text: "text-teal-700",    bg: "bg-teal-50" },
];

function getColor(name: string, idx: number) {
  return SELLER_COLORS[name] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

// ─────────────────────────────────────────────────────────────
// Price distribution bar chart colors
// ─────────────────────────────────────────────────────────────

const PRICE_COLORS = [
  "bg-emerald-500",
  "bg-emerald-400",
  "bg-sky-400",
  "bg-violet-400",
  "bg-amber-400",
  "bg-rose-400",
];

// ─────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────

interface Props {
  data: MonopolyData;
}

export function MonopolyCard({ data }: Props) {
  const sortedSellers = Object.entries(data.sellers)
    .sort(([, a], [, b]) => b - a);
  const sellersTotal = sortedSellers.reduce((sum, [, c]) => sum + c, 0) || 1;

  const sortedPrices = Object.entries(data.price_distribution)
    .sort(([a], [b]) => Number(a) - Number(b));
  const maxPriceCount = Math.max(...sortedPrices.map(([, c]) => c), 1);

  const newComps = Object.entries(data.new_competitors_7d)
    .sort(([, a], [, b]) => b - a);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Monopoly Control</CardTitle>
            <CardDescription>Тир 0–30 ₽ — доля рынка и конкуренты</CardDescription>
          </div>
          <Badge
            variant={data.share_pct >= 90 ? "success" : data.share_pct >= 70 ? "warning" : "error"}
            className="text-sm px-3 py-1"
          >
            {data.share_pct.toFixed(1)}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">

        {/* ── Market share bar ── */}
        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-ink-500">
            <span>Доля рынка</span>
            <span className="font-medium text-ink-900">
              {data.my_count.toLocaleString()} / {data.total_count.toLocaleString()} лотов
            </span>
          </div>
          <div className="h-4 overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-500"
              style={{ width: `${Math.min(data.share_pct, 100)}%` }}
            />
          </div>
        </div>

        {/* ── Revenue tiles ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MiniTile label="Продажи 24ч" value={data.sold_24h} />
          <MiniTile label="Выручка 24ч" value={`${data.revenue_24h.toFixed(0)} ₽`} />
          <MiniTile label="Avg 7д" value={`${data.sold_7d_avg.toFixed(1)}/д`} />
          <MiniTile label="Выручка 7д" value={`${data.revenue_7d.toFixed(0)} ₽`} />
        </div>

        {/* ── Sellers breakdown ── */}
        <div>
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Продавцы в тире
          </h4>
          <div className="space-y-2">
            {sortedSellers.map(([name, count], idx) => {
              const pct = (count / sellersTotal) * 100;
              const color = getColor(name, idx);
              return (
                <div key={name} className="grid grid-cols-[140px,1fr,60px] items-center gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <span className={cn("h-2.5 w-2.5 rounded-full", color.bar)} />
                    <span className={cn("font-medium", name === "caratel" ? "text-emerald-700" : "text-ink-700")}>
                      {name}
                    </span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-ink-100">
                    <div
                      className={cn("h-full rounded-full transition-all", color.bar)}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-right text-xs text-ink-500">
                    {count.toLocaleString()} <span className="text-ink-400">({pct.toFixed(1)}%)</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Price distribution ── */}
        <div>
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Распределение цен
          </h4>
          <div className="flex items-end gap-1.5" style={{ height: 80 }}>
            {sortedPrices.map(([price, count], idx) => {
              const heightPct = (count / maxPriceCount) * 100;
              return (
                <div key={price} className="group relative flex flex-1 flex-col items-center">
                  <div
                    className={cn(
                      "w-full min-w-[20px] rounded-t-md transition-all hover:opacity-80",
                      PRICE_COLORS[idx % PRICE_COLORS.length],
                    )}
                    style={{ height: `${Math.max(heightPct, 4)}%` }}
                  />
                  <span className="mt-1 text-[10px] font-medium text-ink-500">{price}₽</span>
                  {/* Tooltip on hover */}
                  <div className="pointer-events-none absolute -top-8 rounded bg-ink-900 px-2 py-1 text-[10px] text-white opacity-0 shadow transition-opacity group-hover:opacity-100">
                    {count.toLocaleString()} шт
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Mayo + new competitors ── */}
        <div className="grid gap-3 sm:grid-cols-2">
          {/* Mayo card */}
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-800">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
              Mayo
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-amber-600">Лотов</span>
                <div className="text-lg font-semibold text-amber-900">{data.mayo_count}</div>
              </div>
              <div>
                <span className="text-amber-600">Старейший</span>
                <div className="text-lg font-semibold text-amber-900">{data.mayo_oldest_days} дн</div>
              </div>
            </div>
          </div>

          {/* New competitors card */}
          <div className="rounded-xl border border-ink-200 bg-ink-50 p-4">
            <div className="text-sm font-semibold text-ink-700">
              Новые конкуренты <span className="text-ink-400 font-normal">7д</span>
            </div>
            <div className="mt-2">
              {newComps.length === 0 ? (
                <div className="text-sm text-ink-400">Нет новых</div>
              ) : (
                <div className="space-y-1">
                  {newComps.map(([name, count]) => (
                    <div key={name} className="flex items-center justify-between text-sm">
                      <span className="text-ink-700">{name}</span>
                      <Badge variant={count > 20 ? "error" : "warning"}>
                        {count} лот{count > 4 ? "ов" : count > 1 ? "а" : ""}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

      </CardContent>
    </Card>
  );
}

function MiniTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-center">
      <div className="text-[10px] uppercase tracking-wider text-ink-400">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-ink-900">{String(value)}</div>
    </div>
  );
}
