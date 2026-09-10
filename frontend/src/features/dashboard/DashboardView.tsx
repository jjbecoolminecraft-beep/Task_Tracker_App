import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { useDashboard } from "@/lib/queries";
import { Card, ErrorNote, SectionTitle, Spinner } from "@/components/ui/primitives";
import type { ProjectDashboard, WorkflowCategory } from "@/lib/types";

/**
 * Aggregated project reporting (spec F-22). No per-person figures — the API does
 * not expose them (spec §8.4.1). Single-hue bars + KPI tiles; the only colour
 * with meaning is the coarse workflow category, always shown with a text label.
 */
const CATEGORY_DOT: Record<WorkflowCategory, string> = {
  backlog: "bg-ink-subtle",
  in_progress: "bg-primary",
  done: "bg-success",
};

export function DashboardView({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useDashboard(projectId);

  if (isLoading) return <Spinner label={t("common.loading")} />;
  if (isError || !data)
    return <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />;

  return (
    <div className="space-y-6">
      <KpiRow d={data} />

      <div className="grid gap-4 lg:grid-cols-2">
        <StateDistribution d={data} />
        <PriorityDistribution d={data} />
      </div>

      <Throughput d={data} />

      <p className="text-[11px] text-ink-subtle">{t("dashboard.privacyNote")}</p>
    </div>
  );
}

function Kpi({
  label,
  value,
  caption,
  filled,
  tone,
}: {
  label: string;
  value: number | string;
  caption?: string;
  filled?: boolean;
  tone?: "warning";
}) {
  return (
    <div
      className={clsx(
        "rounded-md border p-4",
        filled ? "border-navy-800 bg-navy-800 text-white" : "border-line bg-white shadow-card",
        tone === "warning" && !filled && "border-warning/30 bg-warning-soft",
      )}
    >
      <span className={clsx("kb-label", filled ? "!text-white/70" : "")}>{label}</span>
      <div
        className={clsx(
          "mt-1 font-display text-[26px] font-bold leading-none",
          filled ? "text-white" : tone === "warning" ? "text-warning" : "text-navy-900",
        )}
      >
        {value}
      </div>
      {caption && (
        <span className={clsx("mt-1 block text-[11px]", filled ? "text-white/60" : "text-ink-subtle")}>
          {caption}
        </span>
      )}
    </div>
  );
}

function KpiRow({ d }: { d: ProjectDashboard }) {
  const { t } = useTranslation();
  const donePct = d.total ? Math.round((d.done / d.total) * 100) : 0;
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label={t("dashboard.kpi.total")} value={d.total} filled />
        <Kpi label={t("dashboard.kpi.open")} value={d.open} />
        <Kpi label={t("dashboard.kpi.done")} value={d.done} caption={`${donePct}%`} />
        <Kpi
          label={t("dashboard.kpi.overdue")}
          value={d.overdue}
          tone={d.overdue > 0 ? "warning" : undefined}
        />
        <Kpi label={t("dashboard.kpi.unassigned")} value={d.unassigned} />
      </div>

      {/* completion progress — the design system's proportion bar */}
      <div className="mt-4">
        <div className="flex justify-between text-[11px] font-semibold text-ink-muted">
          <span>{t("dashboard.doneCount", { count: d.done })}</span>
          <span>{t("dashboard.openCount", { count: d.open })}</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-success" style={{ width: `${donePct}%` }} />
        </div>
        {d.avg_open_age_days != null && (
          <p className="mt-2 text-[11px] text-ink-subtle">
            {t("dashboard.avgAge", { days: d.avg_open_age_days })} ·{" "}
            {t("dashboard.contributors", { count: d.contributor_count })}
          </p>
        )}
      </div>
    </div>
  );
}

function BarRow({
  label,
  count,
  max,
  dot,
}: {
  label: string;
  count: number;
  max: number;
  dot?: string;
}) {
  const pct = max ? Math.max((count / max) * 100, count > 0 ? 4 : 0) : 0;
  return (
    <div className="flex items-center gap-3 py-1.5 text-[13px]">
      <span className="flex w-40 shrink-0 items-center gap-2 truncate text-ink">
        {dot && <span className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", dot)} />}
        <span className="truncate">{label}</span>
      </span>
      <span className="relative h-3 flex-1 rounded-sm bg-surface-muted">
        <span
          className="absolute inset-y-0 left-0 rounded-sm bg-primary"
          style={{ width: `${pct}%` }}
          title={`${count}`}
        />
      </span>
      <span className="w-8 shrink-0 text-right font-mono text-xs font-semibold text-ink-muted">
        {count}
      </span>
    </div>
  );
}

function StateDistribution({ d }: { d: ProjectDashboard }) {
  const { t } = useTranslation();
  const max = Math.max(1, ...d.by_state.map((s) => s.count));
  return (
    <Card className="p-5">
      <SectionTitle>{t("dashboard.byState")}</SectionTitle>
      <div className="mt-1">
        {d.by_state.map((s) => (
          <BarRow
            key={s.state_id}
            label={s.name}
            count={s.count}
            max={max}
            dot={CATEGORY_DOT[s.category]}
          />
        ))}
      </div>
      <Legend />
    </Card>
  );
}

function Legend() {
  const { t } = useTranslation();
  return (
    <div className="mt-3 flex flex-wrap gap-3 border-t border-line pt-2 text-[11px] text-ink-muted">
      {(["backlog", "in_progress", "done"] as const).map((c) => (
        <span key={c} className="flex items-center gap-1.5">
          <span className={clsx("h-1.5 w-1.5 rounded-full", CATEGORY_DOT[c])} />
          {t(`dashboard.category.${c}`)}
        </span>
      ))}
    </div>
  );
}

function PriorityDistribution({ d }: { d: ProjectDashboard }) {
  const { t } = useTranslation();
  const max = Math.max(1, ...d.by_priority.map((p) => p.count));
  return (
    <Card className="p-5">
      <SectionTitle>{t("dashboard.byPriority")}</SectionTitle>
      <div className="mt-1">
        {d.by_priority.map((p) => (
          <BarRow key={p.priority} label={t(`priority.${p.priority}`)} count={p.count} max={max} />
        ))}
      </div>
    </Card>
  );
}

function Throughput({ d }: { d: ProjectDashboard }) {
  const { t } = useTranslation();
  const max = Math.max(1, ...d.throughput.map((w) => w.completed));
  const PLOT = 96; // px

  return (
    <Card className="p-5">
      <SectionTitle>{t("dashboard.throughput")}</SectionTitle>
      <p className="-mt-1 mb-4 text-[12px] text-ink-muted">{t("dashboard.throughputHint")}</p>

      <div className="flex gap-2" style={{ height: PLOT }}>
        {d.throughput.map((w) => (
          <div key={w.week} className="flex flex-1 flex-col justify-end">
            <span className="mb-0.5 text-center text-[11px] font-semibold text-ink-muted">
              {w.completed || ""}
            </span>
            <div
              className="w-full rounded-sm bg-navy-700"
              style={{ height: Math.max((w.completed / max) * (PLOT - 16), w.completed ? 3 : 2) }}
              title={`${w.label}: ${w.completed}`}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-2 border-t border-line pt-1.5">
        {d.throughput.map((w) => (
          <span key={w.week} className="flex-1 text-center text-[10px] text-ink-subtle">
            {w.label}
          </span>
        ))}
      </div>
    </Card>
  );
}
