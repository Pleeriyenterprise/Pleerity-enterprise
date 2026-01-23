# Pleerity Enterprise Ltd - Product Requirements Document

## Overview
Enterprise-grade SaaS platform for property compliance management with AI-driven automation.

## Core Products
1. **Compliance Vault Pro (CVP)** - Property compliance tracking and management
2. **Document Services** - Professional document generation and packs
3. **AI Workflow Automation** - Automated compliance workflows

---

## Implemented Features

### Phase 1: Core Platform (Complete)
- [x] Public website with SEO optimization
- [x] CVP landing page and pricing
- [x] Service catalogue V2 with dynamic routing
- [x] Unified Intake Wizard with schema customization
- [x] Client portal with property management
- [x] Admin dashboard with client management
- [x] Stripe payment integration
- [x] Postmark email integration
- [x] Twilio SMS notifications

### Phase 2: Document & Order System (Complete)
- [x] Order management with workflow automation
- [x] Document generation (PDF, DOCX)
- [x] SLA monitoring and breach detection
- [x] Order delivery automation

### Phase 3: 24/7 Support System (Complete)
- [x] AI chatbot with Gemini integration
- [x] Tawk.to live chat widget
- [x] Email ticket creation via Postmark
- [x] WhatsApp handoff functionality
- [x] Knowledge Base (public & admin)
- [x] Admin canned responses management

### Phase 4: Lead Management System (Complete)
- [x] Lead capture endpoints (chatbot, contact form, document services, WhatsApp, intake abandoned)
- [x] Lead listing API with filters and pagination
- [x] Admin Lead Dashboard UI
- [x] HIGH Intent Lead Notifications
- [x] SLA Breach Notifications
- [x] Follow-up email automation with consent checks

### Phase 5: Admin Intake Schema Manager (Complete)
- [x] Schema versioning with version history
- [x] Draft/Publish workflow
- [x] Rollback to previous versions

### Phase 6: Unified Admin Console (Complete)
- [x] Consolidated sidebar navigation
- [x] All 12+ admin pages accessible from single location
- [x] Real-time badge notifications
- [x] Mobile responsive design

### Phase 7: Postal Tracking UI (Complete)
- [x] Dedicated `/admin/postal-tracking` page
- [x] Stats cards and order management

### Phase 8: Cookie Consent & Compliance System (Complete - Jan 23, 2026)
- [x] **Server-Side Consent Store** (GDPR-compliant)
  - `consent_events` collection (append-only audit trail)
  - `consent_state` collection (materialized current state)
  - No raw IP storage (hashed only)
- [x] **Cookie Categories**:
  - Necessary (always enabled)
  - Functional (consent required)
  - Analytics (consent required)
  - Marketing (consent required)
- [x] **Frontend Cookie Banner**
  - Shows on first visit
  - Accept All / Reject Non-Essential / Manage Preferences
  - No scripts load before consent
- [x] **Preferences Panel**
  - Granular control per category
  - Accessible via Manage Preferences button
  - Changes apply immediately
- [x] **Admin Consent Dashboard** (`/admin/privacy/consent`)
  - KPI cards (Total Visitors, Accept All, Reject, Custom)
  - Category breakdown (Analytics, Marketing, Functional allowed)
  - Consent trend mini chart
  - Filterable consent log table
  - Detail drawer with timeline
  - CSV and PDF export
  - 24-month retention
- [x] **Enforcement Integration**
  - Lead follow-up automation respects marketing consent
  - Outreach eligibility derived from consent state
  - Audit logging for consent changes

---

## API Endpoints Summary

### Cookie Consent (Public)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/consent/capture` | POST | Capture consent from cookie banner |
| `/api/consent/state/{session_id}` | GET | Get consent state for session |
| `/api/consent/withdraw` | POST | Withdraw consent for categories |

### Cookie Consent (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/consent/stats` | GET | Dashboard KPIs and trend |
| `/api/admin/consent/logs` | GET | Paginated consent log |
| `/api/admin/consent/logs/{id}` | GET | Single record detail |
| `/api/admin/consent/export.csv` | GET | Export filtered logs as CSV |
| `/api/admin/consent/export.pdf` | GET | Export summary as PDF |
| `/api/admin/consent/client/{id}` | GET | Consent for specific client |
| `/api/admin/consent/lead/{id}` | GET | Consent for specific lead |

---

## Data Models

### consent_events (Append-only)
```javascript
{
  event_id: "CE-20260123-XXXXXXXX",
  created_at: "2026-01-23T18:22:46+00:00",
  event_type: "ACCEPT_ALL|REJECT_NON_ESSENTIAL|CUSTOM|WITHDRAW|UPDATE",
  consent_version: "v1",
  banner_text_hash: "abc123...",
  session_id: "sess_1234567890",
  user_id: null,
  portal_user_id: null,
  client_id: null,
  crn: null,
  email_masked: "jo***@example.com",
  country: "GB",
  ip_hash: "abc123...",  // Never store raw IP
  user_agent: "...",
  page_path: "/",
  referrer: null,
  utm: { source, medium, campaign, term, content },
  preferences: {
    necessary: true,
    analytics: true,
    marketing: true,
    functional: true
  }
}
```

### consent_state (Materialized)
```javascript
{
  state_id: "CS-XXXXXXXXXXXX",
  session_id: "sess_1234567890",
  updated_at: "2026-01-23T18:22:46+00:00",
  action_taken: "ACCEPT_ALL",
  consent_version: "v1",
  preferences: { ... },
  is_logged_in: false,
  outreach_eligible: true  // Derived from marketing consent
}
```

---

## Credentials
- Admin: admin@pleerity.com / Admin123!
- Client: test@pleerity.com / TestClient123!

## Environment
- Backend: FastAPI on port 8001
- Frontend: React on port 3000
- Database: MongoDB (compliance_vault_pro)

## Configuration
- `CONSENT_RETENTION_MONTHS`: 24 (default)

---

*Last updated: January 23, 2026*
