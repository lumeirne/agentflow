/**
 * API client with Auth0 token injection.
 * All backend calls go through this module.
 */

// Empty string = same-origin: all API calls go through Next.js proxy routes.
// The backend URL is only used server-side (in /app/api/* route handlers).
const API_BASE = "";

export async function apiClient(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  // Get Auth0 token from session API route
  try {
    const sessionRes = await fetch("/api/auth/session", { cache: "no-store" });
    if (sessionRes.ok) {
      const session = await sessionRes.json();
      if (session?.accessToken) {
        headers.set("Authorization", `Bearer ${session.accessToken}`);
      }
    } else if (sessionRes.status === 401) {
      throw new Error("Not authenticated. Please sign in at /api/auth/login.");
    }
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    // Session may not be available.
  }

  return fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
}

/** Parse the error detail from a non-OK response. Falls back to a generic message. */
async function parseError(res: Response): Promise<Error> {
  try {
    const json = await res.json();
    const detail = json?.detail ?? json?.message ?? `API error: ${res.status}`;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    const err = new Error(message) as Error & { status: number };
    err.status = res.status;
    return err;
  } catch {
    const err = new Error(`API error: ${res.status}`) as Error & { status: number };
    err.status = res.status;
    return err;
  }
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const res = await apiClient(endpoint);
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function apiPost<T>(endpoint: string, body?: unknown): Promise<T> {
  const res = await apiClient(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function apiDelete(endpoint: string): Promise<void> {
  const res = await apiClient(endpoint, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw await parseError(res);
}
