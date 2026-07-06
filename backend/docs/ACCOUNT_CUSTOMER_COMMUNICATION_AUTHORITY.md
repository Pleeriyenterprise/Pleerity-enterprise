# Account Customer Communication Authority (ILP-8)

**Programme:** ILP-8-CUSTOMER-COMMUNICATIONS-AND-REACTIVATION-01  
**Module:** `services/account_customer_communication_authority.py`  
**Policy version:** `account_customer_communication_v1`  
**Branch:** `develop`

---

## Purpose

Single decision point for **account-level** customer communication:

- Eligibility and channel selection
- Lifecycle-aware message, severity, tone, CTA
- Recovery journey reference
- Central suppression
- Template lifecycle placeholders

Consumes Runtime Contract `communication_policy` and `customer_experience` only.

**Distinct from** `lifecycle_communication/` (requirement-level compliance wording — LCA programme).

---

## Authority chain

```
Runtime Contract (communication_policy, customer_experience)
        ↓
Customer Communication Authority (ILP-8)
        ↓
Notification orchestrator / template context / frontend metadata
        ↓
Email Presentation Authority (layout unchanged)
```

---

## API

| Function | Use |
|----------|-----|
| `CustomerCommunicationAuthority.from_contract()` | Sync evaluation from contract |
| `evaluate_customer_communication()` | Async — loads live contract |
| `enrich_context_with_lifecycle_placeholders()` | Template `{{ lifecycle_* }}` tokens |
| `log_communication_decision()` | Observability |

---

## Decision fields

| Field | Source |
|-------|--------|
| `allowed` / `suppressed` | `communication_policy` + suppression rules |
| `channel_policy_key` | `email_operational`, `email_billing`, `sms`, `portal_notifications` |
| `message`, `cta_*` | `customer_experience` |
| `template_family` | `communication_policy.template_family` |
| `recovery_journey_id` | Derived from lifecycle + portal mode |
| `template_context` | Placeholders for templates |

---

## Suppression rules (central)

| Rule | Condition |
|------|-----------|
| Billing recovery spam guard | Operational email blocked when `portal_mode` is billing recovery |
| Suspended operational block | Operational email blocked when suspended |
| Archived / deleted | Operational comms blocked; billing may remain per policy |
| Policy denial | Channel key false in `communication_policy` |

---

## Migration

| Consumer | Status |
|----------|--------|
| `notification_orchestrator._apply_gating` | ✓ subscription-gated sends |
| Background jobs (ILP-6) | Unchanged — scheduling authority separate |
| Requirement LCA | Unchanged — requirement-level copy |

---

## Related

- `ACCOUNT_LIFECYCLE_COMMUNICATION_MATRIX.md`
- `ACCOUNT_LIFECYCLE_REACTIVATION_AUTHORITY.md` (implementation module)
- `ACCOUNT_REACTIVATION_AUTHORITY.md` (governance catalogue)

---

## Tests

```bash
pytest tests/test_account_customer_communication_authority.py -q
```
