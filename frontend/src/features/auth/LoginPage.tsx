import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useDevUsers } from "@/lib/queries";
import { Avatar } from "@/components/ui/Avatar";
import { Badge, Spinner } from "@/components/ui/primitives";

export function LoginPage() {
  const { t } = useTranslation();
  const { status, loginAs } = useAuth();
  const { data: users, isLoading } = useDevUsers();
  const [pending, setPending] = useState<string | null>(null);

  if (status === "authenticated") return <Navigate to="/projects" replace />;

  async function pick(id: string) {
    setPending(id);
    try {
      await loginAs(id);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto grid min-h-screen max-w-shell gap-10 px-6 py-10 lg:grid-cols-[1fr_1.15fr] lg:items-center">
        {/* left: brand panel */}
        <div className="flex flex-col justify-center">
          <div className="mb-5 flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded bg-navy-800 font-display text-sm font-extrabold text-white">
              KB
            </span>
            <span className="kb-label">{t("auth.title")}</span>
          </div>
          <h1 className="font-display text-[40px] font-extrabold leading-[1.05] text-navy-900">
            {t("app.name")}
          </h1>
          <p className="mt-3 max-w-md text-[15px] text-ink-muted">{t("app.tagline")}</p>

          <div className="mt-6 flex max-w-md items-start gap-2.5 rounded-md bg-sky-soft px-4 py-3 text-[13px] text-primary-700">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("auth.devNotice")}</span>
          </div>
        </div>

        {/* right: identity picker */}
        <div>
          <p className="kb-label mb-3">{t("auth.devSubtitle")}</p>
          {isLoading || !users ? (
            <Spinner label={t("common.loading")} />
          ) : (
            <ul className="grid gap-2.5 sm:grid-cols-2">
              {users.map((u) => (
                <li key={u.id}>
                  <button
                    onClick={() => pick(u.id)}
                    disabled={!!pending}
                    className="group flex h-full w-full flex-col gap-2 rounded-md border border-line bg-white p-4 text-left shadow-card transition-colors hover:border-primary/40 hover:bg-sky-soft/40 disabled:opacity-60"
                  >
                    <div className="flex items-center gap-2.5">
                      <Avatar name={u.display_name} id={u.id} size={32} />
                      <div className="min-w-0">
                        <div className="truncate font-display text-sm font-bold text-navy-900">
                          {u.display_name}
                        </div>
                        <div className="truncate text-[11px] text-ink-subtle">{u.department}</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {u.roles_summary.map((r) => (
                        <Badge key={r} tone={r.includes("no ") ? "neutral" : "blue"}>
                          {r}
                        </Badge>
                      ))}
                    </div>
                    <span className="mt-auto pt-1 text-[12px] font-semibold text-primary opacity-0 transition-opacity group-hover:opacity-100">
                      {pending === u.id ? t("common.loading") : t("auth.continueAs", { name: u.display_name.split(" ")[0] })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
