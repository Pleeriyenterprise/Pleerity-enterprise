# Pleerity Enterprise — security policy (summary)

This page is the **stakeholder-facing summary**. Authoritative technical detail — default limits, env var names, endpoint lists, session behaviour, and audit events — lives in:

**[SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md](./SECURITY_RATE_LIMIT_AND_SESSION_POLICY.md)**

## Principles

1. **Route-scoped rate limits** (not a single global cap), returning **HTTP 429** with auditable **`RATE_LIMIT_EXCEEDED`** where wired.
2. **Session inactivity** enforced in the SPA with warning, optional extend, and idle audit; **JWT** lifetime is configurable (`JWT_EXPIRATION_HOURS` or optional `JWT_EXPIRATION_MINUTES`). There is **no refresh-token pair**; short JWTs rely on **`/auth/session/extend`** (see technical doc).
3. **Step-up re-authentication** (password → `X-Step-Up-Token`) for high-impact **admin** actions and selected **client** flows (billing mutations, invoice approvals).
4. **Security logging** via audit actions (failed login, rate limits, session extend/idle, step-up, etc.) plus structured `security.rate_limit` logs.

## Admin vs client (at a glance)

| Topic | Client portal | Admin / staff |
|--------|----------------|---------------|
| Idle timeout (default) | 45 min (`REACT_APP_SESSION_IDLE_MINUTES_CLIENT`) | 20 min (`REACT_APP_SESSION_IDLE_MINUTES_STAFF`) |
| Login rate limit | 5 / 10 min per IP + per email | 5 / 10 min per IP + per email |
| Step-up | Billing checkout/portal/cancel; approvals decisions | User management, password-setup link generation, resend setup, etc. (see technical doc) |

## Related

- Product / value narrative gaps: [SECURITY_VALUE_INTEGRATION.md](./SECURITY_VALUE_INTEGRATION.md)
