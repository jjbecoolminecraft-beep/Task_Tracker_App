import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { useCreateProject } from "@/lib/queries";
import { ApiRequestError } from "@/lib/api";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, TextArea } from "@/components/ui/primitives";

export function CreateProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session } = useAuth();
  const create = useCreateProject();

  const portfolios = useMemo(
    () =>
      (session?.roles ?? [])
        .filter((r) => r.scope_type === "portfolio" && r.scope_id)
        .map((r) => ({ id: r.scope_id as string, label: r.scope_label ?? r.scope_id! })),
    [session],
  );

  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [portfolioId, setPortfolioId] = useState(portfolios[0]?.id ?? "");
  const [visibility, setVisibility] = useState<"private" | "internal">("private");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    try {
      const project = await create.mutateAsync({
        key: key.toUpperCase(),
        name,
        description: description || null,
        portfolio_id: portfolioId,
        visibility,
      });
      onClose();
      navigate(`/projects/${project.id}`);
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : t("common.error"));
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("projects.create.title")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("projects.create.cancel")}
          </Button>
          <Button
            onClick={submit}
            disabled={!key || !name || !portfolioId || create.isPending}
          >
            {t("projects.create.submit")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <Field label={t("projects.create.key")} hint={t("projects.create.keyHint")}>
            <Input
              value={key}
              onChange={(e) => setKey(e.target.value.toUpperCase().slice(0, 10))}
              placeholder="MKTG"
              maxLength={10}
            />
          </Field>
          <Field label={t("projects.create.name")}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
        </div>

        <Field label={t("projects.create.description")}>
          <TextArea value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t("projects.create.portfolio")}>
            <Select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
              {portfolios.length === 0 && <option value="">—</option>}
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("projects.create.visibility")}>
            <Select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value as "private" | "internal")}
            >
              <option value="private">{t("projects.visibilityPrivate")}</option>
              <option value="internal">{t("projects.visibilityInternal")}</option>
            </Select>
          </Field>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    </Dialog>
  );
}
