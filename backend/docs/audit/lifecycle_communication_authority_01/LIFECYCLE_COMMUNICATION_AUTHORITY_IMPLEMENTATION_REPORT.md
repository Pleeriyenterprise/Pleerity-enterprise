# LIFECYCLE-COMMUNICATION-AUTHORITY-01 — Implementation Report

**Branch:** `develop` only  
**Date:** 2026-06-30  
**Authority version:** `lifecycle_communication_v1`  
**Evidence:** [`LIFECYCLE_COMMUNICATION_AUTHORITY_IMPLEMENTATION_EVIDENCE.json`](./LIFECYCLE_COMMUNICATION_AUTHORITY_IMPLEMENTATION_EVIDENCE.json)

---

## Summary

Implemented a shared **Lifecycle Communication Authority** (`backend/lifecycle_communication/`) that consumes authoritative lifecycle inputs and returns a structured customer communication model for every lifecycle family.

No lifecycle rules, requirement determination, reminder schedules, notification routing, or scoring were changed.

---

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Authority module | `backend/lifecycle_communication/` |
| Governance | `backend/docs/LIFECYCLE_COMMUNICATION_AUTHORITY.md` |
| Tests | `backend/tests/test_lifecycle_communication_authority.py` (24 tests) |
| Implementation evidence | This report + JSON |

---

## Architecture

### Canonical resolver

`resolve_customer_communication(requirement_row, surface, channel, …)` returns:

- `heading`, `reason`, `primary_action`, `when_text`, `how_text`, `next_step`
- `evidence_expectation`, `urgency`, `primary_cta`, `secondary_cta`
- `completion_wording`, `lifecycle_verb`, `tone`, `surface_variants`

### Registry

`LifecycleCommunicationAuthority.registry_as_list()` — 14 lifecycle families with governed verbs, headings, and supported surfaces.

---

## Integration (surface consumption)

| Surface | Wired via |
|---------|-----------|
| Reminder email/SMS | `email_service`, `lifecycle_reminder_template_registry` |
| Enablement in-app/email | `enablement_service`, `enablement_templates` (LCA tokens) |
| Monthly digest posture | `monthly_digest_operational_intelligence.interpret_evidence_posture` |
| Risk cards | `risk_signal_service._recommended_action_for_risk` |
| Portal requirement API | `requirement_action_resolver` → `customer_communication` on rows |
| Property Detail chips | `frontend/evidenceStatus.js` consumes API field |
| Grouped reminder headings | `email_service` via `heading_for_reminder_group` |

### Not changed (per programme constraints)

- Reminder scheduling / timing
- Notification orchestration / routing / recipients
- Lifecycle Authority rules
- Requirement Authority / scoring
- Today Authority bucket semantics
- Email Presentation Authority

---

## Test results

```
tests/test_lifecycle_communication_authority.py — 24 passed
tests/test_lifecycle_reminders_s44.py — passed (regression)
tests/test_monthly_digest_operational_intelligence.py — passed (regression)
```

Regression guards:

- REVIEW_DUE reminders do not use expiry/renewal language
- Declarations do not receive expiry wording
- Group headings no longer use "Certificates & Expiring Evidence" / "Other Compliance Actions"
- Electrical risk copy does not mandate certificate-only framing

---

## Acceptance checklist

| Criterion | Status |
|-----------|--------|
| One shared Lifecycle Communication Authority | ✓ |
| One Lifecycle Communication Registry | ✓ |
| All 14 lifecycle families governed | ✓ |
| WHY / WHAT / WHEN / HOW / WHAT NEXT on model | ✓ |
| Duplicated reminder heading logic consolidated | ✓ |
| CTA wording consumes take_action + LCA | ✓ |
| Governed lifecycle verbs | ✓ |
| Consumes authorities without reclassifying | ✓ |
| Lifecycle / requirement / notification logic unchanged | ✓ |
| Production / main untouched | ✓ |

---

## Follow-up (out of scope)

- Staging validation cohort per lifecycle family across email + portal
- `LIFECYCLE_AWARE_REMINDERS=active` promotion decision (separate programme)
- Today banner lifecycle verb alignment (documented in TODAY-AUTHORITY-CONSISTENCY-01)
- FE mirror module deprecation for `lifecycleAuthorityCopy.js` risk headlines
