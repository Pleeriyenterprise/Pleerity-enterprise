# Deployment convergence — lifecycle transition fixes

**Programme:** P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01  
**Date:** 2026-07-08

| Surface | Value |
|---------|--------|
| Commit | `a86a1a25` |
| Backend | `https://pleerity-enterprise.onrender.com/api/version` → `a86a1a25` |
| Frontend preview | `https://pleerity-enterprise-5iamq4sfz-victory-aigbochies-projects.vercel.app` |
| Staging alias | `https://pleerity-enterprise-9jjg.vercel.app` → preview (alias set) |
| Bundle | `main.2f67b810.js` |

## Delivered endpoints / behaviour

- `POST /api/billing/resume` — step-up, `CAP_SUB_MANAGE`, idempotent Stripe modify
- Stale scheduled cancellation detection in reconcile job + runtime contract resolve
- Lifecycle messaging guard (no past access dates while transition pending)
- Keep subscription CTA wired to resume flow (banner + billing page)
