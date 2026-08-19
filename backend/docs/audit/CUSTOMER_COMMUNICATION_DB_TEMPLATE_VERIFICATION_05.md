# DB-template verification 05

## Root cause

`finalize_db_email_html` (`backend/services/branding_resolver_service.py`) wrapped DB HTML fragments with `render_customer_email` and called `resolve_greeting` / `strip_embedded_greetings` **without importing them**.

```text
where defined: email_presentation.greeting
where imported (after fix): finalize_db_email_html (local import)
which paths: DB-first customer aliases that are not INTERNAL_EMAIL_ALIASES and are not unconditional code-built
production-facing: any active DB fragment for a customer alias (tenant-invite, onboarding, custom, enablement, etc. when a DB row exists)
failure: during render, before provider send
fallback: orchestrator logs Render email failed; send does not proceed
```

Internal aliases (`admin-manual`, `admin-invite`, …) return the fragment unchanged and never hit the missing name.

## Fix

Import the canonical greeting helpers. Do not swallow the exception. Do not hard-code greetings per template.

## Local proof

`tests/test_customer_communication_cleanup_05.py::test_finalize_db_email_html_uses_canonical_greeting` — Hello Ada, body preserved.

Previously failing orchestrator tests (Gate 04 P2):

* `test_billing_email_allowed_pre_provisioning`
* `test_postmark_send_includes_message_stream_when_set`
* `test_postmark_send_includes_reply_to_when_set`
* `test_postmark_send_includes_message_stream_and_reply_to_together`

These passed in the Cleanup 05 focused suite.

## Path regression (local render)

| Path | Result |
| --- | --- |
| CANONICAL_CODE_BUILT (PAYMENT_FAILED, reminders) | Unchanged; still bypass finalize |
| GOVERNED_DB_TEMPLATE fragment | Greeting injected; no NameError |
| HYBRID (compliance-alert with `affected_properties`) | Still code-built HTML |

No empty-body / generic-notification degradation on these renders.
