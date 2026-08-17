# Commercial Controls — Postmark ACTIVE Suspend Billing 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Recipient:** lere@yopmail.com (staging-only)  
**Production Postmark / production recipients:** not used

Cancelled Suspend Billing delivery remains proven in 03 (`COMMERCIAL_CONTROLS_EMAIL_DELIVERY_03.md`, allison@yopmail.com, ADMIN_MANUAL DELIVERED). This note is the ACTIVE path only.

## Provider + platform log

| Field | Value |
| --- | --- |
| Template | `ADMIN_MANUAL` |
| Subject | Billing temporarily paused on your account |
| Recipient | lere@yopmail.com |
| Platform message id | `2c427fc9-5968-46ac-b3bf-9c2c42eb7be0` |
| Postmark / provider id | `c5493e21-3fd2-4c6b-ad05-41ecb8a8473b` |
| Provider acceptance | `sent` (`sent_at` 2026-08-15T20:43:09.944Z) |
| Delivery status | **DELIVERED** (`delivered_at` 2026-08-15T20:43:11Z) |
| Attempts | 1 |

Do not treat provider-accepted as delivered. This row has **delivered_at**.

## Inbox (separate from provider status)

Yopmail inbox lere@yopmail.com, 15 Aug 2026 21:43 BST (20:43 UTC), from Pleerity Enterprise `<no-reply@pleerityenterprise.co.uk>`.

Visible body:

> Billing collection is paused until 2026-08-15. You keep Portfolio plan access during this period. This does not change your underlying subscription status.
>
> Billing suspended pending review
>
> This arrangement is in place until **2026-08-15**.
>
> Your compliance records and evidence remain available…

## Content truth

| Claim | Present? |
| --- | --- |
| Billing suspension | yes (“collection is paused”) |
| Plan access | yes (“Portfolio plan access”) |
| Duration / end date | yes (until 2026-08-15; matches short-lived expiry) |
| No subscription cancellation | yes (“does not change your underlying subscription status”; no cancel language) |

## Verdict

```text
DELIVERED
```
