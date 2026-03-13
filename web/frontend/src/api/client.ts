import { useAuthStore } from "@/stores/auth";

const BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function requestWithHeaders<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<{ data: T; supportMode: boolean }> {
  const auth = useAuthStore();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (auth.jwt) {
    headers["Authorization"] = `Bearer ${auth.jwt}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    auth.clear();
    // Dynamic import avoids circular dependency at module initialization time
    const { default: router } = await import("@/router");
    router.push("/login");
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const contentType = res.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        const body = (await res.json()) as { detail?: unknown };
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail ?? body);
      } else {
        detail = await res.text();
      }
    } catch {
      // keep statusText fallback
    }
    throw new ApiError(res.status, detail);
  }

  const supportMode = res.headers.get("X-Support-Mode") === "true";
  if (res.status === 204) return { data: undefined as T, supportMode };
  const data = (await res.json()) as T;
  return { data, supportMode };
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  return (await requestWithHeaders<T>(method, path, body)).data;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
  getWithHeaders: <T>(path: string) => requestWithHeaders<T>("GET", path),
};
