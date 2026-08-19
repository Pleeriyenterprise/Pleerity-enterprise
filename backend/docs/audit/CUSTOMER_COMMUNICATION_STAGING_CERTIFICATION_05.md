# Staging certification 05

| Item | Value |
| --- | --- |
| Implementation SHA | `2b2bae4c` |
| Staging API | `https://pleerity-enterprise.onrender.com` |
| Production `/api/version` | `626f35de…` / `environment=production` (untouched) |
| Main merged | No |
| Recipients | yopmail only if live sends are performed |

## Deploy observation

After `develop` push (`9ca92228` + `c68e4b5e` + `8cafa61d` + `2b2bae4c`), GitHub showed Vercel Preview success. Render MCP was **unavailable** (timeout / still loading; `mcp_auth` also timed out). Staging `/api/version` continued to report `0097b85f` / `environment=staging` while remaining healthy.

```text
STAGING_RUNTIME_SHA = pending (last observed 0097b85f)
DEPLOYMENT_ID = not retrieved (Render MCP unavailable)
```

Runtime proofs that require `2b2bae4c` on the staging process **cannot be certified** until `/api/version` matches.

## CTA end-to-end (code + prior 02/03; not a new full click-through)

| Template | CTA | Destination | Correct resource | Action available | Action completes | Negative path | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| COMPLIANCE_EXPIRY_REMINDER | Requirement-specific | `/properties/{id}?requirement_id=` | Yes when property-bound | Upload/review on property | 02 staging | Cooldown | ACTION_RESOLVES_END_TO_END |
| COMPLIANCE_EXPIRY_REMINDER (no property) | List | `/requirements?status=` | List not one item | List only | — | — | GENERIC_FALLBACK |
| COMPLIANCE_ALERT | Open portal to review | Requirements overdue/due-soon or dashboard | Property batch not one requirement | Review list | Not re-clicked in 05 | — | DESTINATION_ONLY |
| PAYMENT_FAILED | Update billing details | `/settings/billing` | Billing | Update PM | 03 | — | DESTINATION_ONLY (no live Stripe mutation in 05) |
| SUBSCRIPTION_CANCELED / 7d / 3d | Open Billing | `/settings/billing` | Billing | View | 03 | — | DESTINATION_ONLY |
| WELCOME / PASSWORD_RESET / ACTIVATION | Token | `/set-password` | Token | Set password | Prior | used/expired fail safely (prior) | ACTION_RESOLVES_END_TO_END |
| TENANT_INVITE | Set Up Your Access | setup token | Tenant | Set password | Prior | 7-day expiry copy | ACTION_RESOLVES_END_TO_END |
| CONTRACTOR_ASSIGNED | Open secure job link | `/job?token=` | Work order | Contractor action | 03 | — | ACTION_RESOLVES_END_TO_END |
| SUPPORT_TICKET_CONFIRMATION | Open Help | `/help` | Help Centre, not ticket id | Chat / articles | Auth required | No `/support` ticket route | DESTINATION_ONLY |
| ONBOARDING_DAY2–6 | Properties / dashboard / settings | Matching suffix | State-adapted | Yes if logged in | Unit | — | DESTINATION_ONLY |
| ORDER_INFO_REQUEST / ORDER_DOCUMENTS_READY / CLIENT_QUOTE_REVIEW_REQUIRED | Order/job links | Existing order/job routes | When ids present | Intended action | Not re-run in 05 | — | NOT_EXERCISED in 05 (carry-forward) |
| MONTHLY_DIGEST | Review portfolio | Portal | Aggregate | View | Unchanged | — | DESTINATION_ONLY |

```text
CTA_END_TO_END_VERIFIED_WITH_GAPS
```

Gaps: no new token negative-path lab in 05; support is not ticket-specific; COMPLIANCE_ALERT is a list/dashboard landing; billing not live-mutated; staging runtime SHA not yet `2b2bae4c`.
