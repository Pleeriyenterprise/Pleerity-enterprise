# Customer communication remediation implementation 02

Programme: `CUSTOMER-COMMUNICATION-QUALITY-REMEDIATION-02`  
Implementation / staging-cert SHA: `a9a2efd329f827f335ca2d759cfa2cf0fb883302`  
Branch: `develop` (not merged to `main`)  
Production touched: **No**

## Governing contract implemented

```text
ONE CUSTOMER MESSAGE = ONE PRIMARY EVENT = ONE PRIMARY BRIEF = ONE PRIMARY CTA
```

Daily compliance reminders send **one independently governed email per eligible requirement**.  
`MONTHLY_DIGEST` and `SCHEDULED_REPORT` remain intentional aggregates.

## Failure semantics (daily reminders)

One send failure does **not** abort remaining eligible requirements.  
Cooldown (`mark_requirement_reminder_sent`) is recorded only after a successful send for **that** requirement.  
SMS remains a same-day aggregate for the client (not split).  
Idempotency is per requirement / property / due date / lifecycle window / recipient / template family — not display names.

## Authority chosen per remediated family

| Communication | Authority |
| --- | --- |
| Daily compliance / lifecycle reminders | `CANONICAL_CODE_BUILT` (lifecycle resolver + EmailService reminder HTML) |
| `PAYMENT_FAILED` | `CANONICAL_CODE_BUILT` (unconditional; never DB-missing generic fallback) |
| `SUBSCRIPTION_CANCELED` | `CANONICAL_CODE_BUILT` using Stripe period / cancel mode + platform entitlement |
| Subscription 7d / 3d renewal | `CANONICAL_CODE_BUILT`; subject uses calculated `days_until` |
| Onboarding Day 0–7 | `HYBRID_WITH_LOCKED_FALLBACK` (code-built body/CTA/subject adapted from existing onboarding state) |
| `CONTRACTOR_ASSIGNED` | `CANONICAL_CODE_BUILT` HTML via `message` (not unused `body`) |
| `MONTHLY_DIGEST` / `SCHEDULED_REPORT` | unchanged aggregate renderers |

## Code touchpoints

- `backend/services/jobs.py` — per-requirement loop, overdue flag, CTA, subjects
- `backend/services/notification_send_idempotency.py` — `daily_compliance_reminder_item_idempotency_key`
- `backend/lifecycle_communication/{context,copy,resolver}.py` — family language, no doubled “registration”, overdue intro
- `backend/services/email_service.py` — single-item reminder HTML; payment-failed copy; onboarding state/jurisdiction
- `backend/services/subscription_lifecycle_service.py` — cancellation access wording; renewal subjects
- `backend/services/stripe_webhook_service.py` — canceled + payment-failed context
- `backend/services/notification_orchestrator.py` — unconditional code-built billing; contractor layout uses `message`
- `backend/services/maintenance_service.py` — assignment HTML in `message`
- `backend/services/onboarding_sequence_service.py` / `onboarding_state_checker.py` — state-aware subjects/CTAs + jurisdiction flags
- `backend/utils/app_urls.py` — `client_portal_requirement_item_url` (existing property deep-link; no invented routes)

## COMPLIANCE_ALERT (not removed)

| Surface | Purpose |
| --- | --- |
| Daily reminder | Per-requirement due/overdue **window** |
| `COMPLIANCE_ALERT` | Property **RAG status degradation** |
| `MONTHLY_DIGEST` | Intentional monthly **summary** |

No extra suppression layer was added. Primary events differ. Residual collision risk if RAG mail and daily reminder describe the same underlying overdue item on the same day is **P2** for programme 03 unless product later requires window-level suppression.

## CTA routing limitation

Requirement-specific reminders use `/properties/{propertyId}?requirement_id=` when property-bound.  
There is no safe `/requirements/{id}` route. Account-level requirements still use the existing overdue/due-soon list.
