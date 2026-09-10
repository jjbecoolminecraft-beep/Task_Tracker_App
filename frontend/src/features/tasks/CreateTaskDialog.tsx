import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useCreateTask } from "@/lib/queries";
import { ApiRequestError } from "@/lib/api";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, TextArea } from "@/components/ui/primitives";
import type { WorkflowState } from "@/lib/types";

export function CreateTaskDialog({
  open,
  projectId,
  states,
  users,
  onClose,
}: {
  open: boolean;
  projectId: string;
  states: WorkflowState[];
  users: { id: string; name: string }[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const create = useCreateTask(projectId);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [stateId, setStateId] = useState("");
  const [priority, setPriority] = useState(3);
  const [assigneeId, setAssigneeId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setStateId(states.find((s) => s.is_default)?.id ?? states[0]?.id ?? "");
      setPriority(3);
      setAssigneeId("");
      setDueDate("");
      setError(null);
    }
  }, [open, states]);

  async function submit() {
    setError(null);
    try {
      await create.mutateAsync({
        title,
        description: description || null,
        state_id: stateId || null,
        priority,
        assignee_id: assigneeId || null,
        due_date: dueDate || null,
      });
      onClose();
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : t("common.error"));
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("task.create")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={submit} disabled={!title.trim() || create.isPending}>
            {t("task.create")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t("list.columns.title")}>
          <Input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("task.titlePlaceholder")}
          />
        </Field>
        <Field label={t("task.description")}>
          <TextArea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("task.descriptionPlaceholder")}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("task.state")}>
            <Select value={stateId} onChange={(e) => setStateId(e.target.value)}>
              {states.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("task.priority")}>
            <Select value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {t(`priority.${n}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("task.assignee")}>
            <Select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
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
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="kb-input"
            />
          </Field>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    </Dialog>
  );
}
