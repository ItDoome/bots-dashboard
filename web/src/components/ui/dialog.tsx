import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

// Minimal modal dialog — no portal, no focus trap, just an overlay + panel.
// Fine for v1 confirmation dialogs on a short-lived dashboard session.

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => onOpenChange(false)}
          className="absolute right-4 top-4 rounded-full p-1 text-ink-500 hover:bg-ink-100 hover:text-ink-900"
          aria-label="Закрыть"
        >
          <X size={16} />
        </button>
        {children}
      </div>
    </div>
  );
}

interface DialogTitleProps {
  children: ReactNode;
  className?: string;
}

export function DialogTitle({ children, className }: DialogTitleProps) {
  return (
    <h2
      className={cn(
        "font-display text-xl font-semibold text-ink-900",
        className,
      )}
    >
      {children}
    </h2>
  );
}

export function DialogDescription({
  children,
  className,
}: DialogTitleProps) {
  return (
    <p className={cn("mt-2 text-sm text-ink-500", className)}>{children}</p>
  );
}

export function DialogFooter({
  children,
  className,
}: DialogTitleProps) {
  return (
    <div className={cn("mt-6 flex justify-end gap-2", className)}>
      {children}
    </div>
  );
}
