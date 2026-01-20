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
2. **Single Sources of Truth:** Stripe for billing status
3. **Strict RBAC:** `ROLE_CLIENT`, `ROLE_CLIENT_ADMIN`, `ROLE_ADMIN`, `ROLE_TENANT` enforced server-side
4. **Mandatory Audit Logging:** All significant actions logged
5. **AI is Assistive Only:** AI extracts data for review, cannot mark requirements compliant

---

## Completed Features (As of January 2026)

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
- [x] **AI Document Scanner Enhancement**
  - Document-type-specific prompts (Gas Safety, EICR, EPC)
  - Priority field extraction (expiry date, issue date, certificate number, engineer details)
  - Extraction quality assessment (high/medium/low)
  - Review workflow (pending → approved/rejected)
  - Apply extraction endpoint updates requirement due_date
  - AI is assistive only - cannot auto-mark compliance

- [x] **Bulk Document Upload**
  - Multi-file drag & drop interface
  - Property-level upload (all files associated with one property)
  - Smart auto-matching via AI
  - Progress indicators
  - File validation (PDF, JPG, PNG)

- [x] **Advanced Reporting (PDF/CSV)**
  - Compliance Status Summary report
  - Requirements by Property report
  - Audit Log Extract report (Admin only)
  - On-demand generation
  - CSV download working, PDF returns JSON for client-side rendering

- [x] **Landlord/Tenant Portal Distinctions**
  - ROLE_TENANT with strictly limited permissions
  - Read-only access to property compliance status
  - Certificate status and expiry dates visible
  - Simplified tenant dashboard
  - Tenant invite via email
  - Property assignment support
  - No document uploads, messaging, audit logs, or admin features for tenants

- [x] **Tenant Management UI** (Enhancement)
  - Full CRUD for tenant management
  - Invite tenants with email notification
  - Assign/unassign properties to tenants
  - Revoke tenant access
  - Resend invitation emails
  - Status badges (Pending, Active, Disabled)
  - Navigation tab in client dashboard

---

## User Roles

| Role | Permissions |
|------|-------------|
| ROLE_ADMIN | Full system access, all clients, audit logs, reports |
| ROLE_CLIENT_ADMIN | Full access to own client data, can invite tenants |
| ROLE_CLIENT | Access to own properties, requirements, documents |
| ROLE_TENANT | Read-only access to assigned property compliance status |

---

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/set-password` - Set password via token

### Client
- `GET /api/client/dashboard` - Client dashboard data
- `GET /api/client/properties` - Client properties
- `GET /api/client/requirements` - Client requirements
- `GET /api/client/compliance-score` - Compliance score with recommendations
- `POST /api/client/tenants/invite` - Invite tenant (CLIENT_ADMIN only)
- `GET /api/client/tenants` - List tenants

### Tenant
- `GET /api/tenant/dashboard` - Tenant dashboard (read-only)
- `GET /api/tenant/property/{id}` - Property compliance details

### Documents
- `POST /api/documents/upload` - Single document upload
- `POST /api/documents/bulk-upload` - Bulk upload multiple files
- `POST /api/documents/analyze/{id}` - Trigger AI analysis
- `POST /api/documents/{id}/apply-extraction` - Apply AI extraction to requirement
- `POST /api/documents/{id}/reject-extraction` - Reject AI extraction
- `GET /api/documents/{id}/details` - Full document details

### Reports
- `GET /api/reports/available` - List available reports
- `GET /api/reports/compliance-summary` - Compliance summary report (CSV/PDF)
- `GET /api/reports/requirements` - Requirements report (CSV/PDF)
- `GET /api/reports/audit-logs` - Audit log extract (Admin only)

### Profile
- `GET /api/profile/me` - User profile
- `PATCH /api/profile/me` - Update profile
- `GET /api/profile/notification-preferences` - Notification settings
- `PUT /api/profile/notification-preferences` - Update notification settings

### Calendar
- `GET /api/calendar/expiries` - Certificate expiries for calendar view

### Admin
- `GET /api/admin/dashboard` - Admin dashboard statistics
- `GET /api/admin/statistics` - System-wide compliance statistics
- `GET /api/admin/clients` - List all clients
- `POST /api/admin/clients/invite` - Invite new client
- `GET /api/admin/audit-logs` - Audit logs with filtering
- `GET /api/admin/jobs/status` - Background jobs status

---

## Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@pleerity.com | Admin123! |
| Client | test@pleerity.com | TestClient123! |
| Live Client | drjpane@gmail.com | DrJamesPane123! |

---

## Known Limitations / Mocked Services

1. **Payments (Stripe):** Using test key - functional but not processing real payments
2. **SMS (Twilio):** Feature-flagged, using dev credentials
3. **PDF Reports:** Returns JSON data for client-side PDF generation (CSV fully working)

---

## Files of Reference

### Backend
- `/app/backend/server.py` - Main FastAPI app with APScheduler
- `/app/backend/routes/` - API endpoints (auth, client, admin, documents, reports, tenant)
- `/app/backend/services/` - Business logic (provisioning, jobs, email, document_analysis, compliance_score, reporting_service)
- `/app/backend/models.py` - Pydantic models including ROLE_TENANT

### Frontend
- `/app/frontend/src/App.js` - React routes including tenant route
- `/app/frontend/src/pages/` - Page components
- `/app/frontend/src/pages/TenantDashboard.js` - Simplified tenant view
- `/app/frontend/src/pages/ReportsPage.js` - Report download UI
- `/app/frontend/src/pages/BulkUploadPage.js` - Bulk document upload
- `/app/frontend/src/pages/DocumentsPage.js` - Enhanced with AI extraction review

### Phase 5: P1 Features (January 2026) ✅
- [x] **Scheduled Reports with Email Delivery**
  - Create schedules: daily, weekly, monthly frequencies
  - Report types: compliance_summary, requirements
  - Multiple recipients support
  - Toggle schedules on/off
  - Email delivery via Postmark (job scheduler ready)
  - API endpoints: POST/GET/DELETE/PATCH /api/reports/schedules

- [x] **Client-side PDF Generation**
  - jsPDF with autoTable plugin integration
  - Branded PDF reports with header, footer, page numbers
  - Table formatting for property and requirement data
  - CSV and PDF format selector in UI

- [x] **Bulk Property Import from CSV**
  - Drag & drop CSV upload interface
  - Column mapping and validation
  - Duplicate detection
  - Automatic requirements generation
  - Download CSV template
  - Preview before import with error highlighting

---

## Backlog / Future Enhancements

### P1 (High Priority)
- [ ] Schedule reports background job execution (cron-style trigger)
- [ ] Email notification digest customization

### P2 (Medium Priority)
- [ ] Production SMS sending with real Twilio credentials
- [ ] Document version history
- [ ] Multi-language support
- [ ] Calendar export (iCal format)

### P3 (Low Priority)
- [ ] Mobile app (React Native)
- [ ] Integration with property management systems
- [ ] Advanced analytics dashboard
- [ ] Webhook notifications
