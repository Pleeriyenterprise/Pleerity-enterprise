# Stranded onboarding — focused regression 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

Does not repeat `STRANDED_ONBOARDING_VERIFIED` (`7b2f83fd` / evidence `b3c2d76b`). The checkout-success fix does not change recovery classification, promo policy, or email-release.

## Automated

| Suite | Result |
| --- | --- |
| `tests/test_onboarding_recovery_orchestration.py` + `tests/test_client_email_identity.py` | **28 passed** |
| `tests/test_portal_setup_status.py` session_id cases | **5 passed** |
| `frontend/src/pages/CheckoutSuccessPage.test.js` | **7 passed** |

## Promo recovery

| Check | Evidence |
| --- | --- |
| Validated / admin-selected promo still pre-applies | Staging runtime: `STAGINGSO01` on `cs_test_a1wgVR4v…`, Checkout **£0.00**, coupon applied |
| Normal paid checkout still works | Unchanged code path; covered by SO-01 paid session `cs_test_b1aKrd9L…` (£68.00) and recovery unit tests. This fix did not touch checkout session creation. |
| Customer-entered Stripe promo remains disabled | Inspect count `customer_entered_promo_ui_count=0`; `allow_promotion_codes` policy unchanged |
| Preserve-existing | Unchanged execution service; covered by SO-01 journey 1 and unit tests |

## Release and restart (API smoke 18 Aug 2026)

Fixture `so.regrel.202608181438@yopmail.com`:

| Step | Result |
| --- | --- |
| Unpaid intake | `c85dd389-…` in Pending Setup |
| Release and restart | 200, `RELEASED_FOR_RESTART`, vacated from Pending Setup, `released_canonical_email` retained |
| Same email registers again | 200 new id `894f0002-…` with `restarted_from_client_id=c85dd389-…` on the client record |
| Third concurrent-style submit | 400 “An account with this email already exists” |
| Active identities | **exactly one** |

Submit JSON does not echo `restarted_from_client_id`; the new client document does. Recorded as PASS.

## Identity protection

| Check | Result |
| --- | --- |
| Provisioned / activation-incomplete cannot be released | `f44b8fd0-…` → 400 `MODE_CLASSIFICATION_MISMATCH` |
| Duplicate active identity blocked | third submit 400 after restart |
| Paid-unprovisioned still protected | Unchanged guards; SO-01 `NOT_ELIGIBLE` / classification mismatch remain authoritative |

JSON: `backend/docs/audit/checkout_success_03/focused_regression_03.json` and `runtime_03.json`.
