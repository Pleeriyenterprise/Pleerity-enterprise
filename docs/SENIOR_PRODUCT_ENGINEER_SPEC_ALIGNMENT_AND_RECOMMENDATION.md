# Senior Product Engineer Spec — Alignment, Integration & Implementation Recommendation

**Document purpose:** Compare the "You are a senior product engineer" PDF specification with the current Compliance Vault Pro (CVP) build; assess alignment, integration feasibility, conflicts, and provide an enhancement/implementation plan without breaking existing flows.

**Status:** Analysis only — **DO NOT IMPLEMENT** until approved.

**Scope note:** The PDF contains two scopes. This report focuses on the **narrow scope** (pages 14–27): Admin + Intake/Provisioning structures only — **no** compliance engine logic, maintenance workflows, contractor network, or invoicing. The broader "Central Intelligence Layer" (pages 1–13) is referenced only where it affects data model or feature-flag design.

---

## 1. Executive Summary

| Question | Answer |
|----------|--------|
| **Does the spec align with the current build?** | **Partially.** Stack (Vercel, Render, MongoDB, Postmark) and plan pricing (Solo £19/£49, Portfolio £39/£79, Pro £79/£149, limits 2/10/25) **match**. Frontend is **React (CRA)** not Next.js; backend is **FastAPI (Python)** not Node. We use **clients** + **portal_users** not **organisations** + **memberships**. Admin has sections but no single "Operations & Compliance" tab with the specified sub-pages. Setup checklist exists but is **client-only** (sessionStorage), not server-validated or dynamic by plan/flags. |
| **Can it be integrated?** | **Yes**, in-place. Extend existing admin layout, intake/provisioning, and plan gating. Add org-level feature flags (new collection or client-level fields), provisioning-status records, and server-validated checklist. No second app or repo required. |
| **Conflicts** | (1) **Stack:** PDF assumes Next.js + Node; we have CRA + FastAPI — **keep current stack**, ignore stack assumption. (2) **Naming:** PDF uses "organisations"; we use "clients" — **keep clients**, map "org" → client_id in docs/APIs. (3) **Roles:** PDF wants Owner, Admin, Manager, Staff, Auditor; we have ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT, ROLE_CONTENT, ROLE_CLIENT_ADMIN, ROLE_CLIENT, ROLE_TENANT — **map** Owner→ROLE_OWNER, Admin→ROLE_ADMIN; add or map Manager/Staff/Auditor as needed (e.g. Auditor = read-only role). (4) **Feature flags:** PDF requires COMPLIANCE_ENGINE, COMPLIANCE_PACKS, MAINTENANCE_WORKFLOWS, etc.; we have plan-based entitlements with different keys (score_trending, audit_log_export, zip_upload, …) — **add** module-level flags (new store) and derive defaults from plan; keep existing plan_registry for billing/limits. |
| **Recommendation** | **In-place enhancement.** (1) Add **Admin + Intake Integration Report** per PDF Step 0 (`/docs/ADMIN_INTAKE_REPORT.md`). (2) Implement feature flags (module keys), Operations & Compliance tab + sub-pages (Overview, Compliance, Maintenance, Contractors, Risk & Insights, Audit & Logs, Feature Controls). (3) Harden audit logging for admin actions (role changes, feature toggles, plan overrides). (4) Server-validated setup checklist + progressive enrichment + provisioning-status hooks. (5) Jurisdiction as first-class on Property; plan/seat usage in admin. No breaking changes to existing intake submit, checkout, or provisioning core. |

---

## 2. Stack and Naming (Conflicts Resolved)

| PDF assumption | Current build | Resolution |
|----------------|---------------|------------|
| Frontend: Next.js + TS | React (CRA) + JavaScript | **Keep CRA/React.** Do not migrate to Next.js for this spec. |
| Backend: Node (Express/Nest/Next API) | FastAPI (Python) | **Keep FastAPI.** All new APIs in Python. |
| organisations, memberships | clients, portal_users | **Keep clients.** Treat client_id as orgId in audit/APIs. "Memberships" = portal_users (user + client_id + role). |
| orgId everywhere | client_id everywhere | **Keep client_id.** Add optional alias in API responses (e.g. org_id: client_id) for clarity if needed. |

---

## 3. What Exists vs What the PDF Requires

### 3.1 Plans and pricing

| Requirement | Current | Gap |
|-------------|---------|-----|
| Solo: £19/mo, 1–2 properties, £49 setup | PLAN_1_SOLO: £19, 2 props, £49 onboarding | **Match.** (PDF says "1–2", we cap at 2.) |
| Portfolio: £39/mo, 2–10 properties, £79 setup | PLAN_2_PORTFOLIO: £39, 10 props, £79 | **Match.** |
| Professional: £79/mo, up to 25 properties, £149 setup | PLAN_3_PRO: £79, 25 props, £149 | **Match.** |
| Plan enforcement at API | `plan_registry.check_property_limit` at intake submit; `plan_registry.enforce_property_limit` at property create/import | **Exists.** |
| Upgrade CTA when at limit | Intake: PropertyLimitPrompt, upgrade prompt; Properties: enforce_property_limit returns upgrade_to | **Exists.** |

### 3.2 Admin dashboard and navigation

| Requirement | Current | Gap |
|-------------|---------|-----|
| Single admin experience, no separate app | UnifiedAdminLayout, all admin under /admin/* | **Exists.** |
| "Operations & Compliance" top-level tab | No. We have: Dashboard, Customers, Products & Services, ClearForm, Content, Support, Settings & System | **Add** new section "Operations & Compliance" with sub-items. |
| Sub-sections: Overview, Compliance, Maintenance, Contractors, Risk & Insights, Audit & Logs, Feature Controls | We have System Health, Automation, Incidents, Audit Logs (tab on dashboard). No Overview/Compliance/Maintenance/Contractors/Risk/Feature Controls as one group | **Add** routes and pages; wire to data contracts (placeholders where modules don't exist). |
| Plan usage and limits in admin | Dashboard shows clients; plan in client detail. No dedicated "properties used / allowed" and "seats used / allowed" widget | **Add** plan usage widget (property count vs limit); seat usage structure (can be 0/0 until seats implemented). |
| Audit Log for admin actions (filter/search) | `audit_logs` collection; create_audit_log(); admin GET /admin/audit-logs with filters. Actions logged: many (e.g. COMPLIANCE_SCORE_REPAIRED, document actions). Role changes, feature toggles, plan overrides may not all be logged | **Extend** audit logging for role changes, feature-flag changes, plan-limit exceptions; ensure admin UI can filter by actionType, entityType, client_id. |

### 3.3 Roles and permissions

| Requirement | Current | Gap |
|-------------|---------|-----|
| Owner, Admin, Manager, Staff, Auditor | ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT, ROLE_CONTENT, ROLE_CLIENT_ADMIN, ROLE_CLIENT, ROLE_TENANT | **Map:** Owner→ROLE_OWNER, Admin→ROLE_ADMIN. Add or map Manager (e.g. ROLE_SUPPORT with more scope), Staff, Auditor (read-only). permissions.py has custom roles (Super Admin, Manager, etc.) for a different system. |
| Only Owner/Admin can change flags, plan settings, roles | admin_route_guard allows admin users; require_owner, require_owner_or_admin used for sensitive ops | **Add** explicit guards for "feature flags" and "roles" so only Owner/Admin can change; Auditor can view only. |
| Auditor: view dashboards and audit logs, no edit | No dedicated Auditor role; ROLE_SUPPORT has limited nav (dashboard, support) | **Add** ROLE_AUDITOR or reuse a read-only role; restrict write endpoints. |

### 3.4 Feature flags (module-level)

| Requirement | Current | Gap |
|-------------|---------|-----|
| Org-level feature flags (MongoDB) | No. Plan-based entitlements in plan_registry (MINIMUM_PLAN_FOR_FEATURE, feature keys like score_trending, zip_upload). feature_entitlement.py deprecated | **Add** new store: e.g. `client_feature_flags` or `feature_flags` (client_id, flag_key, enabled, source, updated_by, updated_at). Flag keys: COMPLIANCE_ENGINE, COMPLIANCE_PACKS, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE, CONTRACTOR_NETWORK, INVOICING. |
| Defaults derived from plan | plan_registry defines which plan gets which feature | **Derive** default flags from plan (e.g. Solo: COMPLIANCE_ENGINE + COMPLIANCE_PACKS on; MAINTENANCE off). Override per client for "request enablement". |
| UI: view flags + request enablement | No | **Add** admin "Feature Controls" page: show plan, flags state, "Request enablement" for locked modules. |
| Server-enforced route + API guards | require_feature(feature_key) uses plan_registry | **Add** checks that read from new feature-flag store (and plan defaults) so module access is enforced server-side. |

### 3.5 Intake and provisioning

| Requirement | Current | Gap |
|-------------|---------|-----|
| Keep existing intake as entry point | 5-step intake (Your Details, Plan, Properties, Preferences, Review) → submit → checkout | **No change.** |
| Post-signup Setup Checklist (dynamic by plan + flags) | First-login checklist on ClientDashboard when ?first_login=1; sessionStorage; static items (portfolio, documents, certs, reminders, report); not server-validated; not dynamic by plan/flags | **Add** server-side checklist: stored per client (e.g. onboarding_checklist: { items[], completedAt? }). Items derived from plan + flags (e.g. "Add properties", "Set jurisdictions", "Confirm property attributes", "Invite team", "Upload certificates" if compliance on, "Enable maintenance" if flag available). |
| Checklist completion server-validated | Completion is sessionStorage only | **Add** API to get checklist state (from server) and PATCH to mark item complete (server validates e.g. "Add properties" only if client has ≥1 property). |
| Deep-links from checklist to right screen | Checklist is linear (checklist → portfolio → documents); no per-item deep-links | **Add** deep-links (e.g. /dashboard?setup=properties, /properties, /documents) and banner until checklist done. |
| Progressive enrichment (don’t add 30 fields to intake) | Intake already has property fields (address, type, bedrooms, occupancy, HMO, licence, certs). No separate "enrichment" flow | **Add** enrichment prompts when: user adds property, enables compliance module, or requests pack. Ask only missing: jurisdiction, hasGas, hasFixedCombustion, floors, propertyType, HMO. |
| Provisioning Hook after property create/update | Provisioning runs after payment (requirements, recalc queue, portal user, invite). No "hook" that creates provisioning-status records per module | **Add** hook (or extend provisioning): validate property completeness; write provisioning_status records (client_id, property_id, module_name, status, missing_fields[], updated_at). Do NOT generate obligations (out of scope). |
| Jurisdiction first-class on Property; Scotland-first; all UK | Property has local_authority, local_authority_code; councils API has nation (England, Wales, Scotland, NI). No explicit jurisdiction field on Property | **Add** jurisdiction (enum: Scotland, England, Wales, Northern_Ireland) on Property. Default from council/nation or org default. Org default: defaultJurisdiction (e.g. Scotland), enabledJurisdictions[]. |
| Existing customers migrated to checklist | — | **Migration:** existing clients get onboarding_checklist with "Add properties" marked complete if they already have properties. |

### 3.6 Data model (MongoDB)

| PDF collection / concept | Current | Gap |
|--------------------------|---------|-----|
| organisations (defaultJurisdiction, enabledJurisdictions, planId, onboardingChecklist, featureFlags) | clients (billing_plan, subscription_status, …). No defaultJurisdiction, enabledJurisdictions, onboardingChecklist, or module feature flags | **Add** to client (or new org doc keyed by client_id): default_jurisdiction, enabled_jurisdictions[], onboarding_checklist: { items[], completed_at? }. New: feature_flags store. |
| featureFlags (orgId, flagKey, enabled, source, updatedBy, updatedAt) | — | **New** collection or embedded in client. |
| memberships (orgId, userId, role) | portal_users (client_id, role, auth_email, …) | **Exists** (client_id = orgId). |
| auditEvents (orgId, actorUserId, actionType, entityType, entityId, diff, at, ip?, userAgent?) | audit_logs (client_id, action, actor_id, resource_type, resource_id, before_state, after_state, metadata, timestamp). create_audit_log() with diff in metadata | **Near match.** Add logging for role changes, feature toggles, plan overrides; optional ip, user_agent. |
| provisioningStatus (orgId, propertyId, moduleName, status, missingFields[], updatedAt) | — | **New** collection (or embed per property). |

### 3.7 Property and jurisdiction

| Requirement | Current | Gap |
|-------------|---------|-----|
| jurisdiction first-class on Property | local_authority, local_authority_code; requirement_catalog uses property attrs | **Add** jurisdiction field (Scotland, England, Wales, Northern_Ireland). Populate from council nation or org default. |
| Scotland-first onboarding | Councils support nation filter; no default jurisdiction in intake | **Add** org default_jurisdiction (default Scotland); in intake/property flow prefill or suggest Scotland. |

---

## 4. Conflicting Instructions and Safest Option

| Conflict | PDF | Current / risk | Safest option |
|----------|-----|-----------------|---------------|
| Stack | Next.js + Node | CRA + FastAPI in production | **Keep current stack.** Do not rewrite for this spec. |
| Org vs client | "organisations" | clients | **Keep client_id.** Use "organisation" only in user-facing copy if desired; internally stay with client. |
| Feature flags vs plan entitlements | Module flags (COMPLIANCE_ENGINE, …) | Plan-based entitlements (score_trending, zip_upload, …) | **Both.** New module-level flags (for future compliance/maintenance/contractor/invoicing) with defaults from plan. Keep plan_registry for billing and existing gating. |
| Checklist storage | Server-side, dynamic | Client-side sessionStorage | **Add server-side checklist.** Keep sessionStorage only as UX cache; authoritative state in DB. |
| "Do not build compliance engine…" | Build only admin + onboarding structures | We already have compliance engine (requirements, scoring, ledger) | **No conflict.** PDF says do not build *new* compliance engine logic; our existing engine stays. New work: admin UI and feature flags that will *support* modules (existing or future). |

---

## 5. Implementation Plan (No Breaking Changes)

Follow PDF implementation order; each step preserves existing behaviour.

### Step 0 — Repo inspection and report (done in this document)

- Produce **Admin + Intake Integration Report** at `/docs/ADMIN_INTAKE_REPORT.md` (or fold into this doc). Contents: dashboard routes/layout, where admin lives, onboarding/intake/provisioning flow, auth/roles, plan enforcement, and minimal-change approach (extend admin with new tab(s), extend intake with checklist + enrichment).

### Step 1 — Feature flags + plan gating

- Add **feature flag store**: collection or embedded doc with (client_id, flag_key, enabled, source, updated_by, updated_at). Keys: COMPLIANCE_ENGINE, COMPLIANCE_PACKS, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE, CONTRACTOR_NETWORK, INVOICING.
- **Defaults from plan:** Solo: COMPLIANCE_ENGINE + COMPLIANCE_PACKS on; others off. Portfolio: + optional maintenance. Pro: + maintenance on, contractor optional.
- **API:** GET/PATCH flags for a client (admin only); resolve effective flags (plan default + overrides).
- **Guards:** Middleware or decorator that checks effective flags for module-scoped routes (when those modules exist); only Owner/Admin can PATCH flags.
- **UI:** "Feature Controls" under Operations & Compliance: show plan, each flag, "Request enablement" (or admin toggle if role allows).
- **Audit:** Log feature-flag changes (create_audit_log with action e.g. FEATURE_FLAG_CHANGED).

### Step 2 — Core portfolio model + multi-jurisdiction

- **Property:** Add `jurisdiction` (enum: Scotland, England, Wales, Northern_Ireland). Optional: build_year, has_fixed_combustion, floors, units (if not already present).
- **Client:** Add `default_jurisdiction` (default Scotland), `enabled_jurisdictions` (array of the four). Use in property defaults and validation.
- **Intake:** When adding property, allow or default jurisdiction (e.g. from council nation or org default). No need to add 30 fields; keep current intake fields, add jurisdiction where it fits (e.g. per property or org-level in a later step).
- **Indexes:** property: jurisdiction; client: default_jurisdiction if queried.

### Step 3 — Compliance engine + evidence + audit + packs (structure only)

- **No new engine logic.** Ensure admin "Compliance" sub-page exists and is wired to data contracts (e.g. list obligations/evidence from existing requirements/documents). Placeholder UI for "setup state" from provisioning_status when that exists.
- **Audit:** Ensure admin actions (e.g. role change, flag change, plan override) call create_audit_log with consistent action/resource_type/resource_id. Add AuditAction enum values if missing (ROLE_CHANGED, FEATURE_FLAG_CHANGED, PLAN_LIMIT_OVERRIDE).
- **Compliance packs:** Already exist (compliance_pack, reports). Expose in admin Compliance section if not already.

### Step 4 — Operations & Compliance tab + sub-pages

- **Nav:** Add section "Operations & Compliance" (visible to Owner/Admin; Auditor sees read-only). Sub-items: Overview, Compliance, Maintenance, Contractors, Risk & Insights, Audit & Logs, Feature Controls.
- **Overview:** Cards for Compliance, Maintenance, Contractors, Risk, Audit; each shows enabled/disabled (from flags) and setup state (from provisioning_status when implemented). CTA "Complete setup" / "Enable module".
- **Compliance / Maintenance / Contractors / Risk:** Placeholder or existing data (e.g. Compliance = requirements/documents summary). Wire to same data contracts so when modules are built, they drop in.
- **Audit & Logs:** Existing audit log viewer; ensure filters (action, client_id, entityType, date range) and that new admin actions are logged.
- **Feature Controls:** Implemented in Step 1.

### Step 5 — Audit log extension and roles

- **Log:** Role changes, feature toggles, plan-limit exceptions, onboarding overrides. Schema already supports action, actor_id, client_id, resource_type, resource_id, metadata, timestamp; add diff or before/after where useful.
- **Roles:** Define Auditor (read-only admin): can view dashboard and audit logs, cannot edit. Implement guard so write endpoints reject Auditor. Map Manager/Staff if needed (e.g. Manager = can manage team, Staff = limited scope).

### Step 6 — Onboarding checklist (server-validated)

- **Model:** onboarding_checklist on client: { items: [{ id, label, required, completed_at?, deep_link }], completed_at? }.
- **Derive items from plan + flags:** e.g. "Add properties" (required), "Set jurisdictions" (required), "Confirm property attributes" (recommended), "Invite team" (Portfolio/Pro), "Upload certificates" (if COMPLIANCE_ENGINE), "Enable maintenance" (if flag available).
- **API:** GET onboarding/checklist (returns items + completion); PATCH onboarding/checklist/items/:id/complete (server validates e.g. "Add properties" only if client has ≥1 property).
- **Dashboard:** Until checklist complete, show banner with deep-links; first-login flow can still show checklist UI but drive it from API. Mark "Add properties" complete if client already has properties (migration).

### Step 7 — Progressive enrichment + provisioning status

- **Enrichment:** When user adds/edits property or when they hit "Enable compliance" (or request pack): if jurisdiction, hasGas, hasFixedCombustion, floors, propertyType missing, show modal or inline prompts. Save to property.
- **Provisioning hook:** After property create/update (and optionally after payment provisioning), call internal hook: validate property (required fields per module); write provisioning_status (client_id, property_id, module_name, status: not_configured | configured | blocked, missing_fields[], updated_at). Do not create obligations.

### Step 8 — Plan usage in admin and runbook

- **Admin dashboard:** Widget or section: "Plan usage" — properties used / allowed (from plan_registry + client property count); seats used / allowed (0/0 or placeholder until seats implemented).
- **RUNBOOK:** Add `/docs/ADMIN_INTAKE_RUNBOOK.md`: how to enable a module for a client, how onboarding checklist works, how to change roles, how to verify plan limits.

### Step 9 — Migrations and tests

- **Migration:** For existing clients, set default_jurisdiction (e.g. Scotland), enabled_jurisdictions (all four), and onboarding_checklist with "Add properties" completed if they have properties.
- **Tests:** Unit tests for plan limit enforcement (already exist); integration tests for role guard (e.g. Staff/Auditor cannot toggle flags), checklist completion logic (server validation), audit append-only behaviour.

---

## 6. What Not to Do (Avoid Duplication and Conflict)

- **Do not** introduce a second admin app or separate repo; extend existing admin.
- **Do not** replace existing intake with a new wizard; extend with checklist and enrichment.
- **Do not** build compliance engine logic, maintenance workflows, contractor network, or invoicing (per narrow scope); only structures (flags, provisioning status, placeholders).
- **Do not** migrate to Next.js or Node for this spec.
- **Do not** rename client → organisation in the database or API; keep client_id.
- **Do not** remove or replace plan_registry; add module flags alongside it.

---

## 7. Recommendation Summary

- **In-place enhancement** is feasible and recommended. No separate service or repo.
- **Resolve conflicts** by keeping current stack (CRA + FastAPI), client_id, and plan_registry; add module feature flags, server-side checklist, provisioning_status, and jurisdiction; extend audit logging for admin actions.
- **Order of work:** Step 0 report → feature flags + plan gating → jurisdiction + checklist + provisioning status → Operations & Compliance tab + sub-pages → audit + roles → migrations + tests + runbook.
- **Risk:** Low if changes are additive (new collections or fields, new routes, new UI sections). Existing intake submit, checkout, and provisioning core remain unchanged; new hooks and checklist APIs are additive.

---

*Reference: "You are a senior product engineer" PDF (narrow scope: Admin + Intake/Provisioning). Current build: BUSINESS_FLOW_AND_USER_JOURNEY_REPORT.md, UnifiedAdminLayout.js, plan_registry.py, feature_gating.py, ClientDashboard.js (setup checklist), intake.py, provisioning.py, utils/audit.py, models/core.py.*
