# Customer Health Model

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Overall states

| Overall | Meaning |
|---------|---------|
| **Healthy** | All indicators `healthy` |
| **Attention Required** | Any `warning` or `unknown` |
| **Critical** | Any `critical` |

## Indicators (authoritative derivation)

| Indicator | Healthy | Warning | Critical | Unknown |
|-----------|---------|---------|----------|---------|
| lifecycle | ACTIVE | GRACE, CANCELLATION_SCHEDULED, transition pending | SUSPENDED, EXPIRED | other |
| billing | mirror + sub, no flags | missing stripe_mode, past period | reconciliation needed, stale cancel mirror | no Stripe |
| runtime_contract | resolved, no warnings | contract warnings | — | no version |
| capabilities | matrix present | many DENY (restricted state) | — | empty |
| stripe | customer + sub | customer only | — | none |
| webhook_processing | recent activity | sub but no webhook ts | failed events > 0 | — |
| reconciliation | no flags | stale cancel mirror | reconciliation_needed | — |
| background_jobs | all CONTINUE sample | paused/skipped | terminated | — |
| communications | recent message | multiple suppressed channels | — | no messages |
| data_integrity | no drift flags | legacy drift flags | — | — |

Health is **never invented** — each indicator includes an `explanation` string citing the source fact.

## API field

`snapshot.customer_health.overall` + `snapshot.customer_health.indicators`
