import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Trash2 } from "lucide-react";
import {
  useAddComment,
  useComments,
  useCompleteTask,
  useDeleteTask,
  useTask,
  useUpdateTask,
  useUsers,
  useWorkflowStates,
} from "@/lib/queries";
import { ApiRequestError } from "@/lib/api";
import { Drawer } from "@/components/ui/Drawer";
import { Button } from "@/components/ui/Button";
import { Avatar, UserChip } from "@/components/ui/Avatar";
import { Field, Select, Spinner, TextArea } from "@/components/ui/primitives";
import { StatePill } from "@/components/ui/task-bits";
import type { Task } from "@/lib/types";

export function TaskDetailDrawer({
  taskId,
  projectId,
  canWrite,
  onClose,
  onOpenTask,
}: {
  taskId: string | null;
  projectId: string;
  canWrite: boolean;
  onClose: () => void;
  onOpenTask: (id: string) => void;
}) {
  const { t } = useTranslation();
  const task = useTask(taskId);
  const states = useWorkflowStates(projectId);
  const users = useUsers();

  return (
    <Drawer open={!!taskId} onClose={onClose} label="Task detail">
      {task.isLoading && <Spinner label={t("common.loading")} />}
      {task.data && (
        <Body
          key={task.data.id}
          task={task.data}
          states={states.data ?? []}
          users={(users.data ?? []).map((u) => ({ id: u.id, name: u.display_name }))}
          canWrite={canWrite}
          onOpenTask={onOpenTask}
          onClose={onClose}
        />
      )}
    </Drawer>
  );
}

function Body({
  task,
  states,
  users,
  canWrite,
  onOpenTask,
  onClose,
}: {
  task: Task;
  states: { id: string; name: string; category: Task["state_category"] }[];
  users: { id: string; name: string }[];
  canWrite: boolean;
  onOpenTask: (id: string) => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const update = useUpdateTask();
  const complete = useCompleteTask();
  const del = useDeleteTask(task.project_id);

  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? "");
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setTitle(task.title);
    setDescription(task.description ?? "");
  }, [task.title, task.description]);

  const done = task.state_category === "done";

  async function save(patch: Record<string, unknown>) {
    setNotice(null);
    try {
      await update.mutateAsync({ id: task.id, version: task.version, patch });
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 412) setNotice(t("task.conflict"));
      else setNotice(t("common.error"));
    }
  }

  return (
    <div className="px-6 pb-16 pt-12">
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs font-bold text-ink-subtle">{task.ref}</span>
        <StatePill name={task.state_name ?? "—"} category={task.state_category} />
        {done && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
            <CheckCircle2 className="h-3.5 w-3.5" /> {t("task.completed")}
          </span>
        )}
      </div>

      {/* title */}
      {canWrite ? (
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title.trim() && title !== task.title && save({ title: title.trim() })}
          className="mt-3 w-full rounded border border-transparent bg-transparent font-display text-xl font-bold text-navy-900 hover:border-line focus:border-primary focus:bg-white focus:outline-none"
        />
      ) : (
        <h2 className="mt-3 font-display text-xl font-bold text-navy-900">{task.title}</h2>
      )}

      {notice && (
        <p className="mt-2 rounded bg-warning-soft px-3 py-2 text-[13px] text-warning">{notice}</p>
      )}

      {/* meta grid */}
      <div className="mt-5 grid grid-cols-2 gap-4">
        <Field label={t("task.state")}>
          <Select
            disabled={!canWrite}
            value={task.state_id}
            onChange={(e) => save({ state_id: e.target.value })}
          >
            {states.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("task.priority")}>
          <Select
            disabled={!canWrite}
            value={task.priority}
            onChange={(e) => save({ priority: Number(e.target.value) })}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {t(`priority.${n}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("task.assignee")}>
          <Select
            disabled={!canWrite}
            value={task.assignee?.id ?? ""}
            onChange={(e) =>
              e.target.value
                ? save({ assignee_id: e.target.value })
                : save({ clear_assignee: true })
            }
          >
            <option value="">{t("task.unassigned")}</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("task.due")}>
          <input
            type="date"
            disabled={!canWrite}
            value={task.due_date ?? ""}
            onChange={(e) =>
              e.target.value ? save({ due_date: e.target.value }) : save({ clear_due_date: true })
            }
            className="kb-input"
          />
        </Field>
      </div>

      {/* description */}
      <div className="mt-5">
        <Field label={t("task.description")}>
          <TextArea
            disabled={!canWrite}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() =>
              description !== (task.description ?? "") && save({ description })
            }
            placeholder={t("task.descriptionPlaceholder")}
          />
        </Field>
      </div>

      {/* reporter + actions */}
      <div className="mt-4 flex items-center justify-between border-y border-line py-3 text-[13px] text-ink-muted">
        <span className="flex items-center gap-2">
          {task.reporter && <Avatar name={task.reporter.display_name} id={task.reporter.id} />}
          <span>
            <strong className="text-ink">{task.reporter?.display_name}</strong> {t("task.createdBy")}
          </span>
        </span>
        {canWrite && (
          <div className="flex gap-2">
            {!done && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => complete.mutate({ id: task.id, version: task.version })}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {t("task.complete")}
              </Button>
            )}
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                if (confirm(t("task.deleteConfirm")))
                  del.mutate({ id: task.id, version: task.version }, { onSuccess: onClose });
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {/* subtasks */}
      {task.subtasks && task.subtasks.length > 0 && (
        <section className="mt-5">
          <h3 className="kb-label mb-2">{t("task.subtasks")}</h3>
          <ul className="divide-y divide-line rounded-md border border-line bg-white">
            {task.subtasks.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => onOpenTask(s.id)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-sky-soft/40"
                >
                  <span className={s.state_category === "done" ? "text-ink-muted line-through" : ""}>
                    {s.title}
                  </span>
                  <StatePill name={s.state_name ?? "—"} category={s.state_category} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <CommentThread taskId={task.id} canWrite={canWrite} users={users} lang={i18n.language} />
    </div>
  );
}

function CommentThread({
  taskId,
  canWrite,
  users,
  lang,
}: {
  taskId: string;
  canWrite: boolean;
  users: { id: string; name: string }[];
  lang: string;
}) {
  const { t } = useTranslation();
  const comments = useComments(taskId);
  const add = useAddComment(taskId);
  const [body, setBody] = useState("");

  function renderBody(text: string) {
    // `@[Name](uuid)` -> "@Name"
    return text.replace(/@\[([^\]]+)\]\([0-9a-f-]{36}\)/gi, "@$1");
  }

  async function submit() {
    const mentioned = [...body.matchAll(/@\[[^\]]+\]\(([0-9a-f-]{36})\)/gi)].map((m) => m[1]);
    await add.mutateAsync({ body, mentioned_user_ids: mentioned });
    setBody("");
  }

  return (
    <section className="mt-6">
      <h3 className="kb-label mb-2">{t("task.comments")}</h3>

      <ul className="space-y-3">
        {comments.data?.map((c) => (
          <li key={c.id} className="flex gap-2.5">
            <Avatar name={c.author?.display_name ?? "?"} id={c.author?.id} size={28} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-[13px] font-semibold text-navy-900">
                  {c.author?.display_name}
                </span>
                <span className="text-[11px] text-ink-subtle">
                  {new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeStyle: "short" }).format(
                    new Date(c.created_at),
                  )}
                </span>
              </div>
              <p className="whitespace-pre-wrap text-[13px] text-ink">{renderBody(c.body)}</p>
            </div>
          </li>
        ))}
        {comments.data?.length === 0 && (
          <li className="text-[13px] text-ink-subtle">{t("task.noComments")}</li>
        )}
      </ul>

      {canWrite && (
        <div className="mt-3">
          <MentionInput value={body} onChange={setBody} users={users} placeholder={t("task.commentPlaceholder")} />
          <div className="mt-2 flex justify-end">
            <Button size="sm" disabled={!body.trim() || add.isPending} onClick={submit}>
              {t("task.addComment")}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function MentionInput({
  value,
  onChange,
  users,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  users: { id: string; name: string }[];
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const match = /(^|\s)@([\w]*)$/.exec(value);
  const query = match?.[2]?.toLowerCase() ?? "";
  const options = open && match ? users.filter((u) => u.name.toLowerCase().includes(query)).slice(0, 5) : [];

  return (
    <div className="relative">
      <TextArea
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(/(^|\s)@[\w]*$/.test(e.target.value));
        }}
        placeholder={placeholder}
      />
      {options.length > 0 && (
        <ul className="absolute bottom-full z-10 mb-1 w-64 overflow-hidden rounded-md border border-line bg-white shadow-raised">
          {options.map((u) => (
            <li key={u.id}>
              <button
                onClick={() => {
                  onChange(value.replace(/(^|\s)@[\w]*$/, `$1@[${u.name}](${u.id}) `));
                  setOpen(false);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] hover:bg-sky-soft/50"
              >
                <UserChip name={u.name} id={u.id} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
