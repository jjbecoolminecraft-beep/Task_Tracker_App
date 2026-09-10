import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Search as SearchIcon } from "lucide-react";
import { useSearch } from "@/lib/queries";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui/primitives";
import { TaskRows } from "@/features/tasks/TaskRows";

export function SearchPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [term, setTerm] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(term);

  useEffect(() => {
    const h = setTimeout(() => setDebounced(term), 250);
    return () => clearTimeout(h);
  }, [term]);

  useEffect(() => {
    if (debounced) params.set("q", debounced);
    else params.delete("q");
    setParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const { data, isLoading, isError, refetch } = useSearch(debounced);

  return (
    <>
      <PageHeader title={t("search.title")} subtitle={t("search.hint")} />

      <div className="relative mb-5 max-w-xl">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
        <input
          autoFocus
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder={t("search.placeholder")}
          className="kb-input h-11 pl-9 text-[15px]"
        />
      </div>

      {!debounced && <p className="text-sm text-ink-subtle">{t("search.prompt")}</p>}
      {debounced && isLoading && <Spinner label={t("common.loading")} />}
      {isError && <ErrorNote message={t("common.error")} onRetry={() => void refetch()} />}
      {debounced && data && <TaskRows tasks={data.items} emptyTitle={t("search.empty")} />}
    </>
  );
}
