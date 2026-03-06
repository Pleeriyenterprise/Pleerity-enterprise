# Admin + Intake Integration Report (Step 0)

**Purpose:** Repo inspection for extending the app with Operations & Compliance admin and post-signup setup checklist. Answers: where admin lives, current intake/provisioning, auth/roles, plan enforcement, and minimal-change approach.

---

## 1) Dashboard routes, layout, and where admin lives

| Item | Location | Notes |
|------|----------|-------|
| **Admin entry** | `/admin/*` routes (React Router) | All admin pages wrapped with auth; redirect to login if not authenticated. |
| **Layout** | `frontend/src/components/admin/UnifiedAdminLayout.js` | Single sidebar layout; logo, nav sections, user menu, notification bell. |
| **Nav sections** | Dashboard, Customers, Products & Services, ClearForm, Content Management, Support, Settings & System | Each section has icon and items (href + label). No "Operations & Compliance" section yet. |
| **Main dashboard** | `frontend/src/pages/AdminDashboard.js` | Tabbed: Overview, Clients, Orders, Audit Logs, etc. (tabTarget in nav). |
| **Other admin pages** | Under `frontend/src/pages/`: AdminBillingPage, AdminSystemHealthPage, AdminAutomationCentrePage, AdminIncidentsPage, AdminOrdersPage, etc. | Routes defined in `App.js` (e.g. `/admin/dashboard`, `/admin/system-health`, `/admin/automation`, `/admin/incidents`, `/admin/team`, `/admin/billing`). |
| **Visibility by role** | `UnifiedAdminLayout.js`: SECTIONS_FOR_SUPPORT, SECTIONS_FOR_CONTENT; ownerOrAdminOnly on some items | Support sees dashboard + support; Content sees dashboard + content; Owner/Admin see all. |

**Conclusion:** Admin is a single experience under `/admin/*` with UnifiedAdminLayout. Minimal-change approach: **add one new nav section** "Operations & Compliance" and new routes for Overview, Compliance, Maintenance, Contractors, Risk & Insights, Audit & Logs, Feature Controls. Reuse existing Audit Logs (tab or link) for "Audit & Logs" or add dedicated page with filters.

---

## 2) Current onboarding / intake flow and provisioning

| Stage | Implementation | Endpoints / routes |
|-------|----------------|--------------------|
| **Intake** | 5-step wizard: Your Details, Select Plan, Properties, Preferences, Review | `frontend/src/pages/IntakePage.js`. Submit → `POST /api/intake/submit`; creates client + properties (no entitlement yet). |
| **Checkout** | Create Stripe session, redirect to Stripe | `POST /api/intake/checkout?client_id=...` → returns checkout_url; frontend redirects. |
| **Post-payment** | Stripe webhook `checkout.session.completed` | `stripe_webhook_service`: sets subscription_status, billing_plan, entitlement_status; creates provisioning job (provisioning_jobs). |
| **Provisioning** | Job: requirements per property, compliance recalc queue, portal user, migrate intake uploads, send set-password email | `provisioning_service.provision_client_portal_core`; optionally run in webhook or via `run_provisioning_poller.py`. Client onboarding_status → PROVISIONED. |
| **Password setup** | Token in email; set password; redirect to portal | `GET /api/portal/set-password?token=...`; frontend SetPasswordPage → redirect to `/dashboard?first_login=1`. |
| **First login** | Dashboard with ?first_login=1 shows setup checklist (client-side) | `ClientDashboard.js`: setup checklist (portfolio → documents) with sessionStorage; no server-side checklist. |

**Conclusion:** Keep existing intake and checkout as entry point. **Extend** with: (1) server-side onboarding checklist (items derived from plan + feature flags), (2) API to get/complete checklist, (3) provisioning hook that writes provisioning_status per property/module. Do not create a second intake flow.

---

## 3) Current auth / roles implementation

| Item | Implementation | Notes |
|------|----------------|-------|
| **Auth** | JWT (Bearer); auth context in frontend; backend middleware | Login → token stored; requests send Authorization header. |
| **Admin guard** | `admin_route_guard(request)` (backend); frontend protects /admin routes | Only users with admin-capable roles can access /api/admin/* and /admin/*. |
| **Roles** | `backend/models/core.py`: UserRole enum | ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT, ROLE_CONTENT, ROLE_CLIENT_ADMIN, ROLE_CLIENT, ROLE_TENANT. |
| **Stored** | `portal_users` collection: role, client_id (for client users), auth_email | One role per user. |
| **Owner vs Admin** | require_owner, require_owner_or_admin in admin routes | Some endpoints restrict to Owner only (e.g. billing/plan overrides). |
| **Custom roles** | `backend/models/permissions.py`: BUILT_IN_ROLES, custom role builder | Different system (e.g. Super Admin, Manager); used in some admin user flows. |

**Conclusion:** Auth and roles exist. Map PDF "Owner, Admin, Manager, Staff, Auditor" to existing roles and add Auditor (read-only) if needed. Ensure only Owner/Admin can change feature flags and roles; Auditor can view only.

---

## 4) Current plan enforcement

| Item | Implementation | Notes |
|------|----------------|-------|
| **Source of truth** | `backend/services/plan_registry.py` | PlanCode enum (PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO); PLAN_DEFINITIONS (name, monthly_price, onboarding_fee, max_properties); Stripe price IDs from env. |
| **Intake submit** | `plan_registry.check_property_limit(plan_code, len(properties))` | 403 PROPERTY_LIMIT_EXCEEDED if over limit. |
| **Property create / import** | `plan_registry.enforce_property_limit(client_id, current_count + n)` | Returns allowed, error_msg, upgrade_to; used in properties routes. |
| **Feature access** | plan_registry MINIMUM_PLAN_FOR_FEATURE + require_feature() decorator | Client must have subscription ACTIVE/TRIALING and plan that includes feature. |
| **Frontend** | UpgradePrompt, PropertyLimitPrompt, EntitlementsContext, EntitlementProtectedRoute | Show upgrade CTA when at limit or when feature not in plan. |

**Conclusion:** Plan enforcement is in place at API and UI. Add **plan usage widget** in admin (properties used/limit; seats 0/0 placeholder). Add **module-level feature flags** (separate from plan_registry) for COMPLIANCE_ENGINE, MAINTENANCE_WORKFLOWS, etc., with defaults derived from plan.

---

## 5) Minimal-change approach (decision)

| Decision | Approach |
|----------|----------|
| **Admin** | **Extend** existing UnifiedAdminLayout with one new section "Operations & Compliance" and sub-routes (Overview, Compliance, Maintenance, Contractors, Risk & Insights, Audit & Logs, Feature Controls). Reuse or duplicate Audit Log viewer for Audit & Logs. Add plan usage and feature-flag UI. |
| **Intake** | **Do not** create a new intake. **Extend** post-signup experience: server-side onboarding checklist (GET/PATCH API), dynamic items by plan + flags, deep-links, banner until complete. Optional: progressive enrichment when adding property or enabling module (prompt for jurisdiction, hasGas, etc.). |
| **Provisioning** | **Extend** with a **hook** after property create/update (and optionally after core provisioning): write provisioning_status (client_id, property_id, module_name, status, missing_fields[]). No new obligation generation. |
| **Data** | **Add** fields/collections: client (default_jurisdiction, enabled_jurisdictions, onboarding_checklist), feature_flags (or client-level), provisioning_status; Property.jurisdiction. **Keep** existing clients, properties, portal_users, audit_logs. |

---

*This report supports the implementation plan in docs/SENIOR_PRODUCT_ENGINEER_SPEC_ALIGNMENT_AND_RECOMMENDATION.md.*
