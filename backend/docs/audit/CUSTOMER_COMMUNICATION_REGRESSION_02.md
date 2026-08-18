# Communication regression 02

Local tests (implementation): `tests/test_customer_communication_remediation_02.py` — **18 passed**.

Also updated: reminder idempotency, email template runtime metadata, lifecycle S44, reminder governance phase 2, certificate expiry tracking, notification preferences, reminder truth checks.

## Surfaces

| Surface | Result |
| --- | --- |
| Notification orchestrator | Payment-failed / canceled locked code-built; contractor layout uses `message`. Pre-existing `resolve_greeting` NameError in some DB-finalize tests remains (P2; code-built billing bypasses that path). |
| Message-log idempotency | Per-requirement keys; second scheduler run 0 duplicates on staging. |
| Compliance scheduler | CLIENT-scoped live on Nancy. |
| Lifecycle reminder resolver | Unit: family subjects, overdue language. |
| Monthly digest | CLIENT job 200; unit aggregate HTML. |
| Scheduled reports | Not re-rendered live; renderer unchanged. |
| Billing webhooks | Code paths unit-tested; **no live Stripe event**. |
| Subscription lifecycle 7d/3d | Unit subjects; live window not hit. |
| Onboarding sequence | Live Day 1 adapted; unit Day 0/7. |
| Contractor communications | Unit HTML; live assign blocked by eligibility. |
| Notification preferences | Preference tests still pass; SMS daily still batch. System-critical billing remains unconditional in orchestrator. |
| Email presentation registry | Header/footer untouched. |
| Postmark | DELIVERED on cert emails. |
| Customer portal CTA | Existing property `?requirement_id=` deep-link used. |

## Negative / concurrency (lab)

| Case | Evidence |
| --- | --- |
| Scheduler twice | Staging run2 = 0 sends |
| Webhook replay billing | Existing `{event_id}_PAYMENT_FAILED` / canceled keys; **not live-replayed** |
| Missing Stripe retry | Unit: no invented date |
| Missing period-end | Unit: safe wording |
| Disabled preference | Existing tests; billing not preference-gated |
| Unknown family | Resolver fallback; not “Certificate” |
| Provider timeout/rejection | Not injected on staging |

## P2/P3 deferred to programme 03

- Tenant RAG terminology
- Generic support acknowledgement
- Dead template keys / registry drift
- Emoji subject polish
- `resolve_greeting` NameError on some DB-template tests
- COMPLIANCE_ALERT vs daily reminder same-day overlap
- Scottish landlord not on Nancy runtime surface (filter, not copy)
- Onboarding Day 2+ England-centric education (P2)
