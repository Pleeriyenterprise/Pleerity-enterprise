# LEGAL-CONTENT-PUBLICATION-CONVERGENCE-01

**Classification:** `PARTIAL`
**Run tag:** `20260605T120217Z`

## Summary
Governed legal_content CMS is wired to public pages via `/api/public/legal-content/{slug}` with canonical server fallback.
Public React pages fetch CMS content; admin save publishes immediately.
**Deploy note:** Staging API sample status `200`; seed `200`. Re-run after Render/Vercel deploy for VERIFIED_OPERATIONALLY.

## Checklist
- architecture: PASS
- seed: FAIL
- sanitisation: PASS
- rendering: PASS
- edit_publication: FAIL
- reset: PASS
- admin_ui: PASS
- version_restore: PASS
- permissions: PASS
- alignment: PASS
- concurrency: PASS
- regression: PASS

**Blockers:** seed, edit_publication
