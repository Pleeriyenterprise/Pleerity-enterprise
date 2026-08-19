# Customer communication — repository reconciliation 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

Does not repeat Audit 01, Remediation 02, or Runtime Closure 03.

Related:

* `CUSTOMER_COMMUNICATION_STAGING_RUNTIME_CERTIFICATION_02.md`
* `CUSTOMER_COMMUNICATION_P0_P1_CLOSURE_03.md`
* `customer_communication_runtime_closure_03.json`

## Verdict on drift

```text
PROMOTION_APPLICATION_SHA = 0097b85f041970719c20c2670003a29ddf001e26
```

No unverified application drift after the certified staging SHA. Not `BLOCKED_BY_UNVERIFIED_DEVELOP_DRIFT`.

Documentation-only commit `4fe86a38` (stranded-onboarding promotion 03 evidence) is an ancestor of `0097b85f` and was already on the staging-certified candidate. Behaviourally identical extra docs, not mixed unverified work.

## Capture (before merge)

| Item | Value |
| --- | --- |
| Primary worktree branch | `develop` (dirty; gallery PDFs / soak notes / tmp probes — **not committed, not merged**) |
| Merge worktree | `C:\pleerity-workspace\ppe-07-main` on `main`, clean |
| `LOCAL_DEVELOP_SHA` | `0097b85f041970719c20c2670003a29ddf001e26` |
| `ORIGIN_DEVELOP_SHA` | `0097b85f041970719c20c2670003a29ddf001e26` |
| `ORIGIN_MAIN_SHA` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `PROMOTION_APPLICATION_SHA` | `0097b85f041970719c20c2670003a29ddf001e26` |
| Merge-base `origin/main`…`origin/develop` | `a803af04205710a3280322beeb7d6b5aa7aa2180` |
| Fast-forward possible | **No** — `main` already had merge `1fcb5fbc` |
| Uncommitted / untracked in primary | Present; excluded from promotion |
| Staged changes | None in merge worktree |

## Source integrity vs certified staging SHA

`origin/develop` **is** `0097b85f`. Behaviour-relevant files in `origin/main...origin/develop`:

* `backend/services/jobs.py`
* `backend/services/notification_send_idempotency.py`
* `backend/lifecycle_communication/*`
* `backend/services/email_service.py`
* `backend/services/subscription_lifecycle_service.py`
* `backend/services/stripe_webhook_service.py`
* `backend/services/notification_orchestrator.py`
* `backend/services/maintenance_service.py`
* `backend/services/onboarding_sequence_service.py`
* `backend/services/onboarding_state_checker.py`
* `backend/utils/app_urls.py`
* `backend/services/billing_period_utils.py` (basil invoice subscription id)
* `backend/services/subscription_operational_events.py`
* reminder template / email presentation metadata
* focused tests listed in the gate document

Compatibility fixes required by staging closure and present in the candidate:

* basil webhook subscription extraction via `subscription_id_from_stripe_invoice_dict` (`parent.subscription_details`)
* cancellation recipient `contact_email or email` in `resolve_client_notification_email`

No irreversible migration, Alembic, or Mongo cleanup scripts in the promotion range.

Frontend files in range: **none**. Customer production frontend is not part of this promotion.

## Runtime Closure 03 evidence (preserved, not rewritten)

Present on disk (untracked in the primary worktree; not required inside merge SHA `0097b85f`):

* `CUSTOMER_COMMUNICATION_PAYMENT_FAILED_RUNTIME_03.md`
* `CUSTOMER_COMMUNICATION_CANCELLATION_RUNTIME_03.md`
* `CUSTOMER_COMMUNICATION_RENEWAL_WINDOW_RUNTIME_03.md`
* `CUSTOMER_COMMUNICATION_CONTRACTOR_RUNTIME_03.md`
* `CUSTOMER_COMMUNICATION_P0_P1_CLOSURE_03.md`
* `customer_communication_runtime_closure_03.json`

01 and 02 evidence remains in-tree on the promotion candidate (`CUSTOMER_COMMUNICATION_*_02.md` plus runtime JSON).

No secrets committed.
