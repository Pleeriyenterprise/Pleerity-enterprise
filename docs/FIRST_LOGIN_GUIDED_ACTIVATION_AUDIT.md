# First-Login Guided Activation — Task Compliance Audit

**Task:** Do not drop users into a dashboard with a "random" score on first login; use a guided activation path so enough information is collected before the dashboard, ensuring accuracy and trust.

**Audit scope:** Understand the task, compare to current flow, identify what exists vs gaps, assess feasibility without breaking provisioning/onboarding, and propose a safe, professional way to incorporate. **No implementation in this document.**

---

## 1) What the task is asking for (interpretation)

- **Problem:** First login today sends the user straight to the dashboard. The dashboard shows a compliance score and summary even when the user has not yet confirmed portfolio details, uploaded documents, or confirmed certificate dates. That score can look arbitrary (e.g. low because nothing is confirmed yet) and causes distrust.

- **Desired behaviour:** Before the user sees the “normal” dashboard, run them through a **guided activation path** so that:
  1. **Step 0** – After setting password: show “Account activated” and redirect to dashboard with a flag (e.g. `?first_login=1`).
  2. **Step 1** – On first load of dashboard (when that flag is present): show a **Setup Checklist** (modal or page) instead of the raw dashboard: “Welcome to Compliance Vault Pro” with checklist items (portfolio confirmation, upload/confirm documents, confirm certificate dates, turn on reminders, view report) and **Start Setup** / **Skip for now** (with a persistent banner if they skip).
  3. **Step 2** – **Portfolio confirmation:** Show properties from intake; for each, show address/nickname, property type, bedrooms, managed by; highlight missing critical info; **Save & Continue**.
  4. **Step 3** – **Documents missing prompt** (only if `documents_count === 0` or there are missing tracked items): “You’re almost done. Upload your certificates to get an accurate score.” List missing items per property (Gas Safety if applicable, EICR, EPC, Licence if HMO) using “tracked items” language. **Upload now** / **I’ll upload later**. If later: score stays “Provisional” and a banner remains.
  5. **Step 4** – **Upload flow:** After upload, show the **Confirm Certificate Details** modal immediately. If multiple uploads: queue (“2 documents awaiting confirmation”) then lead to main dashboard.

So the task is: **intercept first login to dashboard** and run a linear (or skippable) setup flow (checklist → portfolio → documents prompt → upload + confirm modal) so that by the time the user sees the “real” dashboard, they have at least been prompted to confirm portfolio, upload docs, and confirm certificate details, and the score is not a surprise.

---

## 2) Current flow (provisioning and onboarding)

| Stage | Current behaviour | Where |
|-------|-------------------|--------|
| **Intake** | User completes intake (properties, contact, etc.); may upload files (stored as IntakeUploads). | Intake wizard; intake API. |
| **Payment** | User pays; Stripe webhook fires; subscription/plan set. | Billing/Stripe. |
| **Provisioning** | After payment (or admin trigger): create portal user, create properties (from intake or defaults), run `_generate_requirements` per property, migrate CLEAN IntakeUploads to Documents (status PENDING, `uploaded_by=INTAKE_MIGRATION`), send password-setup (activation) email. Client `onboarding_status` = PROVISIONED. | `provisioning.py`, `provisioning_runner.py`, `intake_upload_migration.py`. |
| **Password set** | User clicks link in email → SetPasswordPage → submits password → success screen “Password Set Successfully!” → after 1.5s **navigate to `/app/dashboard`**. No “Account activated” wording; no `first_login=1`. | `SetPasswordPage.js` ~69–72. |
| **Onboarding-status page** | Optional path: user can open `/onboarding-status?client_id=...`. Shows steps (payment, provisioning, activation, password). When `password_set === true`, after 2s **auto-redirect to `/app/dashboard`**. | `OnboardingStatusPage.js` ~163–168. |
| **First dashboard load** | Dashboard loads; no check for first login. Fetches: getDashboard, getComplianceScore, getRequirements, portfolio summary, etc. Renders full dashboard including **compliance score**. If no documents / unconfirmed requirements, score is low or based on “missing” state. | `ClientDashboard.js`; `client.getDashboard`, `get_compliance_score`. |
| **After upload** | Post-upload confirm-details modal opens (property, requirement, expiry/issue/certificate#); user can Save or Skip. No mandatory “Confirm Certificate Details” step before dashboard. | `DocumentsPage.js`. |

So today:

- **Provisioning and onboarding are not broken:** intake → payment → provisioning → activation email → set password → redirect to dashboard works.
- **There is no guided activation:** the only “gate” is that the user must have a provisioned account and set password (and optionally pass 403 checks for plan/provisioning). There is no Step 1–4 flow and no `first_login` handling.
- **“Random score”:** On first dashboard visit the user immediately sees the compliance score (and KPIs). With 0 or few documents and many requirements unconfirmed, that score is often low and can feel arbitrary.

---

## 3) What is implemented vs missing (vs task)

| Task element | Implemented? | Notes |
|--------------|--------------|--------|
| **Step 0: After password set** | **Partial** | Success screen exists (“Password Set Successfully!”); redirect is to `/app/dashboard` with **no** `?first_login=1`. No “Account activated” wording. |
| **Step 1: First-login Setup Checklist** | **No** | No overlay/modal or dedicated page on first dashboard visit. No checklist (portfolio, documents, certificate dates, reminders, report). No “Start Setup” / “Skip for now” with persistent banner. |
| **Step 2: Portfolio confirmation** | **No** | No dedicated “portfolio confirmation” step that shows intake-derived properties and asks for address/type/bedrooms/managed by before dashboard. Properties are editable via normal property/dashboard flows. |
| **Step 3: Documents missing prompt** | **No** | No conditional screen “documents_count === 0 or missing items” with “Upload your certificates…” and per-property missing list (Gas, EICR, EPC, Licence). No “Provisional” score state or “I’ll upload later” with persistent banner. |
| **Step 4: Upload → Confirm Certificate Details** | **Partial** | After single-file upload, confirm-details modal appears. No “queue” for multiple uploads (“2 documents awaiting confirmation”) or forced flow to confirm before “main dashboard”. |
| **Persistent “setup” or “documents need confirmation” banner** | **Partial** | There are banners for “provisional score”, “confirm property details”, “UNKNOWN applicability”. There is **no** “Setup incomplete” or “X documents require confirmation” banner tied to first-login or setup checklist. |
| **Provisional score when docs missing** | **Partial** | “Provisional” score banner exists when REQUIRED items lack confirmed expiry. No explicit “score is provisional until you complete setup” for first-login / zero-docs. |

---

## 4) Conflicts and design choices

| Point | Task | Current | Recommendation |
|-------|------|---------|----------------|
| **Redirect after password set** | “Account activated” then redirect to `/dashboard?first_login=1`. | “Password Set Successfully!” then redirect to `/app/dashboard` (no query). | **Add** `?first_login=1` (or `first_login=true`) on redirect from SetPasswordPage (and optionally from OnboardingStatusPage when it redirects after password_set). Optionally change success copy to “Account activated” so wording matches task. No change to backend or auth. |
| **Where does “first login” live?** | Task implies: first time they hit dashboard after activation. | Nothing. | **Option A (query only):** Use `?first_login=1` on the very first redirect only; dashboard reads it and shows checklist; after “Start Setup” or “Skip”, replace URL (e.g. remove query) and set a **client-side** flag (e.g. sessionStorage `setup_checklist_seen`) so next visit is normal dashboard. **Option B (backend):** Add something like `client.first_login_completed_at` or `portal_user.setup_checklist_dismissed_at` and have dashboard call an endpoint “dismiss setup” so first-login state is persistent across devices. Safest for “no break”: Option A (query + sessionStorage) so existing provisioning and login are unchanged. |
| **Checklist vs full dashboard** | Show checklist (or setup flow) first; only then “main” dashboard. | Dashboard is always full dashboard. | **Intercept only when** `first_login=1` (and optionally when sessionStorage says checklist not yet completed). Show overlay/modal or dedicated route (e.g. `/dashboard/setup`) with checklist. “Start Setup” walks through steps 2–3–4; “Skip” dismisses checklist and shows dashboard with persistent banner. No change to dashboard API or to provisioning. |
| **Portfolio confirmation data** | “Properties from intake” with address, type, bedrooms, managed by. | Properties already exist after provisioning (from intake or creation). Dashboard and property APIs already return them. | **Reuse** existing GET client dashboard (or GET properties) to show the list. Step 2 is a **UI step** that shows that list and lets user edit (existing PATCH property) and click “Save & Continue”. No new backend; only a dedicated “setup” view that uses existing APIs. |
| **Documents count / missing items** | Step 3 only if `documents_count === 0` OR missing required items. | Dashboard and client APIs don’t currently return a single “documents_count” or “missing_tracked_items” for the client. | **Backend:** Either add to existing dashboard payload (e.g. `documents_count`, `missing_tracked_items_summary`) or have frontend derive from existing data (documents.length, requirements with no evidence / unconfirmed). **Safest:** Derive on frontend from already-fetched dashboard + requirements + documents so no backend change for Step 3 gate. |
| **Provisional score** | If user chooses “I’ll upload later”, score shown as “Provisional” and banner remains. | Provisional banner exists for “REQUIRED missing confirmed expiry”. | **Reuse** same concept: when “setup incomplete” (e.g. checklist skipped or “upload later” chosen), show score as “Provisional” and keep a “Complete setup for an accurate score” banner. Can be driven by same “setup incomplete” flag (e.g. sessionStorage or backend field). |

---

## 5) Is it possible without breaking provisioning and onboarding?

**Yes.**

- **Provisioning:** Runs as today (create user, properties, requirements, migrate intake uploads, send activation email). No change.
- **Onboarding:** Intake and payment flows unchanged. Only the **post–password-set** and **first dashboard load** behaviour change:
  - Redirect after set-password (and optionally onboarding-status) adds `?first_login=1`.
  - When dashboard loads with `first_login=1` (and no “checklist completed” flag), show **Setup Checklist** (Step 1) instead of the main dashboard; from there run Step 2 (portfolio) and Step 3 (documents prompt) as UI-only steps using existing APIs.
- **Auth and guards:** No change. User is already provisioned and authenticated when they hit the dashboard.
- **Risk:** Only that the new redirect param and client-side “checklist seen” logic are correct so that (a) first-time users see the checklist once, and (b) returning users don’t get stuck in the checklist. Using a query param plus sessionStorage (or a one-time backend “dismiss” call) keeps this isolated.

---

## 6) How to incorporate into the existing flow (safe, professional)

**Recommended sequence:**

1. **Step 0 (minimal change)**  
   - In **SetPasswordPage** (and optionally **OnboardingStatusPage** when it redirects after `password_set`):  
     - Redirect to `/dashboard?first_login=1` (instead of `/app/dashboard`; app likely normalizes to `/dashboard`).  
     - Optionally change success copy to “Account activated”.

2. **Step 1 – First-login gate on dashboard**  
   - In **ClientDashboard** (or a small wrapper):  
     - On mount, read `searchParams.get('first_login')` (or `first_login=1`).  
     - If `first_login=1` and no “checklist completed” flag (e.g. `sessionStorage.getItem('setup_checklist_done')` or backend flag), **don’t render the main dashboard**; instead render a **Setup Checklist** view (modal or full-page):  
       - Title: “Welcome to Compliance Vault Pro”.  
       - Checklist: Confirm portfolio → Upload/confirm documents → Confirm certificate dates → Turn on reminders → View report.  
       - Buttons: **Start Setup** (go to Step 2), **Skip for now** (set “checklist seen”, clear `first_login` from URL, show dashboard + persistent “Complete setup” banner).  
   - No change to dashboard API or to who can access `/dashboard`.

3. **Step 2 – Portfolio confirmation**  
   - New **sub-view or route** (e.g. inside dashboard or `/dashboard/setup/portfolio`):  
     - Fetch properties via existing **getDashboard** or **getProperties**.  
     - Show list: address/nickname, property type, bedrooms, managed by; highlight missing critical fields.  
     - Use existing **PATCH property** for edits.  
     - **Save & Continue** → mark “portfolio” step done, go to Step 3 (or to “documents missing” check).

4. **Step 3 – Documents missing prompt**  
   - **Only if** (from existing data) `documents_count === 0` or there are requirements with no document / unconfirmed:  
     - Show: “You’re almost done. Upload your certificates to get an accurate score.”  
     - Per-property list of “tracked items” (Gas Safety if applicable, EICR, EPC, Licence if HMO) — **no “legally required”**; use “tracked items” language.  
     - **Upload now** → navigate to Documents (or open upload flow); after upload, show Confirm Certificate Details modal (existing behaviour). **I’ll upload later** → set “upload later” flag, show dashboard with “Provisional” score and persistent banner.

5. **Step 4 – Upload and confirm**  
   - **Reuse** existing behaviour: after upload, open Confirm Certificate Details modal.  
   - If multiple uploads: either show modal once per document or a single “X documents awaiting confirmation” state and then walk through them. No change to backend; optional small frontend “queue” for multiple uploads.

6. **Completion**  
   - When user finishes Step 2 and (if applicable) Step 3/4, set “setup checklist done” (sessionStorage or backend) and show the **main dashboard** without the checklist. Optionally remove `first_login` from URL (e.g. `replace('/dashboard')`).

7. **Banners**  
   - If user skipped checklist or chose “upload later”: on subsequent dashboard loads, show a persistent banner: “Complete setup to get an accurate score” (or “1 document requires confirmation” when that applies), with link to Documents / Setup.

This keeps provisioning and onboarding intact, reuses existing APIs and modals, and only adds a **first-login gate** and a linear setup flow in the UI.

---

## 7) Alignment with the entire provisioning and onboarding flow

| Phase | Current | With guided activation | Aligned? |
|-------|--------|-------------------------|----------|
| Intake | User fills data; may upload files. | Unchanged. | Yes. |
| Payment | Stripe checkout; webhook. | Unchanged. | Yes. |
| Provisioning | Create user, properties, requirements, migrate uploads, send activation email. | Unchanged. | Yes. |
| Activation email | Link to set-password. | Unchanged. | Yes. |
| Set password | Success → redirect to dashboard. | Success → redirect to **dashboard?first_login=1**. | Add param only. |
| First dashboard visit | Full dashboard + score. | **If first_login=1:** Setup Checklist (Step 1) → optionally Step 2 (portfolio) → Step 3 (documents prompt) → Step 4 (upload + confirm modal) → then main dashboard. **If skip:** Dashboard + “Complete setup” banner. | New UI only; dashboard API unchanged. |
| Later visits | Full dashboard. | Same, with optional “Provisional” / “documents need confirmation” banner until setup done. | Yes. |

So the guided activation path **sits between** “password set” and “main dashboard” and **does not replace** provisioning or onboarding. It only changes what the user **sees** on the first one or two visits after activation.

---

## 8) Summary

- **Understanding:** The task asks for a **guided activation path** so the first login does not land on a dashboard with a score that feels random; instead, the user sees a setup checklist, confirms portfolio, is prompted for documents (with “tracked items” language), and is led through upload + Confirm Certificate Details before or alongside the main dashboard.
- **Current state:** No first-login handling; no setup checklist; no portfolio-confirmation or documents-missing step; redirect after password set goes straight to dashboard with no `first_login` param.
- **Feasibility:** **Yes**, without breaking provisioning or onboarding, by (1) adding `?first_login=1` on post–password-set redirect, (2) gating the first dashboard render on that param (and a “checklist done” flag), and (3) implementing Steps 1–4 as UI-only flows that call existing APIs and reuse the existing confirm-details modal.
- **Safest approach:** Query param + sessionStorage (or one backend “dismiss” flag) for “checklist seen”; reuse GET dashboard, GET requirements, PATCH property, Documents page, and Confirm Certificate Details modal; add no new provisioning steps and no change to auth or onboarding-status logic.
- **Alignment:** The guided path fits **after** provisioning and **after** password set, and **before** the user is left on the main dashboard with no context. It aligns with the rest of the flow as an extra, optional “first-time setup” layer that can be skipped without breaking anything.
