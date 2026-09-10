import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import type { WorkflowCategory } from "@/lib/types";

const CATEGORY_DOT: Record<WorkflowCategory, string> = {
  backlog: "bg-ink-subtle",
  in_progress: "bg-primary",
  done: "bg-success",
};

export function StatePill({
  name,
  category,
}: {
  name: string;
  category: WorkflowCategory | null;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-0.5 text-xs font-semibold text-navy-800">
      <span className={clsx("h-1.5 w-1.5 rounded-full", CATEGORY_DOT[category ?? "backlog"])} />
      {name}
    </span>
  );
}

const PRIORITY_STYLE: Record<number, string> = {
  1: "text-danger",
  2: "text-warning",
  3: "text-ink-muted",
  4: "text-ink-subtle",
  5: "text-ink-subtle",
};

export function PriorityTag({ priority }: { priority: number }) {
  const { t } = useTranslation();
  const bars = 6 - priority; // P1 -> 5 bars, P5 -> 1 bar
  return (
    <span
      className={clsx("inline-flex items-center gap-1.5 text-xs font-semibold", PRIORITY_STYLE[priority])}
      title={t(`priority.${priority}`)}
    >
      <span className="flex items-end gap-[2px]" aria-hidden>
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            className={clsx(
              "w-[3px] rounded-sm",
              i <= bars ? "bg-current" : "bg-line",
            )}
            style={{ height: `${4 + i * 2}px` }}
          />
        ))}
      </span>
      {t(`priority.${priority}`)}
    </span>
  );
}

export function DueDate({ value, done }: { value: string | null; done?: boolean }) {
  const { t, i18n } = useTranslation();
  if (!value) return <span className="text-xs text-ink-subtle">—</span>;

  const date = new Date(value + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const overdue = !done && date < today;
  const isToday = date.getTime() === today.getTime();

  const label = new Intl.DateTimeFormat(i18n.language, {
    day: "numeric",
    month: "short",
  }).format(date);

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 whitespace-nowrap text-xs font-medium",
        overdue ? "text-danger" : isToday ? "text-warning" : "text-ink-muted",
      )}
    >
      {overdue && <span className="kb-label !text-danger">{t("common.overdue")}</span>}
      {label}
    </span>
  );
}
