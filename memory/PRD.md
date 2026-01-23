# Compliance Vault Pro - Product Requirements Document

## Overview
**Product:** Compliance Vault Pro  
**Company:** Pleerity Enterprise Ltd  
**Target Users:** UK landlords, letting agents, and tenants  
**Tagline:** AI-Driven Solutions & Compliance  
**Version:** Production v2.0 (January 2026)

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React with Tailwind CSS
- **Database:** MongoDB (via Motor async driver)
- **Authentication:** JWT tokens
- **Integrations:** Stripe (payments), Postmark (email - LIVE), OpenAI/Gemini (AI assistant), Twilio (SMS - dev mode)

## NON-NEGOTIABLE PRINCIPLES
1. **Backend is Authoritative:** All entitlement checks happen server-side
2. **Stripe is Billing, Not Permission:** plan_registry is single source of truth
3. **No Feature Leakage:** Blocked features must fail clearly
4. **Admin ≠ Plan User:** Admin access is never plan-gated
5. **Auditability Everywhere:** All actions are logged

## Core Principles
1. **Deterministic Compliance:** No AI for compliance decisions - all compliance rules are based on predefined dates/rules
2. **Single Sources of Truth:** plan_registry for features, Stripe for billing status
3. **Strict RBAC:** `ROLE_CLIENT`, `ROLE_CLIENT_ADMIN`, `ROLE_ADMIN`, `ROLE_TENANT` enforced server-side
4. **Mandatory Audit Logging:** All significant actions logged
5. **AI is Assistive Only:** AI extracts data for review, cannot mark requirements compliant

---

## Plan Structure (January 2026)

### PLAN_1_SOLO - Solo Landlord
- **Price:** £19/month + £49 onboarding
- **Property Limit:** 2
- **Target:** DIY landlords
- **Features:** Basic AI extraction, email notifications, compliance dashboard

### PLAN_2_PORTFOLIO - Portfolio Landlord / Small Agent  
- **Price:** £39/month + £79 onboarding
- **Property Limit:** 10
- **Target:** Portfolio landlords, small agents
- **Features:** Advanced AI extraction, PDF/CSV reports, SMS reminders, tenant portal, scheduled reports

### PLAN_3_PRO - Professional / Agent / HMO
- **Price:** £79/month (£69 annual) + £149 onboarding
- **Property Limit:** 25
- **Target:** Letting agents, HMOs, serious operators
- **Features:** Everything + webhooks, API access, white-label reports, audit exports

---

## Completed Features

### Phase 1: Core System ✅
- [x] Public marketing landing page
- [x] Client intake/onboarding flow
- [x] User authentication (JWT)
- [x] Password setup via secure token
- [x] Client and Admin portals (route-guarded)
- [x] RBAC middleware (client_route_guard, admin_route_guard)
- [x] Core data models (Client, PortalUser, Property, Requirement, Document, AuditLog)
- [x] Provisioning service
- [x] Email service (Postmark - LIVE)
- [x] Stripe webhook integration

### Phase 2: AI Assistant ✅
- [x] Gemini-powered read-only AI assistant
- [x] Dashboard data explainer (compliance context)
- [x] Property and requirement analysis

### Phase 3: Additive Enhancements ✅
- [x] Admin-initiated client invitations
- [x] Expanded Admin Dashboard with statistics
- [x] AI-assisted document verification
- [x] System-wide compliance statistics
- [x] Enhanced requirement generation (country, construction_year)
- [x] Visual onboarding progress dashboard
- [x] Granular audit logging with before/after diffs
- [x] Feature-flagged SMS reminders with OTP verification
- [x] Client-facing Compliance Score with recommendations
- [x] Compliance Expiry Calendar view

### Phase 4: New Features (January 2026) ✅
- [x] AI Document Scanner Enhancement
- [x] Bulk Document Upload
- [x] Advanced Reporting (PDF/CSV)
- [x] Landlord/Tenant Portal Distinctions
- [x] Tenant Management UI

### Phase 5: P1 Features (January 2026) ✅
- [x] Scheduled Reports with Email Delivery
- [x] Client-side PDF Generation
- [x] Bulk Property Import from CSV

### Phase 6: Webhook & Digest Features (January 2026) ✅
- [x] Webhook Notifications System
- [x] Webhook UI (Integrations Page)
- [x] Email Digest Customization

### Phase 7: Universal Intake Wizard (January 2026) ✅
- [x] **Premium 5-Step Wizard** at `/intake/start`
  
  **Step 1: Your Details (Conditional Fields)**
  - Full Name, Email Address
  - Client Type selection (Individual Landlord, Property Company, Letting Agent)
  - Company Name (conditional - appears for Company/Agent types)
  - Preferred Contact Method (Email, SMS, Both)
  - Phone Number (conditional - appears for SMS/Both)
  
  **Step 2: Select Plan (Hard Limits)**
  - Starter (PLAN_1): 1 property max, £9.99/month + £49.99 setup
  - Growth (PLAN_2_5): 5 properties max, £9.99/month + £49.99 setup
  - Portfolio (PLAN_6_15): 15 properties max, £9.99/month + £49.99 setup
  - Plan limits enforced server-side
  
  **Step 3: Properties (Repeatable, Plan-Limited)**
  - Property Nickname, Postcode, Address, City
  - **Postcode Address Lookup** - Auto-fills city and council from postcodes.io API
  - Property Type dropdown
  - HMO toggle (House in Multiple Occupation)
  - Bedrooms, Occupancy
  - Council searchable dropdown (~300 UK councils with region/nation)
  - Licensing section (Yes/No/Unsure with type and status)
  - Management & Reminders (Landlord/Agent/Both)
  - Agent details (conditional - when reminders to Agent)
  - Current Compliance Status (Gas Safety, EICR, EPC, Licence - YES/NO/UNSURE)
  
  **Step 4: Preferences & Consents**
  - Document submission method:
    - A) Upload Here - direct upload through portal
    - B) Email to Pleerity (info@pleerityenterprise.co.uk) - with mandatory consent
  - GDPR data processing consent (required)
  - Service boundary acknowledgment (required)
  
  **Step 5: Review & Payment**
  - Editable summary of all sections
  - Payment breakdown (monthly + setup fee)
  - Stripe Checkout integration

### Phase 8: Admin Management & Standards (January 2026) ✅
- [x] **Admin Management UI**
  - Dedicated "Admins" page in Admin Dashboard
  - Stats cards for Total/Active/Pending admin counts
  - Admin list with status, last login, actions
  - Invite Admin modal with email + full name
  - Deactivate/Reactivate admin actions
  - Resend invitation for pending admins

- [x] **Council Name Normalization**
  - All council names stored in full official format (audit-ready)
  - "Bristol" → "Bristol City Council"
  - "Camden" → "London Borough of Camden"
  - Applied to all surfaces: intake, properties, reports

- [x] **Brand Colour Standards**
  - Electric Teal (#00B8A9) for affirmative/primary actions
  - Midnight Blue (#0B1D3A) for headings/text
  - Red reserved for errors/risk indicators only

- [x] **Postcode Address Lookup**
  - Uses postcodes.io free API (no authentication required)
  - Auto-fills city/town from postcode
  - Auto-matches and fills local council from our database
  - Shows loading spinner during lookup
  - Green checkmark on successful lookup
  - Error handling for invalid/not found postcodes

- [x] **Postcode Autocomplete**
  - Real-time suggestions as user types (minimum 2 characters)
  - Shows matching UK postcodes with district and region
  - Dropdown with clickable suggestions
  - Select postcode to auto-fill city and council
  - Debounced API calls for performance
  - Uses postcodes.io free autocomplete endpoint

- [x] **Customer Reference Number**
  - Format: `PLE-CVP-YYYY-XXXXX` (e.g., PLE-CVP-2026-4F82C)
  - Unique DB index enforced
  - Safe characters (no O/0/I/1/L)
  - Generated at intake submission
  - Searchable by Admin and AI Assistant

- [x] **UK Councils Data**
  - Static JSON seed file with ~300 councils
  - Searchable API endpoint with pagination
  - Filter by nation (England, Wales, Scotland, Northern Ireland)
  - Includes region metadata

- [x] **Non-Blocking Document Upload**
  - Documents uploaded during intake stored with UNVERIFIED status
  - Property temp key for reconciliation after intake submission
  - AI extraction runs in assistive mode after provisioning
  - Manual review required before authoritative status

---

## User Roles

| Role | Permissions |
|------|-------------|
| ROLE_ADMIN | Full system access, all clients, audit logs, reports. **Authentication fully independent** - no client record required, not blocked by provisioning. **🔒 LOCKED - Do not modify unless security issue.** |
| ROLE_CLIENT_ADMIN | Full access to own client data, can invite tenants, manage webhooks |
| ROLE_CLIENT | Access to own properties, requirements, documents |
| ROLE_TENANT | Read-only access to assigned property compliance status |

### Admin Accounts
| Email | Type | Notes |
|-------|------|-------|
| info@pleerityenterprise.co.uk | **PRODUCTION** | Primary admin, invite flow |
| admin@pleerity.com | TEST-ONLY | Development seed, do not use in production |

---

## API Endpoints

### Intake Wizard
- `GET /api/intake/plans` - Get available billing plans with limits and pricing
- `GET /api/intake/councils` - Search UK councils (q, nation, page, limit)
- `GET /api/intake/postcode-autocomplete` - Autocomplete UK postcodes as user types
- `GET /api/intake/postcode-lookup/{postcode}` - Lookup postcode for city/council auto-fill
- `POST /api/intake/submit` - Submit completed intake wizard
- `POST /api/intake/checkout` - Create Stripe checkout session
- `POST /api/intake/upload-document` - Upload document during intake
- `GET /api/intake/onboarding-status/{client_id}` - Get detailed onboarding progress

### Authentication
- `POST /api/auth/login` - User login (works for all roles)
- `POST /api/auth/admin/login` - Admin-specific login (fully independent)
- `POST /api/auth/set-password` - Set password via token (handles both client and admin invites)
- `POST /api/auth/log-route-guard-block` - Log unauthorized admin route access attempts

### Admin User Management
- `GET /api/admin/admins` - List all admin users
- `POST /api/admin/admins/invite` - Invite new admin via email
- `DELETE /api/admin/admins/{id}` - Deactivate an admin
- `POST /api/admin/admins/{id}/reactivate` - Reactivate disabled admin
- `POST /api/admin/admins/{id}/resend-invite` - Resend invitation email

### Tenant Portal
- `GET /api/tenant/dashboard` - Tenant dashboard with properties and compliance summary
- `GET /api/tenant/property/{property_id}` - Property details with certificates
- `GET /api/tenant/compliance-pack/{property_id}` - Download PDF compliance pack (FREE)
- `POST /api/tenant/request-certificate` - Request certificate from landlord
- `POST /api/tenant/contact-landlord` - Send message to landlord
- `GET /api/tenant/requests` - List tenant's certificate requests

### Compliance Pack
- `GET /api/client/compliance-pack/{property_id}/preview` - Preview certificate list (JSON)
- `GET /api/client/compliance-pack/{property_id}/download` - Download PDF (Plan gated)

### Webhooks
- `GET /api/webhooks` - List webhooks
- `POST /api/webhooks` - Create webhook
- `DELETE /api/webhooks/{id}` - Soft delete webhook
- `POST /api/webhooks/{id}/test` - Send test payload
- `GET /api/webhooks/events` - Available event types

### Client
- `GET /api/client/dashboard` - Client dashboard data
- `GET /api/client/properties` - Client properties
- `GET /api/client/requirements` - Client requirements

### Reports
- `GET /api/reports/available` - List available reports
- `POST /api/reports/schedules` - Create report schedule
- `GET /api/reports/schedules` - List schedules

---

## Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@pleerity.com | Admin123! |
| Client | test@pleerity.com | TestClient123! |

---

## Known Limitations / Mocked Services

1. **Payments (Stripe):** Using test key - functional but not processing real payments
2. **SMS (Twilio):** Feature-flagged, using dev credentials
3. **PDF Reports:** Returns JSON data for client-side PDF generation
4. **Webhook Targets:** Test endpoints only - delivery depends on configured URLs

---

## Files of Reference

### Backend
- `/app/backend/server.py` - Main FastAPI app with APScheduler
- `/app/backend/routes/intake.py` - Universal Intake Wizard routes
- `/app/backend/routes/webhooks_config.py` - Webhook management
- `/app/backend/services/webhook_service.py` - Webhook delivery with HMAC
- `/app/backend/data/uk_councils.json` - Static UK councils data
- `/app/backend/models.py` - All Pydantic models

### Frontend
- `/app/frontend/src/pages/IntakePage.js` - 5-step intake wizard
- `/app/frontend/src/pages/IntegrationsPage.js` - Webhook management UI
- `/app/frontend/src/pages/NotificationPreferencesPage.js` - Digest customization
- `/app/frontend/src/App.js` - All routes

---

## Backlog / Future Enhancements

### P1 (High Priority)
- [x] ~~ZIP file bulk upload~~ ✅ COMPLETED
- [x] ~~Compliance Score Trending~~ ✅ COMPLETED (Session 7)
- [x] ~~Feature Entitlement System~~ ✅ COMPLETED (Session 7)
- [x] ~~iCal Calendar Export~~ ✅ COMPLETED (Session 7)
- [x] ~~White-Label Branding~~ ✅ COMPLETED (Session 7)
- [x] ~~Professional PDF Reports~~ ✅ COMPLETED (Session 7)
- [x] ~~Service Catalogue V2 Phase 1~~ ✅ COMPLETED (January 22, 2026) - Authoritative catalogue with pack hierarchy
- [x] ~~Orders Pipeline Frontend Refactoring~~ ✅ COMPLETED (January 23, 2026) - Enterprise-grade workflow UI
- [x] ~~Service-Specific SLA Monitoring~~ ✅ COMPLETED (January 23, 2026) - Category-based SLA hours, auto-tracking
- [x] ~~Client Portal Document Downloads~~ ✅ COMPLETED (January 23, 2026) - Client orders page with doc downloads
- [x] ~~Admin Notification Preferences~~ ✅ COMPLETED (January 23, 2026) - Email/SMS/In-app channel toggles
- [ ] Full Address Autocomplete with `getaddress.io` (PAUSED by user)
- [ ] Deprecate `plan_gating.py` - Refactor legacy service to use Service Catalogue V2

### P2 (Medium Priority)
- [ ] Property Price Context - Show average property price in area after postcode selection
- [ ] Admin Test Monitoring UI - View test runs, webhook delivery logs, job statuses
- [ ] Production SMS sending with real Twilio credentials
- [x] ~~Document version history~~ ✅ COMPLETED (Document-Centric Review Session)
- [ ] Multi-language support
- [ ] Full calendar export (subscribe via external URL)
- [x] ~~Admin-Managed Blog/Insights system~~ ✅ COMPLETED (January 22, 2026)
- [x] ~~Real document generation (replace MOCK with actual DOCX/PDF generation)~~ ✅ COMPLETED (Document-Centric Review Session)
- [ ] Update "Learn More" public pages - Connect to Service Catalogue V2 dynamic content

### P3 (Low Priority)
- [ ] Mobile app (React Native)
- [ ] Integration with property management systems
- [ ] Advanced analytics dashboard
- [ ] Deprecate Legacy V1 Services - Remove obsolete /app/backend/services/service_catalogue.py

---

## Changelog

### January 20, 2026 (Session 2) - Admin Authentication & Invite Flow + E2E Testing
- **FIXED:** Admin authentication fully decoupled from client provisioning
  - Admin login no longer requires Client record
  - Admin login not blocked by onboarding_status or provisioning checks
  - Admin can login even with no clients, properties, or provisioning
  - Admin session persists across page refresh
- **ADDED:** Dedicated admin login endpoint `/api/auth/admin/login`
- **ADDED:** Route guard correctly blocks non-admin users from /admin/* routes
- **ADDED:** Audit log actions: ADMIN_LOGIN_SUCCESS, ADMIN_LOGIN_FAILED, ADMIN_ROUTE_GUARD_BLOCK
- **ADDED:** Frontend detects /admin/signin route and uses admin login API
- **UPDATED:** LoginPage.js shows "Admin Sign In" with Shield icon on admin route
- **NEW:** Admin Invite Flow (P0 Complete)
  - `POST /api/admin/admins/invite` - Invite new admin via email
  - `GET /api/admin/admins` - List all admin users
  - `DELETE /api/admin/admins/{id}` - Deactivate an admin
  - `POST /api/admin/admins/{id}/reactivate` - Reactivate a disabled admin
  - `POST /api/admin/admins/{id}/resend-invite` - Resend invitation email
  - Audit actions: ADMIN_INVITED, ADMIN_INVITE_ACCEPTED
  - Email template: admin-invite with branded HTML
- **PRODUCTION ADMIN:** info@pleerityenterprise.co.uk (created via invite flow)
- **🔒 ADMIN AUTH LOCKED** - Do not modify unless security issue
- **E2E TESTING COMPLETE:**
  - 35/35 backend API tests passed (100%)
  - All frontend pages tested and working
  - RBAC route guards verified
  - Audit logging verified
- **TEST REPORT:** /app/test_reports/iteration_13.json

### January 20, 2026 (Session 3)
- **Admin Ops + Reference Handling ✅**
  - **Global Search** in admin header
    - Search by CRN, email, name, postcode
    - Debounced input (300ms delay)
    - Search results dropdown with client preview
    - Click result opens Client Detail Modal
  
  - **Client Detail Modal** (4 tabs)
    - **Overview**: Client info, status, compliance summary, properties list
    - **Setup Controls**: Readiness checklist (6 items), Trigger Provisioning, Resend Password Link
    - **Messaging**: Send email to client via Postmark with audit logging
    - **Audit Timeline**: Key events history (intake, payment, provisioning, auth, documents)
  
  - **Profile Update** with before/after audit logging
    - Safe fields only: full_name, phone, company_name, preferred_contact
    - Creates ADMIN_PROFILE_UPDATED audit entry with diff
  
  - **KPI Drill-down Endpoints**
    - GET /api/admin/kpi/properties?status_filter=GREEN/AMBER/RED
    - GET /api/admin/kpi/requirements?status_filter=COMPLIANT/OVERDUE/EXPIRING_SOON
  
  - **MongoDB Indexes** for efficient search
    - customer_reference (unique, sparse)
    - email, client_id, full_name on clients
    - postcode, compliance_status on properties
    - Compound index on audit_logs (client_id, created_at)

- **CRN Display Everywhere ✅**
  - Customer Reference Number now displayed in:
    - Client Dashboard header (teal badge with data-testid='client-crn-badge')
    - All email templates (header badge + footer text)
    - Admin search results
    - Client Detail Modal header
    - KPI drilldown client lists
  - Format: PLE-CVP-YYYY-XXXXX

- **Clickable KPI Tiles ✅**
  - 7 KPI tiles are now interactive buttons:
    - Total Clients, Total Properties, Active Clients, Pending Setup
    - Compliance: GREEN (Compliant), AMBER (Attention Needed), RED (Non-Compliant)
  - Hover effect shows "Click to view details →"
  - Opens KPIDrilldownModal with filtered data
  - Client list shows: avatar, name, email, CRN badge, status
  - Property list shows: icon, address, postcode, council, compliance status
  - Clicking a client opens Client Detail Modal

- **TEST REPORTS:** 
  - `/app/test_reports/iteration_15.json` (29/29 tests - 100%)
  - `/app/test_reports/iteration_16.json` (14/14 tests - 100%)

### January 20, 2026 (Session 4)
- **Admin Assistant with CRN Lookup ✅**
  - **CRN Lookup Endpoint**: `GET /api/admin/client-lookup?crn=...`
    - RBAC enforced (admin only)
    - Returns full client snapshot: client info, properties, requirements, documents
    - Includes compliance_summary with percentages
    - Audit logged: ADMIN_CRN_LOOKUP
  
  - **Admin Assistant Page**: `/admin/assistant`
    - Accessible via "AI Assistant" button in Admin Dashboard header
    - Left panel: CRN input + "Load Client" button
    - Client summary card: name, email, CRN badge, properties, compliance %, status
    - Right panel: AI chat interface with suggested questions
    
  - **AI Analysis Endpoint**: `POST /api/admin/assistant/ask`
    - Accepts `{crn, question}` payload
    - Server-side retrieval: fetches snapshot by CRN
    - Injects snapshot into Gemini LLM prompt (gemini-2.5-flash)
    - LLM cannot query DB directly
    - Rate limited: 20 questions per 10 minutes per admin
    - Audit logged: ADMIN_ASSISTANT_QUERY with question + answer preview
  
  - **Security Features**:
    - RBAC on all endpoints
    - Rate limiting prevents abuse
    - Full audit trail for compliance

- **TEST REPORT:** `/app/test_reports/iteration_17.json` (15/15 tests - 100%)

### January 21, 2026 (Session 5) - Dashboard Drilldowns + Compliance Score + AI Assistant + Plan Gating
- **Dashboard Clickable Tiles ✅**
  - All dashboard KPI tiles now interactive with drilldown navigation
  - **Total Requirements** → `/app/requirements` (all requirements)
  - **Compliant** → `/app/properties?status=COMPLIANT` (GREEN properties)
  - **Attention Needed** → `/app/requirements?status=DUE_SOON` (AMBER requirements)
  - **Action Required** → `/app/requirements?status=OVERDUE_OR_MISSING` (RED requirements)
  - Stats row tiles also clickable (Requirements, Compliant, Days to Next Expiry)
  - Hover effects show "Click to view →"

- **Requirements Page ✅** (`/app/requirements`)
  - NEW dedicated page for requirements drilldown
  - Filter by URL params: status, window (30 days)
  - Filter cards: Total, Compliant, Expiring Soon, Action Required, 30 Day Window
  - Search bar for requirement type, property, description
  - List shows: status icon, requirement type, status badge, property name, due date, days left
  - "View Documents" link for each requirement
  - Sorted by urgency (OVERDUE > EXPIRING_SOON > PENDING)

- **Compliance Score Explanation ✅**
  - Score card now clickable → navigates to `/app/compliance-score`
  - **"How is this calculated?"** expandable section on dashboard card
  - Shows weighting model:
    - Status (40%): Based on requirement statuses
    - Timeline (30%): Days until next expiry
    - Documents (15%): Requirement coverage percentage
    - Overdue Penalty (15%): Heavy penalty for overdue items
  - Concrete breakdown shows actual counts from data
  - Compliance Score Page shows full breakdown + per-property contribution

- **AI Assistant Fix ✅**
  - Refactored to use `emergentintegrations` library with Gemini 3 Flash
  - Returns structured response: `{answer, what_this_is_based_on, next_actions}`
  - Full observability: correlation_id, audit logging, error tracking
  - Rate limited: 10 questions per 10 minutes
  - Refuses action requests (create, modify, delete) with `refused: true`
  - Snapshot size protection (50KB limit)
  - User-friendly error: "Assistant unavailable. Please try again or refresh."

- **Plan Gating ✅**
  - NEW `plan_gating.py` service for feature enforcement
  - Server-side enforcement returns 403 with `PLAN_NOT_ELIGIBLE` error code
  - `GET /api/client/plan-features` endpoint returns feature availability
  - Features gated by plan:
    - PLAN_1 (Starter): Basic features, AI assistant, no SMS/webhooks
    - PLAN_2_5 (Growth): + SMS reminders, advanced reports, scheduled reports
    - PLAN_6_15 (Portfolio): + Webhooks, ZIP upload, compliance packs, integrations, API access
  - Error response includes: error_code, message, feature, upgrade_required

- **Apply & Save Date Parsing Fix ✅**
  - NEW `_normalize_and_parse_date()` function handles multiple date formats
  - Accepts: ISO (YYYY-MM-DD), UK (DD/MM/YYYY), datetime objects, ISO with time
  - Handles unicode dash variants (en-dash, em-dash, figure dash)
  - Strips whitespace and invisible characters
  - Server-side normalization - not reliant on UI
  - Creates `AI_EXTRACTION_APPLIED` audit log with before/after states

- **AI Query History Persistence ✅**
  - Queries saved to `admin_assistant_queries` collection
  - Each query has unique `query_id` (format: aq-XXXXXXXXXXXX)
  - `GET /api/admin/assistant/history` endpoint returns saved queries
  - Filter by CRN with `?crn=PLE-CVP-XXXX-XXXXX`
  - Pagination with `skip` and `limit` parameters
  - Admin Assistant UI shows query history panel with expandable list

- **Calendar Integration ✅**
  - Calendar already integrated via `/api/calendar/expiries` endpoint
  - Shows requirements grouped by due date
  - `GET /api/calendar/upcoming` returns upcoming expiries with urgency levels
  - Expiring/overdue items automatically appear in calendar view

- **TEST REPORTS:** 
  - `/app/test_reports/iteration_18.json` (11/11 tests - 100%)
  - `/app/test_reports/iteration_19.json` (14/14 tests - 100%)
  - `/app/test_reports/iteration_20.json` (9/9 tests - 100%)

### January 21, 2026 (Session 5 - Continued) - ZIP Upload + Email Notifications
- **ZIP File Bulk Upload ✅**
  - NEW `POST /api/documents/zip-upload` endpoint
  - Plan gating: Requires Portfolio plan (PLAN_6_15) or higher
  - Returns 403 with `PLAN_NOT_ELIGIBLE` error code for lower plans
  - Validates ZIP file extension before processing
  - Extracts ZIP to temp directory with security checks:
    - Max 100MB ZIP file size
    - Max 500MB uncompressed size
    - Max 1000 files per archive
  - Processes PDF, JPG, PNG, DOC, DOCX files
  - Auto-skips hidden files and macOS metadata
  - AI auto-matching for extracted documents
  - Audit log for ZIP upload with extraction summary

- **Bulk Upload UI Updated ✅**
  - NEW upload mode toggle: "Individual Files" / "ZIP Archive"
  - ZIP mode disabled for non-Portfolio plans
  - Lock icon and "Upgrade to Portfolio plan for ZIP uploads" message
  - ZIP drop zone accepts single .zip file
  - Progress indicator during ZIP processing
  - Results summary shows: Total, Successful, Failed, Skipped, AI Matched

- **AI Extraction Email Notifications ✅**
  - NEW `EmailTemplateAlias.AI_EXTRACTION_APPLIED`
  - Sends email when Apply & Save completes successfully
  - Email includes:
    - Property address
    - Document type
    - Certificate number
    - Expiry date
    - Compliance status badge (COMPLIANT/EXPIRING_SOON/OVERDUE)
    - CRN badge in header
    - "View in Dashboard" CTA button
  - Handles email failures gracefully without breaking main flow

### January 21, 2026 (Session 6) - Tenant Portal Enhancements + Compliance Pack
- **Tenant Portal Enhancements ✅**
  - **Tenant Dashboard Upgraded**: Full compliance overview for assigned properties
    - Summary stats: Total Properties, Fully Compliant, Needs Attention, Action Required
    - Properties list with compliance status indicators (GREEN/AMBER/RED)
    - Expandable property cards show certificate details
  - **Request Certificate Feature**: `POST /api/tenant/request-certificate`
    - Tenant can request specific certificates (Gas Safety, EICR, EPC, etc.)
    - Creates request record in database
    - Notifies landlord via email with request details
  - **Contact Landlord Feature**: `POST /api/tenant/contact-landlord`
    - Free-form messaging (max 1000 chars)
    - Email sent to landlord with tenant message
    - Modal UI with validation
  - **My Requests Page**: `GET /api/tenant/requests`
    - Lists all tenant requests with status
    - Shows request type, property, date, status

- **Compliance Pack PDF Generation ✅**
  - NEW `compliance_pack.py` service using `reportlab` library
  - **Client Endpoint**: `GET /api/client/compliance-pack/{property_id}/download`
    - Plan gated: Requires Portfolio plan (PLAN_6_15)
    - Returns 403 `PLAN_NOT_ELIGIBLE` for lower plans
  - **Client Preview Endpoint**: `GET /api/client/compliance-pack/{property_id}/preview`
    - Returns JSON with certificate list, counts, and status breakdown
  - **Tenant Endpoint**: `GET /api/tenant/compliance-pack/{property_id}`
    - FREE for tenants (no plan gating)
    - Tenants can download compliance pack for their assigned properties
  - **PDF Contents**:
    - Cover page with property address and generation date
    - Compliance summary table (status, expiry dates)
    - Individual certificate pages with details
    - Compliant items have green status badge
    - Expiring/Overdue items flagged in red/amber

- **Bug Fixed**: EmailTemplateAlias enum passed as string instead of enum in tenant routes
  - Fixed `template_alias='reminder'` → `template_alias=EmailTemplateAlias.REMINDER`

- **TEST REPORT:** `/app/test_reports/iteration_21.json` (29/29 tests - 100%)

### January 21, 2026 (Session 7) - Capability Completion & Gating Build
- **Compliance Score Trending ✅**
  - NEW `compliance_trending.py` service for daily score snapshots
  - **Endpoints**:
    - `GET /api/client/compliance-score/trend` - Returns sparkline data for chart
    - `POST /api/client/compliance-score/snapshot` - Manual snapshot trigger
    - `GET /api/client/compliance-score/explanation` - Plain-English change explanation
  - **Scheduled Job**: Daily snapshot at 2:00 AM UTC for all active clients
  - **Database**: `compliance_score_history` collection with date_key index
  - **Frontend**: Sparkline chart component in ClientDashboard
    - Shows 30-day trend with trend direction indicator (up/down/stable)
    - Color-coded by trend: green (up), red (down), gray (neutral)
    - Placeholder when < 2 data points: "Trend tracking starts tomorrow"

- **Central Feature Entitlement System ✅**
  - NEW `feature_entitlement.py` - Comprehensive feature registry
  - **17 features defined** across 7 categories:
    - AI: ai_basic, ai_advanced
    - Documents: bulk_upload, zip_upload
    - Communication: sms, email_digest
    - Reporting: reports_pdf, reports_csv, scheduled_reports
    - Integration: webhooks, api_access
    - Portal: tenant_portal, calendar_sync
    - Advanced: compliance_packs, audit_exports, white_label, score_trending
  - **Plan Feature Matrix**:
    - PLAN_1 (Starter): 5 features enabled (ai_basic, bulk_upload, email_digest, tenant_portal, score_trending)
    - PLAN_2_5 (Growth): 11 features enabled (+ai_advanced, sms, reports_pdf/csv, scheduled_reports, calendar_sync)
    - PLAN_6_15 (Portfolio): All 17 features enabled (+zip_upload, webhooks, api_access, compliance_packs, audit_exports, white_label)
  - **Endpoints**:
    - `GET /api/client/entitlements` - Full feature availability for client
    - `GET /api/admin/system/feature-matrix` - Admin-only complete plan comparison
  - **Consistent error response**: `error_code: "PLAN_NOT_ELIGIBLE"`, `upgrade_required: true`

- **iCal Calendar Export ✅** (Module H)
  - NEW `GET /api/calendar/export.ics` - Download iCal calendar file
  - Plan gated: Requires Growth plan (PLAN_2_5+)
  - Generates VCALENDAR with VEVENT entries for each expiry
  - Includes VALARM reminders (7 days for expiring, 30 days for pending)
  - Standard iCal format compatible with Google Calendar, Outlook, Apple Calendar
  - `GET /api/calendar/subscription-url` - Returns subscription URL with instructions

- **White-Label Branding Settings ✅**
  - NEW `BrandingSettings` model in models.py
  - **Endpoints**:
    - `GET /api/client/branding` - Returns settings with upgrade_message for locked features
    - `PUT /api/client/branding` - Update settings (Plan gated: PLAN_6_15)
    - `POST /api/client/branding/reset` - Reset to defaults (Plan gated: PLAN_6_15)
  - **Settings**: company_name, logo_url, colors (primary, secondary, accent, text), report_header/footer, email_from_name, contact info
  - **Frontend**: `BrandingSettingsPage.js` at `/app/settings/branding`
    - Full settings form with color pickers
    - Upgrade notice for non-Portfolio plans
    - Preview panel showing color scheme

- **Professional PDF Reports ✅** (Module E Enhancement)
  - NEW `professional_reports.py` using reportlab
  - **Report Types**:
    - Compliance Summary PDF - Executive summary with property breakdown
    - Expiry Schedule PDF - Upcoming expirations with color-coded urgency
    - Audit Log PDF - Activity timeline export
  - **Branding Integration**: Uses client branding settings for colors, logo, header/footer
  - **Endpoints**:
    - `GET /api/reports/professional/compliance-summary` (Plan gated: PLAN_2_5+)
    - `GET /api/reports/professional/expiry-schedule` (Plan gated: PLAN_2_5+)
    - `GET /api/reports/professional/audit-log` (Plan gated: PLAN_6_15)
  - **Professional formatting**: Branded headers, status color-coding, company logo support

- **Bug Fixed**: client.py import error for audit_service → changed to utils.audit

- **TEST REPORT:** `/app/test_reports/iteration_22.json` (22/22 tests - 100%)

### January 21, 2026 (Session 8) - Production-Ready Capability Build
- **NEW PLAN STRUCTURE ✅**
  - **PLAN_1_SOLO**: Solo Landlord (2 properties, £19/mo, £49 onboarding)
  - **PLAN_2_PORTFOLIO**: Portfolio Landlord (10 properties, £39/mo, £79 onboarding)
  - **PLAN_3_PRO**: Professional (25 properties, £79/mo, £149 onboarding)
  - Legacy plan codes (PLAN_1, PLAN_2_5, PLAN_6_15) mapped to new codes
  - NEW `plan_registry.py` - Single source of truth for all plan definitions

- **INTAKE-LEVEL PROPERTY GATING ✅** (NON-NEGOTIABLE)
  - Property limits enforced at intake form, not just post-payment
  - `POST /api/intake/validate-property-count` - Validates before adding properties
  - Frontend must prevent adding beyond limit
  - Server-side blocks submission if limits exceeded
  - Error code: `PROPERTY_LIMIT_EXCEEDED` with upgrade suggestion

- **FEATURE ENTITLEMENT MATRIX ✅**
  | Feature | PLAN_1_SOLO | PLAN_2_PORTFOLIO | PLAN_3_PRO |
  |---------|-------------|------------------|------------|
  | Compliance Dashboard | ✅ | ✅ | ✅ |
  | Compliance Score | ✅ | ✅ | ✅ |
  | Email Notifications | ✅ | ✅ | ✅ |
  | AI Extraction (Basic) | ✅ | ✅ | ✅ |
  | AI Extraction (Advanced) | ❌ | ✅ | ✅ |
  | ZIP Upload | ❌ | ✅ | ✅ |
  | PDF/CSV Reports | ❌ | ✅ | ✅ |
  | SMS Reminders | ❌ | ✅ | ✅ |
  | Tenant Portal (View-only) | ❌ | ✅ | ✅ |
  | Webhooks | ❌ | ❌ | ✅ |
  | API Access | ❌ | ❌ | ✅ |
  | White-Label Reports | ❌ | ❌ | ✅ |
  | Audit Log Export | ❌ | ❌ | ✅ |

- **TENANT PORTAL - VIEW ONLY ✅**
  - Certificate requests: DISABLED (returns FEATURE_DISABLED)
  - Contact landlord: DISABLED (returns FEATURE_DISABLED)
  - My requests: Returns empty list with note
  - View dashboard: Still works (read-only)
  - Download compliance pack: Still works

- **UPGRADE PROMPT COMPONENT ✅**
  - NEW `UpgradePrompt.js` - Inline, modal, and card variants
  - Shows: Feature name, description, required plan, upgrade link
  - `PropertyLimitPrompt.js` - Specific component for property limits
  - `FeatureGate.js` - Wrapper component for conditional rendering

- **Endpoints Updated**:
  - `GET /api/intake/plans` - Returns new plan structure
  - `POST /api/intake/validate-property-count` - NEW property validation
  - `GET /api/client/entitlements` - Uses plan_registry
  - `GET /api/admin/system/feature-matrix` - Uses plan_registry
  - `POST /api/tenant/request-certificate` - Returns FEATURE_DISABLED
  - `POST /api/tenant/contact-landlord` - Returns FEATURE_DISABLED

- **TEST REPORT:** `/app/test_reports/iteration_23.json` (21/21 tests - 100%)

### January 21, 2026 (Session 8 - Continued) - Frontend Integration Complete
- **Intake Wizard Frontend Updated ✅**
  - `IntakePage.js` updated with new PLAN_LIMITS and PLAN_NAMES
  - Plans displayed: Solo £19/mo (2 props), Portfolio £39/mo (10 props), Professional £79/mo (25 props)
  - "Most Popular" badge on Portfolio plan
  - Property counter shows X/Y format (e.g., "1/2")
  - Property limit enforcement with visual feedback

- **UpgradePrompt Components Integrated ✅**
  - `PropertyLimitPrompt` component in Step 3 (Properties)
  - Shows upgrade suggestion when limit reached
  - "Upgrade to Portfolio (up to 10 properties)" link
  - Toast notifications for limit exceeded

- **API Integration ✅**
  - `intakeAPI.validatePropertyCount()` added to client.js
  - Backend validation on property add
  - Error handling with upgrade suggestions

- **AI Extraction Basic vs Advanced ✅**
  - PLAN_1_SOLO (Basic): Returns `extraction_mode: "basic"`
    - Only document_type, issue_date, expiry_date
    - No confidence scoring
    - `auto_apply_enabled: true`
  - PLAN_2+_PORTFOLIO/PRO (Advanced): Returns `extraction_mode: "advanced"`
    - Full extraction with confidence scoring
    - `review_ui_available: true`
    - Field-level validation

- **TEST REPORT:** `/app/test_reports/iteration_24.json` (16/16 tests - 100%)

### January 21, 2026 (Session 9) - Feature Gating UI Complete & E2E Testing
- **UpgradePrompt Integration on Feature-Gated Pages ✅**
  - **ReportsPage.js**: 
    - Added `fetchEntitlements()` to check `reports_pdf`/`reports_csv` availability
    - Shows `UpgradePrompt` card when reports feature is unavailable (requires PLAN_2_PORTFOLIO)
    - "Schedule Report" button shows lock icon for non-eligible users
    - Toast notification redirects to billing page
  - **IntegrationsPage.js**:
    - Added `fetchEntitlements()` to check `webhooks` availability
    - Shows full-page `UpgradePrompt` when webhooks unavailable (requires PLAN_3_PRO)
    - Feature preview section: "What you'll unlock with Professional"
    - Preview cards: Custom Webhooks, Real-time Events, Signed Payloads, Automatic Retries
    - Only shows webhook list and Create button when entitled
  - **BrandingSettingsPage.js**:
    - Replaced custom upgrade notice with reusable `UpgradePrompt` component
    - Shows "White-Label Branding" prompt (requires PLAN_3_PRO)
    - Form fields remain visible but disabled when locked

- **Consistent UX Across Gated Features ✅**
  - All upgrade prompts use same component with variants (`inline`, `modal`, `card`)
  - Shows feature name, description, required plan, and upgrade button
  - Plan names mapped correctly: "Solo Landlord", "Portfolio", "Professional"
  - Upgrade button navigates to `/app/billing?upgrade_to={PLAN_CODE}`

- **API Entitlements Verification ✅**
  - `GET /api/client/entitlements` returns correct feature flags per plan
  - PLAN_1_SOLO: `reports_pdf=false`, `reports_csv=false`, `webhooks=false`, `white_label_reports=false`
  - PLAN_2_PORTFOLIO: `reports_pdf=true`, `reports_csv=true`, `webhooks=false`, `white_label_reports=false`
  - PLAN_3_PRO: All features enabled

- **TEST REPORT:** `/app/test_reports/iteration_25.json` (21/21 tests - 100%)
  - All backend API tests passed
  - All frontend UI tests passed via Playwright
  - Feature gating verified for all three pages
  - PUT /api/client/branding returns 403 for non-PRO plans

### January 21, 2026 (Session 9 - Continued) - Plan Comparison Page
- **NEW Plan Comparison Page ✅** (`/app/billing`)
  - **Current Plan Banner**: Shows user's plan, property count, feature count, and monthly price
  - **Plan Cards**: Side-by-side comparison of Solo (£19), Portfolio (£39), and Professional (£79)
    - "Most Popular" badge on Portfolio plan
    - "Full Features" badge on Professional plan
    - "Current Plan" indicator on active plan
    - Key features summary (property count, feature count, AI extraction, webhooks)
    - Upgrade CTA buttons (disabled for current plan and downgrades)
  - **Feature Comparison Matrix**: Collapsible categories showing all 19 features
    - Core Features (6): Dashboard, Score, Calendar, Email, Upload, Trending
    - AI Features (3): Basic extraction, Advanced extraction, Review UI
    - Documents (1): ZIP upload
    - Reporting (3): PDF, CSV, Scheduled reports
    - Communication (1): SMS reminders
    - Tenant Portal (1): View-only tenant access
    - Integrations (2): Webhooks, API access
    - Advanced (2): White-label, Audit exports
    - Green checkmarks for enabled, gray X for disabled
    - Feature counts per plan per category
  - **FAQ Section**: 4 common questions about upgrades, downgrades, trials, cancellation
  - **Navigation**: "Plans" link added to ClientDashboard navbar

- **Files Created/Modified**:
  - NEW `/app/frontend/src/pages/BillingPage.js` - Full plan comparison page
  - MODIFIED `/app/frontend/src/App.js` - Added `/app/billing` route
  - MODIFIED `/app/frontend/src/pages/ClientDashboard.js` - Added "Plans" nav link

### January 21, 2026 (Session 10) - Production Stripe Webhook Infrastructure ✅
- **Stripe Price ID Configuration ✅**
  - `plan_registry.py` updated with production Stripe price IDs:
    - `PLAN_1_SOLO`: subscription=`price_1Ss7qNCF0O5oqdUzHUdjy27g`, onboarding=`price_1Ss7xICF0O5oqdUzGikCKHjQ`
    - `PLAN_2_PORTFOLIO`: subscription=`price_1Ss6JPCF0O5oqdUzaBhJv239`, onboarding=`price_1Ss80uCF0O5oqdUzbluYNTD9`
    - `PLAN_3_PRO`: subscription=`price_1Ss6uoCF0O5oqdUzGwmumLiD`, onboarding=`price_1Ss844CF0O5oqdUzM0AWrBG5`
  - Added reverse lookup: `SUBSCRIPTION_PRICE_TO_PLAN` maps price_id → plan_code
  - Added `EntitlementStatus` enum: `ENABLED`, `LIMITED`, `DISABLED`

- **Production Webhook Handler ✅** (`stripe_webhook_service.py`)
  - **Signature Verification**: Uses `STRIPE_WEBHOOK_SECRET` (skips in dev mode)
  - **Idempotency**: Records all events in `stripe_events` collection
    - Fields: `event_id`, `type`, `status`, `processed_at`, `related_client_id`, `raw_minimal`
    - If `event_id` already `PROCESSED`, returns 200 immediately
  - **Events Handled**:
    - `checkout.session.completed`: Primary provisioning trigger
    - `customer.subscription.created/updated`: Plan changes + entitlement updates
    - `customer.subscription.deleted`: Cancellation handling
    - `invoice.paid`: Payment recovery from past_due
    - `invoice.payment_failed`: Restricts side-effect actions
  - **Audit Logging**: Every transition logged with before/after state
  - **Always Returns 200**: Prevents Stripe retries, errors logged internally

- **Billing State Model ✅** (`client_billing` collection)
  - Fields: `client_id`, `stripe_customer_id`, `stripe_subscription_id`, `current_plan_code`, `subscription_status`, `entitlement_status`, `current_period_end`, `cancel_at_period_end`, `onboarding_fee_paid`, `latest_invoice_id`, `updated_at`
  - Entitlement Mapping:
    - `ACTIVE/TRIALING` → `ENABLED` (full access)
    - `PAST_DUE` → `LIMITED` (read-only, no side effects)
    - `UNPAID/CANCELED/INCOMPLETE_EXPIRED` → `DISABLED` (locked)

- **Billing API Routes ✅** (`routes/billing.py`)
  - `POST /api/billing/checkout`: Creates Stripe checkout session
  - `GET /api/billing/status`: Returns subscription status for user
  - `GET /api/billing/plans`: Returns all plans with Stripe price IDs (public)
  - `POST /api/billing/portal`: Creates Stripe billing portal session
  - `POST /api/billing/cancel`: Cancels subscription (at period end or immediate)

- **Upgrade/Downgrade Safety Rules ✅**
  - **Upgrade**: Features unlock immediately after `checkout.session.completed`
  - **Downgrade**: Non-destructive - if over property limit, sets `over_property_limit` flag
  - **Cancel**: At period end keeps `ENABLED` until `current_period_end`

- **Frontend Integration ✅**
  - `BillingPage.js` now calls real `/api/billing/checkout` endpoint
  - Redirects to Stripe checkout or billing portal on upgrade click

- **TEST REPORT:** `/app/test_reports/iteration_26.json` (20/20 tests - 100%)
  - All billing API endpoints verified
  - Webhook accepts all event types and returns 200
  - Stripe price IDs correctly mapped in plan registry

### January 21, 2026 (Session 11) - Admin Billing & Subscription Management ✅
- **Admin Billing UI** (`/admin/billing`)
  - **Search Panel**: Search clients by email, CRN, client_id, property address/postcode
  - **Statistics Panel**: Shows entitlement counts (Enabled/Limited/Disabled), plan distribution
  - **Needs Attention Section**: Lists clients with incomplete setup or LIMITED status
  - **Client Billing Snapshot**: Full details panel showing:
    - Client identifiers (name, email, company, CRN, client_id)
    - Plan & subscription info (plan code, name, property limit, over limit warning)
    - Entitlement status badge (ENABLED/LIMITED/DISABLED)
    - Stripe details (customer_id, subscription_id, onboarding fee paid)
    - Portal user & password setup status
    - Recent Stripe webhook events

- **Admin Actions (all audit-logged)**:
  - **Sync Billing Now**: Force fetch from Stripe, update entitlements, trigger provisioning if ENABLED
  - **Create Manage Billing Link**: Generate Stripe billing portal URL for customer
  - **Resend Password Setup Link**: Generate new token and send email
  - **Re-run Provisioning**: Force provision (only if entitlement ENABLED)
  - **Send Message**: Multi-channel (in_app, email, sms) with templates or custom text

- **Backend API Routes** (`routes/admin_billing.py`)
  - `GET /api/admin/billing/statistics` - Subscription stats dashboard
  - `GET /api/admin/billing/clients/search?q=...` - Search clients
  - `GET /api/admin/billing/clients/{client_id}` - Full billing snapshot
  - `POST /api/admin/billing/clients/{client_id}/sync` - Force Stripe sync
  - `POST /api/admin/billing/clients/{client_id}/portal-link` - Create billing portal link
  - `POST /api/admin/billing/clients/{client_id}/resend-setup` - Resend password setup
  - `POST /api/admin/billing/clients/{client_id}/force-provision` - Re-run provisioning
  - `POST /api/admin/billing/clients/{client_id}/message` - Send message to client

- **Safety Rules Enforced**:
  - Force provision only allowed if `entitlement_status == ENABLED`
  - Portal link only available if `stripe_customer_id` exists
  - SMS messaging gated by plan (requires Portfolio+)
  - All actions create audit logs with `UserRole.ROLE_ADMIN` actor

- **TEST REPORT:** `/app/test_reports/iteration_27.json` (29/29 tests - 100%)
  - All admin billing API endpoints verified
  - UI tested via Playwright with all action buttons
  - Fixed 3 bugs: auth_email field, actor_role enum, email service params

### January 21, 2026 (Session 12) - Subscription Lifecycle Emails & Job Safety Controls ✅
- **Subscription Lifecycle Emails** (4 new methods in `email_service.py`):
  - `send_payment_received_email()` - Sent after `checkout.session.completed`
    - Confirms payment, states provisioning started, links to portal
  - `send_payment_failed_email()` - Sent after `invoice.payment_failed`
    - No scare language, includes billing portal link, retry date if available
  - `send_renewal_reminder_email()` - Sent 7 days before renewal
    - Plan name, renewal date, amount, billing portal link
  - `send_subscription_canceled_email()` - Sent after `customer.subscription.deleted`
    - Access end date, billing portal link

- **EmailTemplateAlias Enum Updated** (`models.py`):
  - `PAYMENT_RECEIVED`, `PAYMENT_FAILED`, `RENEWAL_REMINDER`, `SUBSCRIPTION_CANCELED`

- **Stripe Webhook Email Integration** (`stripe_webhook_service.py`):
  - `checkout.session.completed` → Sends payment received email
  - `invoice.payment_failed` → Sends payment failed email
  - `customer.subscription.deleted` → Sends subscription canceled email

- **Background Job Safety Controls** (`jobs.py`):
  - **ALL jobs now check `entitlement_status: ENABLED`** before processing
  - Jobs affected: `daily_reminders`, `monthly_digests`, `compliance_check`, `renewal_reminders`, `scheduled_reports`
  - Clients with `LIMITED` or `DISABLED` entitlement are skipped (no emails, no side effects)
  - Comment added: "Per spec: no background jobs when entitlement is DISABLED"

- **Renewal Reminder Job** (NEW in `jobs.py`):
  - Runs daily, finds billing records with renewal within 7 days
  - Filters: `entitlement_status=ENABLED`, `cancel_at_period_end=False`, `renewal_reminder_sent!=True`
  - Sends email and marks `renewal_reminder_sent: True` to prevent duplicates

- **Admin Job Management Endpoints** (`routes/admin_billing.py`):
  - `GET /api/admin/billing/jobs/status` - Returns job blocking info:
    - `limited_clients` and `disabled_clients` counts
    - List of job types with schedules and descriptions
  - `POST /api/admin/billing/jobs/renewal-reminders` - Manually trigger renewal reminders
    - Returns count of reminders sent
    - Creates audit log

- **TEST REPORT:** `/app/test_reports/iteration_28.json` (21/21 tests - 100%)
  - All email methods verified to exist and be callable
  - Webhook handlers verified to send correct emails
  - Background jobs verified to filter by entitlement_status
  - Job endpoints verified for admin auth requirement

### January 22, 2026 (Session 13) - Public Website Build Phase 1 ✅
- **Public Website Infrastructure** (NEW - Additive, no CVP modifications):
  - Created `/app/frontend/src/pages/public/` directory with 13 new pages
  - Created `/app/frontend/src/components/public/` with shared components
  - All new routes added to App.js without modifying existing client/admin routes
  - SEO support via `react-helmet-async` library

- **New Public Pages Created**:
  - **HomePage.js** (`/`) - Main landing page with hero, features, services preview
  - **CVPLandingPage.js** (`/compliance-vault-pro`) - Product landing page
  - **ServicesHubPage.js** (`/services`) - Services overview hub
  - **ServiceDetailPage.js** (`/services/:slug`) - Individual service pages
  - **PricingPage.js** (`/pricing`) - Plan comparison with monthly/yearly toggle
  - **BookingPage.js** (`/booking`) - Calendly embed for consultations
  - **InsightsHubPage.js** (`/insights`) - Blog/insights hub
  - **AboutPage.js** (`/about`) - Company information
  - **ContactPage.js** (`/contact`) - Contact form with API integration
  - **CareersPage.js** (`/careers`) - Careers page
  - **PartnershipsPage.js** (`/partnerships`) - Partner opportunities
  - **PrivacyPage.js** (`/legal/privacy`) - Privacy policy
  - **TermsPage.js** (`/legal/terms`) - Terms of service

- **Shared Components Created**:
  - **PublicLayout.js** - Wrapper with header/footer
  - **PublicHeader.js** - Navigation with Platform/Services dropdowns
  - **PublicFooter.js** - Footer with link sections
  - **SEOHead.js** - Meta tags, OpenGraph, schema.org support

- **Backend Public API** (`/app/backend/routes/public.py`):
  - `POST /api/public/contact` - Contact form submission with rate limiting
  - `POST /api/public/service-inquiry` - Service inquiry submission
  - `GET /api/public/services` - List available services
  - `GET /api/public/services/:code` - Service details
  - Rate limiting: 5 requests per minute per IP
  - New collections: `contact_submissions`, `service_inquiries`

- **Design Implementation**:
  - Light theme with teal (#00B8A9) + white + charcoal grey
  - Modern UK corporate aesthetic
  - Trust-first look (no startup-y neon, no heavy animations)
  - Accessible contrast, lots of whitespace

- **CVP Isolation Verified**:
  - Zero modifications to existing CVP routes
  - Zero writes to CVP collections
  - Login, intake, client dashboard all still functional

- **Files Created**:
  - 13 page components in `/app/frontend/src/pages/public/`
  - 4 shared components in `/app/frontend/src/components/public/`
  - `/app/backend/routes/public.py` - New backend route file
  - `/app/frontend/public/robots.txt` - SEO robots file

### January 22, 2026 (Session 13b) - Orders System & Admin Pipeline ✅
- **Orders Workflow System** (NEW - CVP Isolated):
  - Created `/app/backend/services/order_workflow.py` - 14-state workflow machine
  - Created `/app/backend/services/order_service.py` - Order business logic with audit logging
  - Created `/app/backend/routes/orders.py` - Public order creation API
  - Created `/app/backend/routes/admin_orders.py` - Admin orders management API
  
- **Order Workflow States (14 total)**:
  - Payment & Intake: CREATED → PAID
  - Execution: QUEUED → IN_PROGRESS → DRAFT_READY → INTERNAL_REVIEW
  - Review Outcomes: REGEN_REQUESTED, REGENERATING, CLIENT_INPUT_REQUIRED
  - Delivery: FINALISING → DELIVERING
  - Terminal: COMPLETED, DELIVERY_FAILED, FAILED, CANCELLED

- **Admin Pipeline View** (`/admin/orders`):
  - Kanban-style pipeline with 8 visible columns
  - Order cards with customer name, service, time in state
  - Click-to-view order detail with full timeline
  - Admin review actions (Approve, Request Regen, Request Info)
  - Internal notes functionality

- **Backend APIs Created**:
  - `POST /api/orders/create` - Create new order
  - `GET /api/orders/{id}/status` - Public order status
  - `GET /api/admin/orders/pipeline` - Orders by status
  - `GET /api/admin/orders/pipeline/counts` - Status counts
  - `GET /api/admin/orders/{id}` - Order detail + timeline
  - `POST /api/admin/orders/{id}/transition` - Manual transition
  - `POST /api/admin/orders/{id}/approve` - Approve from INTERNAL_REVIEW
  - `POST /api/admin/orders/{id}/request-regen` - Request regeneration
  - `POST /api/admin/orders/{id}/request-info` - Request client info (pauses SLA)
  - `POST /api/admin/orders/{id}/notes` - Add internal note

- **Audit Logging**:
  - All state transitions logged to `workflow_executions` collection
  - Each entry includes: previous_state → new_state, triggered_by, timestamp, reason
  - Admin manual transitions require mandatory reason field

- **TEST REPORT**: `/app/test_reports/iteration_30.json` (24/24 tests - 100%)
  - Order creation and status verified
  - Pipeline view and counts verified
  - State transitions with validation verified
  - Admin review actions verified
  - Workflow audit trail verified
  - CVP isolation verified

### January 22, 2026 (Session - Side-by-Side Document Comparison Complete)
- **Side-by-Side Document Comparison ✅**
  
  **Compare Button:**
  - "Compare" button appears in Documents tab when order has 2+ versions
  - Button hidden for orders with 0-1 versions
  - data-testid: compare-versions-btn
  - Defaults to comparing last two versions (previous vs latest)
  
  **Comparison Modal:**
  - Title: "Compare Document Versions" with GitCompare icon
  - Description: "View two document versions side-by-side to identify changes"
  - Two panels: Left Panel (Older) and Right Panel (Newer)
  - Version dropdowns for selecting any version to compare
  - Selected version disabled in opposite dropdown
  - Status badges: DRAFT (amber), SUPERSEDED (gray), REGENERATED (blue), FINAL (green)
  - PDF download button in each panel header
  
  **Comparison Info Bar:**
  - Shows: "Comparing: v{X} (STATUS) → v{Y} (STATUS)"
  - Shows time difference calculation (minutes, hours, or days)
  
  **Technical Notes:**
  - PDF iframe preview shows "Not authenticated" (browser auth limitation)
  - Users should use PDF download buttons to view documents
  - Close modal via Close button, Escape key, or clicking outside
  
  **States Added:**
  - showComparisonModal: boolean
  - compareVersion1, compareVersion2: DocumentVersion objects
  
  **TEST REPORT:** /app/test_reports/iteration_38.json (9/9 features - 100%)

### January 22, 2026 (Session - Frontend Order Intake Complete)
- **Frontend Order Intake - Public Service Ordering ✅**
  
  **New Pages Created:**
  - `/services/catalogue` - ServicesCataloguePage.js
    - Displays all 23 services from database
    - Search functionality
    - Category filter (Reports, Documents, Add-ons, CVP)
    - Sort by Name, Price (Low to High), Price (High to Low)
    - Service cards with price, document count, delivery time
    - "Order Now" buttons linking to order flow
  
  - `/order/:serviceCode` - ServiceOrderPage.js
    - 3-step order flow: Your Details → Service Details → Review & Pay
    - Service summary card with price + VAT
    - Customer details form with validation
    - Dynamic intake form based on service intake_fields
    - Review step with full summary
    - Terms acceptance checkbox
    - Stripe checkout redirect
  
  - `/order-success` - OrderSuccessPage.js
    - Order confirmation display
    - Order reference number
    - "What happens next" steps
    - Links to browse more services
  
  **Backend Updates:**
  - Updated `/app/backend/routes/public.py` to use database-driven services
  - Created `/app/backend/routes/public_services.py` (alternative route)
  - GET /api/public/services returns all active services
  - GET /api/public/services/{code} returns service detail with intake_fields
  
  **Routes Added:**
  - GET /services/catalogue (frontend)
  - GET /order/:serviceCode (frontend)
  - GET /order-success (frontend)
  
  **TEST REPORT:** /app/test_reports/iteration_37.json (16/16 backend + 100% frontend)

### January 22, 2026 (Session - Phase D Service Expansion Complete)
- **Phase D: Service Expansion - 9 New Services Added ✅**
  
  **New Property Services:**
  - `INVENTORY_PRO` - Professional Property Inventory (£199)
  - `DUE_DILIGENCE` - Investment Due Diligence Report (£499)
  - `RENT_REVIEW` - Rent Review Analysis (£79)
  - `TENANT_REF` - Tenant Referencing Report (£35)
  - `EPC_CONSULT` - Energy Performance Consultation (£99)
  
  **New Specialist Services:**
  - `HMO_LICENCE_SUPPORT` - HMO Licensing Support Pack (£299)
  - `PORTFOLIO_ANALYSIS` - Portfolio Performance Analysis (£399)
  - `LEASE_EXTENSION` - Lease Extension Valuation (£249)
  - `AIRBNB_SETUP` - Short-Let Setup Consultation (£199)
  
  **Service Features:**
  - All services have detailed intake_fields with proper validation
  - All services have documents_generated definitions
  - Mix of TEMPLATE_ONLY, AI_ASSISTED_JSON, and HYBRID generation modes
  - Delivery via portal+email
  - Review required for quality assurance
  
  **Total Services in Catalogue: 23**
  - CVP Features: 2 (included)
  - CVP Add-ons: 3 (£49-£149)
  - Document Packs: 3 (£49.99-£149.99)
  - Standalone Reports: 14 (£35-£499)
  
  **TEST REPORT:** /app/test_reports/iteration_36.json (13/13 tests - 100%)

### January 22, 2026 (Session - Phase C UX Polish Complete)
- **Phase C: UX Polish - Enhanced User Experience ✅**
  
  **Improved Button Labels:**
  - "Generate Documents" → "Generate Draft" (clearer purpose)
  - "Request Regeneration" → "Request Revision" (user-friendly)
  - "Request More Info" → "Request Client Info" (specific action)
  - "Generate New" → "Create New Version" (contextual)
  
  **Descriptive Hover Tooltips:**
  - "Generate Draft": Creates an initial draft document (DOCX + PDF) for review
  - "Approve & Finalize": Lock document as FINAL, move order to delivery stage
  - "Request Revision": Create a new document version with changes (old version marked SUPERSEDED)
  - "Request Client Info": Pause workflow, send email to client requesting additional information
  - "DOCX": Download editable Word document (for internal use)
  - "PDF": Download PDF for delivery to customer
  
  **Clickable Timeline Events:**
  - Document-related events now clickable (cursor-pointer, blue hover)
  - Shows "v{X}" badge for version-related events
  - "Click to view document" helper text
  - Clicking opens document in viewer modal
  - Timeline tab has helper text: "Click on document events to open that version in the viewer"
  
  **UI Components Added:**
  - Imported Tooltip, TooltipContent, TooltipProvider, TooltipTrigger from UI components
  - ExternalLink icon for clickable timeline events
  
  **TEST REPORT:** /app/test_reports/iteration_35.json (8/8 features - 100%)

### January 22, 2026 (Session - Phase B Document Quality Complete)
- **Phase B: Document Quality - Real Document Generation ✅**
  
  **Real PDF Generation (reportlab):**
  - Professional PDF documents with branded headers and footers
  - Proper tables, sections, and formatting
  - Status watermarks for DRAFT/REGENERATED documents
  - Pleerity branding (teal #00B8A9, navy #0B1D3A)
  
  **Real DOCX Generation (python-docx):**
  - Editable Word documents with custom styles
  - Professional formatting with tables
  - Customer details, service details, document-type specific content
  - DRAFT watermark for non-final documents
  
  **Input Data Snapshotting:**
  - Each document version stores complete input snapshot
  - Snapshot includes: customer data, parameters, service_code, client responses
  - SHA256 hash of input data for traceability
  - Enables perfect regeneration with same inputs
  
  **UI Enhancements:**
  - Document versions show DOCX (Editable) badge in blue
  - Document versions show PDF (Delivery) badge in red
  - Status labels: DRAFT (amber), REGENERATED (blue), SUPERSEDED (gray), FINAL (green)
  - Document viewer modal shows both download buttons
  - Previous versions correctly marked SUPERSEDED
  
  **New Backend Files:**
  - `/app/backend/services/real_document_generator.py` - Production document generator
  - Updated `/app/backend/services/document_generator.py` to use RealDocumentGenerator
  
  **Dependencies Added:**
  - `python-docx==1.2.0` for DOCX generation
  - `lxml==6.0.2` (dependency of python-docx)
  
  **TEST REPORT:** /app/test_reports/iteration_34.json (16/16 tests - 100%)

### January 22, 2026 (Session - Phase A Foundation Complete)
- **Phase A: Foundation - Enterprise Hardening ✅**
  
  **Service Catalogue (Database-Driven):**
  - NEW `/app/backend/services/service_catalogue.py` - Single source of truth for services
  - 13 services seeded: CVP features, add-ons, document packs, standalone reports
  - NEW `/app/backend/routes/admin_services.py` - Full CRUD API for service management
  - NEW `/app/frontend/src/pages/AdminServiceCataloguePage.js` - Admin UI for service management
  - Service Catalogue navigation link added to admin header
  - Categories: CVP_FEATURE, CVP_ADDON, STANDALONE_REPORT, DOCUMENT_PACK
  - Pricing models: one_time, subscription, addon, included
  - Delivery types: portal, email, portal+email
  - Generation modes: TEMPLATE_ONLY, AI_ASSISTED_JSON, HYBRID
  
  **Immutable Order Records (Cancel/Archive replacing DELETE):**
  - DELETE endpoint returns 405 with message: "Use /cancel or /archive"
  - `POST /api/admin/orders/{id}/cancel` - Soft-delete for unpaid orders (requires reason)
  - `POST /api/admin/orders/{id}/archive` - Hide completed orders from pipeline (requires reason)
  - `POST /api/admin/orders/{id}/unarchive` - Restore archived orders
  - All actions logged to workflow_executions with full audit trail
  - Cancel/Archive modal in AdminOrdersPage with proper UX explanation
  
  **Document Status Labels:**
  - DocumentStatus enum: DRAFT, FINAL, SUPERSEDED, ARCHIVED
  - Status tracked per document version
  - Approval locks status to FINAL
  - Regeneration marks old versions as SUPERSEDED
  
  **Deterministic File Naming:**
  - Format: `{order_ref}_{service_code}_v{version}_{status}_{YYYYMMDD-HHMM}.{ext}`
  - Example: `ORD-2026-ABC123_DOC_PACK_ESSENTIAL_v1_DRAFT_20260122-1430.pdf`
  - Parseable, sortable, and conflict-free
  
  **API Endpoints Added:**
  - `GET /api/admin/services/` - List all services
  - `GET /api/admin/services/categories` - Get dropdown options
  - `GET /api/admin/services/{code}` - Get single service
  - `POST /api/admin/services/` - Create service
  - `PUT /api/admin/services/{code}` - Update service
  - `POST /api/admin/services/{code}/activate` - Activate service
  - `POST /api/admin/services/{code}/deactivate` - Deactivate service
  - `GET /api/public/services` - Public services (no auth)
  
  **TEST REPORT:** /app/test_reports/iteration_33.json (20/20 tests - 100%)

### January 22, 2026 (Session - Document-Centric Internal Review System)
- **Enterprise-Grade Orders Pipeline Complete ✅**
  
  **Document-Centric Internal Review:**
  - Admin must view document before taking action (document viewer modal)
  - Document version display with version number, timestamps, regeneration status
  - Approval locks the reviewed version as final (prevents further edits)
  - Reopen endpoint for exceptional edits with audit trail
  
  **Structured Regeneration (No Blind Regeneration):**
  - Mandatory reason dropdown (Missing info, Incorrect wording, Tone/style, etc.)
  - Required correction/reviewer notes field
  - Optional affected sections selection
  - Optional guardrails (preserve names/dates, preserve format)
  - All regeneration requests stored in audit log with full context
  
  **Request More Information Flow:**
  - Admin specifies what information is needed
  - Optional requested fields checklist
  - Optional deadline
  - Order transitions to CLIENT_INPUT_REQUIRED
  - SLA timer pauses automatically
  - Branded email sent to client with portal link
  - Client submits via /app/orders/{orderId}/provide-info
  - Client response stored versioned (v1, v2...)
  - Auto-transition back to INTERNAL_REVIEW
  - Admin receives email + in-app notification
  
  **Admin Notification Preferences:**
  - Email notifications (enabled/disabled + custom email)
  - SMS notifications (enabled/disabled + custom phone)
  - In-app notifications (bell icon with unread count)
  - Profile page for updating notification settings
  
  **Backend Services Created:**
  - `/app/backend/services/storage_adapter.py` - GridFS storage with abstraction for S3 migration
  - `/app/backend/services/document_generator.py` - Mock document generator (DOCX/PDF) with versioning
  - `/app/backend/services/order_email_templates.py` - Branded HTML email templates
  - `/app/backend/routes/client_orders.py` - Client order endpoints
  - `/app/backend/routes/admin_notifications.py` - Notification preferences API
  
  **Frontend Pages:**
  - `/app/frontend/src/pages/AdminOrdersPage.js` - Complete rewrite with document viewer, modals
  - `/app/frontend/src/pages/ClientProvideInfoPage.js` - Client submission form
  
  **API Endpoints:**
  - `POST /api/admin/orders/{id}/approve` - Approve with version lock
  - `POST /api/admin/orders/{id}/request-regen` - Structured regeneration
  - `POST /api/admin/orders/{id}/request-info` - Request client information
  - `POST /api/admin/orders/{id}/generate-documents` - Generate mock documents
  - `GET /api/admin/orders/{id}/documents` - Get document versions
  - `GET/PUT /api/admin/notifications/preferences` - Notification settings
  - `POST /api/client/orders/{id}/submit-input` - Client submits info
  - `POST /api/client/orders/{id}/upload-file` - Client uploads files
  - `POST /api/orders/create-test-order` - Dev endpoint for testing
  
  **MOCKED:**
  - Document generator produces text/XML files with DRAFT watermark (not real DOCX/PDF)
  - Email sending in test mode
  - SMS sending in test mode
  
  **TEST REPORT:** /app/test_reports/iteration_32.json (24/24 tests - 100%)

### January 22, 2026 - Template Renderer Phase 3 Complete ✅
- **Template Renderer V2 ✅** (`/app/backend/services/template_renderer.py`)
  
  **Deterministic Filename Convention:**
  `{order_ref}_{service_code}_v{version}_{status}_{YYYYMMDD-HHMM}.{ext}`
  Example: `ORD-2026-001234_AI_WF_BLUEPRINT_v1_DRAFT_20260122-1845.docx`
  
  **SHA256 Hash for Tamper Detection:**
  - Each DOCX and PDF has SHA256 hash stored
  - `compute_sha256()` function for integrity verification
  - Hashes stored in `document_versions_v2` collection
  
  **Immutable Versioning:**
  - Each generation creates NEW version (never overwrites)
  - Previous versions marked `SUPERSEDED` via `_mark_previous_superseded()`
  - `RenderStatus` enum: DRAFT, REGENERATED, SUPERSEDED, FINAL
  - All versions retained for audit trail
  
  **Document Generation:**
  - DOCX via `python-docx` with branded styling
  - PDF via `reportlab` with professional formatting
  - Watermarks for non-FINAL documents
  - Service-specific content rendering (AI, MR, Compliance, DocPacks)
  
  **Collection:** `document_versions_v2` with fields:
  - `order_id`, `order_ref`, `service_code`, `version`, `status`
  - `docx.filename`, `docx.sha256_hash`, `docx.size_bytes`
  - `pdf.filename`, `pdf.sha256_hash`, `pdf.size_bytes`
  - `intake_snapshot`, `intake_snapshot_hash`
  - `structured_output`, `json_output_hash`
  - `created_at`, `approved_at`, `approved_by`

- **Document Orchestrator Updates ✅** (`/app/backend/services/document_orchestrator.py`)
  
  **Correct Production Flow:**
  ```
  Payment Verified → Service Identified → Prompt Selected → Intake Validation
  → INTAKE SNAPSHOT (immutable, BEFORE GPT) → GPT Execution → JSON Output
  → Document Rendering (DOCX + PDF) → Versioning + Hashing → Human Review
  → Approve → Auto-Deliver → COMPLETE
     or Regenerate (with mandatory reason) → New Version → Review
     or Request Info → Client Input → Resume Review
  ```
  
  **Key Functions:**
  - `create_intake_snapshot()` - Creates immutable copy with hash BEFORE GPT
  - `execute_full_pipeline()` - Complete generation + rendering pipeline
  - `mark_reviewed()` - Fixed to use `find_one_and_update()` for proper sorting

- **Orchestration API Updates ✅** (`/app/backend/routes/orchestration.py`)
  
  **New Endpoints:**
  - `GET /api/orchestration/versions/{order_id}` - All versions with hashes
  - `GET /api/orchestration/versions/{order_id}/{version}` - Specific version
  
  **Validation Rules:**
  - Regeneration requires mandatory `regeneration_notes` (min 10 chars)
  - Review rejection requires mandatory `review_notes` (min 10 chars)
  - Review approval marks document as FINAL
  
  **Bug Fixed:**
  - `mark_reviewed()` was using unsupported `sort` with `update_one()`
  - Changed to `find_one_and_update()` which supports sort parameter
  
  **TEST REPORT:** `/app/test_reports/iteration_42.json` (27/27 tests - 100%)

### January 22, 2026 - Document Orchestration Phase 2 Complete ✅
- **GPT Prompt Registry ✅** (`/app/backend/services/gpt_prompt_registry.py`)
  
  **AUTHORITATIVE_FRAMEWORK (7 Hard Guardrails):**
  1. Never fabricate or estimate numerical figures
  2. Never provide legal or financial advice
  3. Never recommend specific contractors/service providers by name
  4. Never speculate on outcomes
  5. Never generate content outside user-provided inputs
  6. Flag missing/ambiguous data explicitly
  7. Cite UK-specific compliance standards
  
  **9 Prompts Defined:**
  - `AI_WF_BLUEPRINT_MASTER` - Workflow Automation Blueprint
  - `AI_PROC_MAP_MASTER` - Business Process Mapping
  - `AI_TOOLS_MASTER` - AI Tool Recommendation Report
  - `MR_BASIC_MASTER` - Basic Market Research
  - `MR_ADV_MASTER` - Advanced Market Research
  - `COMP_HMO_MASTER` - HMO Compliance Audit
  - `COMP_FULL_AUDIT_MASTER` - Full Compliance Audit
  - `COMP_MOVEOUT_MASTER` - Move-In/Move-Out Checklist
  - `DOC_PACK_ORCHESTRATOR` - Document Pack Orchestrator
  
  **Prompt Features:**
  - Structured JSON output schemas per service
  - Required fields validation
  - Temperature tuning (0.2 compliance, 0.3-0.4 AI/research)
  - GPT sections mapping to template placeholders
  - max_tokens configured per service complexity

- **Document Orchestrator Service ✅** (`/app/backend/services/document_orchestrator.py`)
  
  **Workflow:**
  Payment Verified → Select Prompt → Validate Intake → Execute GPT → 
  Structured JSON → Template Render → Human Review → Final Delivery
  
  **Payment Gating:**
  - `validate_order_for_generation()` checks `stripe_payment_status == 'paid'`
  - Blocks cancelled/completed/archived orders
  - Validates service_code against V2 catalogue
  
  **Execution Features:**
  - `execute_generation()` - Main entry point
  - `_build_user_prompt()` - Template substitution
  - `_execute_gpt()` - Gemini integration via emergentintegrations
  - Execution history tracking in `orchestration_executions` collection
  - Token usage tracking
  
  **Human Review Gate:**
  - `mark_reviewed()` - Approve or reject
  - Approved → `final_ready` for delivery
  - Rejected → `changes_requested` for regeneration

- **Orchestration API Routes ✅** (`/app/backend/routes/orchestration.py`)
  
  **Endpoints (Admin Auth Required):**
  - `POST /api/orchestration/generate` - Generate documents for paid order
  - `POST /api/orchestration/regenerate` - Regenerate with changes
  - `POST /api/orchestration/review` - Approve/reject generated content
  - `GET /api/orchestration/history/{order_id}` - Get generation history
  - `GET /api/orchestration/latest/{order_id}` - Get latest generation
  - `GET /api/orchestration/validate/{service_code}` - Get prompt definition
  - `POST /api/orchestration/validate-data` - Validate intake against requirements
  - `GET /api/orchestration/stats` - Get execution statistics

- **Integration:**
  - Uses Emergent LLM Key for Gemini integration
  - Service Catalogue V2 integration for service validation
  - Order status updates on generation/review
  
  **TEST REPORT:** `/app/test_reports/iteration_41.json` (33/33 backend tests - 100%)

### January 22, 2026 - Service Catalogue V2 Phase 1 Complete ✅
- **Authoritative Service Catalogue V2 (Foundation) ✅**
  
  **New Categories (Explicit, as Defined):**
  - `ai_automation` - Workflow blueprints, process mapping, AI tools
  - `market_research` - Basic and advanced market research
  - `compliance` - HMO audits, full audits, move-in/out checklists
  - `document_pack` - Essential, Plus (Tenancy), Pro (Ultimate) packs
  - `subscription` - CVP subscription tiers
  
  **12 Authoritative Services Defined:**
  - AI_WF_BLUEPRINT: Workflow Automation Blueprint @ £79
  - AI_PROC_MAP: Business Process Mapping @ £129
  - AI_TOOLS: AI Tool Recommendation Report @ £59
  - MR_BASIC: Market Research – Basic @ £69
  - MR_ADV: Market Research – Advanced @ £149
  - COMP_HMO: HMO Compliance Audit @ £79
  - COMP_FULL_AUDIT: Full Compliance Audit Report @ £99
  - COMP_MOVEOUT: Move-In / Move-Out Checklist @ £35
  - DOC_PACK_ESSENTIAL: Essential Landlord Document Pack @ £29
  - DOC_PACK_PLUS: Tenancy Legal & Notices Pack @ £49
  - DOC_PACK_PRO: Ultimate Landlord Document Pack @ £79
  - CVP_SUBSCRIPTION: Compliance Vault Pro (3 tiers)
  
  **Pack Hierarchy Enforcement (Essential → Plus → Pro):**
  - DOC_PACK_ESSENTIAL: 5 documents (Rent Arrears, Deposit Refund, Tenant Reference, Rent Receipt, GDPR Notice)
  - DOC_PACK_PLUS: 11 documents (5 inherited + AST, PRT, Renewal, Notice to Quit, Rent Increase, Guarantor)
  - DOC_PACK_PRO: 15 documents (11 inherited + Inventory, Deposit Info, Property Access, Additional Notice)
  
  **Add-on Enforcement:**
  - Fast Track: +£20, 24hr delivery (all services)
  - Printed Copy: +£25, postal delivery (document packs only)
  
  **CVP Subscription Tiers:**
  - Solo Landlord: £19/month + £49 setup (up to 2 properties)
  - Portfolio: £39/month + £79 setup (up to 10 properties)
  - Professional: £79/month + £149 setup (up to 25 properties)
  
  **New Backend Files:**
  - `/app/backend/services/service_catalogue_v2.py` - V2 Service Catalogue schema and service
  - `/app/backend/services/service_definitions_v2.py` - 12 authoritative service definitions with seed function
  - `/app/backend/routes/admin_services_v2.py` - Admin CRUD APIs for V2 catalogue
  - `/app/backend/routes/public_services_v2.py` - Public read APIs for V2 catalogue
  
  **New API Endpoints (V2):**
  - `GET /api/public/v2/services` - List all active non-CVP services
  - `GET /api/public/v2/services/by-category` - Services grouped by category
  - `GET /api/public/v2/services/document-packs` - Document packs with hierarchy
  - `GET /api/public/v2/services/{service_code}` - Service details
  - `GET /api/public/v2/services/{service_code}/intake` - CRM field dictionary intake fields
  - `GET /api/public/v2/services/{service_code}/price` - Price calculation with add-ons
  - `GET /api/public/v2/cvp/plans` - CVP subscription plans
  - `GET /api/admin/services/v2/*` - Admin CRUD for catalogue management
  
  **Frontend Updates:**
  - Removed cleaning services from PublicHeader.js navigation
  - Removed cleaning services from PublicFooter.js links
  - Removed cleaning services section from ServicesHubPage.js
  - Removed cleaning entry from ServiceDetailPage.js
  
  **CVP Boundary (Hard Rule Maintained):**
  - CVP remains isolated - no changes to CVP collections
  - CVP documents = reports/summaries/audits only
  - Legal/operational documents flow through Orders system only
  
  **TEST REPORT:** `/app/test_reports/iteration_40.json` (34/34 backend tests - 100%)

### January 22, 2026 - Admin-Managed Blog/Insights Feature Complete
- **Blog Backend APIs ✅**
  - `POST /api/blog/admin/posts` - Create blog post with auto-slug generation
  - `GET /api/blog/admin/posts` - List all posts with pagination, filtering (status, category), search
  - `GET /api/blog/admin/posts/{id}` - Get single post by ID
  - `PUT /api/blog/admin/posts/{id}` - Update post
  - `DELETE /api/blog/admin/posts/{id}` - Delete post
  - `POST /api/blog/admin/posts/{id}/publish` - Publish draft post
  - `POST /api/blog/admin/posts/{id}/unpublish` - Unpublish to draft
  - `GET /api/blog/admin/categories` - Get categories list
  - `GET /api/blog/admin/tags` - Get tags list
  
- **Public Blog APIs ✅**
  - `GET /api/blog/posts` - List published posts only (with pagination)
  - `GET /api/blog/posts/{slug}` - Get single post by slug (increments view count)
  - `GET /api/blog/categories` - Get categories with post counts
  - `GET /api/blog/tags/popular` - Get popular tags with counts
  - `GET /api/blog/featured` - Get featured/recent posts
  
- **Admin Blog UI ✅** (`/admin/blog`)
  - Stats cards: Total Posts, Published, Drafts, Categories
  - Posts table with status badges, view counts, actions
  - Search and filter by status/category
  - Post editor modal with Content/Settings/SEO tabs
  - Create, edit, publish/unpublish, delete posts
  - Auto-slug generation from title
  - Tag management (comma-separated)
  - Featured image URL with preview
  
- **Public Insights Page ✅** (`/insights`)
  - Hero section with search bar
  - Category filter buttons with counts
  - Post cards grid with featured images, excerpts
  - Popular tags sidebar
  - Single post view at `/insights/{slug}`
  - Markdown-like content rendering
  - View count display
  - Related CTA sections
  
- **DB Schema:** `blog_posts` collection with: title, slug, excerpt, content, featured_image, category, tags, status, author_id, author_name, meta_title, meta_description, view_count, created_at, updated_at, published_at
  
- **TEST REPORT:** `/app/test_reports/iteration_39.json` (25/25 tests - 100%)

### January 23, 2026 - Orders Pipeline Refactoring (Frontend)
- **AdminOrdersPage.js Refactored ✅**
  - Original 1900+ line file broken into modular components
  - Enterprise-grade order management with workflow controls
  
- **New Components Created:**
  - `OrderPipelineView.jsx` - Clickable pipeline stages with live counts (badge), auto-refresh toggle
  - `OrderList.jsx` - Sortable/searchable order cards with priority indicators
  - `OrderDetailsPane.jsx` - Order details dialog with 4 tabs (Details, Documents, Timeline, Actions)
  - `DocumentPreviewModal.jsx` - Document viewer with metadata, version history, review checkbox gate
  - `ActionModals.jsx` - RegenerationModal, RequestInfoModal, ManualOverrideModal
  - `AuditTimeline.jsx` - Chronological event timeline with clickable document links
  - `ordersApi.js` - Centralized API client for all order operations
  
- **Pipeline View Features:**
  - 10 pipeline stages: Paid → Queued → In Progress → Draft Ready → Review → Awaiting Client → Finalising → Delivering → Completed → Failed
  - Active indicators (pulsing dots) on stages with orders
  - Click stage to view filtered order list
  - 15-second auto-refresh with toggle control
  - Manual refresh button
  
- **Document Review Features:**
  - Full PDF preview in modal with iframe
  - Document metadata: order_ref, service_code, version, status, generated_at, generated_by, SHA256 hash
  - Version history (v1/v2/v3 clickable)
  - **Review checkbox gate**: "I have reviewed this document" must be checked before Approve button is enabled
  - Download buttons for DOCX (editable) and PDF (delivery)
  
- **Structured Action Modals:**
  - **Regeneration**: Reason dropdown (required) + mandatory notes (min 10 chars) + guardrails checkboxes
  - **Request Info**: Notes (required) + quick select fields + deadline dropdown + email notification
  - **Manual Override**: Retry automation or advance stage (whitelisted only) with mandatory reason
  
- **Bug Fixed:**
  - AuditTimeline.jsx - `triggered_by` object rendered directly fixed to extract `user_email`
  
- **TEST REPORT:** `/app/test_reports/iteration_43.json` (10/10 features - 100%)

### January 23, 2026 - E2E Evidence: Document Pack Flow
- **Full Order Lifecycle Demonstrated:**
  - Order: ORD-2026-C63D54 (DOC_PACK_TENANCY - Tenancy Legal & Notices Pack)
  - Customer: Compare Test User (compare-test@example.com)
  
- **Document Generation Pipeline:**
  - v1 DRAFT → SUPERSEDED (auto-regenerated)
  - v2 REGENERATED → APPROVED & LOCKED
  - Both versions have DOCX + PDF with SHA256 hashes
  - Intake data snapshotted before each generation
  
- **Approval Flow:**
  - Admin reviewed document in INTERNAL_REVIEW status
  - Approved at: 2026-01-22T20:18:38
  - Approved by: admin@pleerity.com
  - Document v2 locked as final
  - Order transitioned: INTERNAL_REVIEW → FINALISING
  
- **Delivery Automation:**
  - Triggered: FINALISING → DELIVERING → COMPLETED
  - Email sent to: compare-test@example.com
  - Documents: 2 (PDF + DOCX)
  - Delivered at: 2026-01-22T20:28:02
  - Deliverables recorded in order with filenames
  
- **Complete Audit Trail:**
  - CREATED (system)
  - FINALISING (admin_manual) - Document v2 locked
  - DELIVERING (system) - Auto-delivery initiated
  - COMPLETED (system) - Documents delivered via email
  
- **Delivery Endpoints Added:**
  - `POST /api/admin/orders/{id}/deliver` - Trigger delivery
  - `POST /api/admin/orders/{id}/retry-delivery` - Retry failed delivery
  - `POST /api/admin/orders/{id}/manual-complete` - Admin override completion
  - `POST /api/admin/orders/batch/process-delivery` - Process all pending

### January 23, 2026 - Background Job: Automatic Delivery Processing
- **APScheduler Job Added:**
  - Job ID: `order_delivery_processing`
  - Schedule: Every 5 minutes (`*/5`)
  - Function: `run_order_delivery_processing()`
  
- **Verified Automatic Flow:**
  - Order: ORD-TEST-891CB5FA (Section 21 Notice Pack)
  - Approval: Admin approved document v1
  - Auto-delivery: Job processed FINALISING → DELIVERING → COMPLETED
  - Delivered at: 2026-01-22T20:35:23
  - Email sent to customer with DOCX + PDF links
  
- **Full Audit Trail:**
  1. INTERNAL_REVIEW - Order created
  2. FINALISING - Admin approved document
  3. DELIVERING - Auto-delivery initiated
  4. COMPLETED - Documents delivered via email

- **Pipeline Counts After Test:**
  - COMPLETED: 2 (up from 0)
  - All state transitions logged with timestamps

### January 23, 2026 - Document Preview Auth & Admin Notifications
- **Document Preview Token System:**
  - Created `document_access_token.py` service for generating signed JWT tokens
  - New endpoint: `GET /api/admin/orders/{id}/documents/{version}/token` - Generates 30-minute access token
  - New endpoint: `GET /api/admin/orders/{id}/documents/{version}/view?token=...` - Token-based document access
  - Frontend `DocumentPreviewModal.jsx` now fetches token before rendering iframe
  - PDF preview works in iframe without Bearer header

- **Admin Notifications System:**
  - Created `order_notification_service.py` with event-based notifications
  - 12 notification event types: NEW_ORDER, DOCUMENT_READY, CLIENT_INPUT_REQUIRED, DOCUMENT_APPROVED, ORDER_DELIVERED, DELIVERY_FAILED, ORDER_FAILED, PRIORITY_FLAGGED, SLA_WARNING, SLA_BREACH, CLIENT_RESPONDED, REGENERATION_REQUESTED
  - Supports Email, SMS, and In-app channels (configurable per admin)
  - Priority levels: LOW, MEDIUM, HIGH, URGENT
  - Created `NotificationBell.jsx` component in admin header
  - Bell icon shows unread count badge
  - Dropdown displays recent notifications with mark-as-read
  - Notifications linked to orders for quick navigation
  - Hooks into delivery service for automatic notifications

- **Files Created:**
  - `/app/backend/services/document_access_token.py`
  - `/app/backend/services/order_notification_service.py`
  - `/app/frontend/src/components/admin/NotificationBell.jsx`

### January 23, 2026 - SLA Monitoring & Client Portal (CURRENT SESSION) ✅
- **Service-Specific SLA Configuration:**
  - SLA_CONFIG_BY_CATEGORY with category-based SLA hours:
    - Document Packs: 48h standard / 24h fast-track
    - Compliance Services: 72h standard / 24h fast-track
    - AI Automation: 120h (5 business days) / 72h fast-track
    - Market Research: 72h basic / 120h advanced
    - Subscriptions: 24h / 12h fast-track
  - SLA_SERVICE_OVERRIDES for service-specific SLA (COMP_HMO, AI_WF_BLUEPRINT, MR_BASIC, etc.)
  - SLA clock: Starts at PAID, Pauses at CLIENT_INPUT_REQUIRED, Ends at COMPLETED
  - FAST_TRACK_GUARDRAILS: Prevents fast-track from bypassing human_review, audit_logs, versioning

- **SLA Tracking Fields:**
  - `sla_started_at`: When SLA clock began (at payment)
  - `sla_target_at`: Deadline timestamp
  - `sla_warning_at`: Warning threshold timestamp (75-80% of SLA)
  - `sla_paused_at`: When SLA paused for client input
  - `sla_total_paused_duration`: Total hours paused
  - `sla_warning_sent`, `sla_breach_sent`: Notification flags

- **SLA Timeline Events Logged:**
  - SLA_STARTED: When payment verified
  - SLA_PAUSED: When waiting for client input
  - SLA_RESUMED: When client provides input
  - SLA_WARNING_ISSUED: When warning notification sent
  - SLA_BREACHED: When deadline exceeded

- **Workflow Functions Updated:**
  - `initialize_order_sla()`: Sets up SLA fields on order payment (WF1)
  - `log_sla_event()`: Records SLA timeline events to workflow_executions
  - `get_sla_hours_for_order()`: Returns SLA config based on service code/category
  - WF1: Now initializes SLA tracking
  - WF5: Now logs SLA resume and tracks pause duration
  - WF9: Now uses service-specific SLA hours for monitoring

- **Client Portal Document Downloads:**
  - NEW page: `/app/orders` - Client orders with search, filter, stats
  - NEW endpoint: `GET /api/client/orders/{id}/documents` - List downloadable docs
  - NEW endpoint: `GET /api/client/orders/{id}/documents/{version}/download` - Stream document
  - NEW endpoint: `GET /api/client/orders/{id}/documents/{version}/access-token` - Get temp token
  - NEW endpoint: `GET /api/client/orders/download-summary` - Document library summary
  - Documents only available for COMPLETED orders with FINAL status

- **Admin Notification Preferences Page:**
  - NEW page: `/admin/notifications/preferences` 
  - Toggle channels: Email, SMS, In-app notifications
  - Configure notification email/phone
  - Event types displayed: New Orders, Document Ready, Client Response, SLA Warning/Breach, Delivery Status
  - Uses existing backend APIs at `/api/admin/notifications/preferences`

- **Files Created/Modified:**
  - `/app/backend/services/workflow_automation_service.py` - SLA config + helper functions
  - `/app/backend/routes/client_orders.py` - Document download endpoints
  - `/app/backend/services/storage_adapter.py` - get_file_content() function
  - `/app/frontend/src/pages/ClientOrdersPage.js` - Client orders portal
  - `/app/frontend/src/pages/AdminNotificationPreferencesPage.js` - Notification settings

- **TEST REPORT:** `/app/test_reports/iteration_44.json` (27/27 backend tests - 100%)
  - SLA configuration verified for all categories
  - Client orders API tested with auth requirements
  - Admin notification preferences API tested
  - Both frontend pages render correctly with all UI elements

### January 23, 2026 - FastTrack, Postal Tracking & Compliance Score Enhancement ✅
- **Legacy Services Removed from V1 Catalogue:**
  - Removed: INVENTORY_PRO, EPC_CONSULT, HMO_LICENCE_SUPPORT, PORTFOLIO_ANALYSIS, LEASE_EXTENSION, AIRBNB_SETUP
  - These were not part of Pleerity's service offering
  - Active services preserved: CVP_COMPLIANCE_REPORT, DOC_PACK_*, AI_WF_BLUEPRINT, MR_BASIC, etc.

- **FastTrack Queue Priority:**
  - WF1 sets `queue_priority`: 10 for priority, 5 for fast_track orders
  - `expedited` flag set on fast-track/priority orders
  - `process_queued_orders` sorts by queue_priority DESC, then priority, then fast_track, then created_at
  - Admin notification sent for fast-track orders with ⚡ indicator
  - Frontend: Purple badge with `animate-pulse` class for visual attention

- **Printed Copy Postal Tracking:**
  - New fields on orders: `requires_postal_delivery`, `postal_status`, `postal_tracking_number`, `postal_carrier`, `postal_delivery_address`
  - Status flow: PENDING_PRINT → PRINTED → DISPATCHED → DELIVERED (with FAILED option)
  - NEW endpoint: `GET /api/admin/orders/postal/pending` - Lists orders grouped by postal status
  - NEW endpoint: `POST /api/admin/orders/{id}/postal/status` - Update postal status with tracking
  - NEW endpoint: `POST /api/admin/orders/{id}/postal/address` - Set delivery address
  - NEW endpoint: `GET /api/admin/orders/{id}/postal` - Get postal details
  - Email notification sent to customer when order is DISPATCHED with tracking number
  - Frontend: Cyan badge showing "Print Copy" on orders, postal section in OrderDetailsPane

- **Enhanced Compliance Score:**
  - **Requirement Type Weighting:**
    - GAS_SAFETY: 1.5x (critical legal requirement)
    - EICR: 1.4x (legally required)
    - HMO_LICENCE: 1.6x (critical for HMO)
    - FIRE_RISK_ASSESSMENT: 1.5x
    - SMOKE_ALARM/CO_ALARM: 1.3x
    - EPC: 1.2x
    - DEPOSIT_PROTECTION: 1.1x
    - Standard requirements: 1.0x
  - **HMO Property Multiplier:** 0.9x (stricter scoring for HMO properties)
  - **Document Verification:** Only VERIFIED documents count for scoring
  - **New Weights:** Status 35%, Expiry 25%, Documents 15%, Overdue Penalty 15%, Risk Factor 10%
  - **Breakdown Fields:** status_score, expiry_score, document_score, overdue_penalty_score, risk_score
  - **Critical Overdue Tracking:** Extra penalty for critical requirements (Gas Safety, EICR, HMO Licence)
  - **Prioritized Recommendations:** Sorted by priority with impact estimates

- **TEST REPORT:** `/app/test_reports/iteration_45.json` (26/26 backend tests - 100%)

### January 23, 2026 - Unified Intake Wizard (Non-CVP Services) Complete ✅
- **Unified Intake Wizard Frontend Complete** (`/order/intake`)
  - 5-step multi-step wizard for all non-CVP services:
    1. Select Service - All 11 services across 4 categories
    2. Your Details - Client identity (Name, Email, Phone, Role, Company)
    3. Service Details - Dynamic form fields from backend schema
    4. Review - Order summary with pricing and consent checkboxes
    5. Payment - Stripe checkout redirect
  
  - **Features Implemented:**
    - Schema-driven dynamic forms from backend `/api/intake/schema/{service_code}`
    - Service pre-selection via URL param: `/order/intake?service=DOC_PACK_ESSENTIAL`
    - Document Pack add-ons: Fast Track (£20), Printed Copy (£25)
    - Postal address form appears when Printed Copy selected
    - Draft reference generation (INT-YYYYMMDD-####)
    - Pricing calculation with add-ons
    - Form validation (client-side and server-side)
    - Step navigation (Continue/Back buttons)
    - Form data persistence across navigation
  
  - **Services Available in Wizard:**
    - AI & Automation: Workflow Blueprint (£79), Process Mapping (£129), Tool Report (£59)
    - Market Research: Basic (£69), Advanced (£149)
    - Compliance: HMO Audit (£79), Full Audit (£99), Move-In/Out Checklist (£35)
    - Document Packs: Essential (£29), Tenancy (£49), Ultimate (£79)
  
  - **Backend APIs (All Working):**
    - `GET /api/intake/services` - List all 11 services
    - `GET /api/intake/packs` - Document packs with 2 add-ons
    - `GET /api/intake/schema/{service_code}` - Dynamic field schema
    - `POST /api/intake/draft` - Create intake draft
    - `PUT /api/intake/draft/{draft_id}/client-identity` - Update client data
    - `PUT /api/intake/draft/{draft_id}/intake` - Update service fields
    - `PUT /api/intake/draft/{draft_id}/addons` - Update add-ons and postal address
    - `PUT /api/intake/draft/{draft_id}/delivery-consent` - Update consent
    - `POST /api/intake/draft/{draft_id}/checkout` - Create Stripe checkout
    - `POST /api/intake/calculate-price` - Calculate total with add-ons
    - `GET /api/intake/draft/{draft_id}/confirmation` - Poll for order conversion
  
  - **Order Confirmation Page** (`/order/confirmation?draft_id=...`)
    - Polls for draft → order conversion after payment
    - Shows loading state, success with order reference, or error
    - Displays "What happens next" steps
    - Links to client orders page
  
  - **Routing Updated:**
    - ServicesCataloguePage "Order Now" buttons now link to `/order/intake?service={code}`
    - App.js routes: `/order/intake`, `/order/intake/:draftId`, `/order/confirmation`
  
  - **Bug Fixed:**
    - API client had `/api` as baseURL, but wizard code also prefixed `/api/`
    - Fixed double `/api/api/` path issue by removing prefix from wizard API calls

- **Files Created/Modified:**
  - `/app/frontend/src/pages/UnifiedIntakeWizard.js` - Full 1093-line wizard implementation
  - `/app/frontend/src/pages/OrderConfirmationPage.js` - Post-payment confirmation page
  - `/app/frontend/src/pages/public/ServicesCataloguePage.js` - Updated "Order Now" links
  - `/app/frontend/src/App.js` - Added wizard routes
  - `/app/backend/tests/test_intake_wizard.py` - 32 comprehensive API tests

- **TEST REPORT:** `/app/test_reports/iteration_46.json` (32/32 backend + 100% frontend)
  - All backend API endpoints verified
  - All frontend wizard flows tested
  - URL pre-selection working
  - Draft creation and step navigation verified

### January 23, 2026 (Session 2) - Four Feature Implementation ✅

**1. Admin Analytics Dashboard (`/admin/analytics`) ✅**
  - Comprehensive business intelligence dashboard
  - **6 API Endpoints:**
    - `GET /api/admin/analytics/summary` - Revenue, orders, AOV, completion rate
    - `GET /api/admin/analytics/services` - Service breakdown by revenue
    - `GET /api/admin/analytics/sla-performance` - On-time, warnings, breached, health score
    - `GET /api/admin/analytics/customers` - Total, repeat rate, top customers
    - `GET /api/admin/analytics/conversion-funnel` - Draft → Payment → Order → Completion
    - `GET /api/admin/analytics/addons` - Fast Track and Printed Copy analytics
  - **UI Components:**
    - 4 stat cards with trend indicators (up/down/flat)
    - Period selector: Today, 7d, 30d, 90d, YTD, All
    - Service Performance bar chart
    - Conversion Funnel visualization
    - SLA Performance with health score
    - Add-on Performance (Fast Track, Printed Copy)
    - Customer Insights with top customers

**2. Admin Intake Schema Manager (`/admin/intake-schema`) ✅**
  - Allows admins to customize wizard forms without code changes
  - **2 API Endpoints:**
    - `GET /api/admin/intake-schema/services` - Lists 11 services with field counts
    - `GET /api/admin/intake-schema/{service_code}` - Returns schema with fields
    - `PUT /api/admin/intake-schema/{service_code}` - Save field overrides
    - `POST /api/admin/intake-schema/{service_code}/reset` - Reset to defaults
  - **Field Customization:**
    - Edit labels, helper text, placeholders
    - Toggle required status
    - Reorder fields
    - Hide/show fields
    - Modify validation rules
    - Edit dropdown options
  - **UI Features:**
    - Left sidebar: Service list with field counts and customization status
    - Right panel: Field editor grouped by category
    - Accordion-based field groups
    - Type badges (Text Input, Email, Phone, Dropdown, etc.)
    - Required badges
    - Eye icon for hide/show toggle

**3. Dynamic Service Detail Pages (V2 API) ✅**
  - `/services/{slug}` now fetches from Service Catalogue V2 API
  - Falls back to static data for legacy slugs
  - **Dynamic Data:**
    - Title, description, long description from API
    - Pricing calculated from base_price (pence to pounds)
    - Turnaround hours from sla_hours or standard_turnaround_hours
    - Fast Track and Printed Copy badges when available
  - **Order Now Button:** Links to `/order/intake?service={CODE}`
  - Slug-to-code mapping for backward compatibility

**4. Toast Error Fix ✅**
  - Fixed transient toast errors on `ClientOrdersPage.js`
  - Fixed transient toast errors on `AdminNotificationPreferencesPage.js`
  - **Root Cause:** API calls firing before auth, showing error toast then redirecting
  - **Fix:** Check for 401 status before showing error toast
  - Also fixed API paths (removed duplicate `/api` prefix)

**Files Created:**
  - `/app/backend/routes/analytics.py` - Analytics API endpoints
  - `/app/backend/routes/admin_intake_schema.py` - Schema management APIs
  - `/app/frontend/src/pages/AdminAnalyticsDashboard.js` - Analytics dashboard UI
  - `/app/frontend/src/pages/AdminIntakeSchemaPage.js` - Schema manager UI

**Files Modified:**
  - `/app/frontend/src/pages/public/ServiceDetailPage.js` - V2 API integration
  - `/app/frontend/src/pages/ClientOrdersPage.js` - Toast error fix
  - `/app/frontend/src/pages/AdminNotificationPreferencesPage.js` - Toast error fix
  - `/app/frontend/src/App.js` - Added new admin routes
  - `/app/backend/server.py` - Registered new routers

- **TEST REPORT:** `/app/test_reports/iteration_47.json` (31/31 backend + 100% frontend)
  - All analytics API endpoints verified
  - All intake schema API endpoints verified
  - Service Detail V2 API integration verified
  - Toast error fix verified
  - All UI components working

### January 23, 2026 (Session 3) - 24/7 Support Assistant System ✅

**Complete Support System Implementation:**

**1. AI Support Chatbot (Gemini-powered) ✅**
  - Custom AI chatbot using Gemini via Emergent LLM Key
  - Knowledge base with all Pleerity services (CVP, Document Packs, AI Automation, Market Research)
  - Multi-service routing based on message content
  - No-legal-advice guardrails (refuses legal interpretation, council enforcement predictions)
  - Service area and category detection
  - Urgency detection from message content
  
**2. Support Chat Widget (`/app/frontend/src/components/SupportChatWidget.js`) ✅**
  - Floating chat button on all public pages
  - Expandable chat window with greeting message
  - Real-time AI responses
  - Human handoff with 3 options:
    - Live Chat via Tawk.to (integration ready, needs property ID)
    - Email Ticket form (inline)
    - WhatsApp link with prefilled message
  - Message history within session
  - Minimize/maximize/close controls
  
**3. Tawk.to Live Chat Integration ✅**
  - Component: `/app/frontend/src/components/TawkToWidget.js`
  - Lazy loading of Tawk.to script
  - API wrapper for show/hide/maximize
  - Context passing (conversation_id, CRN, service_area)
  - **MOCKED:** Needs `REACT_APP_TAWKTO_PROPERTY_ID` configuration in .env
  
**4. WhatsApp Handoff (Tier 1) ✅**
  - Prefilled message links with conversation reference
  - Includes CRN if provided
  - Format: `https://wa.me/{number}?text={message}`
  - **Note:** WhatsApp number placeholder needs real number
  
**5. Support Ticket System ✅**
  - **Data Models:**
    - `support_conversations` - Conversation tracking
    - `support_messages` - Full message transcript
    - `support_tickets` - Ticket management
    - `support_audit_log` - Audit trail
  - **API Endpoints:**
    - `POST /api/support/chat` - AI chatbot interaction
    - `POST /api/support/lookup` - CRN+email verification (sanitized)
    - `POST /api/support/ticket` - Create support ticket
    - `GET /api/support/account-snapshot` - Client-scoped (authenticated)
  
**6. Admin Support Dashboard (`/admin/support`) ✅**
  - **Stats Cards:** Open Tickets, High Priority, Open Conversations, Escalated
  - **Tabs:** Tickets and Chats with filter dropdowns (Status, Priority)
  - **Conversation Viewer:** Full transcript with User/Bot/Human messages
  - **Admin Reply:** Reply input sends message to conversation
  - **Ticket Management:** View, status update, assign, add notes
  - **CRN Lookup:** Admin-only full account lookup
  - **API Endpoints:**
    - `GET /api/admin/support/stats` - Dashboard stats
    - `GET /api/admin/support/conversations` - List with filters
    - `GET /api/admin/support/tickets` - List with filters
    - `GET /api/admin/support/conversation/{id}` - Full transcript
    - `POST /api/admin/support/conversation/{id}/reply` - Admin reply
    - `PUT /api/admin/support/ticket/{id}/status` - Update status
    - `PUT /api/admin/support/ticket/{id}/assign` - Assign ticket
    - `POST /api/admin/support/ticket/{id}/note` - Add note
    - `POST /api/admin/support/lookup-by-crn` - Admin lookup
    - `GET /api/admin/support/audit-log` - View audit logs

**7. Security & Compliance ✅**
  - All admin endpoints require RBAC authentication
  - Public lookup requires both CRN and email match
  - All lookup attempts audit-logged with IP
  - Rate limiting structure in place (TODO: implement)
  - No legal advice guardrails enforced by AI

**Files Created:**
  - `/app/backend/services/support_service.py` - Data models and CRUD services
  - `/app/backend/services/support_chatbot.py` - AI chatbot with Gemini, guardrails
  - `/app/backend/routes/support.py` - All API endpoints (public, client, admin)
  - `/app/frontend/src/components/SupportChatWidget.js` - Chat widget UI
  - `/app/frontend/src/components/TawkToWidget.js` - Tawk.to integration
  - `/app/frontend/src/pages/AdminSupportPage.js` - Admin dashboard
  - `/app/backend/tests/test_support_system.py` - 24 comprehensive tests

**Files Modified:**
  - `/app/backend/server.py` - Registered support routers
  - `/app/frontend/src/App.js` - Added TawkToWidget and /admin/support route
  - `/app/frontend/src/components/public/PublicLayout.js` - Added SupportChatWidget

- **TEST REPORT:** `/app/test_reports/iteration_48.json` (24/24 backend + 100% frontend)
  - All chat/ticket/conversation APIs verified
  - AI chatbot responses verified (service info, legal refusal, handoff)
  - Admin dashboard features verified
  - Transcript viewer and reply capability verified

### January 20, 2026 (Session 2)
- **Admin Management UI (Frontend) ✅**
  - New "Admins" tab in Admin Dashboard sidebar
  - Stats cards: Total Admins, Active, Pending Setup
  - Admin list table with Status badges, Last Login, Created date
  - Invite Admin modal with name/email form
  - Action buttons: Resend Invite, Deactivate, Reactivate
  - All actions integrated with existing backend APIs
  - 20/20 tests passed (100%)

- **Council Name Normalization ✅**
  - All council names now stored and displayed in full official format
  - Examples:
    - "Bristol" → "Bristol City Council"
    - "Camden" → "London Borough of Camden"
    - "Manchester" → "Manchester City Council"
    - "Westminster" → "City of Westminster"
  - `normalize_council_name()` function in `/app/backend/routes/intake.py`
  - Applied to: Postcode lookup, Council search, Property storage, Audit logs
  - Council code-based rules: E06 (Unitary), E07 (District), E08 (Metropolitan), E09 (London), S12 (Scotland), W06 (Wales)

- **Brand Colour Enforcement ✅**
  - Electric Teal (#00B8A9): Affirmative actions, selected states, CTAs
  - Midnight Blue (#0B1D3A): Headings, labels, text
  - Red: Reserved for errors, failures, compliance risk indicators only

- **TEST REPORT:** /app/test_reports/iteration_14.json

### January 20, 2026
- Implemented Universal Intake Wizard (5-step premium wizard)
- Added UK councils searchable endpoint with ~300 councils
- Customer reference number format: PLE-CVP-YYYY-XXXXX
- Stripe pricing updated to £9.99/month + £49.99 setup (not per-property)
- All 30 intake wizard API tests passing (100%)

### January 19, 2026
- Implemented Webhook Notifications System with HMAC signing
- Created Integrations page at /app/integrations
- Added Email Digest Customization toggles
- Webhook events: compliance.status_changed, requirement.status_changed, document.verification_changed, digest.sent, reminder.sent

### Earlier
- Core system, AI assistant, tenant portal, bulk upload, advanced reporting
