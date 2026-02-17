# Notification Template Matrix

Mapping of `template_key` → channel, gating flags, and rate-limit behaviour.  
Source: `database._seed_notification_templates` (notification_templates collection).

| template_key | channel | requires_provisioned | requires_active_subscription | requires_entitlement_enabled | plan_required_feature_key | rate_limit_window_seconds |
|--------------|---------|----------------------|------------------------------|------------------------------|----------------------------|---------------------------|
| WELCOME_EMAIL | EMAIL | true | false | false | null | — |
| PASSWORD_RESET | EMAIL | true | false | false | null | — |
| COMPLIANCE_EXPIRY_REMINDER | EMAIL | true | true | true | null | — |
| SUBSCRIPTION_CONFIRMED | EMAIL | false | false | false | null | — |
| PAYMENT_FAILED | EMAIL | false | false | false | null | — |
| SUBSCRIPTION_CANCELED | EMAIL | false | false | false | null | — |
| MONTHLY_DIGEST | EMAIL | true | true | true | null | — |
| COMPLIANCE_EXPIRY_REMINDER_SMS | SMS | true | true | true | sms_reminders | — |
| PENDING_VERIFICATION_DIGEST | EMAIL | false | false | false | null | — |
| COMPLIANCE_ALERT | EMAIL | true | true | true | null | — |
| RENEWAL_REMINDER | EMAIL | true | true | true | null | — |
| SCHEDULED_REPORT | EMAIL | true | true | true | null | — |
| ADMIN_MANUAL | EMAIL | true | false | false | null | — |
| ADMIN_MANUAL_SMS | SMS | true | false | false | null | — |
| ADMIN_INVITE | EMAIL | false | false | false | null | — |
| ORDER_DELIVERED | EMAIL | true | true | true | null | — |
| ORDER_NOTIFICATION | EMAIL | true | true | true | null | — |
| AI_EXTRACTION_APPLIED | EMAIL | true | true | true | null | — |
| TENANT_INVITE | EMAIL | true | true | true | tenant_portal | — |
| CUSTOM_NOTIFICATION | EMAIL | true | false | false | null | — |
| SUPPORT_TICKET_CONFIRMATION | EMAIL | false | false | false | null | — |
| SUPPORT_INTERNAL_NOTIFICATION | EMAIL | false | false | false | null | — |
| LEAD_MANUAL_MESSAGE | EMAIL | false | false | false | null | — |
| LEAD_FOLLOWUP | EMAIL | false | false | false | null | — |
| LEAD_SLA_BREACH_ADMIN | EMAIL | false | false | false | null | — |
| LEAD_HIGH_INTENT_ADMIN | EMAIL | false | false | false | null | — |
| COMPLIANCE_SLA_ALERT | EMAIL | false | false | false | null | — |
| CLEARFORM_WELCOME | EMAIL | false | false | false | null | — |
| PARTNERSHIP_ACK | EMAIL | false | false | false | null | — |
| ENABLEMENT_DELIVERY | EMAIL | true | true | true | null | — |
| OTP_CODE_SMS | SMS | false | false | false | null | 600 (OTP window) |
| OPS_ALERT_NOTIFICATION_SPIKE | EMAIL | false | false | false | null | — |
| PROVISIONING_FAILED_ADMIN | EMAIL | false | false | false | null | — |
| STRIPE_WEBHOOK_FAILURE_ADMIN | EMAIL | false | false | false | null | — |

Notes:
- **rate_limit_window_seconds**: Optional per-template field; not stored in seed. OTP uses service-level OTP_SEND_LIMIT_WINDOW_SECONDS (default 1800). SMS reminder uses orchestrator 24h throttle for COMPLIANCE_EXPIRY_REMINDER_SMS.
- **Admin/ops templates** (OPS_ALERT_*, PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN, COMPLIANCE_SLA_ALERT): sent to OPS_ALERT_EMAIL or ADMIN_ALERT_EMAILS; client_id=None, recipient from context.
- **COMPLIANCE_EXPIRY_REMINDER_SMS**: only allowed when plan has `sms_reminders` (Pro); plus client sms_enabled and phone present.
