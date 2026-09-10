import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { clsx } from "clsx";
import { useProjectTasks, useUpdateTask, type TaskFilters } from "@/lib/queries";
import { ErrorNote, Spinner } from "@/components/ui/primitives";
import type { Task, WorkflowState } from "@/lib/types";
import { TaskCard } from "./TaskCard";

const CATEGORY_ACCENT: Record<string, string> = {
  backlog: "border-t-ink-subtle",
  in_progress: "border-t-primary",
  done: "border-t-success",
};

export function TaskBoardView({
  projectId,
  filters,
  states,
  canWrite,
  onOpen,
}: {
  projectId: string;
  filters: TaskFilters;
  states: WorkflowState[];
  canWrite: boolean;
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useProjectTasks(projectId, {
    ...filters,
    state_id: undefined, // board shows every column
    limit: 200,
  });
  const updateTask = useUpdateTask();
  const [dragId, setDragId] = useState<string | null>(null);
  const [overState, setOverState] = useState<string | null>(null);

  const ordered = useMemo(() => [...states].sort((a, b) => a.position - b.position), [states]);

  const byState = useMemo(() => {
    const map = new Map<string, Task[]>();
    ordered.forEach((s) => map.set(s.id, []));
    (data?.items ?? []).forEach((task) => {
      if (!map.has(task.state_id)) map.set(task.state_id, []);
      map.get(task.state_id)!.push(task);
    });
    return map;
  }, [data, ordered]);

  if (isLoading) return <Spinner label={t("common.loading")} />;
  if (isError) return <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />;

  function move(task: Task, toStateId: string) {
    if (toStateId === task.state_id) return;
    updateTask.mutate({ id: task.id, version: task.version, patch: { state_id: toStateId } });
  }
  function step(task: Task, dir: -1 | 1) {
    const idx = ordered.findIndex((s) => s.id === task.state_id);
    const next = ordered[idx + dir];
    if (next) move(task, next.id);
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {ordered.map((state) => {
        const items = byState.get(state.id) ?? [];
        return (
          <section
            key={state.id}
            onDragOver={(e) => {
              if (dragId && canWrite) {
                e.preventDefault();
                setOverState(state.id);
              }
            }}
            onDragLeave={() => setOverState((s) => (s === state.id ? null : s))}
            onDrop={() => {
              const task = (data?.items ?? []).find((x) => x.id === dragId);
              if (task && canWrite) move(task, state.id);
              setDragId(null);
              setOverState(null);
            }}
            className={clsx(
              "flex w-[280px] shrink-0 flex-col rounded-md border border-line border-t-2 bg-surface-muted/60",
              CATEGORY_ACCENT[state.category],
              overState === state.id && "ring-2 ring-primary/40",
            )}
          >
            <header className="flex items-center justify-between px-3 py-2.5">
              <span className="text-[13px] font-bold text-navy-900">{state.name}</span>
              <span className="rounded-full bg-white px-2 text-[11px] font-semibold text-ink-subtle">
                {items.length}
              </span>
            </header>

            <div className="flex flex-1 flex-col gap-2 px-2 pb-3">
              {items.map((task) => {
                const idx = ordered.findIndex((s) => s.id === task.state_id);
                return (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onOpen={onOpen}
                    onMove={canWrite ? (dir) => step(task, dir) : undefined}
                    canMovePrev={idx > 0}
                    canMoveNext={idx < ordered.length - 1}
                    dragging={dragId === task.id}
                    draggableProps={
                      canWrite
                        ? {
                            draggable: true,
                            onDragStart: () => setDragId(task.id),
                            onDragEnd: () => {
                              setDragId(null);
                              setOverState(null);
                            },
                          }
                        : undefined
                    }
                  />
                );
              })}
              {items.length === 0 && (
                <p className="px-1 py-6 text-center text-xs text-ink-subtle">—</p>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
