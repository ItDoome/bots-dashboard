import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type HTMLAttributes,
  type ButtonHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

// Minimal hand-rolled Tabs primitive (no Radix) — matches the rest of the UI
// kit. State is held in a context so <TabsTrigger> and <TabsContent> can read
// the active value without prop-drilling.
//
// The active indicator is a single absolutely-positioned pill behind the
// buttons; it animates its `left`/`width` via CSS transition when the active
// tab changes (shared-layout style, no framer-motion dep).

interface TabsContextValue {
  value: string;
  setValue: (v: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("Tabs primitives must be used inside <Tabs>");
  return ctx;
}

interface TabsProps {
  defaultValue: string;
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children: ReactNode;
}

export function Tabs({
  defaultValue,
  value,
  onValueChange,
  className,
  children,
}: TabsProps) {
  const [internal, setInternal] = useState(defaultValue);
  const active = value ?? internal;
  const setValue = (v: string) => {
    if (value === undefined) setInternal(v);
    onValueChange?.(v);
  };
  return (
    <TabsContext.Provider value={{ value: active, setValue }}>
      <div className={cn("flex flex-col gap-4", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  const ctx = useTabsContext();
  const listRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  // Track whether we've positioned the indicator at least once — gate the
  // transition until after the first measurement so the pill doesn't animate
  // from (0,0) on mount.
  const [ready, setReady] = useState(false);

  const measure = () => {
    const list = listRef.current;
    if (!list) return;
    const active = list.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    if (!active) {
      setIndicator(null);
      return;
    }
    const listRect = list.getBoundingClientRect();
    const activeRect = active.getBoundingClientRect();
    setIndicator({
      // offsetLeft would be cleaner but `left - listLeft + scrollLeft` also
      // works when the list is horizontally scrolled on narrow mobile.
      left: activeRect.left - listRect.left + list.scrollLeft,
      width: activeRect.width,
    });
  };

  useLayoutEffect(() => {
    measure();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.value]);

  useEffect(() => {
    // Re-measure when fonts finish loading or viewport resizes — tab widths
    // depend on both.
    const onResize = () => measure();
    window.addEventListener("resize", onResize);
    // Fire once after first paint so indicator CSS transition kicks in for
    // subsequent value changes (not for the initial mount).
    const raf = requestAnimationFrame(() => setReady(true));
    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={listRef}
      role="tablist"
      className={cn(
        "relative inline-flex w-fit max-w-full gap-1 overflow-x-auto whitespace-nowrap rounded-full border border-ink-200 bg-white p-1 shadow-sm [&::-webkit-scrollbar]:hidden [scrollbar-width:none]",
        className,
      )}
      {...props}
    >
      {indicator && (
        <div
          aria-hidden
          className={cn(
            // Absolute at (0,0), transform moves it — GPU-composited (no layout/paint per frame)
            "pointer-events-none absolute left-0 top-1 bottom-1 rounded-full bg-ink-900",
            ready && "transition-[transform,width] duration-[250ms] ease-[cubic-bezier(0.32,0.72,0,1)]",
          )}
          style={{
            width: indicator.width,
            transform: `translate3d(${indicator.left}px, 0, 0)`,
            willChange: "transform, width",
          }}
        />
      )}
      {children}
    </div>
  );
}

interface TabsTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({
  value,
  className,
  children,
  ...props
}: TabsTriggerProps) {
  const ctx = useTabsContext();
  const active = ctx.value === value;
  return (
    <button
      role="tab"
      aria-selected={active}
      className={cn(
        // z-10 keeps text above the sliding indicator
        "relative z-10 rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
        active
          ? "text-white"
          : "text-ink-500 hover:text-ink-900",
        className,
      )}
      onClick={() => ctx.setValue(value)}
      {...props}
    >
      {children}
    </button>
  );
}

interface TabsContentProps extends HTMLAttributes<HTMLDivElement> {
  value: string;
}

export function TabsContent({
  value,
  className,
  children,
  ...props
}: TabsContentProps) {
  const ctx = useTabsContext();
  if (ctx.value !== value) return null;
  return (
    <div
      role="tabpanel"
      className={cn("flex flex-col gap-4", className)}
      {...props}
    >
      {children}
    </div>
  );
}
