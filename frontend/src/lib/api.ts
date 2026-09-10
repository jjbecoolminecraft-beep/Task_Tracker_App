import type { ApiError } from "./types";

const BASE = "/api/v1";

/** In-memory only — never localStorage (spec §5.3). Survives route changes, not reloads. */
let accessToken: string | null = null;
export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}

export class ApiRequestError extends Error {
  status: number;
  code: string;
  details?: unknown;
  requestId?: string | null;

  constructor(status: number, body: ApiError) {
    super(body.message || `Request failed (${status})`);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id ?? null;
  }
}

export interface ApiResponse<T> {
  data: T;
  etag: string | null;
  status: number;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  ifMatch?: string | null;
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  if (opts.ifMatch) headers["If-Match"] = opts.ifMatch;

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  const etag = res.headers.get("ETag");
  if (res.status === 204) return { data: undefined as T, etag, status: res.status };

  const text = await res.text();
  const payload = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const err: ApiError = payload?.error ?? {
      code: "unknown",
      message: `Request failed (${res.status})`,
    };
    throw new ApiRequestError(res.status, err);
  }
  return { data: payload as T, etag, status: res.status };
}

export const get = <T>(path: string, signal?: AbortSignal) => api<T>(path, { signal }).then((r) => r.data);
export const getWithEtag = <T>(path: string) => api<T>(path);

/** Fetch a file with auth and hand it to the browser's download flow. */
export async function downloadFile(path: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    const body = await res.text();
    const err = body ? JSON.parse(body).error : { code: "unknown", message: "Download failed" };
    throw new ApiRequestError(res.status, err);
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? "export";
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Multipart upload with auth. */
export async function uploadFile<T>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: form });
  const text = await res.text();
  const payload = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiRequestError(res.status, payload?.error ?? { code: "unknown", message: "Upload failed" });
  }
  return payload as T;
}
export const post = <T>(path: string, body?: unknown, ifMatch?: string | null) =>
  api<T>(path, { method: "POST", body, ifMatch });
export const patch = <T>(path: string, body: unknown, ifMatch?: string | null) =>
  api<T>(path, { method: "PATCH", body, ifMatch });
export const del = (path: string, ifMatch?: string | null) =>
  api<void>(path, { method: "DELETE", ifMatch });
