# Training Manuals – Compliance Vault Pro / Pleerity Enterprise

This folder contains **structured training manuals** for the platform. All content is based on the **current codebase and implemented behaviour**; flows that are placeholder, admin-only, or not fully wired are marked as such.

---

## Intended audiences

| Audience | Description |
|----------|-------------|
| **Admin / internal staff** | Users who log in via the Admin portal (`/login/admin` or `/admin/signin`) and access `/admin/*` routes. They manage clients, billing, automation, content, and system health. |
| **Client / end user** | Users who log in via the Client portal (`/login/client`) and access the client dashboard, properties, compliance, documents, and settings. Typically landlords or property managers. |

---

## Manual index

### Admin manuals (`docs/training/admin/`)

| Manual | Audience | Covers |
|--------|----------|--------|
| [dashboard.md](admin/dashboard.md) | Admin | Admin dashboard overview: clients, search, tabs (Clients, Rules, Templates, Email delivery), quick actions. |
| [property-management.md](admin/property-management.md) | Admin | How admins view and manage client properties (via admin dashboard/client context). Property limits and provisioning. |
| [compliance-engine.md](admin/compliance-engine.md) | Admin | Backend compliance logic, requirements catalog, status computation. Admin ops compliance views (e.g. `/admin/ops/compliance`). |
| [evidence-upload.md](admin/evidence-upload.md) | Admin | Admin-side document/evidence handling: extraction queue, document management, client evidence visibility. |
| [compliance-score.md](admin/compliance-score.md) | Admin | How compliance score is calculated; admin visibility of client scores; reporting/export. |
| [admin-console.md](admin/admin-console.md) | Admin | Full admin console: navigation sections (Dashboard, Customers, Products & Services, Operations & Compliance, Content, Support, Settings & System), routes, and where to find key functions. |
| [reminder-system.md](admin/reminder-system.md) | Admin | Daily reminders job, notification health, Automation Centre, SLA watchdog, and how to monitor/troubleshoot reminder delivery. |

### Client manuals (`docs/training/client/`)

| Manual | Audience | Covers |
|--------|----------|--------|
| [dashboard.md](client/dashboard.md) | Client | Client dashboard: portfolio summary, compliance score, score trend, setup checklist, properties at a glance, operations KPIs (if entitled). |
| [property-management.md](client/property-management.md) | Client | Properties list, add property, property detail, compliance status per property, plan limits. |
| [compliance-engine.md](client/compliance-engine.md) | Client | “Compliance” (Requirements) page: view requirements by property, due dates, status, mark not applicable, link documents. |
| [evidence-upload.md](client/evidence-upload.md) | Client | Documents page: upload evidence, select property/requirement, document types, extraction and confirm details, view/delete documents. |
| [compliance-score.md](client/compliance-score.md) | Client | Compliance Score page: overall score, drivers, trend, methodology, PDF/CSV export (plan-gated). |
| [reminder-system.md](client/reminder-system.md) | Client | How reminders work (daily compliance reminders), Notification preferences (email/SMS toggles), and what users can control. |

---

## How to use these manuals

- **New staff:** Start with [admin-console.md](admin/admin-console.md) and the module that matches their role (e.g. support → reminder-system, ops → compliance-engine).
- **New clients:** Start with [client/dashboard.md](client/dashboard.md), then property-management, compliance-engine, and evidence-upload.
- **Trainers:** Each manual ends with a **Trainer walkthrough** (5–10 minutes) for live demos.
- **Gaps and unknowns:** See [TRAINING_GAP_ANALYSIS.md](TRAINING_GAP_ANALYSIS.md) for incomplete UX, flows that need runtime confirmation, and areas that may confuse users.

---

## Document conventions

- **Implemented:** Described behaviour is present in the codebase and routes.
- **Partial / placeholder:** Feature exists but is limited or not fully wired; manual states this clearly.
- **Admin-only:** Not available in the client portal.
- **Client-facing:** Available to client users (possibly plan- or feature-gated).
- **Needs runtime confirmation:** Logic is in code but not verified in a live environment; trainers should validate.

---

## Implementation notes (for trainers and QA)

| Manual type | Confirmed from codebase | Needs runtime confirmation |
|-------------|-------------------------|----------------------------|
| **Admin** | Routes, sidebar structure, API endpoints (client, admin, properties, documents, compliance-score, observability, knowledge_base), job names (daily_reminders, etc.), notification preferences and reminder logic. | Exact tab order on Admin Dashboard; Ops Compliance page content; Extraction Queue path; which admin actions open dashboard with tabTarget vs separate page; role-based visibility matrix. |
| **Client** | Routes (/dashboard, /properties, /requirements, /documents, /compliance-score, /settings/notifications), APIs (dashboard, compliance-score, score-trend, requirements, documents upload/extraction, profile/notifications), document types, requirement statuses, plan-gating (property limit, reports_pdf). | Layout order of dashboard cards; when setup checklist appears; extraction polling timeout and “extraction failed” UX; exact notification toggle labels and SMS availability per plan. |

**Admin-only manuals:** dashboard, property-management, compliance-engine, evidence-upload, compliance-score, admin-console, reminder-system (all 7 in `admin/`).

**Client-facing manuals:** dashboard, property-management, compliance-engine, evidence-upload, compliance-score, reminder-system (6 in `client/`). There is no client “Admin Console” manual; the Admin Console is admin-only.

**Trainer walkthrough:** Each manual ends with a “Trainer walkthrough” section (5–10 minutes) for live demos.

---

*Last generated from repository scan. Base implementation only; no invented or future-only behaviour.*
