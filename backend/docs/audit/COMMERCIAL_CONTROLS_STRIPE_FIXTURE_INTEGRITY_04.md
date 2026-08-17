# Commercial Controls — staging Stripe fixture integrity 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Audit window:** 2026-08-15T20:24Z (read-only)  
**Staging runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`  
**Production SHA:** `89217062481b4eb858a8b530ec90c83de067a4be` (untouched)  
**Mutation:** none during this audit  
**Evidence JSON:** `backend/docs/audit/commercial_controls_stripe_integrity_04.json`

Preserves 03 Stripe missing-object evidence: `COMMERCIAL_CONTROLS_STRIPE_RUNTIME_03.md`.

## Method

Read-only classification of staging clients whose platform subscription status is ACTIVE.

- Stripe test-mode retrieve was **not** called from the integrity script (avoids `billing_last_synced_at` writes on successful retrieve).
- Existence for the 03 cohort uses the live `No such subscription` / `resource_missing` log from 03.
- Current fixtures are those with **future** `current_period_end` and recent **test-mode** `customer.subscription.updated` webhooks.

## Decision

```text
ISOLATED_STALE_STAGING_FIXTURES
```

Not `BLOCKED_BY_STAGING_STRIPE_RECONCILIATION_DRIFT`.

| Class | Count | Meaning |
| --- | ---: | --- |
| `STALE_STAGING_FIXTURE` | 27 | Past period end (May–June 2026); 03 Stripe retrieve failed `resource_missing` on sampled ids |
| Current test subscriptions | 2 | Future period end; August 2026 test-mode webhooks |
| `MISSING_STRIPE_CUSTOMER` | 0 | — |
| `STATUS_DRIFT` / `PLAN_DRIFT` / `DUPLICATE_REFERENCE` | 0 | — |

The 03 ACTIVE probes failed because they targeted **historic** `sub_1T2*`–`sub_1TI*` ids. That is fixture decay, not a current-subscription integrity defect.

## Compact matrix

| Client | Platform state | Stripe customer | Stripe subscription | Exists? | Stripe status | Drift class |
| --- | --- | --- | --- | --- | --- | --- |
| lere@yopmail.com `ce8d3b56-…` | ACTIVE / PLAN_2_PORTFOLIO | `cus_UqkF…` | `sub_1Tr2…` | yes (Phase 7 pause retrieve) | ACTIVE | current valid test fixture |
| lucas@yopmail.com `3edc554b-…` | ACTIVE / PLAN_3_PRO | `cus_UsYu…` | `sub_1Tsn…` | yes (test webhook 2026-08-13) | ACTIVE (platform) | current valid test fixture (not mutated in 04) |
| nancy@yopmail.com `6fd5ac4c-…` | ACTIVE / PLAN_3_PRO | `cus_UGeQ…` | `sub_1TI7…` | no (03 `No such subscription`) | missing | `STALE_STAGING_FIXTURE` |
| 03 ACTIVE probes (drjpane, olivia.chen, anya.sharma, …) | ACTIVE, period ended May–June 2026 | historic `cus_U*` | historic `sub_1T2*`–`sub_1TI*` | no | missing | `STALE_STAGING_FIXTURE` (27 total) |

Phase 1 labelled the two current rows `UNKNOWN` because this audit did not live-retrieve Stripe. Phase 7 upgraded lere to **proven existing** via `pause_collection` accept. Lucas was left unused.

## Authoritative ACTIVE certification fixture

Used as-is from the normal staging billing lifecycle (signup July 2026, test customer, test subscription, webhook ingestion). No Mongo `sub_*` was fabricated.

| Field | Value |
| --- | --- |
| Email | lere@yopmail.com |
| Client | `ce8d3b56-0659-46d8-88af-0988fe48de25` |
| Plan | `PLAN_2_PORTFOLIO` |
| Canonical | ENABLED |
| Active exception at audit | none |
| Stripe test customer | `cus_UqkF…` |
| Stripe test subscription | `sub_1Tr2…` |
| Period end | 2026-09-08T21:11:39Z |
| Recipient | staging yopmail only |

## Production non-touch

No production Stripe objects queried or mutated in this audit.
