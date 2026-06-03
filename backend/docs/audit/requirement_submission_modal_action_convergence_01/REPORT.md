# REQUIREMENT-SUBMISSION-MODAL-ACTION-CONVERGENCE-01

**Classification:** `VERIFIED_OPERATIONALLY`

## Summary

When users open **View submission** or **View evidence** on requirements with existing submissions, `RequirementIntelligenceModal` now converges hero and footer actions by context instead of repeating pre-submission CTAs.

## Changes

- `requirementSubmissionModalContext.js` — context model (`view_submission`, `view_verified_evidence`, `satisfy_requirement`)
- `RequirementModalContextHero` — replaces stale `NextActionHero` when submission/evidence is on file
- Footer: **Update submission**, **Add supporting evidence**, **View documents** — no duplicate **View submission**
- Update flow routes to `ComplianceEvidenceResolveModal` with `reopen_context` prefill
- Supporting evidence routes with `initialCtaFocusKey: attach_supporting_files`

## Tests

Frontend modal context tests: `pass`

## Watchlist

See `watchlist.md`.
