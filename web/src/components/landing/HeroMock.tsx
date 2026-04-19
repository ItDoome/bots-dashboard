import { Bot, Coins, Gamepad2, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";

/** A macOS-window-shaped mock dashboard preview under the hero.
 *
 *  Intentionally not connected to any live data — this is the marketing
 *  snapshot. Real numbers are approximations of the user's actual state.
 */
export function HeroMock() {
  return (
    <div className="mx-auto mt-16 max-w-4xl animate-fade-in">
      <div className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-xl">
        {/* macOS window chrome */}
        <div className="flex items-center gap-2 border-b border-ink-200 bg-ink-100 px-4 py-3">
          <span className="h-3 w-3 rounded-full bg-red-400" />
          <span className="h-3 w-3 rounded-full bg-amber-400" />
          <span className="h-3 w-3 rounded-full bg-emerald-400" />
          <div className="ml-4 flex items-center gap-2 text-xs font-medium text-ink-500">
            <Bot size={14} />
            doomedash / Dashboard
          </div>
        </div>

        {/* Body */}
        <div className="space-y-6 bg-white p-6">
          {/* Top stat row */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Total bots" value="3" sub="all available" />
            <StatTile label="Active sales 24h" value="27" sub="+72% vs avg" />
            <StatTile
              label="miHoYo stock"
              value="2,141"
              sub="94.2% market share"
            />
            <StatTile
              label="Loliland coins"
              value="786"
              sub="2 accounts · auto"
            />
          </div>

          {/* Bot cards */}
          <div className="grid gap-3 md:grid-cols-3">
            <MockBotCard
              icon={<Bot size={16} />}
              name="LOLZ Valorant Resell"
              state="running"
              line1="Autosell · 30 min"
              line2="Revenue 24h: 761 ₽"
            />
            <MockBotCard
              icon={<Coins size={16} />}
              name="Loliland Bonus Claimer"
              state="running"
              line1="2 accounts · refresh ok"
              line2="Next claim: 23h 14m"
            />
            <MockBotCard
              icon={<Gamepad2 size={16} />}
              name="reBot ReManga"
              state="running"
              line1="bot + crawler active"
              line2="Users: 1,847"
            />
          </div>

          {/* Tiny chart-like row */}
          <div className="rounded-xl border border-ink-200 bg-ink-50/60 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink-900">
                Monopoly control — 0–30 ₽ tier
              </div>
              <Badge>
                <TrendingUp size={12} />
                holding
              </Badge>
            </div>
            <div className="space-y-2">
              <ProgressRow label="caratel (you)" pct={93.6} color="emerald" />
              <ProgressRow label="Mayo" pct={4.6} color="amber" />
              <ProgressRow label="others" pct={1.8} color="slate" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-ink-900">{value}</div>
      <div className="mt-0.5 text-xs text-ink-500">{sub}</div>
    </div>
  );
}

function MockBotCard({
  icon,
  name,
  state,
  line1,
  line2,
}: {
  icon: React.ReactNode;
  name: string;
  state: "running" | "error";
  line1: string;
  line2: string;
}) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-900">
        <span className="text-ink-500">{icon}</span>
        {name}
      </div>
      <div className="mb-2 flex items-center gap-2 text-xs">
        <StatusDot state={state} />
        <span className="text-ink-500 capitalize">{state}</span>
      </div>
      <div className="text-xs text-ink-500">{line1}</div>
      <div className="text-xs text-ink-500">{line2}</div>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
      {children}
    </span>
  );
}

function StatusDot({ state }: { state: "running" | "error" }) {
  return (
    <span
      className={cn(
        "h-2 w-2 rounded-full",
        state === "running" ? "bg-emerald-500" : "bg-red-500",
      )}
    />
  );
}

function ProgressRow({
  label,
  pct,
  color,
}: {
  label: string;
  pct: number;
  color: "emerald" | "amber" | "slate";
}) {
  const barColor =
    color === "emerald"
      ? "bg-emerald-500"
      : color === "amber"
        ? "bg-amber-500"
        : "bg-ink-300";
  return (
    <div className="grid grid-cols-[140px,1fr,50px] items-center gap-3 text-xs">
      <span className="text-ink-500">{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-ink-100">
        <div className={cn("h-full", barColor)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-right text-ink-900 font-medium">{pct}%</span>
    </div>
  );
}
