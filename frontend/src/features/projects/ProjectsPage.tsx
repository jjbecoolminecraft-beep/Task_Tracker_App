import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, ArrowRight } from "lucide-react";
import { useProjects } from "@/lib/queries";
import { useAuth, hasRole } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, ErrorNote, PageHeader, Spinner } from "@/components/ui/primitives";
import { CreateProjectDialog } from "./CreateProjectDialog";
import type { Project } from "@/lib/types";

function roleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function ProjectCard({ project }: { project: Project }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/projects/${project.id}`}
      className="group flex flex-col rounded-md border border-line bg-white p-5 shadow-card transition-colors hover:border-primary/40"
    >
      <div className="flex items-center justify-between">
        <span className="rounded-sm bg-navy-800 px-2 py-1 font-display text-xs font-bold tracking-wide text-white">
          {project.key}
        </span>
        <Badge tone={project.visibility === "internal" ? "blue" : "neutral"}>
          {project.visibility === "internal"
            ? t("projects.visibilityInternal")
            : t("projects.visibilityPrivate")}
        </Badge>
      </div>

      <h3 className="mt-3 font-display text-[17px] font-bold text-navy-900">{project.name}</h3>
      {project.description && (
        <p className="mt-1 line-clamp-2 text-[13px] text-ink-muted">{project.description}</p>
      )}

      <div className="mt-4 flex items-end justify-between border-t border-line pt-3">
        <div>
          <span className="kb-label block">{t("projects.role")}</span>
          <span className="text-sm font-semibold capitalize text-navy-800">
            {project.my_role ? roleLabel(project.my_role) : "—"}
          </span>
        </div>
        <div className="text-right">
          <span className="font-display text-2xl font-bold text-navy-900">
            {project.open_task_count ?? "—"}
          </span>
          <span className="kb-label block">{t("projects.openTasks", { count: project.open_task_count ?? 0 })}</span>
        </div>
      </div>

      <span className="mt-3 inline-flex items-center gap-1 text-[13px] font-semibold text-primary opacity-0 transition-opacity group-hover:opacity-100">
        Open <ArrowRight className="h-3.5 w-3.5" />
      </span>
    </Link>
  );
}

export function ProjectsPage() {
  const { t } = useTranslation();
  const { session } = useAuth();
  const { data, isLoading, isError, refetch } = useProjects();
  const [creating, setCreating] = useState(false);

  const canCreate = hasRole(session, "system_admin", "portfolio_owner");

  return (
    <>
      <PageHeader
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
        actions={
          canCreate && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              {t("projects.new")}
            </Button>
          )
        }
      />

      {isLoading && <Spinner label={t("common.loading")} />}
      {isError && <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />}

      {data && data.length === 0 && (
        <EmptyState title={t("projects.empty")} hint={t("projects.emptyHint")} />
      )}

      {data && data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      <CreateProjectDialog open={creating} onClose={() => setCreating(false)} />
    </>
  );
}
