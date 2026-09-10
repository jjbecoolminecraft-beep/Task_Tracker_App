import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { FolderKanban, ListChecks, LogOut, Search } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { setLanguage } from "@/i18n";
import { Avatar } from "@/components/ui/Avatar";
import { NotificationBell } from "./NotificationBell";

const NAV = [
  { to: "/projects", key: "nav.projects", icon: FolderKanban },
  { to: "/my-tasks", key: "nav.myTasks", icon: ListChecks },
  { to: "/search", key: "nav.search", icon: Search },
];

function contextLabel(pathname: string, t: (k: string) => string): string {
  if (pathname.startsWith("/my-tasks")) return t("nav.myTasks");
  if (pathname.startsWith("/search")) return t("nav.search");
  if (pathname.startsWith("/projects")) return t("nav.projects");
  return t("app.name");
}

export function AppShell() {
  const { t, i18n } = useTranslation();
  const { session, logout } = useAuth();
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-surface-sunken">
      <header className="sticky top-0 z-30 border-b border-line bg-white">
        <div className="mx-auto flex h-14 max-w-shell items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded bg-navy-800 font-display text-sm font-extrabold text-white">
              KB
            </span>
            <span className="font-display text-[15px] font-bold text-navy-900">
              {t("app.name")}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="hidden kb-label sm:block">{contextLabel(pathname, t)}</span>
            {session && <NotificationBell />}
            <div className="flex overflow-hidden rounded border border-line text-xs font-semibold">
              {(["en", "de"] as const).map((lng) => (
                <button
                  key={lng}
                  onClick={() => setLanguage(lng)}
                  className={clsx(
                    "px-2 py-1 uppercase",
                    i18n.language === lng
                      ? "bg-navy-800 text-white"
                      : "bg-white text-ink-muted hover:bg-surface-muted",
                  )}
                >
                  {lng}
                </button>
              ))}
            </div>
            {session && (
              <div className="flex items-center gap-2">
                <Avatar name={session.display_name} id={session.id} size={28} />
                <div className="hidden leading-tight sm:block">
                  <div className="text-[13px] font-semibold text-navy-900">
                    {session.display_name}
                  </div>
                  <div className="text-[11px] text-ink-subtle">{session.department}</div>
                </div>
                <button
                  onClick={logout}
                  className="ml-1 rounded p-1.5 text-ink-subtle hover:bg-surface-muted hover:text-ink"
                  title={t("nav.signOut")}
                  aria-label={t("nav.signOut")}
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-shell gap-6 px-4 py-7 sm:px-6">
        <nav className="hidden w-48 shrink-0 md:block">
          <ul className="space-y-1">
            {NAV.map(({ to, key, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  className={({ isActive }) =>
                    clsx(
                      "flex items-center gap-2.5 rounded px-3 py-2 text-sm font-semibold transition-colors",
                      isActive
                        ? "bg-white text-navy-900 shadow-card"
                        : "text-ink-muted hover:bg-white/60 hover:text-ink",
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {t(key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
