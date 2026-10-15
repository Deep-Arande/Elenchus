/**
 * Typed API client (placeholder).
 *
 * The real client is built in Phase 5 on top of the generated `api-types.ts`
 * (run `pnpm gen:api-types`) with TanStack Query hooks. For now it just exposes
 * the backend base URL. All data flows through the FastAPI backend; the
 * Supabase JS client is used for auth only (AGENTS.md section 3).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchHealth(): Promise<unknown> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}
