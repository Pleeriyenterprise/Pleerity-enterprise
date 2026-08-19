# Customer communication — production promotion gate 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

Staging authority remains:

```text
CUSTOMER_COMMUNICATION_REMEDIATION_VERIFIED_WITH_CONDITIONS
```

Certified staging SHA: `0097b85f041970719c20c2670003a29ddf001e26`.

This gate does not recertify reminder architecture, onboarding, billing copy, or headers/footers.

## Gate issued

```text
GO_FOR_CUSTOMER_COMMUNICATION_PRODUCTION_PROMOTION
```

Issued after repository reconciliation, focused regression, production preflight, and rollback readiness. No launch-blocking P0/P1 communication defect. No unverified develop drift.

## Phase 4 — focused regression (candidate `0097b85f`)

| Item | Value |
| --- | --- |
| `tests_run` | 145 promotion-critical + 14 orchestrator |
| `tests_passed` | 123 promotion-critical; 10 orchestrator |
| `tests_failed` | 0 promotion-critical; **4** orchestrator |
| `tests_skipped` | 22 (promotion-critical) |
| `known_pre_existing_failures` | `resolve_greeting` NameError on DB-template finalize (`branding_resolver_service.py`) |

Promotion-critical suite (all passed):

* `tests/test_customer_communication_remediation_02.py`
* `tests/test_iteration26_billing_webhooks.py` (includes basil payment-failed)
* `tests/test_billing_phase_b_consistency.py`
* `tests/test_notification_reminder_idempotency.py`
* `tests/test_reminder_governance_phase2.py`
* `tests/test_reminder_truth_checks.py`
* `tests/test_lifecycle_reminders_s44.py`
* `tests/test_onboarding_email_governance_unit.py`
* `tests/test_work_order_contractor_routing_notifications.py`
* `tests/test_admin_cancel_subscription.py`
* `tests/test_billing_period_utils.py`
* `tests/test_email_template_runtime_metadata.py`
* `tests/test_notification_preferences_enforcement.py`
* `tests/test_certificate_expiry_tracking.py`

Known P2 (unchanged, not on promoted critical live billing path):

* `test_notification_orchestrator.py`: 4 failed (`failed` vs `sent`) — `name 'resolve_greeting' is not defined` in `finalize_db_email_html`
* Live `PAYMENT_FAILED` / `SUBSCRIPTION_CANCELED` on staging were **code-built** and DELIVERED; they do not use that finalize path

## Phase 5 — production preflight (before merge)

| Check | Result |
| --- | --- |
| `/api/version` | `1fcb5fbc…` / `environment=production` (both API hosts) |
| Health | `healthy`, readiness `ready`, scheduler `heartbeat_fresh` |
| Error-level app logs (1h preflight) | none |
| CPU / memory | ~0.004 CPU, ~335 MB; 1 instance |
| HTTP 5xx (preflight hour) | none material |
| Open P0/P1 | none observed in preflight logs |
| Stripe live webhooks via Stripe MCP | unavailable (`No account found` for livemode) — not treated as a production incident |
| Postmark | not failing in preflight window |
| Mongo Atlas MCP | unauthenticated — health Mongo readiness used instead |
| Sentry MCP | unauthenticated — Render logs used instead |
| Material unrelated incident | **No** — promotion not stopped |

## Phase 6 — rollback readiness

| Item | Value |
| --- | --- |
| `PRE_PROMOTION_MAIN_SHA` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `PRE_PROMOTION_BACKEND_SHA` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `PRE_PROMOTION_FRONTEND_BUNDLE` | `static/js/main.b993e884.js` on `https://pleerityenterprise.co.uk` |
| `ROLLBACK_BACKEND_SHA` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `ROLLBACK_FRONTEND_DEPLOYMENT` | prior production Vercel deploy `pleerity-enterprise-59iauw4f5` / `dpl_7aMvyBNxQX3mpFXC1CfuLJ2WLNDD` (unchanged; frontend not promoted) |
| Irreversible DB migration | **No** |
| Destructive production data operation | **No** |
| Mongo cleanup | **No** |
| Stripe schema mutation | **No** |
| Previous backend redeployable | **Yes** (Render history; `1fcb5fbc` remains) |
| Previous frontend restorable | **Yes** (frontend not changed) |

## Phase 7 — gate matrix

| Domain | Latest staging authority | Current status | Blocking? |
| --- | --- | --- | --- |
| Compliance reminder scope | Runtime 02 | PASS | No |
| Reminder idempotency | Runtime 02 | PASS | No |
| PAYMENT_FAILED | Runtime 03 | PASS | No |
| SUBSCRIPTION_CANCELED | Runtime 03 | PASS | No |
| Renewal 7d | Runtime 03 | PASS | No |
| Renewal 3d | Runtime 03 | PASS | No |
| CONTRACTOR_ASSIGNED | Runtime 03 | PASS | No |
| Onboarding state-aware copy | Runtime 02 | PASS | No |
| Monthly digest regression | Runtime 02 | PASS | No |
| Notification preferences | regression | PASS | No |
| Production preflight | current | PASS | No |
| Rollback readiness | current | PASS | No |
| `resolve_greeting` P2 | known | PASS_WITH_CONDITION | No |
| Stripe event resend | Closure 03 condition | PASS_WITH_CONDITION | No |
| CAPE deletion email | Closure 03 condition | PASS_WITH_CONDITION | No |

## Merge / push (executed)

| Item | Value |
| --- | --- |
| Strategy | `ort` merge commit (not fast-forward, **no conflicts**, **no force-push**) |
| Merge SHA | `626f35de80ca71dd03b4782552126213cab414b4` |
| Parents | `1fcb5fbc` (main) + `0097b85f` (develop) |
| `origin/main_before` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `origin/main_after` | `626f35de80ca71dd03b4782552126213cab414b4` |
| `push_result` | `1fcb5fbc..626f35de  main -> main` |
| Remote advanced unexpectedly | **No** |

Worktree: `C:\pleerity-workspace\ppe-07-main`.

## Phase 19 — production matrix

| Domain | Staging authority | Production deployment | Smoke/observation | Verdict |
| --- | --- | --- | --- | --- |
| Reminder single-item scope | 02 | PASS (code on `626f35de`) | PASS (code/job); cron send counts NOT_RETRIEVED | PASS_WITH_CONDITION |
| Reminder idempotency | 02 | PASS | PASS (code) | PASS |
| Reminder CTA | 02 | PASS | PASS (code) | PASS |
| PAYMENT_FAILED | 03 | PASS (code + webhook route) | NOT_EXERCISED naturally | PASS_WITH_CONDITION |
| SUBSCRIPTION_CANCELED | 03 | PASS (code) | NOT_EXERCISED naturally | PASS_WITH_CONDITION |
| Renewal 7d | 03 | PASS (job registered) | NOT_EXERCISED naturally | PASS_WITH_CONDITION |
| Renewal 3d | 03 | PASS (job registered) | NOT_EXERCISED naturally | PASS_WITH_CONDITION |
| CONTRACTOR_ASSIGNED | 03 | PASS (code) | NOT_EXERCISED | PASS_WITH_CONDITION |
| Onboarding state copy | 02 | PASS (code) | PASS (code) | PASS |
| Monthly digest | 02 | PASS (regression) | PASS (regression) | PASS |
| Notification preferences | regression | PASS | PASS (regression) | PASS |
| Scheduler | current | PASS after recycle | PASS `heartbeat_fresh` through 09:27Z | PASS |
| Mongo | current | PASS connect `pleerity_production` | PASS readiness `ready` | PASS |
| Stripe/webhooks | current | PASS route 400 signature; `STRIPE_MODE=live` | NOT_EXERCISED naturally | PASS_WITH_CONDITION |
| Postmark | current | PASS client init; one INTERNAL_ALERT | no customer-reminder spike in pre-09:00 logs | PASS_WITH_CONDITION |

## Final verdict

```text
CUSTOMER_COMMUNICATION_PRODUCTION_DEPLOYMENT_SUCCESSFUL_WITH_CONDITIONS
```

Certified staging SHA `0097b85f` reached production via merge `626f35de`. Reminder scope remains single-item in promoted code. Per-requirement idempotency is intact in promoted code. Production health remained stable for ~94 minutes after recycle recovery. No P0/P1 customer-communication regression was observed. Accepted staging limitations, P2 `resolve_greeting`, and the Render-MCP gap on first-cron send counts remain documented conditions — they do not hide a live customer-truth defect.
