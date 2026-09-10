import { useTranslation } from "react-i18next";
import { useMyTasks } from "@/lib/queries";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui/primitives";
import { TaskRows } from "@/features/tasks/TaskRows";

export function MyTasksPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useMyTasks();

  return (
    <>
      <PageHeader title={t("myTasks.title")} subtitle={t("myTasks.subtitle")} />
      {isLoading && <Spinner label={t("common.loading")} />}
      {isError && <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />}
      {data && <TaskRows tasks={data.items} emptyTitle={t("myTasks.empty")} />}
    </>
  );
}
