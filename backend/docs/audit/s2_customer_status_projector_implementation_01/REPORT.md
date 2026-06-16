# S2 customer status projector — implementation report

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-01  
**Date:** 2026-06-16  
**Status:** Implemented — default `disabled`; no production/staging env changes

---

## Files changed

### New

| File | Purpose |
|------|---------|
| `backend/services/customer_status_projector_v2.py` | Authoritative projector + enrich integration API |
| `backend/services/customer_status_projector_config.py` | `CUSTOMER_STATUS_PROJECTOR_V2_MODE` flag |
| `backend/services/customer_status_projector_shadow.py` | Legacy vs projector comparison + safe logging |
| `backend/tests/test_customer_status_projector_v2.py` | Unit, integration, flag, REM, D-family tests |

### Modified

| File | Change |
|------|--------|
| `backend/services/requirement_truth.py` | Projector integration; deferred take_action; REM-01 |
| `backend/services/cer_governance_presentation.py` | `emit_legacy_customer_labels` param; REM-02 |
| `backend/services/operational_cognition_service.py` | Cognition reads `customer_status_*` when active; REM-03 |
| `backend/services/cer_actionability_presentation.py` | Queue-gated banners; REM-04 |
| `backend/services/requirement_action_resolver.py` | CTA alignment post-projector; REM-05 |
| `backend/routes/client.py` | Expose `customer_status_projector_v2_mode` |
| `backend/routes/admin.py` | Expose `customer_status_projector_v2_mode` |
| `backend/tests/test_cer_actionability_presentation.py` | Banner assertion updated for approved copy |

---

## Projector summary

- Maps enrich signals to `CUSTOMER_STATUS_VOCABULARY.json` terms only (v1.0.0).
- Overlay precedence: escalation → rejected → under_review → expiry → followup → additional → base.
- Gates: Class A never `under_review` without queue; Class B `uploaded` when pending admin but not queued; escalation supersedes review; follow-up supersedes satisfied display; `supporting_upload_only` → Action required (class A only).
- Outputs: `customer_status_key`, `customer_status_label`, `customer_status_subline`, `customer_status_class`, `customer_status_reason`, `customer_status_overlay`, `vocabulary_version`, `customer_status_projector_version`.

---

## Feature flag

| Item | Value |
|------|-------|
| Env var | `CUSTOMER_STATUS_PROJECTOR_V2_MODE` |
| Values | `disabled` \| `shadow` \| `active` |
| Default | `disabled` |
| API | `server_feature_flags.customer_status_projector_v2_mode` |

| Mode | Behaviour |
|------|-----------|
| `disabled` | Legacy only; no `customer_status_*` |
| `shadow` | Projector runs; legacy fields unchanged; divergence logged |
| `active` | Projector authoritative; legacy `truth_*` mirrored from projector |

**Production active not enabled.** No env vars modified on production or staging.

---

## Shadow logging

- Event: `customer_status_projector_divergence`
- Compares: label, subline, key/class, retired phrases, review-without-gate, escalation normalization
- Logs: requirement_id, client_id, property_id, requirement_code, governance_family, queue flags — **no PII**
- Internal field: `_customer_status_shadow` on enrich row when divergence detected

---

## Five remediations

| ID | Status |
|----|--------|
| REM-01 enrich overwrite | Done — active uses `customer_status_label` for `client_lifecycle_label` |
| REM-02 legacy label emission | Done — `emit_legacy_customer_labels=False` when active |
| REM-03 cognition | Done — `cognition_copy_from_customer_status` when active |
| REM-04 banners | Done — queue-gated copy; no retired review phrases |
| REM-05 take_action | Done — resolved after projector; CTA aligned when active |

---

## Tests

| Suite | Result |
|-------|--------|
| `test_customer_status_projector_v2.py` | 26 passed |
| `test_customer_status_vocabulary.py` | 16 passed |
| `test_cer_actionability_presentation.py` | passed |
| `test_cer_governance_presentation.py` | passed |
| `test_vocabulary_governance_lint.py` | passed |
| `vocabulary_governance_ci_gate.py` | **pass** (0 violations) |

---

## Out of scope (confirmed unchanged)

- Frontend consumers
- Reports / emails
- Mongo schemas / migrations
- Production or staging environment variables
- S3 work

---

## GO / NO-GO — staging shadow deployment

| Criterion | Verdict |
|-----------|---------|
| Code complete | **Yes** |
| Tests green | **Yes** |
| Default disabled | **Yes** |
| CI vocabulary gate | **Pass** |
| 12-family staging fixtures (manual) | **Pending** — automated unit coverage in place |
| G1–G6 shadow soak | **Not started** |

**GO** for **staging deploy with `CUSTOMER_STATUS_PROJECTOR_V2_MODE=disabled`** (zero customer impact).

**GO WITH CONDITIONS** for **staging `shadow`** after:
1. Deploy build to staging
2. Set `CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow` (ops approval)
3. Run 12-family manual spot-check + monitor divergence logs
4. Hold G1–G6 before any `active` promotion

**NO-GO** for production `active` or staging `active` until shadow acceptance completes.
