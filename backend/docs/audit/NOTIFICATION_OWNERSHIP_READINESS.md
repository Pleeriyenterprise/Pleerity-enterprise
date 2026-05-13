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

---

## External audit snapshot — email & notification ecosystem (2026-05-13)

**Method:** Code and registry review (`notification_orchestrator.py`, `notification_template_seed_definitions.py`, `email_event_registry.py`, `NOTIFICATION_GOVERNANCE_INVENTORY.json`, `email_service.py` quarantine status, `_render_email` hybrid paths). **Not** a live Postmark template content review of every alias body.

### A. Architecture verdict (summary)

| Criterion | Assessment |
|-----------|------------|
| **Single send API** | **Strong** — `NotificationOrchestrator.send` is the declared canonical path; L-008e CI binds literal `template_key` to seed. |
| **Template sources** | **Hybrid / fragmented** — DB `notification_templates` + Postmark aliases **plus** many **code-built** bodies via `EmailService._build_html_body` inside `_render_email` (intentional for trust-critical layouts; also increases dual-maintenance surface). |
| **`admin-manual` alias overload** | **High fragmentation risk** — dozens of distinct `template_key` values map to the same `email_template_alias` (`admin-manual`); Postmark/DB bodies may feel generic or disconnected unless each `template_key` is curated in DB. |
| **Deprecated parallel lane** | **Quarantined but large** — `EmailService` remains layout engine inside orchestrator; inventory marks cluster **QUARANTINED_DEPRECATED** for *new* direct callers, not for internal `_build_html_body` use. |

### B. Email family map (from `email_category` + `EMAIL_EVENTS` + seed)

| Family | Examples (`template_key` / event) | Intended tone | Implementation notes |
|--------|-----------------------------------|---------------|----------------------|
| **system_critical** | `WELCOME_EMAIL`, `PASSWORD_RESET`, `ADMIN_INVITE`, `TENANT_INVITE`, `PAYMENT_FAILED`, Stripe receipts | Calm, factual, high-trust | Mix of code-built (`payment-receipt` structured, `portal-ready` milestone, `activation-reminder`) and DB-driven aliases. |
| **compliance_notifications** | `COMPLIANCE_EXPIRY_REMINDER`, `COMPLIANCE_ALERT`, `AI_EXTRACTION_APPLIED`, `ORDER_NOTIFICATION` | Operational, non-panicky | Reminder idempotency fingerprinted (L-008d). **Risk:** `ORDER_NOTIFICATION` reuses `compliance-alert` alias — verify copy matches order semantics. |
| **reporting_notifications** | `MONTHLY_DIGEST`, `SCHEDULED_REPORT`, `RENEWAL_REMINDER`, onboarding day 0–7 | Advisory / digest | Onboarding sequence in `EMAIL_EVENTS`; scheduled report has **forced** code path for job-driven rows. |
| **internal** | `INTERNAL_ALERT`, `ADMIN_MANUAL`, many ops alerts | Operator-focused | Heavy use of `admin-manual` — **support must not** paste compliance guarantees into freeform admin sends. |
| **lead_nurture** | `LEAD_FOLLOWUP`, `LEAD_TRANSACTIONAL_*` | Marketing-adjacent | Inventory: **parallel lane** — must not be mistaken for tenant compliance mail. |
| **marketing_notifications** | `FEATURE_ANNOUNCEMENT`, `PRODUCT_UPDATE` | Lower urgency product | Gated by `marketing_notifications_enabled` in orchestrator prefs. |
| **SMS** | `COMPLIANCE_EXPIRY_REMINDER_SMS`, `OTP_CODE_SMS`, `ADMIN_MANUAL_SMS` | Ultra-short operational | Separate channel; same orchestrator. |

### C. Customer-safe hierarchy (operational)

Orchestrator enforces **notification_preferences** buckets (`compliance_notifications_enabled`, `reporting_notifications_enabled`, `marketing_notifications_enabled`, SMS flags). **Unsubscribe** semantics are implementation-dependent per channel — treat preference changes as authoritative when exposed in product.

### D. Consolidation recommendation (notifications only)

**Verdict:** **Operationally usable but fragmented** — architecture is **governed** (orchestrator + seed + CI), but **visual/copy cohesion** across families depends on **Postmark DB templates + admin-manual overload + code-built subsets**. Before wider launch: (1) curate or split `admin-manual` into additional aliases where customer-facing; (2) document per-alias “owner” and CTA destination in admin comms runbook; (3) keep async-honesty review on `AI_EXTRACTION_APPLIED` and compliance alerts aligned with `PRESENTATION_LANGUAGE_GOVERNANCE.md`.

---

## Governed notification semantic families — authoritative in repo

**Normative companion:** `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` (core async-honesty + **Email & notification CTA semantics** + **High-risk operational mail — trust wording**). **Authority for KPI truth** remains `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` — email never overrides persisted compliance state.

Each row is a **governance family** (may span multiple `template_key` values and Postmark `email_template_alias`). **Intentional** emotional and visual differences between families are required; **accidental** drift is forbidden (same family must not contradict itself across channels without documented reason).

| Family (seed `email_category` or logical lane) | Semantic purpose | Emotional intensity | Urgency ceiling | CTA philosophy | Operational vs lifecycle weight | Legal / trust constraints | Allowed visual variance |
|-----------------------------------------------|------------------|---------------------|-----------------|----------------|----------------------------------|---------------------------|-------------------------|
| **system_critical** | Account access, password, invites, hard payment failures | Low drama, high clarity | **High only for expiry of security links** — not for upsell | One decisive primary CTA (set password, reset, accept invite) | **Operational** | No marketing guarantees; no “fully compliant” from account actions alone | Code-built layouts preferred where frozen (`payment-receipt` structured, `portal-ready` milestone); DB alias must not soften security copy |
| **compliance_notifications** | Reminders, alerts, AI assist outcomes, document vault | Calm operational | **No panic headlines**; status change = “may require attention” | **EXECUTE_OPERATIONAL** CTAs — portal deep link when available | **Operational** dominant | **Async honesty:** no “verified/legal” from AI; no “score updated instantly”; extraction = assistive suggestions | Softer panels OK; avoid casino reds on routine reminders |
| **reporting_notifications** | Digests, scheduled reports, renewal nudges | Informational | Low–medium | **INFORMATIONAL_REVIEW** primary; secondary operational link | Mix: **advisory** first, operational second | Snapshot/as-of language for scores and counts | Tables and summaries encouraged; must label freshness |
| **internal** | Ops alerts, admin manual, SLA spikes | Technical / terse | Medium for true incidents | Link to admin surfaces or ticket context | **Non-client** or operator-first | Must not use tenant “cheerful product” tone for failures | `admin-manual` Postmark body often minimal — acceptable if **lane** rules below are respected |
| **marketing_notifications** | Product updates, feature announcements | Brighter allowed | Medium | Single billing/product CTA; respect prefs | **Lifecycle / growth** | Must respect `marketing_notifications_enabled`; never disguise as compliance | May use richer marketing layout **only** in this family |
| **lead_nurture** | Pre-tenant intake | Conversion-appropriate | Medium–higher allowed | Conversion CTAs to landing / book demo | **Lifecycle** | **Must not** mimic `compliance_notifications` envelope or subject patterns | Distinct sender/subject patterns recommended |

---

## `admin-manual` semantic lanes (governance without mandatory alias split)

**Problem:** Many `template_key` values share `email_template_alias: admin-manual`, which creates **phishing-like ambiguity** if bodies are generic or emotionally mismatched.

**Phase A (this document — no orchestration change):** classify sends into **lanes** when authoring Postmark/DB bodies or admin broadcasts. Routing and `template_key` stay unchanged.

| Lane | Typical `template_key` examples | Tone | CTA / link rules |
|------|----------------------------------|------|------------------|
| **INTERNAL_OPS** | `INTERNAL_ALERT`, `OPS_ALERT_NOTIFICATION_SPIKE`, `PROVISIONING_FAILED_ADMIN`, `STRIPE_WEBHOOK_FAILURE_ADMIN`, `COMPLIANCE_SLA_ALERT` | Operator alert; no faux “customer delight” | Link to admin/ops console or runbook; **no** tenant billing upsell |
| **CUSTOMER_SUPPORT** | `SUPPORT_TICKET_*`, `CUSTOM_NOTIFICATION` (when used for client comms) | Neutral service desk | Ticket URL or reply-to support; one primary action |
| **BILLING_ADJACENT_MANUAL** | `INVOICE_AVAILABLE`, subscription grace / renewal copies using admin-manual | Factual money language | Billing portal deep link; **no** fake urgency |
| **LEAD_RECOVERY** | `LEAD_*`, `LEAD_MANUAL_MESSAGE` | Nurture / sales-appropriate | Landing or calendar link — **never** compliance RAG semantics |
| **PLACEHOLDER_FALLBACK** | `COMPLIANCE_SCORE_UPDATE`, `DOCUMENT_MISSING_ALERT` when still on admin-manual | **Must** be upgraded to dedicated alias + copy when product prioritises | Until then: opening sentence must state what happened in plain English |

**Phase B (product + Postmark + engineering — deferred):** introduce **additional** `email_template_alias` values (e.g. `internal-ops-alert`, `customer-support-notice`) **only** with: seed update, new Postmark templates, **`notification_orchestrator_send_template_key_audit.py` / L-008e** updates, and staged rollout. **Do not** rename `template_key` silently.

---

## Hybrid rendering & shared DNA (wrapper inheritance policy)

**Facts:** `NotificationOrchestrator._render_email` mixes (1) DB `notification_templates`, (2) forced code-built HTML via `EmailService._build_html_body`, and (3) pre-rendered `context["message"]` for some paths.

**Shared DNA (required):**

- Customer-facing code layouts must use `_customer_email_html` (or equivalent) so **footer support line**, **preference link** (where applicable), and **“informational — not legal advice”** treatment stay consistent.
- `merge_email_branding_context` remains the single branding merge for code-built paths.

**Intentional variance (allowed):**

- Compliance tables vs onboarding storytelling vs internal ops plain text.

**Accidental fragmentation (forbidden):**

- One-off HTML hand-rolled outside `_customer_email_html` for tenant mail without security review.
- Reusing **green “success”** panels for **non-terminal** async states (AI extraction) — use neutral panels for “suggested / pending confirmation” semantics.
