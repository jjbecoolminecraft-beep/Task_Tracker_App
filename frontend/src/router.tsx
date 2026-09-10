import { createBrowserRouter, Navigate } from "react-router-dom";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import { ProjectPage } from "@/features/projects/ProjectPage";
import { MyTasksPage } from "@/features/my-tasks/MyTasksPage";
import { SearchPage } from "@/features/search/SearchPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/projects" replace /> },
      { path: "projects", element: <ProjectsPage /> },
      { path: "projects/:projectId", element: <ProjectPage /> },
      { path: "my-tasks", element: <MyTasksPage /> },
      { path: "search", element: <SearchPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/projects" replace /> },
]);
