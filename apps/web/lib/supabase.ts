/**
 * Supabase client (placeholder) — used for AUTH ONLY (AGENTS.md section 3).
 *
 * All application data goes through the FastAPI backend, never directly through
 * Supabase from the browser. The real auth client is wired in Phase 5.
 */

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
