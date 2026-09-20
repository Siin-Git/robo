/** Single fetch wrapper: same-origin proxy, CSRF on mutations, error parsing. */

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string | null;
  constructor(code: string, message: string, status: number, requestId: string | null) {
    super(message);
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|; )ra_csrf=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const res = await fetch(path, { ...init, method, headers, credentials: "include" });
  const requestId = res.headers.get("X-Request-ID");
  if (res.status === 401 && typeof window !== "undefined") {
    const here = window.location.pathname;
    if (here !== "/login" && here !== "/signup") {
      window.location.replace(`/login?next=${encodeURIComponent(here + window.location.search)}`);
    }
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = (body as { error?: { code?: string; message?: string } })?.error;
    throw new ApiError(err?.code ?? `HTTP_${res.status}`, err?.message ?? res.statusText,
      res.status, requestId);
  }
  return body as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, data?: unknown) =>
  api<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });
export const put = <T,>(path: string, data?: unknown) =>
  api<T>(path, { method: "PUT", body: data === undefined ? undefined : JSON.stringify(data) });
export const del = <T,>(path: string) => api<T>(path, { method: "DELETE" });
