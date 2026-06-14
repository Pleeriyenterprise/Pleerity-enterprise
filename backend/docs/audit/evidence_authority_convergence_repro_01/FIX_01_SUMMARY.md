# EVIDENCE-AUTHORITY-CONVERGENCE-FIX-01

**Status:** Implemented on local `develop` workspace (not deployed to staging/production in this session).

## Root cause (confirmed)

Single convergence pipeline failure: `evidence_authority` → `cer_governance_presentation` → `operational_cognition` → frontend modal/hero could disagree.

| Symptom | Mechanism fixed |
|---------|-----------------|
| Legionella CER on file, EA `MISSING` | `PLATFORM_OVERSIGHT_OPTIONAL` + `PENDING_REVIEW` structured CER excluded from `non_document_record_satisfies_policy` |
| Verified FRA + wrong hero | Cognition truth flags ignored `VERIFIED_CURRENT` / `truth_presentation_stage=verified` |
| EPC/EICR fake review | Expiry guard used generic upload/review semantics; no `expiry_confirmation_required` stage |
| Link verified doc → pending CER | `upsert_document_upload_evidence_for_linked_document` always inserted `PENDING_REVIEW` |

## Files changed

### Backend
- `services/compliance_evidence_record_service.py` — PLATFORM_OPT pending structured satisfaction; verified doc link inherits `VERIFICATION_VERIFIED`
- `services/operational_cognition_service.py` — verified/expiry precedence in flags, workflow stage, envelope primary action
- `services/cer_governance_presentation.py` — `expiry_confirmation_required` truth stage + cognition next step
- `services/contractor_service.py` — indentation fix (blocked pytest import)
- `tests/test_evidence_authority_convergence_fix_01.py` — new regression suite
- `tests/test_operational_cognition_service.py` — align guidance flag expectation with queue-backed semantics

### Frontend
- `utils/requirementSubmissionModalContext.js` — `VIEW_VERIFIED_EVIDENCE` when EA verified
- `utils/requirementLifecyclePresentation.js` — verified CTA override; expiry label; queue-gated review pending
- `utils/cerGovernancePresentation.js` — map `expiry_confirmation_required`
- `utils/requirementSubmissionModalContext.test.js` — verified EA modal context test
- `utils/requirementLifecyclePresentation.test.js` — queue-backed review pending tests

## Tests

| Suite | Result |
|-------|--------|
| `pytest tests/test_evidence_authority_convergence_fix_01.py tests/test_operational_cognition_service.py` | **18 passed** |
| `npm test --testPathPattern=requirementSubmissionModalContext\|requirementLifecyclePresentation` | **28 passed** |

## Staging harness (before deploy)

Prior run (`REPRO_RUNTIME_latest.json`, API `b038eb49`):

- Legionella: `uploaded_not_verified` warning, Record Legionella CTA
- FRA: hero contradiction (Add compliance evidence + verified truth)
- EPC/EICR: `document_upload_missing_required_expiry_semantics`, generic next-action warnings
- Link probe: new `PENDING_REVIEW` DOCUMENT_UPLOAD CER on verified doc

**After deploy + authority re-sync** on affected requirements, re-run:

```bash
cd backend
python scripts/evidence_authority_convergence_repro_01_execute.py --pace 1.0
```

Expected post-fix (with sync):

- Legionella: EA not `MISSING`; cognition `View evidence`; no `uploaded_not_verified`
- FRA: hero aligns with verified summary
- EPC/EICR: `Expiry date needed` stage; no fake review pending CTA
- Link verified doc: CER `VERIFICATION_VERIFIED` (no new pending row)
- Gas Safety: unchanged healthy path

## Production data repair (still required)

Code + staging validation do **not** automatically repair existing Mongo rows. After production deploy:

1. **Dry-run inventory** (read-only): requirements with CER + EA `MISSING`, or verified CER + expiry semantics downgrade
2. **Scoped repair**: `authority_sync_with_transition_observability` per requirement; archive duplicate pending link CERs only when verified sibling exists
3. **No** manual queue inserts; **no** document deletion

## Rollout plan

1. **develop** — merge this fix branch
2. **staging** — deploy API + frontend; run repro harness; trigger authority sync on test property (`d35a58ae…`)
3. **main** — after staging sign-off
4. **production deploy** — code only first
5. **production dry-run inventory** — read-only script from repro harness fields
6. **scoped production repair** — batched authority sync + orphan CER archive (post-approval)
