import { Link, NavLink } from "react-router-dom";
import { Bot, LayoutDashboard, ScrollText, LogOut, Fish } from "lucide-react";
import { useMe, useLogout } from "@/api/hooks";
import { cn } from "@/lib/cn";

export function Shell({ children }: { children: React.ReactNode }) {
  const { data: me } = useMe();
  const logout = useLogout();

  return (
    <div className="min-h-screen bg-ink-50">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link
            to="/dashboard"
            className="flex items-center gap-2 font-display text-lg font-semibold text-ink-900"
          >
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-ink-950 text-white">
              <Bot size={16} />
            </span>
            doomedash
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            <NavItem to="/dashboard" icon={<LayoutDashboard size={14} />} label="Dashboard" />
            <NavItem to="/audit" icon={<ScrollText size={14} />} label="Audit" />
            <a
              href="/voodoo/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
            >
              <Fish size={14} /> Voodoo
            </a>
          </nav>

          <div className="flex items-center gap-3">
            {me && (
              <div className="hidden items-center gap-2 text-sm text-ink-500 md:flex">
                {me.photo_url && (
                  <img
                    src={me.photo_url}
                    alt=""
                    className="h-6 w-6 rounded-full"
                  />
                )}
                <span className="font-medium text-ink-900">
                  {me.first_name || me.username || me.tg_id}
                </span>
              </div>
            )}
            <button
              onClick={() => logout.mutate()}
              className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:bg-ink-100"
              disabled={logout.isPending}
            >
              <LogOut size={13} /> Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}

function NavItem({
  to,
  icon,
  label,
}: {
  to: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors",
          isActive
            ? "bg-ink-900 text-white"
            : "text-ink-500 hover:bg-ink-100 hover:text-ink-900",
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}
