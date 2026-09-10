/** Mirrors the FastAPI response schemas (backend/app/schemas). */

export type Role =
  | "system_admin"
  | "auditor"
  | "portfolio_owner"
  | "project_admin"
  | "contributor"
  | "viewer"
  | "guest";

export type WorkflowCategory = "backlog" | "in_progress" | "done";
export type Visibility = "private" | "internal";

export interface SessionRole {
  role: Role | string;
  scope_type: "global" | "portfolio" | "project" | "none";
  scope_id: string | null;
  scope_label: string | null;
}

export interface SessionInfo {
  id: string;
  display_name: string;
  upn: string;
  department: string | null;
  roles: SessionRole[];
}

export interface DevUser {
  id: string;
  display_name: string;
  upn: string;
  department: string | null;
  roles_summary: string[];
}

export interface UserRef {
  id: string;
  display_name: string;
}

export interface UserOut extends UserRef {
  upn: string;
  department: string | null;
  is_active: boolean;
}

export interface Project {
  id: string;
  key: string;
  name: string;
  description: string | null;
  visibility: Visibility;
  status: "active" | "archived";
  portfolio_id: string | null;
  created_at: string;
  archived_at: string | null;
  my_role: Role | null;
  open_task_count: number | null;
}

export interface WorkflowState {
  id: string;
  name: string;
  category: WorkflowCategory;
  position: number;
  is_default: boolean;
}

export interface Task {
  id: string;
  project_id: string;
  project_key: string | null;
  parent_task_id: string | null;
  seq: number;
  ref: string | null;
  title: string;
  description: string | null;
  state_id: string;
  state_name: string | null;
  state_category: WorkflowCategory | null;
  priority: number;
  assignee: UserRef | null;
  reporter: UserRef | null;
  due_date: string | null;
  estimate_hours: number | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  subtask_count: number | null;
  subtasks?: Task[];
}

export interface Comment {
  id: string;
  task_id: string;
  author: UserRef | null;
  body: string;
  mentioned_user_ids: string[];
  created_at: string;
}

export interface PageMeta {
  next_cursor: string | null;
  limit: number;
}

export interface Paginated<T> {
  items: T[];
  page: PageMeta;
}

export interface ProjectMember {
  id: string;
  user_id: string | null;
  entra_group_id: string | null;
  role: Role;
  display_name: string | null;
}

export type NotificationKind =
  | "task.assigned"
  | "comment.mention"
  | "comment.added"
  | "task.due_soon";

export interface Notification {
  id: string;
  kind: NotificationKind | string;
  task_id: string | null;
  project_id: string | null;
  actor_name: string | null;
  task_ref: string | null;
  snippet: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  occurred_at: string;
  actor_id: string | null;
  actor_upn: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  project_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  request_id: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string | null;
}
