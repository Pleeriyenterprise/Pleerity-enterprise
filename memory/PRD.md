# Compliance Vault Pro - Product Requirements Document

## Overview
**Product:** Compliance Vault Pro  
**Company:** Pleerity Enterprise Ltd  
**Target Users:** UK landlords, letting agents, and tenants  
**Tagline:** AI-Driven Solutions & Compliance  

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React with Tailwind CSS
- **Database:** MongoDB (via Motor async driver)
- **Authentication:** JWT tokens
- **Integrations:** Stripe (payments), Postmark (email - LIVE), OpenAI/Gemini (AI assistant), Twilio (SMS - dev mode)

## Core Principles
1. **Deterministic Compliance:** No AI for compliance decisions - all compliance rules are based on predefined dates/rules
2. **Single Sources of Truth:** Stripe for billing status, Client.onboarding_status for provisioning
3. **Strict RBAC:** `ROLE_CLIENT`, `ROLE_CLIENT_ADMIN`, `ROLE_ADMIN`, `ROLE_TENANT` enforced server-side
4. **Mandatory Audit Logging:** All significant actions logged
5. **AI is Assistive Only:** AI extracts data for review, cannot mark requirements compliant

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
- [ ] ZIP file bulk upload - Upload single archive containing multiple documents

### P2 (Medium Priority)
- [ ] Production SMS sending with real Twilio credentials
- [ ] Document version history
- [ ] Multi-language support
- [ ] Calendar export (iCal format)

### P3 (Low Priority)
- [ ] Mobile app (React Native)
- [ ] Integration with property management systems
- [ ] Advanced analytics dashboard

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
