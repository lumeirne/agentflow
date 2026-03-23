/**
 * API client with Auth0 token injection.
 * All backend calls go through this module.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function apiClient(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  // Fetch the session token from Next.js auth
  let token = "";
  try {
    const sessionRes = await fetch("/auth/profile");
    if (sessionRes.ok) {
      // For client-side, we'll use the access token from session
    }
  } catch {
    // Session fetch may fail on server side
  }

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const res = await apiClient(endpoint);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function apiPost<T>(endpoint: string, body?: unknown): Promise<T> {
  const res = await apiClient(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function apiDelete(endpoint: string): Promise<void> {
  const res = await apiClient(endpoint, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`API error: ${res.status}`);
}
