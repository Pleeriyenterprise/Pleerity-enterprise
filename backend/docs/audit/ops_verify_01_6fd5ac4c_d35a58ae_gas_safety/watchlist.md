# gas_safety watchlist (non-blocking)

- Baseline was **pre_existing_evidence**: 1 VERIFIED doc (`07115f75…`), row `COMPLIANT` / authority `VERIFIED_CURRENT`.
- Second CP12 uploaded (`400f1090…`): CER `PENDING_REVIEW` created; authority fingerprint **unchanged** (still anchored on prior verified doc) — expected until admin verify.
- Requirements page: **no** `compliance-view-requirement` CTA when row already compliant — inspectability via Documents vault only.
- Upload API reported `score_change: -20` (67→47); queue `DOC_UPLOADED:400f1090…` terminal **DONE** in ~30s.
- Admin verify path for new document **not** exercised this run (optional follow-up).
