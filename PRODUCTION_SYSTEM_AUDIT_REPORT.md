# Production System Audit Report

**Date:** 2026-02-12  
**Scope:** Full system audit for production launch (no code changes)  
**Source of truth:** `backend/services/plan_registry.py` (Solo 2 / Portfolio 10 / Professional 25; £19 / £39 / £79; feature matrix)

---

## Executive summary

The codebase has **one canonical plan source** (`plan_registry.py`) but **three parallel gating systems** (plan_registry, plan_gating, feature_entitlement). Several routes and the feature-gating middleware use the wrong field or the wrong system, leading to incorrect property caps, feature leakage, and possible denial of paid features. The intake → Stripe → provisioning → email → portal flow is largely correct; document generation uses prompts correctly; compliance score and background jobs have minor risks. Admin lockout is partially mitigated (self-deactivation blocked) but there is no “last admin” safeguard.

---

## 1. Plan feature gating (Solo, Portfolio, Professional)

### 1.1 Pricing table (source of truth) – `backend/services/plan_registry.py`

| Plan              | Code            | Properties | Monthly | Onboarding |
|-------------------|-----------------|------------|---------|------------|
| Solo Landlord     | PLAN_1_SOLO     | 2          | £19     | £49        |
| Portfolio         | PLAN_2_PORTFOLIO| 10         | £39     | £79        |
| Professional      | PLAN_3_PRO      | 25         | £79     | £149       |

`FEATURE_MATRIX` and `MINIMUM_PLAN_FOR_FEATURE` in `plan_registry.py` define which features each plan gets. This is the only source that matches the intended 2/10/25 and Solo/Portfolio/Pro naming.

### 1.2 Inconsistencies and issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 1 | **CRITICAL** | Feature-gating middleware reads `plan_code` from client; DB stores only `billing_plan`. So `client.get("plan_code", "PLAN_1_SOLO")` is always the default. All users are effectively gated as Solo on middleware-protected routes. | `backend/middleware/feature_gating.py` (lines 41–42, 58–59) | Client document has `billing_plan`, never `plan_code`. | Use `billing_plan` in middleware (and project it as `plan_code` in responses if needed). Resolve plan via `plan_registry._resolve_plan_code(client.get("billing_plan", "PLAN_1_SOLO"))`. |
| 2 | **CRITICAL** | `plan_gating.py` uses legacy plans only (PLAN_1, PLAN_2_5, PLAN_6_15) with **max_properties 1, 5, 15**. Clients with PLAN_1_SOLO / PLAN_2_PORTFOLIO / PLAN_3_PRO fall back to PLAN_1 and get wrong limits and wrong feature set. | `backend/services/plan_gating.py` (PLAN_FEATURES, MINIMUM_PLAN_FOR_FEATURE) | Legacy plan enum and matrix never updated for new plan codes. | Either deprecate plan_gating and use plan_registry everywhere, or add PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO to plan_gating with 2/10/25 and aligned features. |
| 3 | **CRITICAL** | `feature_entitlement.py` uses same legacy plans (PLAN_1, PLAN_2_5, PLAN_6_15) with **max_properties 1, 5, 15**. PLAN_1_SOLO not in PLAN_FEATURE_MATRIX → defaults to PLAN_1 (1 prop, tenant_portal True). So Solo gets wrong limit and feature leakage (e.g. tenant_portal). | `backend/services/feature_entitlement.py` (PLAN_FEATURE_MATRIX, lines 171–273) | Matrix keyed only by legacy BillingPlan values. | Add PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO to PLAN_FEATURE_MATRIX with 2/10/25 and features matching plan_registry; or route all entitlement checks through plan_registry. |
| 4 | **MAJOR** | Routes mix three systems: (a) `require_feature()` middleware (plan_registry logic but wrong client field), (b) `plan_gating_service.enforce_feature()`, (c) `feature_entitlement_service.enforce_feature()`. Reports and documents use (a) and (c); webhooks use (b). Inconsistent behaviour and wrong limits/features where (b)/(c) are used. | `backend/routes/reports.py`, `backend/routes/documents.py`, `backend/routes/client.py`, `backend/routes/calendar.py`, `backend/routes/webhooks_config.py` | No single enforcement path; legacy services not aligned with plan_registry. | Standardise on plan_registry for all plan/feature checks; migrate routes to plan_registry.enforce_feature() and fix middleware to use billing_plan. |
| 5 | **MINOR** | `ENDPOINT_FEATUREKEY_MAPPING.md` uses different feature names (e.g. COMPLIANCE_DASHBOARD) and says some features are “PROFESSIONAL only” (e.g. CSV, SMS, tenant) while plan_registry has them at PLAN_2_PORTFOLIO. | `ENDPOINT_FEATUREKEY_MAPPING.md` | Doc not updated when plan_registry was defined. | Update doc to match plan_registry (snake_case keys, correct minimum plan per feature). |

---

## 2. Property caps (2 / 10 / 25)

### 2.1 Where caps are enforced

- **Intake:** `backend/routes/intake.py` uses `plan_registry.check_property_limit(plan_code, len(data.properties))` and `plan_registry.get_property_limit(plan_code)` — **correct** (2/10/25).
- **Stripe webhook / billing:** Uses plan_registry for plan and limits — **correct**.

### 2.2 Where caps are wrong or inconsistent

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 6 | **CRITICAL** | Any code that uses `plan_gating` or `feature_entitlement` for limits returns **1 / 5 / 15** (e.g. get_client_plan_info, get_client_entitlements). Frontend that shows “max_properties” from `/client/entitlements` can show 1 for Solo instead of 2. | `backend/services/plan_gating.py`, `backend/services/feature_entitlement.py`, frontend BillingPage/UpgradePrompt | Legacy matrices use 1/5/15. | Use plan_registry for all property limit and entitlement APIs; or add new plan codes to feature_entitlement/plan_gating with 2/10/25. |
| 7 | **MAJOR** | `routes/properties.py` uses `client.get("plan_code", "PLAN_1_SOLO")` and `plan_registry.get_plan(plan_code)`. Client has `billing_plan`, not `plan_code`, so default is always used; plan-specific limit in response can be wrong if client had no plan_code set. | `backend/routes/properties.py` (line 51) | Same wrong field as middleware. | Read `billing_plan` and resolve via plan_registry.get_plan_by_code_string(). |
| 8 | **MINOR** | Intake route exposes `plan_registry.get_all_plans()` and validate-property-count uses plan_registry — correct. No backend inconsistency for intake flow itself. | — | — | None for intake; ensure all other “plan info” endpoints use plan_registry and billing_plan. |

---

## 3. Client intake → Stripe payment → provisioning → welcome email → portal access

### 3.1 Flow (verified)

1. **Intake:** `POST /intake/submit` creates client (with `email`, `billing_plan`), properties, and stores intake. Client has `onboarding_status: INTAKE_PENDING`.
2. **Checkout:** Client hits Stripe Checkout (subscription mode) with `metadata.client_id`. Session includes subscription + onboarding line items.
3. **Stripe webhook:** `checkout.session.completed` (mode=subscription) → `_handle_subscription_checkout` in `stripe_webhook_service.py`: derives plan from subscription price_id via plan_registry, upserts `client_billing`, updates `clients` with `billing_plan`, `subscription_status`, `entitlement_status`.
4. **Provisioning:** If entitlement is ENABLED and client not yet PROVISIONED, `provisioning_service.provision_client_portal(client_id)` is called: sets PROVISIONING, creates requirements per property, creates PortalUser (ROLE_CLIENT_ADMIN) with `auth_email=client["email"]`, sets PROVISIONED, sends password-setup link.
5. **Email:** After provisioning, `send_payment_received_email` is sent (payment received + portal link). Password setup email is sent in provisioning. There is no separate “welcome” template for CVP; “welcome” is effectively payment received + password setup.
6. **Portal access:** PortalUser is created with INVITED status; after password set, user can log in. No lockout of client admin from portal once provisioned.

### 3.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 9 | **MINOR** | Provisioning uses `client["email"]` and `client["full_name"]`. Client model and intake set `email` (not only contact_email). If any code path created a client with only `contact_email`, portal user could have wrong email. | `backend/services/provisioning.py` (lines 167, 208) | Reliance on single `email` field. | Ensure all client-creation paths set `email`; optionally fallback to `contact_email` if `email` missing and document single source. |
| 10 | **MINOR** | `send_payment_received_email` is sent after provisioning; if provisioning fails, client still gets “payment received” with portal link. Acceptable but could confuse if portal not yet ready. | `backend/services/stripe_webhook_service.py` (lines 416–430) | Email sent whenever entitlement is ENABLED, regardless of provisioning success. | Consider sending payment-received only after successful provisioning, or add a line “If you don’t receive a separate password email, contact support.” |
| 11 | **MINOR** | Order intake (mode=payment, type=order_intake) is a separate path: draft → order, no CVP provisioning. Document-pack flow is consistent. No issue identified. | — | — | None. |

---

## 4. Owner / admin access (lockout prevention)

### 4.1 Current behaviour

- Admin routes require `ROLE_ADMIN`. Admin list/invite/deactivate/reactivate live in `backend/routes/admin.py`.
- **Self-deactivation:** A user cannot deactivate themselves (`portal_user_id` check).
- **Last admin:** There is **no** check that at least one admin must remain. If there are two admins, A can deactivate B; then only A remains. If the last admin is disabled by external action (e.g. DB, bug, or future “disable all” logic), there is no in-app recovery path documented.

### 4.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 12 | **MAJOR** | Last admin can be deactivated by another admin, or the only admin could be disabled by DB/script. No “at least one admin” rule or recovery flow. | `backend/routes/admin.py` (deactivate_admin, lines 2029–2090) | No minimum-admin count or safeguard. | Before deactivating, count active admins; if count would become 0, return 400 with clear message. Document a recovery procedure (e.g. direct DB update or script to reactivate one admin). |
| 13 | **MINOR** | plan_registry comment says “Admin access is never plan-gated.” Middleware and route guards skip gating for `ROLE_ADMIN`. No plan-gating of admin routes found. | — | — | None. |

---

## 5. Document generation pipeline (prompts vs raw intake)

### 5.1 Flow (verified)

- **Orchestrator:** `document_orchestrator.py` – validates intake, creates immutable intake snapshot, selects prompt (registry or prompt_manager_bridge), builds user prompt with intake data, runs GPT, then template_renderer for DOCX/PDF. Snapshot is taken **before** GPT; prompt template controls what is sent (e.g. `{{INPUT_DATA_JSON}}` or structured placeholders).
- **Prompt build:** `_build_user_prompt` uses `prompt_def.user_prompt_template.format(**data)` (with safe fallback for missing keys). So output is **prompt-driven**, not a raw dump, unless the template is literally only `{{INPUT_DATA_JSON}}`.
- **Rendering:** `template_renderer.render_from_orchestration` uses **structured_output** from GPT plus intake_snapshot, not raw intake as document body. Comment at line 383: “Prevents rendering empty documents or raw intake as content.”

### 5.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 14 | **MINOR** | If a prompt template is created that only injects `{{INPUT_DATA_JSON}}` with no instruction, output could be a raw JSON dump. No automated check that templates structure the data. | `backend/services/document_orchestrator.py`, prompt manager | Templates are flexible. | Operational: review prompt templates before activation; consider a rule or test that active prompts must contain structuring instructions, not only INPUT_DATA_JSON. |
| 15 | **MINOR** | Document pack / order flow uses same orchestrator and snapshot; document_versions store prompt_version_used. No inconsistency found. | — | — | None. |

---

## 6. Compliance score accuracy and calculation flow

### 6.1 Flow (verified)

- `backend/services/compliance_score.py`: `calculate_compliance_score(client_id)` loads properties and requirements, computes weighted score (Requirement Status 35%, Expiry 25%, Document coverage 15%, Overdue 15%, Risk 10%). Requirement type weights use `get_requirement_weight(req_type)` with `req_type.upper()` (e.g. `gas_safety` → `GAS_SAFETY`). Provisioning creates requirements with `requirement_type` = rule type (e.g. `gas_safety`, `eicr`), so casing is consistent after `.upper()`.

### 6.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 16 | **MINOR** | If a new requirement type is added in provisioning (e.g. new rule_type) but not in `REQUIREMENT_TYPE_WEIGHTS`, it gets `DEFAULT_REQUIREMENT_WEIGHT` (1.0). Score remains consistent but new types are not weighted as “critical” until added. | `backend/services/compliance_score.py` (REQUIREMENT_TYPE_WEIGHTS) | Weights are fixed in code. | When adding new requirement rules, add corresponding weights; or load weights from DB/config. |
| 17 | **MINOR** | No caching; every dashboard/compliance call recomputes. For large portfolios this could be slow. | `backend/services/compliance_score.py` | No cache layer. | Consider short TTL cache or materialised score per client if needed for scale. |

---

## 7. Frontend–backend contract consistency

### 7.1 Verified

- **Plans:** Frontend calls `GET /intake/plans` and `GET /client/entitlements`. Intake plans come from plan_registry (correct 2/10/25 and pricing). Entitlements come from `plan_registry.get_client_entitlements` in client route (reads `billing_plan`) — **correct**. So the **backend** contract for plans/entitlements is correct when using plan_registry.
- **Problem:** `/client/entitlements` is implemented in `client.py` and uses **plan_registry** (see route around 271–278). So the **response** shape and values (plan, max_properties, features) are correct for plan_registry. However, if any other code path (e.g. feature_entitlement) were used for the same endpoint, it would return 1/5/15 and different feature keys (e.g. `ai_advanced` vs `ai_extraction_advanced`). Current client route uses plan_registry for entitlements — **correct**.

### 7.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 18 | **MAJOR** | Feature keys differ between systems: plan_registry uses e.g. `reports_pdf`, `ai_extraction_advanced`, `white_label_reports`. feature_entitlement uses `reports_pdf`, `ai_advanced`, `white_label`. Frontend (ReportsPage, IntegrationsPage, UpgradePrompt) uses keys like `reports_pdf`, `reports_csv`, `scheduled_reports`, `webhooks`. If any endpoint switched to feature_entitlement, key mismatches could break UI or show wrong state. | `backend/services/plan_registry.py` vs `backend/services/feature_entitlement.py`, frontend | Two registries with different key names. | Use a single feature key set (prefer plan_registry) and ensure all endpoints and frontend use the same keys. |
| 19 | **MINOR** | BrandingSettings docstring says “Portfolio plan (PLAN_6_15) and above” — legacy code. Plan_registry has PLAN_2_PORTFOLIO for white_label. | `backend/models/core.py` (BrandingSettings) | Outdated comment. | Update comment to PLAN_2_PORTFOLIO / PLAN_3_PRO. |

---

## 8. Background jobs, queues, and stuck states

### 8.1 Verified

- **Jobs:** `backend/services/jobs.py` – send_daily_reminders, digest job, etc. Use `subscription_status: ACTIVE` and `entitlement_status: ENABLED` (or None). Plan info for digest uses `plan_registry.get_plan_by_code_string(plan_code)` with `billing.get("current_plan_code", "PLAN_1_SOLO")` — client_billing has `current_plan_code` set by webhook; clients have `billing_plan`. Jobs use client_billing for plan — **correct**.
- **Stuck orders:** `STUCK_ORDER_INVESTIGATION.md` documents past issue: orders in FINALISING without documents. Fixes: validation in admin_orders before approval, recovery script `fix_stuck_orders.py`. No separate queue engine (e.g. Celery); jobs are script/scheduled.

### 8.2 Issues

| # | Severity  | Issue | File(s) | Root cause | Recommended fix |
|---|-----------|--------|---------|------------|------------------|
| 20 | **MINOR** | jobs.py sends reminders using `client["email"]` (line 79). Clients are created with `email` from intake; if a client were ever created without `email`, job could fail or skip. | `backend/services/jobs.py` | Assumes `email` exists. | Same as #9: ensure email is always set; optional defensive fallback. |
| 21 | **MINOR** | No formal queue; jobs are run as scripts/cron. Failed job state is not persisted in a “job runs” table, so “stuck” is only observable by order/workflow state (e.g. FINALISING without docs). | `backend/services/jobs.py`, workflow | No job queue abstraction. | Acceptable for launch; document run schedule and add monitoring for orders stuck in FINALISING or PROVISIONING. |
| 22 | **MINOR** | Stuck order recovery is manual (run script). No automatic retry or alert when an order is stuck in FINALISING. | `backend/scripts/fix_stuck_orders.py` | By design. | Consider scheduled check or alert when orders remain in FINALISING for N hours. |

---

## Summary table by severity

| Severity  | Count | Item numbers |
|-----------|-------|----------------|
| **CRITICAL** | 4     | 1, 2, 3, 6    |
| **MAJOR**    | 4     | 4, 7, 12, 18  |
| **MINOR**    | 14    | 5, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22 |

---

## Recommended order of fixes (when approved)

1. **CRITICAL:** Fix feature-gating middleware to use `billing_plan` and plan_registry (issue #1).
2. **CRITICAL:** Align property caps and feature sets: either migrate all gating to plan_registry only, or add PLAN_1_SOLO / PLAN_2_PORTFOLIO / PLAN_3_PRO with 2/10/25 to plan_gating and feature_entitlement (issues #2, #3, #6).
3. **MAJOR:** Standardise routes on plan_registry for feature enforcement and fix properties route to use billing_plan (issues #4, #7).
4. **MAJOR:** Enforce “at least one active admin” before deactivation and document recovery (issue #12).
5. **MAJOR:** Unify feature key naming between backend and frontend (issue #18).
6. **MINOR:** Update docs and comments (issues #5, #19); optional improvements for email fallback, compliance weights, job monitoring (issues #9, #10, #16, #20, #21, #22).

---

*End of audit report. No code changes were made; this document is for planning and remediation only.*
