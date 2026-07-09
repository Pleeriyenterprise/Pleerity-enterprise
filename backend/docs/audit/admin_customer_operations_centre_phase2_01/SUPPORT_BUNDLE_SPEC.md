# Support Bundle Specification

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Action

`POST /api/admin/clients/{client_id}/lifecycle-operations/export-support-bundle`

Governance: `lifecycle_ops_export_support_bundle` (reason + confirmation, audited).

## Format

ZIP archive containing JSON files + README.txt.

## Contents

| File | Content |
|------|---------|
| README.txt | Client id, generated_at, usage note |
| customer_summary.json | id, email, name, plan |
| customer_health.json | health summary + indicators |
| lifecycle.json | lifecycle authority fields |
| billing.json | billing mirror (no secrets) |
| authority_chain.json | chain stages |
| runtime_diagnostics.json | diagnostics |
| capabilities.json | capability summary |
| webhook_diagnostics.json | webhook health + events |
| operational_timeline.json | merged timeline |
| background_processing.json | job samples |
| communications.json | comm state |
| recovery.json | recovery guidance |
| actions_eligibility.json | governed action eligibility |
| audit_timeline.json | recent lifecycle audit slice |

## Redaction

Keys matching password, secret, token, raw_minimal, api_key → `[REDACTED]`.

## Response

`Content-Type: application/zip`, `Content-Disposition: attachment`.

Audit metadata: `LIFECYCLE_OPS_EXPORT_SUPPORT_BUNDLE`, bundle_size_bytes, health_overall.
