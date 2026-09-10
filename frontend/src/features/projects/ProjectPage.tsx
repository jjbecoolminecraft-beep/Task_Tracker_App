import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { ChevronLeft, LayoutGrid, List as ListIcon, Plus } from "lucide-react";
import { useProject, useUsers, useWorkflowStates, type TaskFilters } from "@/lib/queries";
import { Button } from "@/components/ui/Button";
import { Badge, ErrorNote, Select, Spinner } from "@/components/ui/primitives";
import { TaskListView } from "@/features/tasks/TaskListView";
import { TaskBoardView } from "@/features/tasks/TaskBoardView";
import { TaskDetailDrawer } from "@/features/tasks/TaskDetailDrawer";
import { CreateTaskDialog } from "@/features/tasks/CreateTaskDialog";
import { ImportExportMenu } from "@/features/tasks/ImportExportMenu";

type Tab = "list" | "board";

export function ProjectPage() {
  const { t } = useTranslation();
  const { projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();

  const tab = (params.get("view") as Tab) ?? "list";
  const selectedTaskId = params.get("task");
  const [creating, setCreating] = useState(false);

  const project = useProject(projectId);
  const states = useWorkflowStates(projectId);
  const users = useUsers();

  const [filters, setFilters] = useState<TaskFilters>({ sort: "created_at" });
  const canWrite =
    project.data?.my_role === "project_admin" ||
    project.data?.my_role === "contributor" ||
    project.data?.my_role === "portfolio_owner";

  function setTab(next: Tab) {
    params.set("view", next);
    setParams(params, { replace: true });
  }
  function openTask(id: string | null) {
    if (id) params.set("task", id);
    else params.delete("task");
    setParams(params, { replace: true });
  }

  if (project.isLoading) return <Spinner label={t("common.loading")} />;
  if (project.isError || !project.data)
    return <ErrorNote message={t("common.error")} onRetry={() => void project.refetch()} />;

  const p = project.data;

  return (
    <>
      <Link
        to="/projects"
        className="mb-3 inline-flex items-center gap-1 text-[13px] font-semibold text-ink-muted hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" />
        {t("projects.title")}
      </Link>

      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="mt-1 rounded-sm bg-navy-800 px-2.5 py-1 font-display text-sm font-bold text-white">
            {p.key}
          </span>
          <div>
            <h1 className="font-display text-[24px] font-bold text-navy-900">{p.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone={p.visibility === "internal" ? "blue" : "neutral"}>
                {p.visibility === "internal"
                  ? t("projects.visibilityInternal")
                  : t("projects.visibilityPrivate")}
              </Badge>
              {p.status === "archived" && <Badge tone="warning">{t("projects.archived")}</Badge>}
              {p.my_role && (
                <span className="text-xs capitalize text-ink-subtle">
                  {t("projects.role")}: {p.my_role.replace(/_/g, " ")}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ImportExportMenu projectId={projectId} canWrite={!!canWrite} />
          {canWrite && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              {t("task.new")}
            </Button>
          )}
        </div>
      </div>

      {/* tab switch + filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex overflow-hidden rounded border border-line">
          {(
            [
              ["list", ListIcon, t("list.title")],
              ["board", LayoutGrid, t("board.title")],
            ] as const
          ).map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 text-[13px] font-semibold",
                tab === id ? "bg-navy-800 text-white" : "bg-white text-ink-muted hover:bg-surface-muted",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <FilterBar
          filters={filters}
          onChange={setFilters}
          states={states.data ?? []}
          users={(users.data ?? []).map((u) => ({ id: u.id, name: u.display_name }))}
        />
      </div>

      {tab === "list" ? (
        <TaskListView projectId={projectId} filters={filters} onOpen={openTask} />
      ) : (
        <TaskBoardView
          projectId={projectId}
          filters={filters}
          states={states.data ?? []}
          canWrite={!!canWrite}
          onOpen={openTask}
        />
      )}

      <TaskDetailDrawer
        taskId={selectedTaskId}
        projectId={projectId}
        canWrite={!!canWrite}
        onClose={() => openTask(null)}
        onOpenTask={openTask}
      />
      <CreateTaskDialog
        open={creating}
        projectId={projectId}
        states={states.data ?? []}
        users={(users.data ?? []).map((u) => ({ id: u.id, name: u.display_name }))}
        onClose={() => setCreating(false)}
      />
    </>
  );
}

function FilterBar({
  filters,
  onChange,
  states,
  users,
}: {
  filters: TaskFilters;
  onChange: (f: TaskFilters) => void;
  states: { id: string; name: string }[];
  users: { id: string; name: string }[];
}) {
  const { t } = useTranslation();
  const set = (patch: Partial<TaskFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        value={filters.q ?? ""}
        onChange={(e) => set({ q: e.target.value || undefined })}
        placeholder={t("list.filters.search")}
        className="kb-input h-[34px] w-52 py-1"
      />
      <Select
        className="h-[34px] w-auto py-1 text-[13px]"
        value={filters.state_id ?? ""}
        onChange={(e) => set({ state_id: e.target.value || undefined })}
      >
        <option value="">{t("list.filters.state")}: {t("list.filters.all")}</option>
        {states.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </Select>
      <Select
        className="h-[34px] w-auto py-1 text-[13px]"
        value={filters.unassigned ? "__unassigned" : (filters.assignee_id ?? "")}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "__unassigned") set({ unassigned: true, assignee_id: undefined });
          else set({ unassigned: undefined, assignee_id: v || undefined });
        }}
      >
        <option value="">{t("list.filters.assignee")}: {t("list.filters.anyAssignee")}</option>
        <option value="__unassigned">{t("list.filters.unassigned")}</option>
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </Select>
      <Select
        className="h-[34px] w-auto py-1 text-[13px]"
        value={filters.priority ?? ""}
        onChange={(e) => set({ priority: e.target.value ? Number(e.target.value) : undefined })}
      >
        <option value="">{t("list.filters.priority")}: {t("list.filters.all")}</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            {t(`priority.${n}`)}
          </option>
        ))}
      </Select>
      {(filters.q || filters.state_id || filters.assignee_id || filters.priority || filters.unassigned) && (
        <button
          onClick={() => onChange({ sort: filters.sort })}
          className="text-[13px] font-semibold text-primary hover:underline"
        >
          {t("list.filters.clear")}
        </button>
      )}
    </div>
  );
}
