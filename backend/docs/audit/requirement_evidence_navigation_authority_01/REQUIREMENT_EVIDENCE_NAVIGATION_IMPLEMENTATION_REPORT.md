# REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-IMPLEMENTATION-01 — Implementation Report

**Programme:** REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-IMPLEMENTATION-01  
**Branch:** `develop` only (no `main`, no production)  
**Date:** 2026-06-30  
**Verdict:** **IMPLEMENTATION_COMPLETE**

## Objective

Introduce one canonical, lifecycle-aware evidence navigation resolver used by all requirement evidence CTAs. Presentation routing only — no changes to document lifecycle, requirement authority, evidence status, or scoring.

## Root cause (from audit)

`executeRequirementPrimaryCta` preferred `resolveAuthoritativeEvidenceViewPath` (document-primary → `/documents`) before `resolveSettledEvidenceNavigationTarget` (registry rewrite). Verified linked documents therefore opened Document Operations, whose default queue filters `ATTENTION_REQUIRED` only — producing an empty Needs Action view.

## Implementation summary

### Canonical resolver

**New:** `frontend/src/utils/resolveEvidenceNavigationTarget.js`

- `resolveEvidenceNavigationTarget(requirement, { ta, pagePropertyId, latestCer, intent, lifecycle })`
- `inferEvidenceNavigationIntent(requirement, ta)`
- `requirementNeedsLinkageReview(requirement)`
- `EVIDENCE_NAV_INTENT` constants aligned with backend intents
- `resolveAuthoritativeEvidenceViewPath` re-exported via `authoritativeEvidenceView.js` (thin compatibility layer)

### Lifecycle routing

| State | Intent / condition | Destination |
|-------|-------------------|-------------|
| Missing / ACTION_REQUIRED | upload | `/documents?...&focus=upload` |
| Needs linkage | reconciliation | `/documents?property_id&requirement_id` |
| Pending review | review document | Document Operations queue |
| Pending review | view submission | Registry + `open=intel&focus=submission` |
| Verified linked document | view settled | Property Evidence Registry |
| Verified structured / self-certified | view submission | Registry + intel inspect |
| Archived / superseded | view | Registry (historical section) |
| Non-evidence operational | guidance / issues | Pass-through route unchanged |

### Surfaces wired

| Surface | Mechanism |
|---------|-----------|
| Requirements page | `executeRequirementPrimaryCta` |
| Property Detail | `executeRequirementPrimaryCta` |
| Requirement drawer / intel modal | `resolveEvidenceNavigationTarget` in `viewAuthoritativeEvidence` + footer paths |
| Operating hub / Command Center / Dashboard | `executeRequirementPrimaryCta` (shared parity helper) |
| Compliance Score tier-B fallback | Already registry (`ComplianceScorePage.scoreDriverActions.js`) — unchanged |

### Backend intent alignment (presentation contract only)

**`backend/services/requirement_action_resolver.py`**

- `INTENT_VIEW_SETTLED_EVIDENCE`
- `INTENT_REVIEW_UPLOADED_DOCUMENT`
- `INTENT_VIEW_SUBMISSION`

**`backend/services/operational_cognition_service.py`**

- `_verified_view_primary_action`: verified linked document URL → Property Evidence Registry; emits `intent` field (`view_settled_evidence` / `view_submission`)

**`frontend/src/utils/requirementTakeActionResolver.js`**

- `primaryIntentFromTakeActionPrimary` recognises new intents and registry deep links

### Tests reconciled

| File | Change |
|------|--------|
| `authoritativeEvidenceView.test.js` | Verified document-primary → registry (was `/documents`) |
| `documentEvidenceAuthority.test.js` | Unchanged behaviour via canonical delegation |
| `requirementCtaParity.test.js` | Added verified + `document_id` + `upload_evidence` intent case |
| `resolveEvidenceNavigationTarget.test.js` | **New** — full lifecycle matrix + surface parity |
| `test_post_submission_evidence_ux_fix_p0.py` | Verified document cognition URL → registry + intent |

**Test results (local):** 37 frontend + 7 backend tests passing in scoped suites.

## Acceptance checklist

| Criterion | Status |
|-----------|--------|
| Verified linked document opens Evidence Registry | ✅ |
| Missing / unresolved evidence opens operational workflow | ✅ |
| CTA wording and destination agree (lifecycle presentation + resolver) | ✅ |
| No lifecycle authority changes | ✅ |
| No production / `main` changes | ✅ |
| No empty queue routing for settled evidence | ✅ |

## Files changed

### Frontend

- `frontend/src/utils/resolveEvidenceNavigationTarget.js` (new)
- `frontend/src/utils/resolveEvidenceNavigationTarget.test.js` (new)
- `frontend/src/utils/authoritativeEvidenceView.js`
- `frontend/src/utils/authoritativeEvidenceView.test.js`
- `frontend/src/utils/documentEvidenceAuthority.js`
- `frontend/src/utils/requirementCtaParity.js`
- `frontend/src/utils/requirementCtaParity.test.js`
- `frontend/src/utils/requirementTakeActionResolver.js`
- `frontend/src/components/client/RequirementIntelligenceModal.js`

### Backend

- `backend/services/requirement_action_resolver.py`
- `backend/services/operational_cognition_service.py`
- `backend/tests/test_post_submission_evidence_ux_fix_p0.py`

### Audit

- `backend/docs/audit/requirement_evidence_navigation_authority_01/REQUIREMENT_EVIDENCE_NAVIGATION_IMPLEMENTATION_REPORT.md`
- `backend/docs/audit/requirement_evidence_navigation_authority_01/REQUIREMENT_EVIDENCE_NAVIGATION_IMPLEMENTATION_EVIDENCE.json`

## Out of scope (by design)

- Document lifecycle / linkage authority logic
- Requirement satisfaction or scoring
- Production promotion
- Document Operations queue filter behaviour (unchanged; navigation no longer sends settled users there)
