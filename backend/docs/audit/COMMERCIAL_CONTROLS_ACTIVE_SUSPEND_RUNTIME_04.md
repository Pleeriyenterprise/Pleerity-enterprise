# Commercial Controls — ACTIVE Suspend Billing runtime 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Fixture:** lere@yopmail.com `ce8d3b56-0659-46d8-88af-0988fe48de25`  
**Plan:** `PLAN_2_PORTFOLIO`  
**Stripe:** test customer `cus_UqkF…` / subscription `sub_1Tr2…`  
**Staging API SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`  
**Execute:** 2026-08-15T20:43:11Z HTTP 200, `elapsed_ms` ≈ 10838  
**Evidence JSON:** `backend/docs/audit/commercial_controls_final_results_04.json`

03 ACTIVE path was **FAIL** (`STRIPE_PAUSE_FAILED` / missing historic subs). Authority was not redesigned. This 04 run uses a current test-mode subscription.

## BEFORE

| Axis | Value |
| --- | --- |
| Classification | ACTIVE |
| Active exception | none |
| Canonical / effective | ENABLED / ENABLED |
| Plan | PLAN_2_PORTFOLIO |
| Stripe subscription status | ACTIVE |
| `pause_collection` | null |
| Latest invoice | `in_1U2HX…` |
| Open invoice | none |
| Next billing / period end | 2026-09-08T21:11:39Z |
| Billing sync | ok |
| Reconciliation needed | false |

## EXECUTE

Governed API path: operator token → `STEP_UP_REQUIRED` eligible → step-up verify 200 → execute with confirmation.

| Axis | Value |
| --- | --- |
| HTTP | 200 `ok` |
| Stripe mutation | `pause_collection` |
| Behavior | `void` |
| Reconciliation | `pause_collection_applied` |
| Subscription status after pause | ACTIVE (not cancelled, not recreated) |
| Email | selected; outcome `sent` |

## AFTER (exception active)

| Axis | Value |
| --- | --- |
| Classification | BILLING_SUSPENDED |
| Exception | `billing_suspension` active (`b48240a7-…`) |
| Canonical lifecycle | ENABLED (preserved) |
| Effective access | ENABLED, `full_access`, PLAN_2_PORTFOLIO |
| Reason | Billing suspended pending review |
| Notification | `sent` |
| Stripe reconciliation | `reconciled_lightweight` |
| Period end | **unchanged** 2026-09-08T21:11:39Z |
| Latest invoice | **same** `in_1U2HX…` |
| Open invoice | none |
| Audit | `commercial_granted` 20:43:11Z (observability); assessment listed `suspend_billing` |

Billing GET still projected `pause_collection: null` while paused. That is a **snapshot lag**, not a failed pause. Authority for the pause is the execute `stripe_pause` payload plus the later resume webhook.

## UI

Staging alias with circuit-fix bundle. Control panel Billing tab after recovery:

- Plan PLAN_2_PORTFOLIO, subscription ACTIVE, access ENABLED
- Next billing 08/09/2026 22:11:39
- Last webhook 15 Aug 2026 20:45:12 UTC `customer.subscription.updated`
- Governance ACTIVE; recent audit `commercial_expired` then `commercial_granted`
- Impact preview (14-day dialog, not persisted): collection paused via `pause_collection (void)`; Portfolio access kept; underlying status unchanged

Circuit UI: submit → 403 STEP_UP_REQUIRED → modal → cancel → immediate retry → modal. See `COMMERCIAL_CONTROLS_STEP_UP_CIRCUIT_FIX_04.md`.

## EXPIRY / RECOVERY

Short-lived fixture: `entitlement_expiry_at` 2026-08-15T20:44:37Z (`duration_days=1` with backdated expiry). Job `commercial_entitlement_expiry` 200, `expired_count: 1` for this governance id.

| Axis | After expiry 20:45:09Z |
| --- | --- |
| Active exception | none |
| Classification | ACTIVE |
| Canonical / effective | ENABLED / ENABLED |
| Plan | PLAN_2_PORTFOLIO |
| Subscription id | same `sub_1Tr2…` (no duplicate) |
| Period end | same 2026-09-08 |
| Latest invoice | same `in_1U2HX…` (no duplicate / no immediate invoice) |
| Open invoice | none |
| Pause | removed (webhook `customer.subscription.updated` 20:45:12Z) |
| Observability | `commercial_expired` |
| Access gap | none |

## Chain

```text
valid ACTIVE staging subscription
→ Commercial Control submit
→ STEP_UP_REQUIRED
→ modal (UI) / step-up token (API)
→ no circuit penalty
→ Stripe pause applied (behavior=void)
→ commercial exception persisted
→ plan-equivalent access maintained
→ customer communication correct (Postmark DELIVERED + inbox body)
→ UI refreshes (panel; no full reload required)
→ expiry
→ Stripe billing resumes (same period end, no immediate invoice)
→ commercial exception expires
→ lifecycle remains canonical ENABLED
```

## Verdict for ACTIVE Suspend Billing

```text
PASS
```
