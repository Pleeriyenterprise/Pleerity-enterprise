# Staging runtime certification 02

| Item | Value |
| --- | --- |
| Staging API | `https://pleerity-enterprise.onrender.com` |
| `/api/version` at cert | `a9a2efd329f827f335ca2d759cfa2cf0fb883302` / `environment=staging` |
| Render deploy | `dep-da2afh6gekts7392qjrg` live |
| Production `/api/version` | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` / `production` (untouched) |
| Main merged | No |
| Recipients | yopmail only (`nancy@`, `agent@`, `elena@`) |

PASS is not HTTP 200 or Postmark accept alone. Where claimed DELIVERED, `message_logs.status` is **DELIVERED** (webhook-backed), distinct from SENT.

## Critical path captures

### Overdue HMO fire evidence

- template_key: `COMPLIANCE_EXPIRY_REMINDER`
- message_id (nancy): `511fc025-c444-4d35-9fea-46c4949963ed`
- idempotency_key: `…_nancy_at_yopmail.com_27e4bb733f01ce4a`
- provider_message_id: `28e29f81-e2ee-46d2-b012-883f98eaaed4`
- provider: accepted then **DELIVERED** `2026-08-18T19:04:24Z`
- subject / CTA: evidence overdue / Upload HMO fire safety evidence

### Overdue Gas Safety

- message_id (nancy): present in client logs as DELIVERED
- idempotency_key: `…_d65c8d329ac60a25`
- subject: Gas Safety Certificate is overdue

### Upcoming EICR

- message_id (nancy): `eca6255a-ca02-45d3-9ab6-9775680932fc`
- provider_message_id: `9cde6d88-e3c2-4b1f-b713-7990cd529dd8`
- **DELIVERED** `2026-08-18T18:54:09Z`
- subject: expires in 4 days

### Duplicate scheduler

Second CLIENT `daily_reminders` after each send window: count **0**, `COOLDOWN_ACTIVE`.

### Onboarding

See ONBOARDING_STATE_VERIFICATION_02. Day 1 DELIVERED.

### PAYMENT_FAILED / cancellation / CONTRACTOR_ASSIGNED

Not live-sent. See billing and contractor verification docs.

### Postmark (this cert, yopmail)

Messages **DELIVERED** (reminders + onboarding Day 1): at least 7 email rows (3 requirements × 2 recipients, minus any capture gaps, plus 1 onboarding). SMS attempts `BLOCKED_PLAN_GATE` (not counted as customer email). No failed email sends observed on these paths.
