import { useTranslation } from "react-i18next";
import { CornerDownRight } from "lucide-react";
import { useProjectTasks, type TaskFilters } from "@/lib/queries";
import { Avatar } from "@/components/ui/Avatar";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui/primitives";
import { DueDate, PriorityTag, StatePill } from "@/components/ui/task-bits";
import type { Task } from "@/lib/types";

export function TaskListView({
  projectId,
  filters,
  onOpen,
}: {
  projectId: string;
  filters: TaskFilters;
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useProjectTasks(projectId, filters);

  if (isLoading) return <Spinner label={t("common.loading")} />;
  if (isError) return <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />;
  if (!data || data.items.length === 0) return <EmptyState title={t("list.empty")} />;

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-sunken text-left">
              <Th className="w-24">{t("list.columns.ref")}</Th>
              <Th>{t("list.columns.title")}</Th>
              <Th className="w-44">{t("list.columns.state")}</Th>
              <Th className="w-32">{t("list.columns.priority")}</Th>
              <Th className="w-40">{t("list.columns.assignee")}</Th>
              <Th className="w-32">{t("list.columns.due")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((task, i) => (
              <Row key={task.id} task={task} zebra={i % 2 === 1} onOpen={onOpen} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-4 py-2.5 text-[11px] font-semibold uppercase tracking-label text-ink-subtle ${className ?? ""}`}>
      {children}
    </th>
  );
}

function Row({ task, zebra, onOpen }: { task: Task; zebra: boolean; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const done = task.state_category === "done";
  return (
    <tr
      onClick={() => onOpen(task.id)}
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen(task.id))}
      className={`cursor-pointer border-b border-line/70 transition-colors hover:bg-sky-soft/40 ${
        zebra ? "bg-surface-sunken/60" : "bg-white"
      }`}
    >
      <td className="px-4 py-3 font-mono text-xs font-semibold text-ink-subtle">{task.ref}</td>
      <td className="px-4 py-3">
        <span className="flex items-center gap-2">
          {task.parent_task_id && <CornerDownRight className="h-3.5 w-3.5 text-ink-subtle" />}
          <span className={done ? "text-ink-muted line-through" : "font-medium text-ink"}>
            {task.title}
          </span>
          {(task.subtask_count ?? 0) > 0 && (
            <span className="rounded-full bg-surface-muted px-1.5 text-[11px] font-semibold text-ink-subtle">
              {task.subtask_count}
            </span>
          )}
        </span>
      </td>
      <td className="px-4 py-3">
        <StatePill name={task.state_name ?? "—"} category={task.state_category} />
      </td>
      <td className="px-4 py-3">
        <PriorityTag priority={task.priority} />
      </td>
      <td className="px-4 py-3">
        {task.assignee ? (
          <span className="flex items-center gap-2">
            <Avatar name={task.assignee.display_name} id={task.assignee.id} />
            <span className="truncate text-[13px]">{task.assignee.display_name}</span>
          </span>
        ) : (
          <span className="text-xs text-ink-subtle">{t("task.unassigned")}</span>
        )}
      </td>
      <td className="px-4 py-3">
        <DueDate value={task.due_date} done={done} />
      </td>
    </tr>
  );
}
