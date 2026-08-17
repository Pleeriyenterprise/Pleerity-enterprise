# Commercial Controls — E2E Certification

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_E2E_CERTIFICATION_01.md`  
**Date:** 2026-08-15  
**Verdict:** `COMMERCIAL_CONTROLS_INCOMPLETE`

## Why this is not VERIFIED

A Commercial Control is certified only when UI → API → authority → persistence → Stripe/email/audit → UI refresh are **runtime-proven**. This exercise:

1. Identified and fixed the indefinite spinner in source.
2. Added unit/source regression coverage.
3. Could **not** complete staging execute of all seven controls: admin login returned **423 Locked**.
4. Could **not** prove the spinner fix on the deployed frontend (fix not deployed).
5. Did not re-run expiry against staging Mongo in this window.

Machine-readable companion: `commercial_controls_e2e_results_01.json`.

## Required matrix

Legend: `P` = proven this exercise; `U` = unverified this exercise; `C` = code-path only; `N/A` = not applicable under v1 Stripe posture.

| Control | UI | API | DB | Authority | Stripe | Email | Audit | Expiry | UI Refresh | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Grant grace period | U | U | C | P (unit) | C `NO_STRIPE_ACTION` | U | C | U (prior 2026-06-01) | C | FAIL unverified |
| Suspend billing | U (hang on deployed UI) | U | C | P (unit, cancelled stays CANCELLED) | C `NO_STRIPE_ACTION` | U | C | U | C | FAIL unverified |
| Sponsored access | U | U | C | P (sponsor required) | C | U | C | U | C | FAIL unverified |
| Retention extension | U | U | C | C | C | U | C | U | C | FAIL unverified |
| Waive onboarding fee | U | U | C | C (now sets existing waiver flags) | C checkout flags | U | C | N/A permanent waiver flags | C | FAIL unverified |
| Recovery compensation | U | U | C | C time-bound continuity, not credit | C | U | C | U | C | FAIL unverified |
| Restrict entitlement | U | U | C | P (canonical SUSPENDED) | C | U | C | U | C | FAIL unverified |

No row may be PASS while a required column is unverified. All rows are **FAIL unverified**.

## Proof attempted

| Probe | Result |
| --- | --- |
| Local unit tests | Pass |
| Frontend source tests (step-up host, timeout, silent reload) | Pass |
| Staging admin login | **423 Locked** |
| Staging execute of 7 controls | Not run |
| Deployed frontend `commercial-step-up-modal-host` | Not deployed |
| Prior Phase 2C staging closeout | API execute + expiry job proven 2026-06-01; does not certify this spinner fix |

## Intended outcomes (Phase 3) — code authority, not staging objects

### Grant grace period

Access remains operational when baseline is not `CANCELLED` (`ENABLED` preserved). Billing collection is **not** Stripe-paused. Expiry is `now + duration_days` (max 30). Commercial Controls shows `Expires`. Billing card “Grace period ends” is **dunning** grace, not this exception — operators must read Commercial Controls expiry.

### Suspend billing

Modal claims full access + billing paused. Access preservation is true only when baseline ≠ `CANCELLED`. Billing pause is **platform record only**; Stripe subscription is unchanged in v1. Dunning/next billing dates in Stripe remain until a future governed Stripe pause exists.

### Sponsored access

Requires sponsor reference. Review required. Max 90 days. Must not be permanent: expiry job closes the row; access returns to subscription-derived canonical state.

### Retention extension

Extends operational access window via `RETENTION_EXTENSION` until expiry. Does not by itself change Stripe period end.

### Waive onboarding fee

After this fix, sets `onboarding_fee_waived` used by checkout. Does not waive recurring subscription items. Idempotent.

### Recovery compensation

Time-bound `RECOVERY_CONTINUITY` with full access. **Not** a monetary Stripe credit. No amount field exists on the execute body.

### Restrict entitlement

Sets access policy `suspended`, canonical `SUSPENDED`. Does not delete compliance records (`preserve_compliance_records` false for restricted, records not deleted).

## Next actions to reach VERIFIED

1. Unlock or use a non-locked staging admin.
2. Deploy this `develop` change set to **staging only** (not `main`).
3. Record soak impact if backend scheduler restarts.
4. Run `python scripts/commercial_controls_e2e_certification_01.py` against an **ENABLED** fixture and a **CANCELLED** fixture.
5. One real UI submit per control with step-up modal completing (spinner must stop).
6. One continuity email to a staging inbox with Postmark message id.
7. Expiry closeout on a backdated row.
