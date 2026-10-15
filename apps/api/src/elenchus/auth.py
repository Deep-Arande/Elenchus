"""Authentication: Supabase JWT verification (JWKS) and anonymous sessions.

Placeholder in Phase 0; implemented in Phase 5. Verifies Supabase access tokens
on every request via JWKS (legacy JWT secret supported via config); owner-only
admin routes check ``ADMIN_EMAILS`` (AGENTS.md section 8.3).
"""
