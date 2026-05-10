# Evidence Review V2 — configuration and visibility matrix

**Flag:** `FEATURE_EVIDENCE_REVIEW_V2` (`1` / `true` / `yes` → on). Implemented in `services/evidence_review_config.py`.

## Surfaces

| Surface | When OFF | When ON |
|---------|----------|---------|
| **HTTP API** (`routes/evidence_review.py`) | All POST/GET review routes return `400` with `EVIDENCE_REVIEW_V2_DISABLED`. | Routes active; transitions fan out through `authority_mutation_fanout` + recalc enqueue consistent with governance. |
| **Admin verify** (`routes/documents.verify_document`) | Uses legacy v1 verify path (still runs authority sync + recalc enqueue). | Delegates to `execute_verify_document_v2` (`services/evidence_review_verify.py`). |
| **Admin dashboard** (`GET /admin/dashboard`) | `server_feature_flags.evidence_review_v2_enabled`: `false` — pending-verification **AI review** entry points hidden in `AdminDashboard.js` (Verify / resolve match / reject unchanged). | `true` — **AI review** panel enabled; matches API + `FEATURE_EVIDENCE_REVIEW_V2`. |
| **Client dashboard payload** | `server_feature_flags.evidence_review_v2_enabled`: `false`. | `true` — lets the SPA align labels or hide experimental controls without inferring from partial document fields. |
| **Client documents list** | Labels derive from `effectiveEvidenceReviewState` / assurance tier with legacy fallbacks (`utils/evidenceReviewUi.js`). | Same helpers; externally verified tier must not display as generic “Uploaded” if tier is present without state (frontend maps tier → `VERIFIED` + “Externally verified” badge override). |

## Anti–half-enabled rules

1. **No API without flag:** Review router `_v2_guard()` blocks all mutations when the flag is off.
2. **Coherent labels:** If `assurance_tier == EXTERNALLY_VERIFIED` but `evidence_review_state` is empty, UI treats review state as verified-level for display (`evidenceReviewUi.js`) so clients do not see “Uploaded” beside an external verification tier.
3. **Admin tooling:** Prefer admin verify / resolve flows that either use V2 (flag on) or v1 with documented authority sync (flag off); do not add parallel review state writers outside `evidence_review` + documents routes. **L-005e:** `GET /admin/dashboard` exposes the same boolean as the client payload so the admin SPA does not surface **AI review** when the flag is off.

## Tests

- `frontend/src/utils/evidenceReviewUi.test.js` — tier/state coherence.
- `frontend/src/pages/AdminDashboard.pendingVerification.test.js` — AI review visibility vs `server_feature_flags.evidence_review_v2_enabled`.
- `tests/test_l005_evidence_review_v2_guard_contract.py` — every `@router` handler in `routes/evidence_review.py` calls `_v2_guard()` first (after docstring); admin dashboard flag shape.
- Backend transition observability tests reference `routes.evidence_review.*` origins (e.g. `tests/test_requirement_transition_admin_review_phase6.py`).
