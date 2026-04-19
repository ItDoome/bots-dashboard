import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRunAction } from "@/api/hooks";
import type { ActionDescriptor, ActionResult, DangerLevel } from "@/api/types";
import { cn } from "@/lib/cn";

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

const DANGER_STYLES: Record<
  DangerLevel,
  { variant: "primary" | "secondary" | "destructive"; label: string }
> = {
  low: { variant: "secondary", label: "low risk" },
  medium: { variant: "primary", label: "confirm" },
  high: { variant: "destructive", label: "danger" },
};

// ─────────────────────────────────────────────────────────────
// Single action card
// ─────────────────────────────────────────────────────────────

interface ActionButtonProps {
  slug: string;
  descriptor: ActionDescriptor;
}

export function ActionButton({ slug, descriptor }: ActionButtonProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mutation = useRunAction(slug);

  const style = DANGER_STYLES[descriptor.danger_level];
  const needsConfirm = descriptor.danger_level !== "low";

  const runAction = async () => {
    setError(null);
    setResult(null);
    try {
      const r = await mutation.mutateAsync({ actionKey: descriptor.key });
      setResult(r);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setConfirmOpen(false);
    }
  };

  const onClick = () => {
    if (needsConfirm) {
      setConfirmOpen(true);
    } else {
      void runAction();
    }
  };

  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-ink-900">
              {descriptor.label}
            </h3>
            <Badge
              variant={
                descriptor.danger_level === "high"
                  ? "error"
                  : descriptor.danger_level === "medium"
                    ? "warning"
                    : "muted"
              }
            >
              {style.label}
            </Badge>
          </div>
          {descriptor.description && (
            <p className="mt-1 text-xs text-ink-500">{descriptor.description}</p>
          )}
          {descriptor.estimated_duration_sec && (
            <p className="mt-1 text-[11px] uppercase tracking-wider text-ink-400">
              ~{descriptor.estimated_duration_sec}s
            </p>
          )}
        </div>
        <Button
          size="sm"
          variant={style.variant}
          disabled={mutation.isPending}
          onClick={onClick}
        >
          {mutation.isPending ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          {mutation.isPending ? "Running…" : "Запустить"}
        </Button>
      </div>

      {(result || error) && (
        <div
          className={cn(
            "mt-3 rounded-lg border px-3 py-2 text-xs",
            error || (result && !result.ok)
              ? "border-red-200 bg-red-50 text-red-900"
              : "border-emerald-200 bg-emerald-50 text-emerald-900",
          )}
        >
          <div className="flex items-center gap-2 font-medium">
            {error || (result && !result.ok) ? (
              <AlertTriangle size={14} />
            ) : (
              <CheckCircle2 size={14} />
            )}
            {error
              ? "Ошибка"
              : result?.ok
                ? result.message || "OK"
                : "Не удалось"}
            {result?.duration_sec != null && (
              <span className="ml-auto text-ink-400">
                {result.duration_sec.toFixed(1)}s
              </span>
            )}
          </div>
          {(result?.error || error) && (
            <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words text-[11px] text-red-800">
              {result?.error || error}
            </pre>
          )}
          {result?.output && (
            <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words text-[11px] text-ink-700">
              {result.output}
            </pre>
          )}
        </div>
      )}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogTitle>Подтвердите: {descriptor.label}</DialogTitle>
        <DialogDescription>
          {descriptor.confirm_prompt || descriptor.description || "Точно запустить это действие?"}
        </DialogDescription>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setConfirmOpen(false)}
            disabled={mutation.isPending}
          >
            Отмена
          </Button>
          <Button
            variant={
              descriptor.danger_level === "high" ? "destructive" : "primary"
            }
            onClick={runAction}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : null}
            Подтвердить
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
