# Operational Timeline Model

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Event sources (merged, sorted by timestamp)

| Source collection | event_kind | Examples |
|-------------------|------------|----------|
| `account_lifecycle_events` | lifecycle | LifecycleStateChanged, PaymentRecovered |
| `stripe_events` | webhook | invoice.payment_succeeded, customer.subscription.updated |
| `audit_logs` | audit | LIFECYCLE_OPS_*, BILLING, SUBSCRIPTION |
| `message_logs` | communication | Recovery email, renewal reminder |

## Event shape

```json
{
  "timestamp": "ISO-8601",
  "event_kind": "lifecycle|webhook|audit|communication",
  "title": "human-readable",
  "source": "service or stripe",
  "authority": "governing authority name",
  "result": "outcome",
  "duration_ms": 123.4,
  "audit_ref": "optional action_type",
  "metadata": {}
}
```

## Distinction from audit tab

Operational timeline **curates** cross-domain operational events. Activity & Audit tab retains full searchable audit history.

## API field

`snapshot.operational_timeline` (max 40 events)
