/**
 * Resolved API base URL.
 *
 * Priority:
 * 1. NEXT_PUBLIC_API_URL env var (set at build time on Vercel)
 * 2. Runtime detection: if running on a deployed host (not localhost),
 *    fall back to the known Render backend URL.
 * 3. Empty string for local dev (Next.js rewrites proxy to localhost:5001).
 */

const RENDER_BACKEND = "https://polybacker-api.onrender.com";

function resolveApiBase(): string {
  // 1. Env var set at build time — always wins
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;

  // 2. Runtime detection — if we're in a browser and NOT on localhost,
  //    we're deployed (Vercel) and need the Render backend URL
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1") {
      return RENDER_BACKEND;
    }
  }

  // 3. Local dev — empty string, Next.js rewrites handle it
  return "";
}

export const API_BASE = resolveApiBase();
