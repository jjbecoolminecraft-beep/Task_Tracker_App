import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, EmptyState } from "@/components/ui/primitives";
import { Avatar } from "@/components/ui/Avatar";
import { DueDate, PriorityTag, StatePill } from "@/components/ui/task-bits";
import type { Task } from "@/lib/types";

/** A flat, cross-project task list used by "My tasks" and Search. */
export function TaskRows({ tasks, emptyTitle }: { tasks: Task[]; emptyTitle: string }) {
  const { t } = useTranslation();
  if (tasks.length === 0) return <EmptyState title={emptyTitle} />;

  return (
    <Card className="divide-y divide-line overflow-hidden">
      {tasks.map((task) => {
        const done = task.state_category === "done";
        return (
          <Link
            key={task.id}
            to={`/projects/${task.project_id}?task=${task.id}`}
            className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-sky-soft/40"
          >
            <span className="w-20 shrink-0 font-mono text-xs font-semibold text-ink-subtle">
              {task.ref}
            </span>
            <span className="min-w-0 flex-1">
              <span className={done ? "text-ink-muted line-through" : "font-medium text-ink"}>
                {task.title}
              </span>
              <span className="ml-2 text-[11px] uppercase tracking-label text-ink-subtle">
                {task.project_key}
              </span>
            </span>
            <StatePill name={task.state_name ?? "—"} category={task.state_category} />
            <span className="hidden sm:block">
              <PriorityTag priority={task.priority} />
            </span>
            <span className="hidden w-24 md:block">
              <DueDate value={task.due_date} done={done} />
            </span>
            <span className="w-8 shrink-0">
              {task.assignee ? (
                <Avatar name={task.assignee.display_name} id={task.assignee.id} />
              ) : (
                <span className="text-[11px] text-ink-subtle">{t("task.unassigned")}</span>
              )}
            </span>
          </Link>
        );
      })}
    </Card>
  );
}
