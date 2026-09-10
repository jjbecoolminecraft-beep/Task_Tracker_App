import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ShieldCheck } from "lucide-react";
import { useAuditEvents, useProjects } from "@/lib/queries";
import { useAuth, hasRole } from "@/lib/auth";
import { Avatar } from "@/components/ui/Avatar";
import { Badge, Card, EmptyState, ErrorNote, PageHeader, Select, Spinner } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import type { AuditEvent } from "@/lib/types";

const ACTION_TONE: Record<string, "neutral" | "blue" | "success" | "warning" | "danger"> = {
  created: "success",
  updated: "blue",
  completed: "success",
  deleted: "danger",
  archived: "warning",
  exported: "warning",
  imported: "warning",
  member_added: "blue",
  member_removed: "danger",
};

function toneFor(action: string) {
  const verb = action.split(".").pop() ?? "";
  return ACTION_TONE[verb] ?? "neutral";
}

function DiffCell({ event }: { event: AuditEvent }) {
  const keys = [
    ...new Set([...Object.keys(event.before ?? {}), ...Object.keys(event.after ?? {})]),
  ];
  if (keys.length === 0) return <span className="text-ink-subtle">—</span>;
  return (
    <ul className="space-y-0.5">
      {keys.map((k) => (
        <li key={k} className="flex flex-wrap items-baseline gap-1.5 text-[12px]">
          <span className="font-mono text-ink-subtle">{k}</span>
          <span className="text-danger/80 line-through">{fmt(event.before?.[k])}</span>
          <span className="text-ink-subtle">→</span>
          <span className="font-medium text-success">{fmt(event.after?.[k])}</span>
        </li>
      ))}
    </ul>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "∅";
  if (typeof v === "string" && v.length > 40) return v.slice(0, 40) + "…";
  return String(v);
}

export function AuditLogPage() {
  const { t, i18n } = useTranslation();
  const { session } = useAuth();
  const projects = useProjects();
  const [projectId, setProjectId] = useState("");
  const [cursor, setCursor] = useState<number | undefined>();

  const events = useAuditEvents({ projectId: projectId || undefined, beforeId: cursor });

  // Spec §2.2 / §8.4.4: audit access is the Auditor's alone.
  if (session && !hasRole(session, "auditor")) return <Navigate to="/projects" replace />;

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-primary" />
            {t("audit.title")}
          </span>
        }
        subtitle={t("audit.subtitle")}
        actions={
          <Select
            className="h-[34px] w-56 py-1 text-[13px]"
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value);
              setCursor(undefined);
            }}
          >
            <option value="">{t("audit.allProjects")}</option>
            {(projects.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.key} — {p.name}
              </option>
            ))}
          </Select>
        }
      />

      {events.isLoading && <Spinner label={t("common.loading")} />}
      {events.isError && <ErrorNote message={t("common.error")} onRetry={() => void events.refetch()} />}
      {events.data && events.data.length === 0 && <EmptyState title={t("audit.empty")} />}

      {events.data && events.data.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-sunken text-left">
                  {["when", "actor", "action", "resource", "changes"].map((c) => (
                    <th
                      key={c}
                      className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-label text-ink-subtle"
                    >
                      {t(`audit.col.${c}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.data.map((e, i) => (
                  <tr
                    key={e.id}
                    className={`border-b border-line/70 align-top ${i % 2 ? "bg-surface-sunken/60" : "bg-white"}`}
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-[12px] text-ink-muted">
                      {new Intl.DateTimeFormat(i18n.language, {
                        dateStyle: "short",
                        timeStyle: "medium",
                      }).format(new Date(e.occurred_at))}
                    </td>
                    <td className="px-4 py-3">
                      {e.actor_upn ? (
                        <span className="flex items-center gap-2">
                          <Avatar name={e.actor_upn} id={e.actor_id ?? undefined} />
                          <span className="text-[12px] text-ink">{e.actor_upn}</span>
                        </span>
                      ) : (
                        <span className="text-[12px] text-ink-subtle">system</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={toneFor(e.action)}>{e.action}</Badge>
                    </td>
                    <td className="px-4 py-3 text-[12px]">
                      <span className="text-ink">{e.resource_type}</span>
                      {e.resource_id && (
                        <span className="ml-1 font-mono text-ink-subtle">
                          {e.resource_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <DiffCell event={e} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {events.data.length === 50 && (
            <div className="flex justify-center border-t border-line py-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCursor(events.data![events.data!.length - 1].id)}
              >
                {t("list.loadMore")}
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
