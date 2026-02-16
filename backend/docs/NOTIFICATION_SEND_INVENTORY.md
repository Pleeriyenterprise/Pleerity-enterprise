# Notification Send Inventory (Pre-Migration)

All outbound email/SMS must go through `NotificationOrchestrator`. This table lists every send path before migration.

| File | Function | Trigger/Event | Channel | Recipient type | Current send path | Proposed template_key | requires_provisioned | requires_active_subscription | requires_entitlement_enabled | plan_required_feature_key | Proposed idempotency_key formula |
|------|----------|---------------|---------|----------------|-------------------|------------------------|----------------------|---------------------------|------------------------------|----------------------------|----------------------------------|
| stripe_webhook_service.py | _handle_payment_failed | invoice.payment_failed | email | client | notification_orchestrator (done) | PAYMENT_FAILED | false | false | false | null | stripe_event_id + _PAYMENT_FAILED |
| stripe_webhook_service.py | _handle_checkout_completed | checkout.session.completed | email | client | notification_orchestrator (done) | SUBSCRIPTION_CONFIRMED | false | false | false | null | stripe_event_id + _SUBSCRIPTION_CONFIRMED |
| stripe_webhook_service.py | _handle_subscription_* | subscription.deleted | email | client | email_service.send_subscription_canceled_email | SUBSCRIPTION_CANCELED | false | false | false | null | stripe_event_id + _SUBSCRIPTION_CANCELED |
| provisioning_runner.py | _run_provisioning_job_locked | after PROVISIONING_COMPLETED | email | client | _send_password_setup_link → orchestrator (done) | WELCOME_EMAIL | true | false | false | null | job_id + _welcome |
| provisioning.py | _send_password_setup_link | token created | email | client | notification_orchestrator (done) | WELCOME_EMAIL | true | false | false | null | job_id + _welcome or caller-provided |
| admin.py | resend_password_setup | admin resend | email | client | notification_orchestrator (done) | WELCOME_EMAIL | true | false | false | null | client_id + WELCOME_EMAIL + token_id |
| admin_billing.py | resend_password_setup | admin resend (billing) | email | client | email_service.send_password_setup_email | WELCOME_EMAIL | true | false | false | null | client_id + WELCOME_EMAIL + token_id |
| jobs.py | _send_reminder_email | daily_reminders job | email | client | (audit only, no email_service call in current code) | COMPLIANCE_EXPIRY_REMINDER | true | true | true | null | client_id + COMPLIANCE_EXPIRY_REMINDER + YYYY-MM-DD |
| jobs.py | _maybe_send_reminder_sms | daily_reminders job | sms | client | sms_service.send_sms | COMPLIANCE_EXPIRY_REMINDER_SMS | true | true | true | sms_reminders | client_id + COMPLIANCE_EXPIRY_REMINDER_SMS + YYYY-MM-DD |
| jobs.py | _send_digest_email | monthly digest job | email | client | email_service.send_email(MONTHLY_DIGEST) | MONTHLY_DIGEST | true | true | true | null | client_id + MONTHLY_DIGEST + YYYY-MM-DD (period_end date) |
| jobs.py | send_pending_verification_digest | pending_verification_digest job | email | admin | email_service.send_email(PENDING_VERIFICATION_DIGEST) | PENDING_VERIFICATION_DIGEST | false | false | false | null | PENDING_VERIFICATION_DIGEST + YYYY-MM-DD + admin_email |
| jobs.py | check_compliance_status_changes | compliance status job | email | client | email_service.send_compliance_alert_email | COMPLIANCE_ALERT | true | true | true | null | client_id + COMPLIANCE_ALERT + property_ids_hash + date |
| jobs.py | send_renewal_reminders | renewal reminder job | email | client | email_service.send_renewal_reminder_email | RENEWAL_REMINDER | true | true | true | null | client_id + RENEWAL_REMINDER + period_end |
| jobs.py | process_scheduled_reports | scheduled_reports job | email | client | email_service.send_email(SCHEDULED_REPORT) | SCHEDULED_REPORT | true | true | true | null | schedule_id + SCHEDULED_REPORT + YYYY-MM-DD |
| admin.py | send_manual_email | admin manual email | email | client | email_service.send_email(ADMIN_MANUAL) | ADMIN_MANUAL | true | false | false | null | client_id + ADMIN_MANUAL + timestamp_minute or request_id |
| admin.py | send_manual_email (other) | admin send message | email | client | email_service.send_email | ADMIN_MANUAL | true | false | false | null | client_id + ADMIN_MANUAL + idempotency |
| admin.py | resend_admin_invite | admin resend invite | email | admin | email_service.send_admin_invite_email | ADMIN_INVITE | false | false | false | null | portal_user_id + ADMIN_INVITE |
| admin.py | (invite flow) | admin invite | email | admin | email_service.send_admin_invite_email | ADMIN_INVITE | false | false | false | null | portal_user_id + ADMIN_INVITE |
| owner_bootstrap.py | (bootstrap) | owner creation | email | admin | email_service.send_admin_invite_email | ADMIN_INVITE | false | false | false | null | portal_user_id + ADMIN_INVITE |
| admin_billing.py | (billing message) | admin message to client | email | client | email_service.send_admin_message | ADMIN_MANUAL | true | false | false | null | client_id + ADMIN_MANUAL + message_id |
| admin_orders.py | (order notification) | order event | email | client | email_service.send_email | ORDER_NOTIFICATION | true | true | true | null | order_id + template_key + event_type |
| admin_orders.py | send_custom_notification | admin custom notify | email | client | email_service.send_custom_notification | CUSTOM_NOTIFICATION | true | false | false | null | client_id + CUSTOM_NOTIFICATION + id |
| order_delivery_service.py | (delivery) | order delivered | email | client | email_service.send_email(ORDER_DELIVERED) | ORDER_DELIVERED | true | true | true | null | order_id + ORDER_DELIVERED |
| order_notification_service.py | (notify) | order event | email/sms | client | email_service.send_email / sms_service.send_sms | ORDER_* | true | true | true | sms_reminders for SMS | order_id + template_key |
| documents.py | (ai extraction) | AI extraction applied | email | client | email_service.send_ai_extraction_email | AI_EXTRACTION_APPLIED | true | true | true | null | document_id + AI_EXTRACTION_APPLIED |
| client.py | (tenant invite) | client invites tenant | email | tenant | email_service.send_email(TENANT_INVITE) | TENANT_INVITE | true | true | true | tenant_portal | tenant_id + TENANT_INVITE |
| client.py | (tenant invite 2) | tenant invite flow | email | tenant | email_service.send_email(TENANT_INVITE) | TENANT_INVITE | true | true | true | tenant_portal | tenant_id + TENANT_INVITE |
| client_orders.py | (order) | client order | email | client | email_service.send_email | ORDER_* or GENERIC | true | true | true | null | order_id + template_key |
| intake_draft_service.py | (draft share?) | intake draft | email | client/lead | email_service.send_email | INTAKE_DRAFT_SHARE or similar | false | false | false | null | draft_id + template_key |
| support.py | create ticket | support ticket created | email | customer + internal | send_ticket_confirmation_email / send_internal_ticket_notification | SUPPORT_TICKET_CONFIRMATION, SUPPORT_INTERNAL_NOTIFICATION | false | false | false | null | ticket_id + SUPPORT_TICKET_CONFIRMATION ; ticket_id + SUPPORT_INTERNAL |
| support_email_service.py | send_ticket_confirmation_email | - | email | customer | PostmarkClient.emails.send | SUPPORT_TICKET_CONFIRMATION | false | false | false | null | ticket_id + _CONFIRMATION |
| support_email_service.py | send_internal_ticket_notification | - | email | internal | PostmarkClient.emails.send | SUPPORT_INTERNAL_NOTIFICATION | false | false | false | null | ticket_id + _INTERNAL |
| enablement_service.py | deliver_email | enablement | email | client | email_service.client.emails.send | ENABLEMENT_* | true | true | true | null | client_id + category + content_id |
| reporting.py | send_report_email | report email | email | client | email_service.client.emails.send | SCHEDULED_REPORT or REPORT_EMAIL | true | true | true | null | report_job_id + template_key |
| partnerships.py | (ack) | partnership enquiry | email | external | email_service.client.emails.send | PARTNERSHIP_ACK | false | false | false | null | enquiry_id + PARTNERSHIP_ACK |
| leads.py | send_lead_message | admin manual to lead | email | lead | PostmarkClient.emails.send | LEAD_MANUAL_MESSAGE | false | false | false | null | lead_id + LEAD_MANUAL_MESSAGE + timestamp |
| lead_followup_service.py | send_followup_email | lead follow-up | email | lead | PostmarkClient.emails.send | LEAD_FOLLOWUP | false | false | false | null | lead_id + template_id + YYYY-MM-DD |
| lead_followup_service.py | (SLA breach) | SLA breach | email | admin | PostmarkClient.emails.send | LEAD_SLA_BREACH_ADMIN | false | false | false | null | lead_id + LEAD_SLA_BREACH + date |
| lead_service.py | (HIGH intent) | HIGH intent lead | email | admin | PostmarkClient.emails.send | LEAD_HIGH_INTENT_ADMIN | false | false | false | null | lead_id + LEAD_HIGH_INTENT + date |
| compliance_sla_monitor.py | (alert) | compliance recalc SLA | email | internal (OPS) | PostmarkClient.emails.send | COMPLIANCE_SLA_ALERT | false | false | false | null | alert_id + COMPLIANCE_SLA_ALERT |
| clearform/routes/auth.py | - | ClearForm signup | email | user | email_service.send_clearform_welcome_email | CLEARFORM_WELCOME | false | false | false | null | clearform_user_id + CLEARFORM_WELCOME |
| scripts/resend_portal_invite.py | (script) | CLI resend | email | client | email_service.send_password_setup_email | WELCOME_EMAIL | true | false | false | null | client_id + WELCOME_EMAIL + script_run_id |
| routes/sms.py | send_otp | phone verify OTP | sms | user | sms_service.send_otp | (OTP: keep Twilio Verify path or route via orchestrator with template OTP_VERIFICATION) | false | false | false | null | phone + OTP_VERIFICATION + session |
| routes/sms.py | (send_sms) | client SMS | sms | client | sms_service.send_sms | - | true | true | true | sms_reminders | client_id + template + idempotency |

Notes:
- Sends with no client_id (admin/internal/lead/ops): orchestrator must support optional client_id and recipient from context.
- OTP (Twilio Verify): may remain as special path or get template_key OTP_VERIFICATION with no client_id.
