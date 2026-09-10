import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { DueDate, PriorityTag } from "@/components/ui/task-bits";
import type { Task } from "@/lib/types";

export function TaskCard({
  task,
  onOpen,
  onMove,
  canMovePrev,
  canMoveNext,
  dragging,
  draggableProps,
}: {
  task: Task;
  onOpen: (id: string) => void;
  onMove?: (dir: -1 | 1) => void;
  canMovePrev?: boolean;
  canMoveNext?: boolean;
  dragging?: boolean;
  draggableProps?: React.HTMLAttributes<HTMLDivElement> & { draggable?: boolean };
}) {
  const { t } = useTranslation();
  const done = task.state_category === "done";

  return (
    <div
      {...draggableProps}
      onClick={() => onOpen(task.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen(task.id);
        if (onMove && (e.key === "[" || e.key === "ArrowLeft") && canMovePrev) {
          e.preventDefault();
          onMove(-1);
        }
        if (onMove && (e.key === "]" || e.key === "ArrowRight") && canMoveNext) {
          e.preventDefault();
          onMove(1);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`${task.ref} ${task.title}`}
      className={clsx(
        "group cursor-pointer rounded-md border border-line bg-white p-3 shadow-card transition-shadow hover:shadow-raised",
        dragging && "opacity-50",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] font-semibold text-ink-subtle">{task.ref}</span>
        <PriorityTag priority={task.priority} />
      </div>

      <p className={clsx("mt-1.5 text-[13px] font-medium", done ? "text-ink-muted line-through" : "text-ink")}>
        {task.title}
      </p>

      <div className="mt-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {task.assignee ? (
            <Avatar name={task.assignee.display_name} id={task.assignee.id} />
          ) : (
            <span className="text-[11px] text-ink-subtle">{t("task.unassigned")}</span>
          )}
          <DueDate value={task.due_date} done={done} />
        </div>

        {onMove && (
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <button
              disabled={!canMovePrev}
              onClick={(e) => {
                e.stopPropagation();
                onMove(-1);
              }}
              className="rounded p-1 text-ink-subtle hover:bg-surface-muted hover:text-ink disabled:opacity-30"
              aria-label={t("board.moveLeft")}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button
              disabled={!canMoveNext}
              onClick={(e) => {
                e.stopPropagation();
                onMove(1);
              }}
              className="rounded p-1 text-ink-subtle hover:bg-surface-muted hover:text-ink disabled:opacity-30"
              aria-label={t("board.moveRight")}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
