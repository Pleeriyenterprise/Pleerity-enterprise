# Training Gap Analysis

This document identifies **incomplete UX**, **flows that need runtime confirmation**, **missing help/onboarding**, and **areas where the current build may confuse staff or users**. It is derived from repository scan only; no behaviour was invented.

---

## 1. Modules with incomplete or partial UX

| Module | Gap | Impact |
|--------|-----|--------|
| **Admin Dashboard** | Single large page with many tabs (Clients, Rules, Templates, Email delivery, etc.). New admins may not know which tab to use for which task. | Training should map “I need to do X” → tab/section. |
| **Client Dashboard** | Setup checklist and first-login views depend on `onboarding_status`, `billing_plan`, and entitlements. Edge cases (e.g. not provisioned, plan missing) show restrict reasons; copy may be technical. | Clarify in training when to escalate to admin vs “wait for provisioning”. |
| **Compliance (Requirements)** | “Mark as not applicable” and “Confirm expiry date” require user to understand requirement types and dates. No inline help on what each status (PENDING, EXPIRING_SOON, OVERDUE) means in practice. | Add “Notes for training staff” to explain status semantics. |
| **Evidence upload** | Extraction is async; user must wait for “Confirm details” or see extraction failed. No in-UI explanation of extraction timeout or retry. | Document expected wait time and “extraction failed” handling. |
| **Compliance Score** | Methodology and “advanced details” are expandable; some users may not discover them. Export (PDF/CSV) is plan-gated; 403 may show as generic error. | Train on where methodology lives and what “upgrade required” means. |
| **Reminder system (client)** | Users see Notification preferences (email/SMS toggles) but do not see *when* the next reminder runs or a log of sent reminders. | Set expectation: “reminders are sent by the system; you control channels only.” |
| **Admin reminder/automation** | Automation Centre shows job states (healthy, degraded, never ran, etc.). Staff may not know when to use “Run Now” vs when to create an incident or contact dev. | Training should clarify “Run Now is for recovery/testing only.” |

---

## 2. Flows that need runtime confirmation

| Flow | What to confirm |
|------|------------------|
| **Client login → dashboard data** | After login, `GET /api/client/dashboard` returns client, properties, and entitlements. Confirm in target environment that restricted users see correct restrict reason (e.g. “Client not found”, “Account must be provisioned”). |
| **Daily reminders delivery** | `daily_reminders` job runs on schedule (e.g. 09:00 UTC); respects `daily_reminder_enabled` and `expiry_reminders` preferences. Confirm that a test client with expiring requirements and preferences ON receives email (and SMS if configured). |
| **Document upload → extraction → confirm details** | Upload triggers async extraction; frontend polls `GET /documents/{id}/extraction`. Confirm extraction completes within expected timeout and “Confirm details” modal pre-fills from extraction where applicable. |
| **Compliance score calculation** | Score is computed from requirements and evidence (catalog or stored). Confirm that adding/removing evidence or changing expiry dates updates score and trend in UI within expected time (recalc jobs may be scheduled). |
| **Admin “Run Now” for a job** | Triggers `run_instrumented` for that job. Confirm that running e.g. `daily_reminders` manually does not duplicate sends (e.g. idempotency/dedup by client+date). |
| **Plan-gated features** | Property limit, PDF/CSV export, tenant portal, etc. Confirm 403 response and UI upgrade prompts match plan configuration in target environment. |

---

## 3. Missing or minimal help text

| Location | Gap |
|----------|-----|
| **Client Dashboard** | No inline help for “Compliance score” or “Score trend” (what the grade/band means). Some tooltips exist; coverage is partial. |
| **Properties list** | Status badges (GREEN/AMBER/RED) are not explained in-page. Manual describes them; in-app help could link to Help Centre. |
| **Requirements (Compliance) page** | No explanation of “PENDING” vs “EXPIRING_SOON” vs “OVERDUE” in the UI. |
| **Documents page** | “Confirm details” modal explains expiry/issue date; no help on what “extraction failed” means or what to do (e.g. re-upload or enter manually). |
| **Compliance Score page** | “Methodology” and “Definitions” are in expandable sections; no pointer for first-time users. |
| **Notification preferences** | SMS verification flow is present; no in-UI explanation of reminder schedule (e.g. “once per day”) or which reminders are affected by each toggle. |
| **Admin Automation Centre** | Job states (e.g. “never_ran_and_overdue”, “not_yet_due_since_startup”) have reasons in UI; new admins may still need a short “when to worry” guide. |

---

## 4. Missing onboarding / training content

| Gap | Recommendation |
|-----|----------------|
| **First-time client** | No in-app wizard that says “Add your first property → Add requirements → Upload evidence.” Setup checklist exists but is optional/skippable; some users may skip and not know next steps. | Consider a one-time “Getting started” checklist or link to Help Centre “Adding a property” / “Uploading evidence.” |
| **First-time admin** | No guided tour of admin console sections. New admins must learn from sidebar and tabs. | Use admin-console.md and dashboard.md as basis for a short “Admin tour” script. |
| **Reminder behaviour** | Clients are not told explicitly “You will receive daily emails for items due in the next X days” (X may be configurable). | Add to Help Centre and/or Notification preferences page. |
| **Plan limits** | When property limit is reached, the UI shows an error; the manual explains plan limits. In-app message could link to Billing or Help. | Add one-line explanation and link where 403 plan limit is shown. |

---

## 5. Places that may confuse staff or users

| Area | Risk | Mitigation in training |
|------|------|------------------------|
| **Two portals** | Client vs Admin login URLs and roles. Users with both roles must use the correct portal. | Emphasise “Client portal” vs “Admin portal” and when to use each. |
| **Compliance vs Requirements** | UI label is “Compliance” (nav) but data is “requirements” (API). Some copy may say “requirement” or “compliance item.” | Use consistent wording in training: “Compliance (requirements)”. |
| **Documents vs Evidence** | “Documents” page is used for compliance evidence (certificates, EICR, etc.). “Evidence” and “documents” used interchangeably. | Clarify: “Documents = evidence you upload for compliance.” |
| **Score vs status** | Portfolio has a numeric score (0–100) and grade; properties have status (GREEN/AMBER/RED). Both reflect compliance but at different levels. | Explain: “Score = overall portfolio; status = per-property summary.” |
| **Run Now (admin)** | “Run Now” on Automation Centre runs the job immediately. Overuse can cause duplicate reminders or load. | Document: “Use only for recovery or testing; routine runs are automatic.” |
| **Archived vs draft (KB)** | In Knowledge Centre, “Archive” is a status (article hidden from users); “Delete” is soft delete. | Brief note in admin KB manual. |
| **Feature-gated client nav** | Operations (Issues, Work Orders, Contractors, Risk Signals, Approvals) and Tenants, Billing appear only if the client has the feature. | Tell clients “some menu items depend on your plan.” |

---

## 6. Summary table

| Category | Count | Action |
|----------|-------|--------|
| Modules with incomplete UX | 7 | Document in manuals; add “Current limitations” and “Notes for training staff.” |
| Flows needing runtime confirmation | 6 | Include in trainer checklist; verify in staging before training. |
| Missing / minimal help text | 7 | List in this doc; consider in-app help or Help Centre articles. |
| Missing onboarding content | 4 | Consider “Getting started” and admin tour. |
| Confusing areas | 7 | Address in manuals and trainer scripts. |

---

*This gap analysis is based on codebase scan only. Priorities and fixes should be agreed with product and support.*
