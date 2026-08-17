# Commercial Controls — Regression

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_REGRESSION_01.md`  
**Date:** 2026-08-15

## Intent

Commercial Controls remain **exceptions** to normal lifecycle authority, not a second billing system.

## Local tests this exercise

| Suite | Result |
| --- | --- |
| `tests/test_commercial_entitlement_governance.py` | Passed (including new transition, cancelled-access, operator copy, duplicate-key tests) |
| `tests/test_commercial_entitlement_expiry_integration.py` | Skipped (no Mongo in this pytest process) |
| `CommercialEntitlementControls.test.js` | 5 passed |
| `tests/test_admin_action_governance_policy.py` | Pre-existing FAIL: registry contains extra `lifecycle_ops_*` keys. Unrelated. |

## Not re-run (no claim)

Normal subscription renewal, cancellation, dunning, payment recovery, termination, onboarding checkout, Stripe webhooks, and lifecycle emails were **not** executed as a full regression suite in this window.

## Risk of this diff

| Change | Regression risk |
| --- | --- |
| Render step-up modal | Low; matches other admin panels |
| Axios timeout 60s on execute only | Low; other admin calls unchanged |
| Unique partial index | Medium on deploy if duplicate `active` rows already exist — create is try/except |
| Onboarding waiver flags | Connects to existing checkout authority; could skip setup fee on next checkout for waived clients — **intended** |
| Email idempotency key | Low; better dedupe |
| Isolated email/recon timeouts | Prevents execute hang; exception still committed |

## Soak

No deploy. Existing Mongo soak evidence is not invalidated by this source change. A future backend deploy must record timestamp and whether the soak window restarts.

## Existing commercial exceptions

Expiry job and governance collection unchanged in semantics. Unique index tightens the already-stated one-active-row rule.
