import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { AtSign, Bell, CheckCheck, MessageSquare, UserPlus } from "lucide-react";
import {
  useMarkAllRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/queries";
import type { Notification } from "@/lib/types";

const ICON: Record<string, typeof Bell> = {
  "task.assigned": UserPlus,
  "comment.mention": AtSign,
  "comment.added": MessageSquare,
  "task.due_soon": Bell,
};

function useOutsideClose(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);
  return ref;
}

function relativeTime(iso: string, locale: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (mins < 1) return rtf.format(0, "minute");
  if (mins < 60) return rtf.format(-mins, "minute");
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return rtf.format(-hrs, "hour");
  return rtf.format(-Math.round(hrs / 24), "day");
}

export function NotificationBell() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useOutsideClose(() => setOpen(false));

  const unread = useUnreadCount();
  const list = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllRead();

  const count = unread.data?.unread ?? 0;

  function activate(n: Notification) {
    if (!n.is_read) markRead.mutate(n.id);
    setOpen(false);
    if (n.project_id && n.task_id) navigate(`/projects/${n.project_id}?task=${n.task_id}`);
  }

  function label(n: Notification): string {
    const who = n.actor_name ?? t("notifications.someone");
    return t(`notifications.kind.${n.kind}`, { who, ref: n.task_ref ?? "" });
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink"
        aria-label={t("notifications.title")}
        aria-expanded={open}
      >
        <Bell className="h-[18px] w-[18px]" />
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-[16px] place-items-center rounded-full bg-primary px-1 text-[10px] font-bold text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[360px] overflow-hidden rounded-md border border-line bg-white shadow-overlay">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <span className="font-display text-sm font-bold text-navy-900">
              {t("notifications.title")}
            </span>
            {count > 0 && (
              <button
                onClick={() => markAll.mutate()}
                className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                {t("notifications.markAllRead")}
              </button>
            )}
          </div>

          <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
            {(list.data ?? []).map((n) => {
              const Icon = ICON[n.kind] ?? Bell;
              return (
                <li key={n.id}>
                  <button
                    onClick={() => activate(n)}
                    className={clsx(
                      "flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-sky-soft/40",
                      !n.is_read && "bg-sky-soft/30",
                    )}
                  >
                    <span
                      className={clsx(
                        "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full",
                        n.is_read ? "bg-surface-muted text-ink-subtle" : "bg-primary/10 text-primary",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] leading-snug text-ink">{label(n)}</span>
                      {n.snippet && (
                        <span className="mt-0.5 block truncate text-xs text-ink-muted">
                          “{n.snippet}”
                        </span>
                      )}
                      <span className="mt-0.5 block text-[11px] text-ink-subtle">
                        {relativeTime(n.created_at, i18n.language)}
                      </span>
                    </span>
                    {!n.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />}
                  </button>
                </li>
              );
            })}
            {list.data?.length === 0 && (
              <li className="px-4 py-8 text-center text-[13px] text-ink-subtle">
                {t("notifications.empty")}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
