# Customer communication quality cleanup 05 — implementation

Programme: `CUSTOMER-COMMUNICATION-QUALITY-CLEANUP-05`  
Branch: `develop` (not merged to `main`)  
Production touched: **No**  
Implementation SHA: `2b2bae4c`

Previous programme closed as `CUSTOMER_COMMUNICATION_PRODUCTION_DEPLOYMENT_SUCCESSFUL_WITH_CONDITIONS` at production `626f35de` (certified staging `0097b85f`). This programme does not reopen P0/P1 architecture.

## Phase 0 — Production 04 evidence

```text
PRODUCTION_04_EVIDENCE_PRESERVED = TRUE
EVIDENCE_COMMIT_SHA = 9ca92228
UNRELATED_FILES_EXCLUDED = TRUE
```

04 evidence was committed separately from gallery/tmp dirt, then pushed with Cleanup 05 so staging was not restarted solely for documentation.

## Residual matrix (from 01–04; no new platform-wide audit)

| Finding | Previous | Revalidation |
| --- | --- | --- |
| `resolve_greeting` NameError | P2 | **Send-blocker on DB-fragment finalize**. Missing import in `finalize_db_email_html`. Code-built billing/reminders were already healthy. Fixed in this programme; not treated as a new billing-truth P0. |
| COMPLIANCE_ALERT vs daily reminder | P2 | Runtime reachable. Distinct roles remain. Same-day duplicate intent when daily reminders are on **and** exactly one contributing requirement caused the RAG change. |
| Tenant RAG terminology | P2 | `TENANT_INVITE` listed GREEN/AMBER/RED. Package delivery did not dump RAG. |
| Support acknowledgement | P2 | Invented 24-hour SLA; generic notification risk. |
| Dead keys / registry drift | P3 | Documentation/lifecycle_status only. No live key renamed. |
| Onboarding Day 2+ | P2/P3 | England-centric / fear-based / overclaim. Reused existing state flags. |
| Emoji subjects | P3 | Deferred. |

## Fix summary

| Area | Change |
| --- | --- |
| Greeting | Import `resolve_greeting` / `strip_embedded_greetings` in `finalize_db_email_html`. Canonical greeting authority preserved. |
| Collision | `should_suppress_compliance_alert_for_property`: suppress email only when daily reminders enabled and exactly one contributing requirement. Status/webhooks still update. COMPLIANCE_ALERT not globally disabled. |
| Tenant / alert copy | Customer-facing labels: In order / Needs review / Needs attention. Scoring unchanged. |
| Support | Received + ticket ref + next step + no invented SLA. CTA → authenticated `/help`. |
| Onboarding Day 2–6 | Jurisdiction-neutral, less fear/overclaim, CTA adapts to `has_added_property` / `monitoring_enabled`. Day 0/1/7 not reopened. |
| Registry | `lifecycle_status` on legacy/unimplemented ids only. |

## Not changed

One-requirement-per-email architecture, billing lifecycle authority, onboarding engine, Commercial Controls, Stranded Onboarding, global headers/footers.

## Severity note

`resolve_greeting` can prevent a customer DB-template send. It is a **path-specific send-blocker**, not a new P0 billing-truth defect. Cleanup 05 was the authorised fix. No separate `HIGHER_SEVERITY_DEFECT_DISCOVERED` stop was issued.
