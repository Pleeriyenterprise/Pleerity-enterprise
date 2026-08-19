# Registry reconciliation 05

Objective: live customer communications have known event / category / template authority. Not aesthetic perfection. No live key renamed (message logs / preferences depend on them).

## lifecycle_status added (identifiers preserved)

| Event id | Status | Notes |
| --- | --- | --- |
| RENEWAL_REMINDER | LEGACY_ALIAS | Live: SUBSCRIPTION_RENEWAL_REMINDER_7D / _3D |
| DOCUMENT_PACK_DELIVERY | SUPERSEDED | Live: ORDER_DOCUMENTS_READY (maps to ORDER_DELIVERED key historically) |
| INVOICE_AVAILABLE | NOT_IMPLEMENTED | No send path |
| DOCUMENT_MISSING_ALERT | NOT_IMPLEMENTED | No send path |
| PASSWORD_CHANGED_CONFIRMATION | UNKNOWN_RUNTIME | No proven live sender |
| SUPPORT_TICKET_UPDATED | NOT_IMPLEMENTED | |
| SUPPORT_TICKET_RESOLVED | NOT_IMPLEMENTED | |

## Classification (questionable keys)

| Key | Class |
| --- | --- |
| PAYMENT_FAILED, SUBSCRIPTION_RENEWAL_REMINDER_7D/3D, COMPLIANCE_EXPIRY_REMINDER, COMPLIANCE_ALERT, TENANT_INVITE, SUPPORT_TICKET_CONFIRMATION, onboarding Day0–7 | ACTIVE |
| RENEWAL_REMINDER | LEGACY_BUT_REACHABLE as registry id only |
| ORDER_DELIVERED / DOCUMENT_PACK_DELIVERY | SUPERSEDED |
| INVOICE_AVAILABLE, DOCUMENT_MISSING_ALERT, FEATURE_ANNOUNCEMENT, PRODUCT_UPDATE, COMPLIANCE_SCORE_UPDATE | DEAD / NOT_IMPLEMENTED — **not deleted** |
| ACCESS_GRANTED / ACCESS_REVOKED | NOT_IMPLEMENTED — not deleted |

No destructive removal. Uncertainty → deprecation notes.

## Live sends vs registry

Orchestrator `template_key` remains the send authority. Registry event ids are documentation + lookup. Duplicate semantic names (CERTIFICATE_EXPIRY_REMINDER vs CERTIFICATE_OVERDUE) both map to COMPLIANCE_EXPIRY_REMINDER — preserved as aliases, not merged.
