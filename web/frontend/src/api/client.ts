import { useAuthStore } from "@/stores/auth";

const BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
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
    let detail = "";
    try {
      detail = await res.text();
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
