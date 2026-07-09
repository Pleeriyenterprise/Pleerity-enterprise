# Communication Model

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Sources

1. **Runtime Contract** `communication_policy` — channel suppress/allow  
2. **Communication Authority** — template eligibility samples (read-only evaluate)  
3. **message_logs** — recent sent/skipped/failed messages  

## Template samples evaluated (no send)

- SUBSCRIPTION_GRACE_REMINDER (recovery / grace)  
- SUBSCRIPTION_RENEWAL_7D / 3D (renewal reminders)  

Each returns: allowed, suppressed, suppression_reason, channel_policy_key.

## Displayed fields

- Last communication timestamp  
- Suppressed channels (from policy)  
- Recent messages (template_key, channel, status — no body)  
- notification_eligibility_note  

## API field

`snapshot.communications`

Does not duplicate Automation Centre message log search — provides per-customer operational context only.
