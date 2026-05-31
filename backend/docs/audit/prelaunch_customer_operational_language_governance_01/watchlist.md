# Watchlist — customer operational language governance

- **Programme:** PRELAUNCH-CUSTOMER-OPERATIONAL-LANGUAGE-GOVERNANCE-01
- **Commit (local):** `1298a98b`
- **Classification:** IMPLEMENTED_PENDING_RUNTIME

## Post-deploy checks
- Today / Command Centre API payloads: zero `Gap:` / `Key:` / internal enums
- Evidence-gap issues: CTA must not be `Start maintenance job`
- Legacy DB issue rows: sanitization must override stored diagnostic descriptions

## Residual surfaces (monitor)
- Admin diagnostics and audit logs (internal — exempt)
- Upload pre-analysis API may still return `mismatch_reason_code` internally; ensure customer `user_messages` only on UI
- Contractor / tenant portals: re-run cross-role harness after deploy
