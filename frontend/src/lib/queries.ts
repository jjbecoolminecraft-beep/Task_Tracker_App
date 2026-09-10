import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, del, downloadFile, get, patch, post, uploadFile } from "./api";
import type {
  AuditEvent,
  Comment,
  DevUser,
  Notification,
  Paginated,
  Project,
  ProjectMember,
  Task,
  UserOut,
  WorkflowState,
} from "./types";

export const keys = {
  devUsers: ["dev-users"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  states: (id: string) => ["projects", id, "states"] as const,
  members: (id: string) => ["projects", id, "members"] as const,
  tasks: (id: string, q: string) => ["projects", id, "tasks", q] as const,
  task: (id: string) => ["tasks", id] as const,
  comments: (id: string) => ["tasks", id, "comments"] as const,
  myTasks: ["me", "tasks"] as const,
  users: ["users"] as const,
  search: (q: string) => ["search", q] as const,
  notifications: ["me", "notifications"] as const,
  unreadCount: ["me", "notifications", "unread-count"] as const,
};

export const useDevUsers = () =>
  useQuery({ queryKey: keys.devUsers, queryFn: () => get<DevUser[]>("/auth/dev-users") });

export const useProjects = () =>
  useQuery({ queryKey: keys.projects, queryFn: () => get<Project[]>("/projects") });

export const useProject = (id: string) =>
  useQuery({ queryKey: keys.project(id), queryFn: () => get<Project>(`/projects/${id}`) });

export const useWorkflowStates = (projectId: string) =>
  useQuery({
    queryKey: keys.states(projectId),
    queryFn: () => get<WorkflowState[]>(`/projects/${projectId}/workflow-states`),
    enabled: !!projectId,
  });

export const useProjectMembers = (projectId: string) =>
  useQuery({
    queryKey: keys.members(projectId),
    queryFn: () => get<ProjectMember[]>(`/projects/${projectId}/members`),
    enabled: !!projectId,
  });

export const useUsers = () =>
  useQuery({ queryKey: keys.users, queryFn: () => get<UserOut[]>("/users"), staleTime: 60_000 });

export interface TaskFilters {
  state_id?: string;
  assignee_id?: string;
  unassigned?: boolean;
  priority?: number;
  q?: string;
  sort?: string;
  limit?: number;
}

function toQuery(f: TaskFilters, cursor?: string): string {
  const p = new URLSearchParams();
  if (f.state_id) p.set("state_id", f.state_id);
  if (f.assignee_id) p.set("assignee_id", f.assignee_id);
  if (f.unassigned) p.set("unassigned", "true");
  if (f.priority) p.set("priority", String(f.priority));
  if (f.q) p.set("q", f.q);
  if (f.sort) p.set("sort", f.sort);
  if (f.limit) p.set("limit", String(f.limit));
  if (cursor) p.set("cursor", cursor);
  return p.toString();
}

export const useProjectTasks = (projectId: string, filters: TaskFilters) => {
  const qs = toQuery(filters);
  return useQuery({
    queryKey: keys.tasks(projectId, qs),
    queryFn: () => get<Paginated<Task>>(`/projects/${projectId}/tasks?${qs}`),
    enabled: !!projectId,
  });
};

// `version` on the payload is the concurrency token (backend accepts If-Match: "<version>").
export const useTask = (taskId: string | null) =>
  useQuery({
    queryKey: keys.task(taskId ?? ""),
    queryFn: () => get<Task>(`/tasks/${taskId}`),
    enabled: !!taskId,
  });

export const useComments = (taskId: string | null) =>
  useQuery({
    queryKey: keys.comments(taskId ?? ""),
    queryFn: () => get<Comment[]>(`/tasks/${taskId}/comments`),
    enabled: !!taskId,
  });

export const useMyTasks = () =>
  useQuery({ queryKey: keys.myTasks, queryFn: () => get<Paginated<Task>>("/me/tasks") });

export const useSearch = (q: string) =>
  useQuery({
    queryKey: keys.search(q),
    queryFn: () => get<Paginated<Task>>(`/search?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length > 0,
  });

export const useAuditEvents = (opts: { projectId?: string; beforeId?: number }) => {
  const p = new URLSearchParams({ limit: "50" });
  if (opts.projectId) p.set("project_id", opts.projectId);
  if (opts.beforeId) p.set("before_id", String(opts.beforeId));
  const qs = p.toString();
  return useQuery({
    queryKey: ["audit", qs],
    queryFn: () => get<AuditEvent[]>(`/audit?${qs}`),
  });
};

// ---- mutations ----

export function useCreateTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      post<Task>(`/projects/${projectId}/tasks`, body).then((r) => r.data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects", projectId, "tasks"] });
      void qc.invalidateQueries({ queryKey: keys.project(projectId) });
    },
  });
}

export interface UpdateTaskArgs {
  id: string;
  version: number;
  patch: Record<string, unknown>;
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version, patch: body }: UpdateTaskArgs) =>
      patch<Task>(`/tasks/${id}`, body, `"${version}"`).then((r) => r.data),
    onSuccess: (task) => {
      qc.setQueryData(keys.task(task.id), task);
      void qc.invalidateQueries({ queryKey: ["projects", task.project_id, "tasks"] });
      void qc.invalidateQueries({ queryKey: keys.myTasks });
    },
  });
}

export function useCompleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      post<Task>(`/tasks/${id}/complete`, undefined, `"${version}"`).then((r) => r.data),
    onSuccess: (task) => {
      qc.setQueryData(keys.task(task.id), task);
      void qc.invalidateQueries({ queryKey: ["projects", task.project_id, "tasks"] });
      void qc.invalidateQueries({ queryKey: keys.myTasks });
    },
  });
}

export function useDeleteTask(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      del(`/tasks/${id}`, `"${version}"`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects", projectId, "tasks"] });
      void qc.invalidateQueries({ queryKey: keys.myTasks });
    },
  });
}

export function useAddComment(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; mentioned_user_ids?: string[] }) =>
      post<Comment>(`/tasks/${taskId}/comments`, body).then((r) => r.data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.comments(taskId) }),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      post<Project>("/projects", body).then((r) => r.data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

// ---- import / export (spec F-12) ----

export interface ImportResult {
  created: number;
  refs: string[];
  skipped: { row: number; reason: string }[];
}

export function exportProjectTasks(projectId: string, format: "csv" | "json") {
  return downloadFile(`/projects/${projectId}/tasks/export?format=${format}`);
}

export function useImportTasks(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return uploadFile<ImportResult>(`/projects/${projectId}/tasks/import`, form);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects", projectId, "tasks"] });
      void qc.invalidateQueries({ queryKey: keys.project(projectId) });
    },
  });
}

// ---- notifications (spec F-10) ----

export const useUnreadCount = () =>
  useQuery({
    queryKey: keys.unreadCount,
    queryFn: () => get<{ unread: number }>("/me/notifications/unread-count"),
    refetchInterval: 30_000, // WebSocket push is Phase 2 (F-27); poll for now
    staleTime: 15_000,
  });

export const useNotifications = () =>
  useQuery({
    queryKey: keys.notifications,
    queryFn: () => get<Notification[]>("/me/notifications?limit=30"),
  });

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/me/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.notifications });
      void qc.invalidateQueries({ queryKey: keys.unreadCount });
    },
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post("/me/notifications/read-all"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.notifications });
      void qc.invalidateQueries({ queryKey: keys.unreadCount });
    },
  });
}
