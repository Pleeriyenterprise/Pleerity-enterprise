# Step 2: plan_gating and feature_entitlement – Imports, usages, and affected endpoints

**Purpose:** List every import/usage of `plan_gating` and `feature_entitlement` and the endpoints they affect, before migrating to plan_registry.

**Source of truth:** `backend/services/plan_registry.py` (canonical feature keys and plans).

---

## 1. plan_gating (backend/services/plan_gating.py)

| # | File | Line(s) | Usage | Endpoint (method + path) | Feature key (legacy) |
|---|-----|---------|--------|---------------------------|----------------------|
| 1 | `backend/routes/webhooks_config.py` | 132–134 | `plan_gating_service.enforce_feature(client_id, "webhooks")` | **POST** `/api/webhooks` | webhooks |
| 2 | `backend/routes/client.py` | 252–254 | `plan_gating_service.get_client_plan_info(client_id)` | **GET** `/api/client/plan-features` | (returns full plan info – replace with plan_registry) |
| 3 | `backend/routes/client.py` | 352–354 | `plan_gating_service.enforce_feature(client_id, "compliance_packs")` | **GET** `/api/client/compliance-pack/{property_id}/download` | compliance_packs |
| 4 | `backend/routes/documents.py` | 343–345 | `plan_gating_service.enforce_feature(client_id, "zip_upload")` | **POST** `/api/documents/zip-upload` | zip_upload |

**Summary – plan_gating:**
- **4 usages** in **3 route files**.
- **Endpoints affected:**  
  - POST `/api/webhooks` (webhooks)  
  - GET `/api/client/plan-features` (plan info only – no feature key)  
  - GET `/api/client/compliance-pack/{property_id}/download` (compliance_packs)  
  - POST `/api/documents/zip-upload` (zip_upload)

**plan_registry mapping:**
- `webhooks` → plan_registry key **webhooks** (PLAN_3_PRO).
- `compliance_packs` → plan_registry has no `compliance_packs`; FEATURE_MATRIX has no such key. May need to gate by e.g. **reports_pdf** (Portfolio+) or define/add key in Step 5.
- `zip_upload` → plan_registry key **zip_upload** (PLAN_2_PORTFOLIO).

---

## 2. feature_entitlement (backend/services/feature_entitlement.py)

| # | File | Line(s) | Usage | Endpoint (method + path) | Feature key (legacy) |
|---|-----|---------|--------|---------------------------|----------------------|
| 1 | `backend/routes/reports.py` | 284–286 | `feature_entitlement_service.enforce_feature(client_id, "scheduled_reports")` | **POST** `/api/reports/schedules` | scheduled_reports |
| 2 | `backend/routes/reports.py` | 490–497 | `feature_entitlement_service.enforce_feature(client_id, "reports_pdf")` | **GET** `/api/reports/professional/compliance-summary` | reports_pdf |
| 3 | `backend/routes/reports.py` | 560–567 | `feature_entitlement_service.enforce_feature(client_id, "reports_pdf")` | **GET** `/api/reports/professional/expiry-schedule` | reports_pdf |
| 4 | `backend/routes/reports.py` | 636–643 | `feature_entitlement_service.enforce_feature(client_id, "audit_exports")` | **GET** `/api/reports/professional/audit-log` | audit_exports |
| 5 | `backend/routes/calendar.py` | 251–257 | `feature_entitlement_service.enforce_feature(client_id, "calendar_sync")` | **GET** `/api/calendar/export.ics` | calendar_sync |
| 6 | `backend/routes/calendar.py` | 407–414 | `feature_entitlement_service.enforce_feature(client_id, "calendar_sync")` | **GET** `/api/calendar/subscription-url` | calendar_sync |
| 7 | `backend/routes/client.py` | 851–861 | `feature_entitlement_service.enforce_feature(client_id, "white_label")` | **GET** `/api/client/branding` | white_label |
| 8 | `backend/routes/client.py` | 924–937 | `feature_entitlement_service.enforce_feature(client_id, "white_label")` | **PUT** `/api/client/branding` | white_label |
| 9 | `backend/routes/client.py` | 1022–1033 | `feature_entitlement_service.enforce_feature(client_id, "white_label")` | **POST** `/api/client/branding/reset` | white_label |

**Summary – feature_entitlement:**
- **9 usages** in **3 route files**.
- **Endpoints affected:**  
  - **reports:** POST `/api/reports/schedules`, GET `/api/reports/professional/compliance-summary`, GET `/api/reports/professional/expiry-schedule`, GET `/api/reports/professional/audit-log`  
  - **calendar:** GET `/api/calendar/export.ics`, GET `/api/calendar/subscription-url`  
  - **client (branding):** GET `/api/client/branding`, PUT `/api/client/branding`, POST `/api/client/branding/reset`

**plan_registry mapping:**
- `scheduled_reports` → plan_registry key **scheduled_reports** (PLAN_2_PORTFOLIO).
- `reports_pdf` → plan_registry key **reports_pdf** (PLAN_2_PORTFOLIO).
- `audit_exports` → plan_registry key **audit_log_export** (PLAN_3_PRO).
- `calendar_sync` → plan_registry has **compliance_calendar** (all plans); no **calendar_sync**. Gate iCal export by a Portfolio+ feature (e.g. **reports_pdf** or add **calendar_sync** in Step 5 if required).
- `white_label` → plan_registry key **white_label_reports** (PLAN_3_PRO).

---

## 3. Endpoints not using plan_gating / feature_entitlement (for context)

- **GET /api/client/entitlements** – already uses `plan_registry.get_client_entitlements()` (client.py ~276). No change for Step 2.
- **GET /api/reports/compliance-summary** (format=pdf) – uses middleware `require_feature("reports_pdf")` (reports.py ~44–45). Already plan_registry via middleware after Step 1.

---

## 4. Feature key mapping (legacy → plan_registry)

| Legacy key (route) | plan_registry key | Notes |
|--------------------|-------------------|--------|
| webhooks | webhooks | Same |
| zip_upload | zip_upload | Same |
| compliance_packs | (none) | No key in plan_registry; gate by reports_pdf or add in Step 5 |
| scheduled_reports | scheduled_reports | Same |
| reports_pdf | reports_pdf | Same |
| audit_exports | audit_log_export | Different name |
| calendar_sync | (none) | plan_registry has compliance_calendar only; gate by Portfolio+ or add in Step 5 |
| white_label | white_label_reports | Different name |

---

## 5. Checklist for Step 2 migration

- [ ] **webhooks_config.py:** Replace plan_gating.enforce_feature("webhooks") with plan_registry.enforce_feature(client_id, "webhooks"); same 403 shape.
- [ ] **client.py:** Replace get_plan_features: use plan_registry.get_client_entitlements (or dedicated plan_info from plan_registry); preserve response shape until Step 5.
- [ ] **client.py:** Replace compliance-pack download gating with plan_registry (compliance_packs → choose plan_registry key or keep behaviour via reports_pdf).
- [ ] **documents.py:** Replace plan_gating.enforce_feature("zip_upload") with plan_registry.enforce_feature(client_id, "zip_upload").
- [ ] **reports.py:** Replace all feature_entitlement.enforce_feature with plan_registry.enforce_feature; use "scheduled_reports", "reports_pdf", "audit_log_export".
- [ ] **calendar.py:** Replace feature_entitlement.enforce_feature("calendar_sync") with plan_registry (map to existing key or same behaviour).
- [ ] **client.py (branding):** Replace feature_entitlement.enforce_feature("white_label") with plan_registry.enforce_feature(client_id, "white_label_reports"); preserve response shape.
- [ ] Mark plan_gating.py and feature_entitlement.py as DEPRECATED (do not delete).
