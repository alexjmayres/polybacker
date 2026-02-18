import { API_BASE } from "@/lib/config";

/**
 * API client helper that attaches JWT Bearer token to all requests.
 * Handles 401 by clearing the token and reloading.
 */

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("polybacker_token")
      : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = API_BASE ? `${API_BASE}${path}` : path;
  const res = await fetch(url, { ...options, headers });

  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("polybacker_token");
    window.location.reload();
  }

  return res;
}

/**
 * Convenience wrapper that parses JSON response.
 */
export async function apiJson<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || `API error: ${res.status}`);
  }
  return res.json();
}
