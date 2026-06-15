# POST-SUBMISSION-EVIDENCE-UX-FIX-P0

**Status:** Implemented (code + tests)  
**Scope:** Six P0 defect classes only — no P1 review/escalation changes, no production data writes.

---

## 1. Root cause per defect class

| # | Class | Root cause | Fix |
|---|-------|------------|-----|
| 1 | Verified evidence routing | `_verified_view_primary_action` always returned `/documents`; modal `VIEW_VERIFIED` navigated away from inspect panel for structured CERs | Backend intel submission URL when no authoritative document; frontend `authoritativeEvidenceView` + scroll-to-inspect in modal |
| 2 | Update prefill | `build_reopen_prefill_from_record` skipped non-dict field values; contractor/checklist metadata not extracted | Expanded prefill normalisation + modal consumption |
| 3 | Duplicate Update CTAs | Hero and footer both rendered primary “Update submission” | `showHeroPrimary: false` for VIEW_SUBMISSION / VIEW_VERIFIED contexts |
| 4 | False upload warning | `_truth_flags_for_requirement` keyed off lifecycle alone | `_upload_verification_attention_required` requires linked/uploaded document |
| 5 | Display hygiene | `formatFieldValue` JSON-stringified empty answer objects | `formatFieldValueForDisplay` + skip empty optional rows |
| 6 | PAT dead CTA | JOB-class PAT routed to `/properties/{id}#req=` instead of document upload | `_pat_document_upload_primary` → DOCUMENT upload route with external-assessment label |

---

## 2. Files changed

### Backend
- `services/operational_cognition_service.py` — truth flags, verified view URL
- `services/cer_actionability_presentation.py` — prefill expansion
- `services/requirement_action_resolver.py` — PAT document-primary override
- `tests/test_post_submission_evidence_ux_fix_p0.py` (new)
- `tests/test_operational_cognition_service.py` — fixture update
- `tests/test_cer_actionability_presentation.py` — scalar prefill assertion

### Frontend
- `utils/authoritativeEvidenceView.js` (new)
- `utils/complianceEvidenceSubmissionView.js` — display hygiene
- `utils/requirementSubmissionModalContext.js` — suppress hero primary duplicate
- `utils/documentEvidenceAuthority.js` — settled navigation uses authoritative path
- `utils/requirementCtaParity.js` — view submission opens intel inspect, not empty guided
- `components/client/RequirementIntelligenceModal.js` — view evidence routing
- `components/client/RequirementModalContextHero.jsx` — `showHeroPrimary`
- `components/ComplianceEvidenceResolveModal.js` — contractor/checklist prefill
- Tests: `authoritativeEvidenceView.test.js`, `complianceEvidenceSubmissionView.display.test.js`, `requirementSubmissionModalContext.test.js`

---

## 3. Before vs after behaviour

| Scenario | Before | After |
|----------|--------|-------|
| Verified Legionella (structured CER) → View evidence | `/documents` (empty) or blank guided form | Intel modal scrolls to read-only inspect panel / deep link `?open=intel&focus=submission` |
| Update submission (structured) | Blank fields if scalar storage | Prior answers prefilled (dict + scalar) |
| Satisfied modal | Two “Update submission” buttons | Hero informational only; single footer primary |
| Self-recorded declaration satisfied | “Uploaded is not verified” | No upload warning without document |
| Tenancy optional empty field | `{"answer":null,...}` | Hidden or “Not provided” (not shown in list) |
| PAT CTA | Navigate to property hash (dead end) | Navigate to `/documents?...` upload with PAT label |

---

## 4. Update semantics (documented)

**Update submission still creates a new CER** via `POST …/compliance-evidence` (`create_compliance_evidence_record` always inserts). Prefill is for UX continuity only. Supersede/archive policy remains **P1** — not changed in this workstream.

---

## 5. Test evidence

**Backend:** `37 passed` including `test_post_submission_evidence_ux_fix_p0.py` (7 tests).

**Frontend:** `17 passed` across authoritativeEvidenceView, display hygiene, modal context tests.

---

## 6. Requirement-family coverage matrix

| Family | P0-1 View | P0-2 Prefill | P0-3 CTA | P0-4 Warning | P0-5 Display | P0-6 PAT |
|--------|-----------|--------------|----------|--------------|--------------|----------|
| Guided declarations (tenancy, deposit, Wales contract) | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Multi-evidence (smoke/heat, HMO fire) | ✓ | ✓ checklist | ✓ | ✓ | ✓ | — |
| External assessment (legionella, lead) | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Document-primary (gas, EICR, EPC) | ✓ documents | N/A | ✓ | ✓ | ✓ | — |
| PAT | ✓ | N/A | ✓ | ✓ | ✓ | ✓ |
| Registration (Rent Smart Wales) | ✓ | ✓ | ✓ | ✓ | ✓ | — |

Mechanism is family-agnostic via `authoritativeEvidenceView` + cognition truth gating + prefill normalisation.

---

## 7. Remaining known gaps (out of scope)

- **P1:** Phantom review/escalation after document link (`manual_review_flag`, MISMATCH_FLAGGED)
- **P1:** CER update vs new-version policy (duplicate CER accumulation on repeated updates)
- **P2:** Card-level `take_action` label still “Record…” when cognition says “View evidence” (lifecycle rewrite on list row — cosmetic)
- Staging E2E harness re-run not executed in this session (no staging credential writes)

---

## 8. Rollback plan

1. Revert commit(s) touching files listed in §2.
2. No database migration or backfill required.
3. Safe to deploy independently of registry content.
4. If partial rollback needed: backend-only restores truth flags + PAT resolver; frontend-only restores modal routing.

---

## Constraints observed

- No production data modified
- No registry changes
- No P1 escalation workflow changes
