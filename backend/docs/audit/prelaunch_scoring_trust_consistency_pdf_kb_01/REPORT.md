# PRELAUNCH-SCORING-TRUST-CONSISTENCY-PDF-KB-01

## Summary

Secondary customer-facing scoring surfaces were audited and updated for trust-safe, operational language. Scoring logic was not changed.

## Classification

| Layer | Result |
|-------|--------|
| Code / static scan | **TRUST_SAFE** |
| PDF export (local) | **TRUST_SAFE** |
| Directional copy (email/timeline) | **TRUST_SAFE** |
| Staging browser (pre-deploy) | **TRUST_DRIFT_RISK** — Requirements page still serves prior bundle with "scoring engine" until frontend deploy |

**Programme closeout:** **TRUST_DRIFT_RISK** until staging frontend picks up `confidenceUxCopy.js` change; all code paths remediated.

## Files changed

- `backend/services/scoring_explanation_copy.py` — shared trust-safe copy (PDF/KB/email/timeline)
- `backend/services/pdf_report_builder.py` — score summary PDF + evidence report methodology
- `backend/services/property_timeline_service.py` — directional score-change narratives
- `backend/services/email_service.py` — digest score delta line
- `backend/services/monthly_digest_pdf_service.py` — monthly PDF score delta line
- `backend/scripts/seed_kb_articles.py` — expanded KB article + refresh on seed
- `backend/docs/assistant_kb/how_scoring_works.md` — assistant KB rewrite
- `backend/docs/assistant_kb/score_changes.md` — assistant KB rewrite
- `frontend/src/utils/confidenceUxCopy.js` — requirements confidence line
- `docs/knowledge-centre-drafts/drafts/cvp-pilot-user-04-understanding-your-compliance-score.md` — draft cleanup

## Post-deploy verification

1. Re-run `python tmp_prelaunch_scoring_trust_consistency_pdf_kb_01.py`
2. Confirm `/requirements` no longer shows "scoring engine"
3. Export Compliance Score Summary PDF from staging and spot-check area labels
