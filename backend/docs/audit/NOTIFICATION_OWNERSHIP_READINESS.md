# Notification ownership — readiness snapshot

**Purpose:** Map real send paths for pilot governance. **Does not** enable `NOTIFICATION_DISPATCH` globally.

## Machine-readable inventory (governance visibility layer)

- **File:** `docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` (`schema_version: notification_governance_inventory_v1`)
- **Contents:** Sender clusters (module groupings), launch criticality (`LAUNCH_CRITICAL` vs `PILOT_TOLERABLE`), governance tier, blast radius, mitigation status, idempotency / `message_logs` notes.
- **Use:** Diff-friendly audits; extend with per-`template_key` rows when a registry script lands. **Not** a claim of 100% line coverage.

## Launch criticality & launch recommendation (notifications only)

| Topic | Launch criticality | Operational blast radius | Support implications | Launch recommendation |
|-------|-------------------|--------------------------|----------------------|-------------------------|
| Orchestrator as primary send path | **LAUNCH_CRITICAL** | Wrong template/recipient undermines all trust | Ops must trace `message_logs` + audit | **Continue** — keep enforcing bypass tests |
| `NOTIFICATION_DISPATCH` global activation | **LAUNCH_CRITICAL** (if mishandled) | Broad unintended sends | Incident scale | **Do not activate** until workflow activation evidence satisfies program gates |
| Deprecated `EmailService` live usage | **LAUNCH_CRITICAL** | Governance bypass | Hard to explain deliveries | **Block** new callers; shrink surface over time |
| Lead / marketing lanes | **PILOT_TOLERABLE** | Pre-tenant noise | Separate from compliance inbox triage | **Label** clearly in runbooks; do not conflate with compliance notifications |
| Per-template idempotency proof | **LAUNCH_CRITICAL** for reminders | Duplicate reminders erode trust | “Why twice?” tickets | **REDUCED** — daily reminders + `COMPLIANCE_ALERT` fingerprinted (**L-008d**); **L-008e** CI closes seed ↔ literal `template_key` drift; other templates rely on orchestrator keys + preferences |

**Launch posture (notifications slice):** **READY** for **L-008 parent** (`READY_FOR_WIDER_LAUNCH` — see `LAUNCH_AUTHORITY_TRACKER.md` L-008 closure): orchestrator baseline + bypass test + reminder/alert idempotency + **L-008e** CI seed ↔ literal `template_key` + lifecycle registry; composite product launch still governed by other gates.

## Primary sender

- **`NotificationOrchestrator.send`** (`services/notification_orchestrator.py`) — intended sole production path for tenant-scoped email/SMS; writes **`message_logs`** (see orchestrator implementation). Idempotency via `idempotency_key` where callers supply it.

## Known orchestrator call sites (non-exhaustive grep snapshot)

| Area | Module / route | Notes |
|------|----------------|-------|
| Jobs / reminders | `services/jobs.py` | Reminder email/SMS via orchestrator; references `message_logs` metadata patterns for reminders. |
| Admin | `routes/admin.py` | Multiple `notification_orchestrator.send` calls (e.g. onboarding resend, broadcasts). |
| Client | `routes/client.py` | User-triggered notifications where applicable. |
| Documents | `routes/documents.py` | Tenant-scoped notifications tied to document lifecycle. |
| Contractors | `services/contractor_service.py` | Operational notifications. |

## Bypass / parallel paths

- **`EmailService.send_*`**: Marked **deprecated** in `services/email_service.py`; static governance test **`tests/test_notification_bypass_governance.py`** asserts orchestrator-only usage pattern for production sends.
- **Risk / lead flows**: `risk_lead_email_service` / `risk_check` — **marketing/intake** lane, not tenant operational notifications; keep isolated from client compliance orchestration.

## Workflow family `NOTIFICATION_DISPATCH`

- Referenced in **`services/workflow_activation_readiness.py`** and reliability audits as a **workflow family**, not an automatic “send everything” switch.
- **Readiness:** Do **not** treat global activation as satisfied until activation registry + gate evidence match pilot policy (same standard as other workflow families).

## Gaps / follow-ups (honest)

- **Template seed vs trigger:** **L-008e (2026-05-08)** — CI asserts (1) every audited production **string literal** `template_key=` on `notification_orchestrator.send` ⊆ canonical `notification_template_seed_definitions`; (2) every `template_key` in `services/email_event_registry.py` `EMAIL_EVENTS` ⊆ seed; (3) `LANDLORD_ONBOARDING_EVENT_IDS` resolve via `get_template_key_for_event` into seed. See `notification_orchestrator_send_template_key_audit.py` and `tests/test_l008_orchestrator_template_seed_contract.py`. **Residual:** dynamic `template_key` parameters (non-literal) must stay bounded by those registries; per-route narrative matrix in JSON remains optional enrichment.
- **Reminder idempotency:** Orchestrator supports keys; **daily COMPLIANCE_EXPIRY_REMINDER email/SMS** (`services/jobs.py`) now suffixes keys with `daily_compliance_reminder_scope_fingerprint(reminder_refs)` so the same recipient/day does not dedupe across **different requirement batches** (`tests/test_notification_reminder_idempotency.py`). **COMPLIANCE_ALERT** (same module, `check_compliance_status_changes`) uses `compliance_alert_property_scope_fingerprint` so large multi-property degradation batches are not collapsed by a 32-character truncation of sorted property IDs (`tests/test_notification_compliance_alert_idempotency.py`). Other callers still need periodic review.
- **Tenant isolation:** Orchestrator paths must continue to enforce `client_id` scoping from authenticated context — regression coverage relies on integration tests + code review for any new caller.

## Related artifacts

- `services/workflow_trigger_reliability_audit_phase2.py` — mentions `message_logs` + orchestrator idempotency.
- `tests/test_reminder_governance_phase2.py` — patches orchestrator for governance assertions.
