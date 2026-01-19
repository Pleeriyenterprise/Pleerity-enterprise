# Compliance Vault Pro - Product Requirements Document

## Overview
**Product:** Compliance Vault Pro  
**Company:** Pleerity Enterprise Ltd  
**Target Users:** UK landlords and letting agents  
**Tagline:** AI-Driven Solutions & Compliance  

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React with Tailwind CSS
- **Database:** MongoDB (via Motor async driver)
- **Authentication:** JWT tokens
- **Integrations:** Stripe (payments), Postmark (email - MOCKED), OpenAI (AI assistant)

## Core Principles
1. **Deterministic Compliance:** No AI for compliance decisions - all compliance rules are based on predefined dates/rules
2. **Single Sources of Truth:** Stripe for billing status
3. **Strict RBAC:** `ROLE_CLIENT`, `ROLE_CLIENT_ADMIN`, `ROLE_ADMIN` enforced server-side
4. **Mandatory Audit Logging:** All significant actions logged

---

## Phase 1: Core System (COMPLETE)

### Features Implemented
- [x] Public marketing landing page
- [x] Client intake/onboarding flow
- [x] User authentication (JWT)
- [x] Password setup via secure token
- [x] Client and Admin portals (route-guarded)
- [x] RBAC middleware (client_route_guard, admin_route_guard)
- [x] Core data models (Client, PortalUser, Property, Requirement, Document, AuditLog)
- [x] Provisioning service
- [x] Email service (Postmark - MOCKED)
- [x] Stripe webhook integration
- [x] Basic admin console

### Data Models
- **Client:** client_id, full_name, email, billing_plan, subscription_status, onboarding_status
- **PortalUser:** portal_user_id, client_id, auth_email, role, status, password_status
- **Property:** property_id, client_id, address, property_type
- **Requirement:** requirement_id, property_id, rule_id, status, due_date
- **Document:** document_id, property_id, file_url, status
- **AuditLog:** timestamp, actor_id, action, details

---

## Phase 2: AI Assistant (COMPLETE)

### Features Implemented
- [x] Read-only AI assistant at `/app/assistant`
- [x] OpenAI integration via Emergent LLM Key
- [x] Data snapshot endpoint (`/api/assistant/snapshot`)
- [x] All interactions audited
- [x] Strict read-only mode (no system state modifications)

---

## Phase 3: Additive Enhancements (IN PROGRESS)

### Completed (January 19, 2026)
- [x] **User Profile Page:** `/app/profile` with backend APIs
- [x] **Property Creation Flow:** `/app/properties/create` with guided steps
- [x] **Admin Features Backend:**
  - [x] Job monitoring endpoint (`/api/admin/jobs/status`)
  - [x] Manual job trigger endpoint (`/api/admin/jobs/trigger/{type}`)
  - [x] Client invitation endpoint (`/api/admin/clients/invite`)
  - [x] Manual provisioning trigger (`/api/admin/clients/{id}/provision`)
  - [x] Password setup link generation (`/api/admin/clients/{id}/password-setup-link`)
  - [x] Full client status endpoint (`/api/admin/clients/{id}/full-status`)
  - [x] Admin property creation (`/api/admin/clients/{id}/properties`)
  - [x] Enhanced audit log filtering
- [x] **Background Job Scheduler:** APScheduler with MongoDBJobStore (persistent)
  - Daily reminders at 9:00 AM UTC
  - Monthly digests on 1st at 10:00 AM UTC
- [x] **Admin Login Fix:** Admins can login without client association
- [x] **Database Utility:** `get_db_context()` for standalone scripts
- [x] **Live Email Delivery:** Postmark integration working
  - Sender: `info@pleerityenterprise.co.uk`
  - Fallback from template to HTML email
- [x] **Admin Dashboard Frontend UI:**
  - [x] Overview tab (stats, compliance overview, recent activity)
  - [x] Jobs tab (scheduler status, manual triggers, job statistics)
  - [x] Clients tab (list, search, filter, detail panel with status)
  - [x] Rules tab (CRUD for compliance rules, default UK rules)
  - [x] Audit Logs tab (filterable, paginated log viewer)
  - [x] Messages tab (email delivery logs with provider tracking)
- [x] **Requirement Rules Management:**
  - [x] Backend API for rules CRUD (`/api/admin/rules/*`)
  - [x] Database model for RequirementRule with categories
  - [x] Default UK compliance rules (7 rules: Gas Safety, EICR, EPC, Fire, Legionella, HMO, PAT)
  - [x] Provisioning service updated to use database rules
  - [x] Frontend UI with table view, create/edit modal
- [x] **Email Templates Management:**
  - [x] Backend API for templates CRUD (`/api/admin/templates/*`)
  - [x] Database model for EmailTemplate with placeholders
  - [x] Default templates (Password Setup, Portal Ready, Reminder, Monthly Digest)
  - [x] Email service updated to use database templates
  - [x] Frontend UI with grid view, edit modal, live preview
  - [x] Template preview with sample data rendering
- [x] **Document AI Verification:**
  - [x] Backend AI service using Gemini for document analysis
  - [x] Metadata extraction (dates, certificate numbers, engineer info)
  - [x] Confidence scores for extracted data
  - [x] API endpoints (`/api/documents/analyze/{id}`, `/api/documents/{id}/extraction`)
  - [x] Frontend Documents page with upload form
  - [x] AI extraction display with extracted fields
  - [x] General requirements endpoint (`/api/client/requirements`)
- [x] **System-wide Compliance Statistics Dashboard:**
  - [x] Backend API (`/api/admin/statistics`) with comprehensive metrics
  - [x] Executive-style stat cards (Total Properties, Compliant, Attention Needed, Action Required, Expiring Soon)
  - [x] Urgent Actions widget with overdue/expiring items
  - [x] System Summary widget with portfolio stats
  - [x] Collapsible Detailed Analytics section
  - [x] Donut chart for Requirements by Certificate Type
  - [x] Bar chart for Requirement Status Distribution
  - [x] Email/Document/Rules tertiary stats
- [x] **SetPasswordPage Redirect Fix:**
  - [x] Fixed redirect after password setup (now uses AuthContext.loginWithToken)
  - [x] Users now redirected directly to `/app/dashboard` after setting password
- [x] **Compliance Status Change Notifications:**
  - [x] Email alerts when property status degrades (GREEN→AMBER, AMBER→RED, GREEN→RED)
  - [x] New `COMPLIANCE_ALERT` email template with property table
  - [x] Scheduled compliance checks twice daily (8:00 AM & 6:00 PM UTC)
  - [x] Manual trigger available via Admin Jobs tab
  - [x] Tracks `last_notified_status` to prevent duplicate alerts
  - [x] Audit logging for all compliance alerts sent
- [x] **Onboarding Progress Dashboard:**
  - [x] Enhanced `/api/intake/onboarding-status/{client_id}` API with step-by-step progress
  - [x] Frontend OnboardingStatusPage.js with visual timeline
  - [x] 5-step progress (Intake → Payment → Portal Setup → Account Activation → Ready)
  - [x] Property and requirements count display
  - [x] Next action guidance and "Go to Portal" button
  - [x] Auto-refresh while onboarding is in progress
  - [x] Checkout success redirect to onboarding status
- [x] **Notification Preferences Page:**
  - [x] Backend API endpoints GET/PUT `/api/profile/notifications`
  - [x] NotificationPreferencesPage.js with comprehensive settings
  - [x] 5 notification types: Status Alerts, Expiry Reminders, Monthly Digest, Document Updates, System Announcements
  - [x] Configurable reminder timing (7, 14, 30, 60, 90 days)
  - [x] Quiet Hours support (optional time window)
  - [x] Floating "unsaved changes" indicator
  - [x] Linked from Profile page
- [x] **Client Dashboard Notification Widget:**
  - [x] Quick summary of notification settings on dashboard
  - [x] Shows Status Alerts, Expiry Reminders, Monthly Digest status
  - [x] Shows Reminder Timing (days before expiry)
  - [x] "Manage Preferences" button to full settings page
  - [x] Profile nav link added to dashboard

### Upcoming (P2)
- [ ] **Onboarding progress dashboard** - Visual flow for new clients

### Upcoming (P2)
- [x] **Audit Log Granularity:** Before/after diffs on profile and notification changes
  - [x] Enhanced `create_audit_log` utility with automatic diff calculation
  - [x] Diff shows added, removed, and changed fields with from/to values
  - [x] Changes count included in metadata

### Upcoming (P3)
- [ ] **Enhanced Requirement Generation:** Dynamic rules based on property type/location
- [ ] **RuleRequirementDefinition Expansion:** Conditional logic, risk weights
- [ ] **SMS Reminder Support:** Feature-flagged, third-party gateway

---

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/set-password` - Set password via token

### Client
- `GET /api/client/dashboard` - Client dashboard data
- `GET /api/client/properties` - Client properties
- `GET /api/client/requirements` - Client requirements

### Profile
- `GET /api/profile/me` - User profile with notification preferences
- `PATCH /api/profile/me` - Update profile (name, phone)
- `GET /api/profile/notifications` - Get notification preferences
- `PUT /api/profile/notifications` - Update notification preferences

### Admin
- `GET /api/admin/dashboard` - Admin dashboard statistics
- `GET /api/admin/statistics` - Comprehensive system-wide compliance statistics
- `GET /api/admin/clients` - List all clients
- `GET /api/admin/clients/{id}` - Client details
- `GET /api/admin/audit-logs` - Audit logs with filtering
- `GET /api/admin/jobs/status` - Background jobs status
- `POST /api/admin/jobs/trigger/{type}` - Manually trigger job (daily, monthly, compliance)
- `POST /api/admin/clients/invite` - Invite new client
- `POST /api/admin/clients/{id}/provision` - Manual provisioning
- `GET/POST /api/admin/rules` - Requirement rules CRUD
- `GET/POST /api/admin/templates` - Email templates CRUD

### Documents
- `POST /api/documents/upload` - Upload document
- `GET /api/documents/{id}` - Get document

### Properties
- `POST /api/properties` - Create property
- `GET /api/properties/{id}` - Get property details

### AI Assistant
- `POST /api/assistant/ask` - Ask the AI assistant
- `GET /api/assistant/snapshot` - Get data snapshot for AI

### Intake
- `POST /api/intake/submit` - Submit intake form
- `POST /api/intake/checkout` - Create Stripe checkout session
- `GET /api/intake/onboarding-status/{client_id}` - Detailed onboarding progress with 5 steps

### Webhooks
- `POST /api/webhooks/stripe` - Stripe webhook handler

---

## Test Credentials
- **Admin Email:** admin@pleerity.com
- **Admin Password:** Admin123!

---

## Known Limitations / Mocked Services
1. **Payments (Stripe):** Using test key from environment
2. **Email (Postmark):** Live integration working with sender `info@pleerityenterprise.co.uk`

---

## Files of Reference
- `/app/backend/server.py` - Main FastAPI app with APScheduler
- `/app/backend/routes/` - All API endpoints
- `/app/backend/services/` - Business logic (provisioning, jobs, email)
- `/app/backend/models.py` - Pydantic models
- `/app/frontend/src/App.js` - React routes
- `/app/frontend/src/pages/` - Page components
