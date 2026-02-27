# Monthly Compliance Digest – Implementation Audit

**Purpose:** Compare the codebase to the task requirements for "Implement Monthly Digest (portfolio summary) end-to-end", identify what is implemented vs missing, and recommend the safest path without blind implementation.

**Date:** 2025-02 (codebase snapshot).

---

## 1) How the Monthly Digest Is Configured

| Aspect | Current implementation |
|--------|------------------------|
| **Schedule** | APScheduler: 1st of each month at **10:00 AM UTC** (`server.py`: `CronTrigger(day=1, hour=10, minute=0)`). |
| **Eligibility** | Clients with `subscription_status == "ACTIVE"` and `entitlement_status` in `["ENABLED", None]`. |
| **Toggle** | `notification_preferences.monthly_digest` (default True). Job skips if `monthly_digest` is False. |
| **Quiet hours** | If `quiet_hours_enabled` and current time is within `quiet_hours_start`–`quiet_hours_end`, digest is skipped. |
| **Digest sections** | Section toggles in `notification_preferences`: `digest_compliance_summary`, `digest_action_items`, `digest_upcoming_expiries`, `digest_property_breakdown`, `digest_recent_documents`, `digest_recommendations`, `digest_audit_summary`. All default True except `digest_audit_summary` (False). |
| **Channels** | Email only. Recipient: `client.email` or `client.contact_email`. No SMS for monthly digest in current code. |
| **Template** | `notification_templates`: `template_key` `MONTHLY_DIGEST`, `email_template_alias` `monthly-digest`. HTML/plain text built in `email_service.py` (inline), not from a separate `monthly_digest.html` file. |

---

## 2) Flow (Current)

1. **Trigger:** Cron runs `run_monthly_digests()` (e.g. 1st at 10:00 UTC).
2. **Clients:** Load active clients with ENABLED entitlement.
3. **Per client:** Load `notification_preferences`; skip if `monthly_digest` is False or within quiet hours.
4. **Data:** Last 30 days: `period_end = now`, `period_start = now - 30d`. Load properties, requirements (counts: compliant/overdue/expiring_soon), recent documents (uploaded in period). Build `digest_content` (counts + section flags from prefs).
5. **Send:** `_send_digest_email(client, digest_content)` → `notification_orchestrator.send(template_key="MONTHLY_DIGEST", ...)`. If no recipient → `create_audit_log(EMAIL_SKIPPED_NO_RECIPIENT)` and return False.
6. **On success:** Insert into **`digest_logs`** (digest_id, client_id, period start/end, content, sent_at, created_at). No `create_audit_log(DIGEST_SENT, ...)` in the success path.
7. **Webhook:** `fire_digest_sent(...)` is called after send (non-blocking).

---

## 3) Is It Currently Active?

**Yes**, provided:

- APScheduler is running (same process as the app in `server.py`).
- Job `monthly_digest` is registered (lines 330–337 in `server.py`).
- No feature flag or env disables it.

Admin can trigger it manually via admin job trigger (`triggerJob('monthly_digest')`); job status reads from `digest_logs` for last run and total sent.

---

## 4) Task Requirements vs Current State

### Backend

| Requirement | Status | Notes |
|-------------|--------|--------|
| **`monthly_digests` collection** with client_id, crn, period (YYYY-MM), generated_at, score_summary, status_counts, top_actions[], upcoming_expiries[], doc_activity, settings_snapshot, audit_ref | **Not implemented** | Current store is **`digest_logs`** with: digest_id, client_id, digest_period_start/end, content (counts + section flags), sent_at, created_at. No crn, no score_summary/status_counts/top_actions/upcoming_expiries/doc_activity/settings_snapshot/audit_ref. |
| Scheduled job: 1st **business day** **09:00 local** time | **Different** | Current: 1st calendar day **10:00 UTC**. No “business day” logic, no per-client/local time. |
| Generate digest from portal records and **compare with previous digest** for “changes since last month” | **Not implemented** | No fetch of previous digest; no delta computation. |
| Respect **monthly_digest_enabled** + **preferred channels (email/sms)** | **Partial** | `monthly_digest` (stored as such; task calls it monthly_digest_enabled) is respected. Channels: email only; no SMS for digest. |
| Send email via existing provider; template **monthly_digest.html** + plain text fallback | **Partial** | Email sent via existing provider. Template is inline in `email_service.py` (MONTHLY_DIGEST alias), not a separate `monthly_digest.html` file. Plain text exists. |
| **GET /api/portal/digests?limit=12** and **GET /api/portal/digests/{id}** | **Missing** | No portal digest list/detail endpoints. |
| **Audit DIGEST_SENT** with digest_id and channel | **Missing** | On send success, only `digest_logs.insert_one`; no `create_audit_log(DIGEST_SENT, digest_id=..., channel=...)`. |

### Frontend

| Requirement | Status | Notes |
|-------------|--------|--------|
| Notifications page: “Monthly Digest” toggle **saved and enforced by backend** | **Done** | Toggle is in NotificationPreferencesPage; PUT `/api/profile/notifications` saves `monthly_digest`; job reads it. |
| “Digests” section under Reports or Dashboard: **last 6 digests**, “View” and “Download PDF” | **Missing** | ReportsPage has reports and scheduled reports; no Digests subsection. No digest list/detail UI or PDF download. |

### Safety

| Requirement | Status | Notes |
|-------------|--------|--------|
| Wording **informational, not legal verdicts** | **Reasonable** | Current email is counts/summary. |
| **“Data as of”** timestamp + **“Not legal advice”** disclaimer | **Missing** | Footer has company/tagline/CRN only; no “Data as of” or “Not legal advice” in digest body or footer. |

---

## 5) Conflicts and Safest Option

### Conflicts

1. **Collection name and schema**  
   Task specifies **`monthly_digests`** with a rich schema (crn, period YYYY-MM, score_summary, status_counts, top_actions[], etc.). The codebase uses **`digest_logs`** with a simpler schema. Introducing a second collection and dual-write adds complexity and migration; changing schema of `digest_logs` may break admin/job status that rely on it.

2. **Schedule**  
   Task: “1st business day 09:00 local time.” Current: “1st of month 10:00 UTC.” Changing to business-day + local time affects all clients and deployment (e.g. server timezone vs client timezone).

3. **Template file**  
   Task: “template monthly_digest.html”. Current: inline HTML in `email_service.py`. Moving to a file is additive; renaming/removing the inline path could break existing behaviour if anything else references it.

4. **SMS for digest**  
   Task mentions “preferred channels (email/sms)”. Current digest is email-only. Adding SMS is a feature/scope decision and may depend on templates and plan gating.

### Recommended (safest) approach

- **Do not duplicate or replace working behaviour blindly.** Keep the existing monthly digest job and `digest_logs` flow; extend where the task adds value and avoid breaking admin or job status.

- **Backend – storage**  
  - **Option A (recommended):** Extend **`digest_logs`** with optional fields (e.g. crn, period_ym “YYYY-MM”, score_summary, status_counts, top_actions, upcoming_expiries, doc_activity, settings_snapshot) and set `audit_ref` when you add DIGEST_SENT. Keep existing fields so current consumers (admin job status, etc.) keep working.  
  - **Option B:** Add a separate **`monthly_digests`** collection for the richer “portfolio summary” and have the job write both (digest_logs for backward compatibility and monthly_digests for portal/API). More code and consistency to maintain.  
  Prefer **Option A** unless product explicitly wants a separate “report” entity and portal-only API.

- **Backend – schedule**  
  - Keep **1st at 10:00 UTC** unless product confirms a change. If changing: implement “1st business day” (e.g. skip weekend) in one timezone first (e.g. server or UK), then consider “09:00 local” only if there is a clear product need and a defined way to resolve “local” (e.g. client timezone or tenant timezone).

- **Backend – “changes since last month”**  
  - Add only if product asks: before building digest, fetch the previous month’s digest (from digest_logs or monthly_digests) for that client and compute deltas; include a short “changes since last month” section in the email and in stored content.

- **Backend – audit**  
  - Add **DIGEST_SENT** on successful send: generate a stable `digest_id` (e.g. UUID) before send, pass it through, insert it into `digest_logs`, then `create_audit_log(AuditAction.DIGEST_SENT, client_id=..., metadata={ "digest_id": digest_id, "channel": "EMAIL" })`. No change to skip path (keep EMAIL_SKIPPED_NO_RECIPIENT).

- **Backend – portal API**  
  - Add **GET /api/portal/digests?limit=12** and **GET /api/portal/digests/{id}** (portal-auth), reading from the same store as the job (`digest_logs` or, if introduced, `monthly_digests`). Return only that client’s digests.

- **Frontend**  
  - Add a **“Digests”** section (under Reports or Dashboard). Call GET `/api/portal/digests?limit=6` (or 12), show last 6 with “View” (detail) and “Download PDF”. Implement PDF generation only if required (e.g. backend endpoint that renders digest as PDF or reuses existing report PDF pipeline).

- **Safety**  
  - Add “Data as of &lt;timestamp&gt;” and “This summary is for information only and does not constitute legal advice” to the digest email (and any PDF). No change to legal character of other product wording unless specifically requested.

- **Template**  
  - Optional: extract the monthly digest HTML into a **`monthly_digest.html`** (or similar) template file and load it from the email service for consistency with the task wording; keep the same template alias and fallback so behaviour stays the same.

---

## 6) Summary Table

| Item | Implemented | Missing / Different |
|------|-------------|----------------------|
| Monthly digest job | Yes (1st, 10:00 UTC) | Schedule: business day + 09:00 local not implemented |
| monthly_digest toggle saved & enforced | Yes | — |
| digest_logs storage | Yes (simpler schema) | monthly_digests schema (or extend digest_logs) |
| “Changes since last month” | No | — |
| Email send + plain text | Yes | Optional: monthly_digest.html file |
| DIGEST_SENT audit on send | No | — |
| GET /api/portal/digests (list + detail) | No | — |
| Digests UI (last 6, View, Download PDF) | No | — |
| “Data as of” + “Not legal advice” | No | — |

Implement in this order to minimise risk: (1) DIGEST_SENT audit + optional digest_log schema extension, (2) Portal API GET digests, (3) Frontend Digests section with View, (4) PDF download if required, (5) Safety disclaimer and “Data as of”, (6) Optional “changes since last month” and schedule/template refinements once product confirms.
