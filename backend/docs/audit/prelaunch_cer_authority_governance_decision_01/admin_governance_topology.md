# Admin governance topology

**Programme:** PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01

## Queue topology (target state)

```
┌─────────────────────────────────────────────────────────────┐
│ PLATFORM ADMIN (Pleerity ops)                                │
├─────────────────────────────────────────────────────────────┤
│ 1. Document verification queue (EXISTING)                    │
│    - documents.status=UPLOADED                               │
│    - Family D only                                           │
│ 2. Escalation review queue (NEW — design only)               │
│    - manual_review_flag, mismatch, abuse, repeat rejection   │
│    - Family E overlay on any type                            │
│ 3. Oversight sample queue (OPTIONAL — low volume)            │
│    - Family C flagged for sample only                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ORGANISATION ADMIN (client portal)                           │
├─────────────────────────────────────────────────────────────┤
│ Org compliance review queue (NEW UX — design only)             │
│    - CER PENDING_REVIEW where governance_family=B            │
│    - Uses existing verify API                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ NO QUEUE (by design)                                         │
├─────────────────────────────────────────────────────────────┤
│ Family A default path — automated guard closure              │
│ Family C default path — follow-up driven, not review queue   │
└─────────────────────────────────────────────────────────────┘
```

## Anti-patterns prevented

- **Fake pending queues:** No UI "awaiting review" without queue enrollment.
- **Review overload:** A and C default paths exclude platform human review.
- **Invisible workflows:** Every queued item exposes queue_owner in admin/org UI.
- **Operational deadlocks:** Follow-up states route to landlord action, not orphan review.

## Current vs target gap (from prior audit)

| Queue | Current | Target |
|-------|---------|--------|
| Platform doc verify | Exists | Keep |
| Platform CER review | Missing (drift) | Only E + optional C sample |
| Org CER review | API only, no queue UI | Org queue for family B |
| Escalation | Ad hoc flags | Dedicated escalation queue |
