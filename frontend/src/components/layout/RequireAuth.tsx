import { useEffect, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui/primitives";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { status, bootstrap } = useAuth();

  useEffect(() => {
    if (status === "loading") void bootstrap();
  }, [status, bootstrap]);

  if (status === "loading") {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label={t("common.loading")} />
      </div>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <>{children}</>;
}
