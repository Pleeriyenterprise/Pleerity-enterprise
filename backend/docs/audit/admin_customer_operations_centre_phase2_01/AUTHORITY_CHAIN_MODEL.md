# Authority Chain Model

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Stages (ordered)

1. Stripe — Stripe API  
2. Billing mirror — `client_billing` sync (mirror labelled)  
3. Lifecycle resolver — `account_lifecycle_state_resolver`  
4. Runtime Contract — `account_lifecycle_runtime_contract`  
5. Capabilities — capability matrix  
6. Navigation — portal_mode  
7. Background policies — `account_background_runtime_authority`  
8. Communications — `account_customer_communication_authority`  
9. Customer experience — lifecycle response / CX copy  
10. Webhook processing — `stripe_webhook_service`  

## Per-stage status

| Status | Meaning |
|--------|---------|
| healthy | Stage converged |
| waiting | Policy pause / transition pending |
| drift_detected | Mirror or legacy drift |
| failed | Terminal failure (e.g. failed webhooks, terminated jobs) |
| unknown | Insufficient data |

## API field

`snapshot.authority_chain[]` — `{ stage, authority, status, explanation, mirror? }`

Drift visibility is the primary support goal — not a second resolver.
