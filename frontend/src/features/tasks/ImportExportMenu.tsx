import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, FileUp, Loader2, Upload } from "lucide-react";
import { exportProjectTasks, useImportTasks, type ImportResult } from "@/lib/queries";
import { ApiRequestError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";

export function ImportExportMenu({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function doExport(format: "csv" | "json") {
    setMenuOpen(false);
    setBusy(true);
    try {
      await exportProjectTasks(projectId, format);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="relative">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setMenuOpen((v) => !v)}
          onBlur={() => setTimeout(() => setMenuOpen(false), 150)}
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
          {t("io.export")}
        </Button>
        {menuOpen && (
          <div className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-md border border-line bg-white shadow-raised">
            {(["csv", "json"] as const).map((f) => (
              <button
                key={f}
                onMouseDown={() => doExport(f)}
                className="block w-full px-3 py-2 text-left text-[13px] hover:bg-sky-soft/50"
              >
                {t("io.exportAs", { format: f.toUpperCase() })}
              </button>
            ))}
          </div>
        )}
      </div>

      {canWrite && (
        <Button variant="secondary" size="sm" onClick={() => setImportOpen(true)}>
          <Upload className="h-3.5 w-3.5" />
          {t("io.import")}
        </Button>
      )}

      <ImportDialog
        open={importOpen}
        projectId={projectId}
        onClose={() => setImportOpen(false)}
      />
    </>
  );
}

function ImportDialog({
  open,
  projectId,
  onClose,
}: {
  open: boolean;
  projectId: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const importer = useImportTasks(projectId);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function onFile(file: File) {
    setError(null);
    setResult(null);
    try {
      setResult(await importer.mutateAsync(file));
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : t("common.error"));
    }
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title={t("io.importTitle")}
      footer={
        <Button
          variant="secondary"
          onClick={() => {
            reset();
            onClose();
          }}
        >
          {t("common.close")}
        </Button>
      }
    >
      <div className="space-y-4">
        <p className="text-[13px] text-ink-muted">{t("io.importHint")}</p>
        <code className="block overflow-x-auto rounded bg-surface-muted px-3 py-2 text-[12px] text-ink">
          title,state,priority,assignee_upn,due_date,parent_ref
        </code>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) void onFile(f);
          }}
          className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line bg-surface-sunken px-4 py-8 text-center"
        >
          <FileUp className="h-6 w-6 text-ink-subtle" />
          <span className="text-[13px] text-ink-muted">{t("io.dropOrPick")}</span>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && void onFile(e.target.files[0])}
          />
          <Button size="sm" onClick={() => inputRef.current?.click()} disabled={importer.isPending}>
            {importer.isPending ? t("common.loading") : t("io.chooseFile")}
          </Button>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        {result && (
          <div className="rounded-md border border-line">
            <div className="flex items-center gap-2 border-b border-line bg-success-soft px-3 py-2 text-[13px] font-semibold text-success">
              {t("io.created", { count: result.created })}
              {result.skipped.length > 0 && (
                <span className="text-warning">
                  · {t("io.skipped", { count: result.skipped.length })}
                </span>
              )}
            </div>
            {result.skipped.length > 0 && (
              <ul className="max-h-40 divide-y divide-line overflow-y-auto text-[12px]">
                {result.skipped.map((s) => (
                  <li key={s.row} className="flex gap-3 px-3 py-1.5">
                    <span className="font-mono text-ink-subtle">{t("io.row", { n: s.row })}</span>
                    <span className="text-ink-muted">{s.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </Dialog>
  );
}
