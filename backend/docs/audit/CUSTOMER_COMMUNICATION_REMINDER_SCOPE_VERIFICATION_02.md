# Reminder scope verification 02

Staging SHA: `a9a2efd329f827f335ca2d759cfa2cf0fb883302`  
Fixture: `nancy@yopmail.com` / `6fd5ac4c-3fd4-4112-ade7-156977deb49f` (plus `agent@yopmail.com` where the property is agent-copied).

## One requirement per email

Three independently scoped emails were accepted and **DELIVERED** by Postmark on 2026-08-18 (after SHA `a9a2efd3`):

| Requirement | Subject | Idempotency suffix (shared per requirement, distinct per recipient) | CTA | Property |
| --- | --- | --- | --- | --- |
| EICR upcoming | Your Electrical Installation Condition Report (EICR) expires in **4 days** | `..._24237401d1ce52db` | Review EICR | `9786b4ea-…?requirement_id=9d3ad68d-…` |
| Gas Safety overdue | Gas Safety Certificate is overdue | `..._d65c8d329ac60a25` | Review Gas Safety Certificate | `9786b4ea-…?requirement_id=bb32fac0-…` |
| HMO fire evidence overdue | HMO fire safety management evidence … **is overdue** | `..._27e4bb733f01ce4a` | Upload HMO fire safety evidence | `0a6f0874-…?requirement_id=68622908-…` |

Nancy and agent each received the same requirement-scoped subject. Bodies do not mix siblings (HMO mail does not name Gas Safety / EICR as a second brief).

## Two-unrelated same-day proof

```text
scheduler (CLIENT-scoped daily_reminders)
→ independent eligibility (HMO fire evidence vs Gas Safety)
→ independent idempotency keys (different fingerprints)
→ independent renders / message_logs
→ independent Postmark MessageIDs
→ DELIVERED
```

Second `daily_reminders` run on the same client/window: **0 new emails** (`Daily reminders: no reminders due`, `COOLDOWN_ACTIVE`).

## Copy defects A–E (live + unit)

| Defect | Before (Audit 01) | After |
| --- | --- | --- |
| A overdue “before expiry” | Present | Absent in unit + live overdue subjects |
| B due-on vs overdue | Intro could disagree | Overdue state passed into renderer |
| C “registration registration” | Present | Unit: “Scottish landlord registration is overdue” |
| D HMO as certificate | Present | Live subject uses **evidence** + CTA **Upload** |
| E generic “Certificate” fallback | Present | Fallback is “Compliance requirement” |

## Scottish landlord registration residual

Nancy has `scotland_landlord_registration` overdue on property `cd7c9bbc-…`, but that row was **not in the 12-item client runtime surface** evaluated by the job (surface/calendar filter). Live pair used Gas Safety + HMO fire evidence from the evaluated set. Unit fixtures still cover Scottish landlord isolation.

## Cooldown / amplification control

Cert temporarily marked non-target Nancy `reminder_item_state` rows ineligible for 30 days so the job would not fan out ~12 emails. Production behaviour remains: every **evaluated eligible** requirement may send, subject to per-requirement cooldown (default 24h) and existing preference/quiet-hour gates.

## Aggregates preserved

`monthly_digest` CLIENT-scoped run returned HTTP 200. Renderer tests still treat `MONTHLY_DIGEST` as summary-shaped. Scheduled reports were not redesigned.
