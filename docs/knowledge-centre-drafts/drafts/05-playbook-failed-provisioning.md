---
title: Failed Provisioning Recovery
slug: playbook-failed-provisioning
audience: ADMIN
category_id: operations-playbooks
module: Provisioning
excerpt: "What to do when a client's provisioning has failed or is stuck: how to check status, when to resend activation, and when to escalate."
tags: playbook, provisioning, onboarding, recovery, failure
status: draft
---

# Failed Provisioning Recovery (Playbook)

**Audience:** ADMIN / STAFF  
**Category:** Operations Playbooks  
**Module:** Provisioning  
**Summary:** What to do when a client’s provisioning (post-payment setup) has failed or is stuck: how to check status, when to resend activation, and when to escalate.

---

## Purpose

After payment, the system provisions the client (e.g. creates tenant, sends activation email). Sometimes provisioning fails or the client never receives the activation email. This playbook gives a consistent procedure to diagnose and recover (e.g. resend activation, retry provisioning) or escalate to engineering.

---

## When to use this guide

- A client reports they paid but cannot log in or never received a “set your password” or activation email.
- The onboarding or setup status page shows “failed” or “error” for that client.
- Support or ops need to decide: resend activation, retry provisioning, or escalate.

---

## Steps

1. **Identify the client** — Use admin search or client list to open the client record. Note client_id and email.
2. **Check onboarding / setup status** — In the client record or via the portal setup-status API (if you have a tool or internal page), confirm: **onboarding_status** (e.g. PROVISIONED, PROVISIONING, FAILED) and **password_status** (e.g. NOT_SET, SET). If status is FAILED or stuck in PROVISIONING for a long time, note the state.
3. **Check payment and provisioning state** — Ensure payment was confirmed (e.g. subscription_status or webhook). If payment is pending or unpaid, provisioning may not have started; resolve payment first. If payment is confirmed and status is FAILED, provisioning may have failed; check logs or job status if available.
4. **Resend activation (if appropriate)** — If the client never received the activation email but provisioning completed, use the **Resend activation** (or equivalent) flow. The portal API is `POST /api/portal/resend-activation`. Respect rate limits: **max 3 per hour per client**. Tell the client to check spam and to use the new link within the validity period.
5. **Retry provisioning** — For failed or stuck provisioning, use **Re-run Provisioning** in the admin UI (e.g. from Billing or the client context). The backend endpoint is `POST /api/admin/billing/clients/{client_id}/force-provision`. Use after confirming payment and that the failure was transient. Document the result.
6. **Escalate** — If resend and retry do not work, or if the client is stuck in PROVISIONING for more than a defined threshold (e.g. 24 hours), escalate to engineering with: client_id, email, onboarding_status, payment state, and any error message or log snippet. Do not promise a fix time until engineering confirms.

---

## What happens next

- After resend, the client receives a new activation email (if the backend sent it). They set their password and can log in.
- After a successful retry, onboarding_status should move to PROVISIONED; then the client can set password if not already set.
- Escalation should result in a ticket or incident; track until the client can log in or is clearly informed of next steps.

---

## Common mistakes / troubleshooting

- **Resending too often:** Respect rate limits to avoid blocking or triggering abuse controls.
- **Assuming “no email” = provisioning failed:** Sometimes the email was sent but filtered or delayed; check delivery or logs before retrying provisioning.
- **Wrong client:** Confirm client_id and email before resend or retry to avoid activating the wrong account.

---

## Related guides

- Reviewing Onboarding Status  
- How Provisioning Works  
- Admin Console Overview  
- Login Failure Investigation (playbook)  

---

**Verification status:** Draft. API paths and rate limits verified against codebase. Confirm where **Re-run Provisioning** is exposed in your admin UI (e.g. Billing vs client detail).
