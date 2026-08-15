# Commercial Controls — Email Delivery

**Audit ID:** `COMMERCIAL-CONTROLS-END-TO-END-REMEDIATION-01`  
**Document:** `COMMERCIAL_CONTROLS_EMAIL_DELIVERY_01.md`  
**Date:** 2026-08-15  
**Runtime status:** **UNVERIFIED** (staging admin 423; no Postmark capture this run)

## Path

```text
execute send_customer_email=true
  → send_commercial_continuity_email
  → notification_orchestrator.send
       template_key=ADMIN_MANUAL
       event_type=commercial_entitlement_continuity
  → message_logs (idempotency_key)
  → Postmark
```

Recipient: `client.email` or `client.contact_email`. Missing recipient → `outcome=no_recipient`, governance `customer_notification_status=skipped`.

## Checkbox contract

| Checkbox | Intended | Code |
| --- | --- | --- |
| Unchecked | No continuity email | Insert `customer_notification_status=skipped`; send block not entered |
| Checked | Exactly one send for that governance row | Idempotency `commercial_entitlement_{client_id}_{governance_id}_{action}` |

Previously the key included `uuid4()`, so a retry could send duplicates. That is fixed in source, not deployed.

## Template / content

HTML is built in `build_commercial_continuity_email_html` (not a versioned Postmark template id). Subject varies by action. Body uses `impact_preview.customer_impact` plus effective access reason and expiry date **from the persisted governance row**.

Customer-safe constraints from Phase 2C still apply: no `pause_collection`, no Stripe jargon in `customer_impact`.

### Truthfulness issue (authority)

Suspend billing customer line remains: “Billing for your account is temporarily paused while we review your request.”

v1 does **not** pause Stripe collection. Operator copy was corrected; customer copy was **not** silently rewritten. Decision required: pause Stripe, or stop claiming collection is paused.

## Failure policy

Email is **not** in the commercial transaction. Timeout/exception → exception remains; `customer_notification_status=failed`; UI toast warning. Retry is via existing `notification_retry_worker`, not a parallel mechanism.

## Provider verification this exercise

| Field | Value |
| --- | --- |
| Internal notification ID | not captured |
| Template/version | `ADMIN_MANUAL` / inline HTML |
| Recipient | not captured |
| Postmark message ID | not captured |
| Provider acceptance | not captured |
| Delivery/bounce | not captured |

Do not label queued/orchestrator `sent` as **DELIVERED**.

## Prior evidence

Phase 2C closeout exercised execute with `send_customer_email: False`. Continuity HTML unit tests exist. That is not Postmark delivery proof.
