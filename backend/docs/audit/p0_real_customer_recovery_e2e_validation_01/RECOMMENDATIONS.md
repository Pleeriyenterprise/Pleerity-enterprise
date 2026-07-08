# Recommendations — P0-REAL-CUSTOMER-RECOVERY-E2E-VALIDATION-01

## Immediate (blocking)

1. **Render staging deploy convergence** — `pleerity-api-staging` must serve `aac35cbd`. Poll `GET https://pleerity-enterprise.onrender.com/api/version` until `commit_sha` starts with `aac35cbd`.

2. **Vercel staging alias** — Promote the latest `pleerity-enterprise-9jjg` build (from `develop` at `aac35cbd`) to `pleerity-enterprise-9jjg.vercel.app`. Confirm bundle hash changes from `main.0d2f6082.js`.

3. **Re-run validation** — Execute full browser recovery on `lere@yopmail.com` only after both surfaces pass deployment authority.

## Account policy

- **Use:** `lere@yopmail.com` — SUSPENDED, billing recovery caps ALLOW, existing portfolio data.
- **Do not use:** `isabella@yopmail.com` — ACTIVE/FULL_ACCESS; unsuitable for suspension recovery proof.

## Success criteria (unchanged)

Programme completes only when a real customer completes login → billing → step-up → Stripe test payment → webhook → automatic ACTIVE/FULL_ACCESS restoration with data intact and no manual intervention.

## Release readiness

Platform-Wide Release Readiness Audit is **gated** on `REAL_CUSTOMER_RECOVERY_E2E_VALIDATED`.
