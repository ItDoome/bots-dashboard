import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ValshopData } from "@/api/types";
import { cn } from "@/lib/cn";

// Only 5 canonical Valorant tiers — Select / Deluxe / Premium / Exclusive / Ultra.
// BP / Contract / Bundle are separate flags (is_bp, is_contract, is_bundle)
// rendered as badges instead of price, not as tiers.
const TIER_COLORS: Record<string, string> = {
  "Select": "text-sky-700 border-sky-200 bg-sky-50",
  "Deluxe": "text-emerald-700 border-emerald-200 bg-emerald-50",
  "Premium": "text-violet-700 border-violet-200 bg-violet-50",
  "Exclusive": "text-pink-700 border-pink-200 bg-pink-50",
  "Ultra": "text-amber-700 border-amber-300 bg-amber-50",
};

function fmtDur(sec: number): string {
  if (sec <= 0) return "—";
  if (sec < 3600) return `${Math.floor(sec / 60)} мин`;
  if (sec < 86400) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h}ч ${m}м`;
  }
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  return `${d}д ${h}ч`;
}

interface Props {
  data: ValshopData;
}

type CollectionTab = "cards" | "sprays" | "buddies" | "titles";

const COLLECTION_INITIAL_LIMIT: Record<CollectionTab, number> = {
  cards: 12,
  sprays: 20,
  buddies: 24,
  titles: 16,
};

export function ValshopCard({ data }: Props) {
  const [showAll, setShowAll] = useState(false);
  const [collectionTab, setCollectionTab] = useState<CollectionTab>("cards");
  const [collectionExpanded, setCollectionExpanded] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);

  if (!data.ok) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="pt-6 text-sm text-red-900">
          <div className="font-semibold mb-1">Ошибка Valorant Shop</div>
          <div className="text-xs">{data.error || "Не удалось получить данные с Riot API"}</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ── Wallet ── */}
      {data.wallet && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Кошелёк</CardTitle>
                <CardDescription>
                  {data.region?.toUpperCase() || "?"} region
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              <WalletTile label="Valorant Points" value={data.wallet.vp} unit="VP" color="amber" />
              <WalletTile label="Radianite" value={data.wallet.rad} unit="RP" color="sky" />
              <WalletTile label="Kingdom Credits" value={data.wallet.kc} unit="KC" color="violet" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Inventory summary ── */}
      {data.inventory && (() => {
        const inv = data.inventory!;
        const uniqueCount = inv.unique_skins ?? inv.total;
        const items = showAll ? (inv.all || inv.recent) : inv.recent;
        const hasMore = inv.all && inv.all.length > inv.recent.length;
        return (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>🎒 Инвентарь</CardTitle>
                  <CardDescription>
                    {uniqueCount} уникальных скинов · {
                      (inv.known_prices_count ?? 0) > 0
                        ? <>~{inv.estimated_vp.toLocaleString()} VP <span className="text-ink-400" title="точных / приблизительных">({inv.known_prices_count}/{uniqueCount} точных)</span></>
                        : <span className="italic">~{inv.estimated_vp.toLocaleString()} VP (оценка по тирам)</span>
                    }
                    {inv.total_levels && inv.total_levels !== uniqueCount && (
                      <span className="text-ink-400"> · {inv.total_levels} уровней</span>
                    )}
                  </CardDescription>
                </div>
                <Badge variant="default">{uniqueCount}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {/* Tier breakdown — sorted by rarity (Ultra top, Select bottom) */}
              <div className="mb-4 space-y-1.5">
                {(() => {
                  const TIER_RANK: Record<string, number> = {
                    Ultra: 4, Exclusive: 3, Premium: 2, Deluxe: 1, Select: 0,
                  };
                  return Object.entries(inv.tiers)
                    .sort(([a], [b]) => (TIER_RANK[b] ?? -1) - (TIER_RANK[a] ?? -1));
                })().map(([tier, count]) => {
                    const pct = uniqueCount > 0 ? (count / uniqueCount) * 100 : 0;
                    const barColor =
                      tier === "Ultra" ? "bg-amber-500" :
                      tier === "Exclusive" ? "bg-pink-500" :
                      tier === "Premium" ? "bg-violet-500" :
                      tier === "Deluxe" ? "bg-emerald-500" :
                      tier === "Select" ? "bg-sky-500" :
                      "bg-ink-300";
                    return (
                      <div key={tier} className="grid grid-cols-[120px,1fr,60px] items-center gap-3 text-xs">
                        <span className="text-ink-700 font-medium">{tier}</span>
                        <div className="h-2 overflow-hidden rounded-full bg-ink-100">
                          <div className={cn("h-full rounded-full", barColor)} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-right text-ink-500">
                          {count} <span className="text-ink-400">({pct.toFixed(0)}%)</span>
                        </span>
                      </div>
                    );
                  })}
              </div>

              {items.length > 0 && (
                <>
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-500">
                      {showAll ? "Все скины (по редкости)" : "Топ скинов (по редкости)"}
                    </h4>
                    <span className="text-xs text-ink-400">
                      {items.length} {showAll ? "" : `из ${inv.all?.length || uniqueCount}`}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {items.map((s, idx) => (
                      <div key={idx} className="rounded-lg border border-ink-200 bg-white p-2">
                        <img
                          src={s.icon}
                          alt={s.name}
                          className="h-12 w-full rounded object-contain bg-ink-900/5"
                          loading="lazy"
                        />
                        <div className="mt-1 text-xs font-medium text-ink-900 truncate">{s.name}</div>
                        <div className="flex items-center justify-between">
                          <span
                            className={cn(
                              "inline-block rounded-full border px-1.5 py-0.5 text-[9px]",
                              TIER_COLORS[s.tier] || "text-ink-500 border-ink-200 bg-ink-50",
                            )}
                          >
                            {s.tier}
                          </span>
                          {s.is_bundle ? (
                            <span className="text-[10px] text-amber-600 font-medium" title={`Только в бандле${s.bundle_group ? ` «${s.bundle_group}»` : ""}`}>
                              {s.vp ? s.vp.toLocaleString() : "?"} VP 📦
                            </span>
                          ) : s.is_bp ? (
                            <span className="text-[10px] text-violet-600 italic" title="Получен из Battle Pass — не продаётся за VP">
                              Battle Pass
                            </span>
                          ) : s.is_contract ? (
                            <span className="text-[10px] text-cyan-700 italic" title="Получен из контракта агента — не продаётся за VP">
                              Контракт
                            </span>
                          ) : (
                            <span
                              className={cn(
                                "text-[10px]",
                                s.vp_actual ? "text-emerald-600 font-medium" : "text-ink-400 italic",
                              )}
                              title={
                                (s.vp_actual ? "Точная цена" : "Оценка по тиру") +
                                (s.is_melee ? " · Melee (×2)" : "")
                              }
                            >
                              {s.vp ? s.vp.toLocaleString() : "?"} VP
                              {s.is_melee && <span className="ml-0.5 text-ink-400">🔪</span>}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {hasMore && (
                    <div className="mt-4 flex justify-center">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setShowAll(v => !v)}
                      >
                        {showAll
                          ? `Свернуть (показано ${inv.all!.length})`
                          : `Показать все ${inv.all!.length} скинов`}
                      </Button>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Collection: cards, sprays, buddies, titles ── */}
      {data.collection && (() => {
        const col = data.collection!;
        const totalAll = col.cards.total + col.sprays.total + col.buddies.total + col.titles.total;
        if (totalAll === 0) return null;

        const tabs: { key: CollectionTab; emoji: string; label: string; total: number }[] = [
          { key: "cards", emoji: "🪪", label: "Карточки", total: col.cards.total },
          { key: "sprays", emoji: "🎨", label: "Граффити", total: col.sprays.total },
          { key: "buddies", emoji: "🔑", label: "Брелки", total: col.buddies.total },
          { key: "titles", emoji: "🏷️", label: "Звания", total: col.titles.total },
        ];

        const currentItems = (() => {
          if (collectionTab === "cards") return col.cards.items;
          if (collectionTab === "sprays") return col.sprays.items;
          if (collectionTab === "buddies") return col.buddies.items;
          return col.titles.items;
        })();
        const limit = COLLECTION_INITIAL_LIMIT[collectionTab];
        const visible = collectionExpanded ? currentItems : currentItems.slice(0, limit);
        const hasMore = currentItems.length > limit;

        return (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>🎭 Коллекция</CardTitle>
                  <CardDescription>
                    {totalAll} предметов · {col.cards.total} карточек · {col.sprays.total} граффити · {col.buddies.total} брелков · {col.titles.total} званий
                  </CardDescription>
                </div>
              </div>
              {/* Tabs — horizontally scrollable on narrow mobile to avoid page overflow */}
              <div className="mt-3 flex gap-1 overflow-x-auto border-b border-ink-200 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
                {tabs.map(t => (
                  <button
                    key={t.key}
                    onClick={() => {
                      setCollectionTab(t.key);
                      setCollectionExpanded(false);
                    }}
                    className={cn(
                      "shrink-0 whitespace-nowrap px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px",
                      collectionTab === t.key
                        ? "border-amber-500 text-amber-700"
                        : "border-transparent text-ink-500 hover:text-ink-700 hover:border-ink-300",
                    )}
                  >
                    <span className="mr-1">{t.emoji}</span>
                    {t.label}
                    <span className="ml-1.5 text-ink-400">({t.total})</span>
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {currentItems.length === 0 ? (
                <div className="text-center py-6 text-sm text-ink-400 italic">
                  Нет предметов в этой категории
                </div>
              ) : (
                <>
                  {/* Cards: wide banners 452x128 (~3.53:1), 2-col */}
                  {collectionTab === "cards" && (
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {(visible as typeof col.cards.items).map(c => (
                        <div key={c.uuid} className="overflow-hidden rounded-lg border border-ink-200 bg-white">
                          {c.icon ? (
                            <img
                              src={c.icon}
                              alt={c.name}
                              className="w-full aspect-[452/128] object-contain bg-ink-900/5"
                              loading="lazy"
                            />
                          ) : (
                            <div className="w-full aspect-[452/128] bg-gradient-to-br from-ink-100 to-ink-200 flex items-center justify-center text-2xl">
                              🪪
                            </div>
                          )}
                          <div className="p-2 text-xs font-medium text-ink-900 truncate" title={c.name}>
                            {c.name}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Sprays: square icons, 4-col */}
                  {collectionTab === "sprays" && (
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
                      {(visible as typeof col.sprays.items).map(s => (
                        <div key={s.uuid} className="rounded-lg border border-ink-200 bg-white p-2">
                          {s.icon ? (
                            <img
                              src={s.icon}
                              alt={s.name}
                              className="h-16 w-full rounded object-contain bg-ink-900/5"
                              loading="lazy"
                            />
                          ) : (
                            <div className="h-16 w-full rounded bg-ink-100 flex items-center justify-center text-xl">
                              🎨
                            </div>
                          )}
                          <div className="mt-1 text-[10px] text-ink-700 truncate" title={s.name}>
                            {s.name}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Buddies: compact icons, 6-col */}
                  {collectionTab === "buddies" && (
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6">
                      {(visible as typeof col.buddies.items).map(b => (
                        <div key={b.uuid} className="rounded-lg border border-ink-200 bg-white p-2">
                          {b.icon ? (
                            <img
                              src={b.icon}
                              alt={b.name}
                              className="h-14 w-full rounded object-contain bg-ink-900/5"
                              loading="lazy"
                            />
                          ) : (
                            <div className="h-14 w-full rounded bg-ink-100 flex items-center justify-center text-lg">
                              🔑
                            </div>
                          )}
                          <div className="mt-1 text-[10px] text-ink-700 truncate" title={b.name}>
                            {b.name}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Titles: text pills, 2-col */}
                  {collectionTab === "titles" && (
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {(visible as typeof col.titles.items).map(t => (
                        <div
                          key={t.uuid}
                          className="flex items-center gap-2 rounded-lg border border-ink-200 bg-white p-3"
                          title={t.name}
                        >
                          <span className="text-lg">🏷️</span>
                          <span className="text-sm font-medium text-ink-900 truncate">
                            «{t.text}»
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {hasMore && (
                    <div className="mt-4 flex justify-center">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setCollectionExpanded(v => !v)}
                      >
                        {collectionExpanded
                          ? `Свернуть (показано ${currentItems.length})`
                          : `Показать все ${currentItems.length}`}
                      </Button>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Daily Shop ── */}
      {data.daily && data.daily.items.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>🎯 Daily Shop</CardTitle>
                <CardDescription>
                  До обновления: {fmtDur(data.daily.remaining_sec)}
                </CardDescription>
              </div>
              <Badge variant="default">{data.daily.items.length} скинов</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.daily.items.map((skin, idx) => (
                <div
                  key={idx}
                  className={cn(
                    "group flex items-center gap-3 rounded-xl border p-3",
                    skin.owned ? "border-emerald-200 bg-emerald-50/40" : "border-ink-200 bg-white",
                  )}
                >
                  {skin.icon ? (
                    <img
                      src={skin.icon}
                      alt={skin.name}
                      className="h-14 w-24 rounded object-contain bg-ink-900/10 flex-shrink-0"
                    />
                  ) : (
                    <div className="h-14 w-24 rounded bg-ink-100 flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm text-ink-900 truncate">
                      {skin.name}
                      {skin.owned && <span className="ml-1 text-emerald-600">✓</span>}
                    </div>
                    {skin.tier && (
                      <span
                        className={cn(
                          "mt-0.5 inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium",
                          TIER_COLORS[skin.tier] || "text-ink-500 border-ink-200 bg-ink-50",
                        )}
                      >
                        {skin.tier}
                      </span>
                    )}
                    <div className="mt-1 text-sm font-semibold text-amber-600">
                      {skin.cost_vp.toLocaleString()} VP
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Daily Shop history ── */}
      {data.history && data.history.length > 0 && (() => {
        const today = new Date().toISOString().slice(0, 10);
        const past = data.history.filter(h => h.date !== today);
        if (past.length === 0) return null;
        const initialLimit = 5;
        const visible = historyExpanded ? past : past.slice(0, initialLimit);
        const hasMore = past.length > initialLimit;
        return (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>📅 История Daily Shop</CardTitle>
                  <CardDescription>
                    {past.length} {past.length === 1 ? "день" : past.length < 5 ? "дня" : "дней"} в записи
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {visible.map(day => (
                  <div key={day.date}>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
                      {day.date}
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {day.items.map((skin, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-3 rounded-lg border border-ink-200 bg-white p-2"
                        >
                          {skin.icon ? (
                            <img
                              src={skin.icon}
                              alt={skin.name}
                              className="h-10 w-20 rounded object-contain bg-ink-900/5 flex-shrink-0"
                              loading="lazy"
                            />
                          ) : (
                            <div className="h-10 w-20 rounded bg-ink-100 flex-shrink-0" />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-ink-900 truncate">
                              {skin.name}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              {skin.tier && (
                                <span
                                  className={cn(
                                    "inline-block rounded-full border px-1.5 py-0.5 text-[9px]",
                                    TIER_COLORS[skin.tier] || "text-ink-500 border-ink-200 bg-ink-50",
                                  )}
                                >
                                  {skin.tier}
                                </span>
                              )}
                              <span className="text-xs text-amber-600 font-medium">
                                {skin.cost_vp.toLocaleString()} VP
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {hasMore && (
                <div className="mt-4 flex justify-center">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setHistoryExpanded(v => !v)}
                  >
                    {historyExpanded
                      ? `Свернуть (показано ${past.length})`
                      : `Показать все ${past.length} дней`}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* ── Featured Bundle ── */}
      {data.bundle && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>📦 Featured Bundle</CardTitle>
                <CardDescription>
                  {data.bundle.name !== "Unknown Bundle" ? data.bundle.name : "Bundle"} · осталось {fmtDur(data.bundle.remaining_sec)}
                </CardDescription>
              </div>
              <Badge variant="success">-{data.bundle.pct}%</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              {(data.bundle.icon || data.bundle.items?.find(i => i.icon)?.icon) && (
                <img
                  src={data.bundle.icon || data.bundle.items?.find(i => i.icon)?.icon || ""}
                  alt={data.bundle.name}
                  className="h-16 w-28 rounded object-contain bg-ink-900/10"
                />
              )}
              <div className="flex-1">
                <div className="flex items-baseline gap-3">
                  <span className="text-xs text-ink-400 line-through">
                    {data.bundle.base.toLocaleString()} VP
                  </span>
                  <span className="text-xl font-bold text-amber-600">
                    {data.bundle.discounted.toLocaleString()} VP
                  </span>
                </div>
                <div className="mt-1 text-xs text-ink-500">
                  экономия {(data.bundle.base - data.bundle.discounted).toLocaleString()} VP
                  {data.bundle.items && ` · ${data.bundle.items.length} предмета`}
                </div>
              </div>
            </div>

            {/* Bundle items grid */}
            {data.bundle.items && data.bundle.items.length > 0 && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {data.bundle.items.map((it, idx) => {
                  // Is this an unresolved item? (name is 8-char UUID fragment)
                  const unresolved = /^[0-9a-f]{8}$/i.test(it.name);
                  const emoji =
                    it.kind === "Skin" ? "🔫" :
                    it.kind === "Спрей" ? "🎨" :
                    it.kind === "Карточка" ? "🪪" :
                    it.kind === "Талисман" ? "🔑" :
                    it.kind === "Титул" ? "🏷️" : "📦";
                  return (
                    <div key={idx} className={cn(
                      "rounded-lg border bg-white p-2 text-xs",
                      unresolved ? "border-ink-200 border-dashed" : "border-ink-200",
                    )}>
                      {it.icon ? (
                        <img
                          src={it.icon}
                          alt={it.name}
                          className="h-16 w-full rounded object-contain bg-ink-900/5 mb-1.5"
                        />
                      ) : (
                        <div className="h-16 w-full rounded bg-gradient-to-br from-ink-100 to-ink-200 mb-1.5 flex items-center justify-center text-2xl">
                          {emoji}
                        </div>
                      )}
                      {unresolved ? (
                        <div className="text-[10px] text-ink-400 italic truncate">
                          {it.kind} · новый
                        </div>
                      ) : (
                        <div className="font-medium text-ink-900 truncate">{it.name}</div>
                      )}
                      <div className="text-[10px] text-ink-500 mt-0.5">
                        {!unresolved && it.kind}
                        {it.qty > 1 && <span className="text-amber-600"> ×{it.qty}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Night Market (если есть) ── */}
      {data.night_market && data.night_market.items.length > 0 && (
        <Card className="border-violet-200 bg-gradient-to-br from-violet-50 to-white">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>🌙 Ночной рынок</CardTitle>
                <CardDescription>
                  До закрытия: {fmtDur(data.night_market.remaining_sec)}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {data.night_market.items.map((item, idx) => (
                <div key={idx} className="flex items-center gap-3 rounded-lg border border-violet-200 bg-white p-2">
                  {item.icon && <img src={item.icon} alt={item.name} className="h-10 w-16 object-contain" />}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-900 truncate">{item.name}</div>
                    <div className="flex items-baseline gap-2 text-xs">
                      <span className="line-through text-ink-400">{item.base}</span>
                      <span className="font-semibold text-violet-700">{item.discounted} VP</span>
                      <span className="text-emerald-600">-{item.pct}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Accessories ── */}
      {data.accessories && data.accessories.items.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>🎨 Аксессуары</CardTitle>
                <CardDescription>
                  Обновление через {fmtDur(data.accessories.remaining_sec)}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {data.accessories.items.map((acc, idx) => (
                <div key={idx} className="flex items-center gap-3 rounded-lg border border-ink-200 bg-white p-2">
                  {acc.icon ? (
                    <img
                      src={acc.icon}
                      alt={acc.name}
                      className="h-10 w-10 rounded object-contain bg-ink-900/5 flex-shrink-0"
                    />
                  ) : (
                    <div className="h-10 w-10 rounded bg-ink-100 flex-shrink-0 flex items-center justify-center text-[10px] text-ink-400">
                      {acc.kind.slice(0, 1)}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-ink-500">{acc.kind}</div>
                    <div className="font-medium text-ink-900 text-sm truncate">{acc.name}</div>
                    {acc.qty > 1 && <span className="text-xs text-amber-600">×{acc.qty}</span>}
                  </div>
                  <span className="font-semibold text-violet-700 text-sm whitespace-nowrap">{acc.cost_kc.toLocaleString()} KC</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Limited Offers removed — valorant-api reports the same plugin 47+ times for each reward,
          not useful as separate section; bundle already covers featured offers. */}
    </div>
  );
}

function WalletTile({ label, value, unit, color }: { label: string; value: number; unit: string; color: "amber" | "sky" | "violet" }) {
  const colorClasses: Record<string, string> = {
    amber: "bg-amber-50 text-amber-900 border-amber-200",
    sky: "bg-sky-50 text-sky-900 border-sky-200",
    violet: "bg-violet-50 text-violet-900 border-violet-200",
  };
  return (
    <div className={cn("rounded-xl border p-4", colorClasses[color])}>
      <div className="text-[11px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-semibold">{value.toLocaleString()}</span>
        <span className="text-sm opacity-70">{unit}</span>
      </div>
    </div>
  );
}
