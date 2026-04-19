import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Activity,
  Settings,
  Zap,
  Terminal,
  AlertTriangle,
} from "lucide-react";
import { Shell } from "@/components/layout/Shell";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { OverviewPanel } from "@/components/detail/OverviewPanel";
import { SettingsForm } from "@/components/detail/SettingsForm";
import { ActionsPanel } from "@/components/detail/ActionsPanel";
import { LogPanel } from "@/components/detail/LogPanel";
import {
  usePluginList,
  usePluginSettings,
  usePluginSummary,
} from "@/api/hooks";
import type { PluginListItem } from "@/api/types";

type TabId = "overview" | "settings" | "actions" | "logs";

export default function BotDetail() {
  const { slug } = useParams<{ slug: string }>();
  const [tab, setTab] = useState<TabId>("overview");

  const listQuery = usePluginList();
  const summaryQuery = usePluginSummary(slug);
  const settingsQuery = usePluginSettings(slug, tab === "settings");

  const entry: PluginListItem | undefined = listQuery.data?.plugins.find(
    (p) => p.slug === slug,
  );
  const capabilities = entry?.capabilities ?? null;

  const displayName = entry?.display_name ?? slug ?? "";
  const hostKey = entry?.host;

  if (!slug) {
    return (
      <Shell>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-900">
          Bot slug is missing.
        </div>
      </Shell>
    );
  }

  const unavailable = entry && !entry.available;

  return (
    <Shell>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft size={14} /> К дашборду
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink-900">
            {displayName}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            slug: <code className="font-mono">{slug}</code>
            {hostKey && (
              <>
                {" "}
                · host: <code className="font-mono">{hostKey}</code>
              </>
            )}
          </p>
        </div>
        {unavailable && (
          <Badge variant="error">
            <AlertTriangle size={12} /> Agent offline
          </Badge>
        )}
      </div>

      {unavailable && entry?.last_error && (
        <Card className="mt-4 border-red-200 bg-red-50">
          <CardContent className="pt-4 text-xs text-red-900">
            {entry.last_error}
          </CardContent>
        </Card>
      )}

      <div className="mt-6">
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as TabId)}
          defaultValue="overview"
        >
          <TabsList>
            <TabsTrigger value="overview">
              <Activity size={14} className="mr-1" /> Обзор
            </TabsTrigger>
            {capabilities?.supports_settings && (
              <TabsTrigger value="settings">
                <Settings size={14} className="mr-1" /> Настройки
              </TabsTrigger>
            )}
            {capabilities?.supports_actions && (
              <TabsTrigger value="actions">
                <Zap size={14} className="mr-1" /> Действия
              </TabsTrigger>
            )}
            {capabilities?.supports_logs && (
              <TabsTrigger value="logs">
                <Terminal size={14} className="mr-1" /> Логи
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="overview">
            {summaryQuery.isLoading && (
              <Card>
                <CardContent className="pt-6 text-sm text-ink-500">
                  loading…
                </CardContent>
              </Card>
            )}
            {summaryQuery.error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6 text-sm text-red-900">
                  error: {String(summaryQuery.error)}
                </CardContent>
              </Card>
            )}
            {summaryQuery.data && (
              <OverviewPanel summary={summaryQuery.data} />
            )}
          </TabsContent>

          <TabsContent value="settings">
            {settingsQuery.isLoading && (
              <Card>
                <CardContent className="pt-6 text-sm text-ink-500">
                  loading…
                </CardContent>
              </Card>
            )}
            {settingsQuery.error && (
              <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6 text-sm text-red-900">
                  error: {String(settingsQuery.error)}
                </CardContent>
              </Card>
            )}
            {settingsQuery.data && (
              <SettingsForm slug={slug} data={settingsQuery.data} />
            )}
          </TabsContent>

          <TabsContent value="actions">
            <ActionsPanel
              slug={slug}
              actions={capabilities?.actions ?? []}
            />
          </TabsContent>

          <TabsContent value="logs">
            <LogPanel slug={slug} active={tab === "logs"} />
          </TabsContent>
        </Tabs>
      </div>
    </Shell>
  );
}
