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

### Phase 9: Admin Site Builder CMS (Complete - Jan 23, 2026)
- [x] **Page Management**
  - Create, edit, archive pages with unique slugs
  - Draft/Published/Archived status workflow
  - SEO metadata (meta title, description, OG tags)
  - Page settings dialog
- [x] **Safe Block System** (Schema-driven, no arbitrary HTML)
  - 14 predefined block types: HERO, TEXT_BLOCK, CTA, FAQ, PRICING_TABLE, FEATURES_GRID, TESTIMONIALS, IMAGE_GALLERY, VIDEO_EMBED, CONTACT_FORM, STATS_BAR, LOGO_CLOUD, TEAM_SECTION, SPACER
  - Content validation per block type
  - VIDEO_EMBED restricted to YouTube/Vimeo only
  - Block visibility toggle
  - Drag-style reordering (move up/down)
- [x] **Revision System**
  - Version snapshots on publish
  - Revision history with notes
  - One-click rollback to any version
- [x] **Media Library**
  - Image upload with GridFS storage
  - File type validation (images only)
  - Alt text and tagging
  - Search and filter
- [x] **Admin UI** (`/admin/site-builder`)
  - Pages tab with grid view
  - Page editor with block management
  - Media Library tab
  - Real-time toast notifications
- [x] **Public Rendering API**
  - GET `/api/public/cms/pages/{slug}` returns published content only
  - Visible blocks only, ordered by position
- [x] **Audit Logging**
  - All CMS mutations logged (create, update, publish, rollback, media upload/delete)

---

## API Endpoints Summary

### CMS Site Builder (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/cms/pages` | GET | List all CMS pages |
| `/api/admin/cms/pages` | POST | Create a new page |
| `/api/admin/cms/pages/{id}` | GET | Get page by ID |
| `/api/admin/cms/pages/{id}` | PUT | Update page metadata |
| `/api/admin/cms/pages/{id}` | DELETE | Archive a page |
| `/api/admin/cms/pages/{id}/blocks` | POST | Add a block to page |
| `/api/admin/cms/pages/{id}/blocks/{block_id}` | PUT | Update block |
| `/api/admin/cms/pages/{id}/blocks/{block_id}` | DELETE | Delete block |
| `/api/admin/cms/pages/{id}/blocks/reorder` | PUT | Reorder blocks |
| `/api/admin/cms/pages/{id}/publish` | POST | Publish page |
| `/api/admin/cms/pages/{id}/revisions` | GET | Get revision history |
| `/api/admin/cms/pages/{id}/rollback` | POST | Rollback to revision |
| `/api/admin/cms/media` | GET | List media library |
| `/api/admin/cms/media/upload` | POST | Upload media file |
| `/api/admin/cms/media/{id}` | DELETE | Delete media |
| `/api/admin/cms/block-types` | GET | Get available block types |

### CMS Public (No Auth)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/public/cms/pages/{slug}` | GET | Get published page content |
| `/api/cms/media/file/{file_id}` | GET | Serve media file |

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

### cms_pages
```javascript
{
  page_id: "PG-XXXXXXXXXXXX",
  slug: "about-us",  // Unique, lowercase, hyphens only
  title: "About Us",
  description: "Company information",
  status: "DRAFT|PUBLISHED|ARCHIVED",
  blocks: [
    {
      block_id: "BLK-XXXXXXXX",
      block_type: "HERO|TEXT_BLOCK|CTA|FAQ|...",
      content: { ... },  // Schema-validated
      visible: true,
      order: 0
    }
  ],
  seo: {
    meta_title: "...",
    meta_description: "...",
    og_title: "...",
    og_image_id: "..."
  },
  current_version: 1,
  created_at: "...",
  updated_at: "...",
  published_at: "...",
  created_by: "admin-001",
  updated_by: "admin-001"
}
```

### cms_revisions
```javascript
{
  revision_id: "REV-XXXXXXXXXXXX",
  page_id: "PG-XXXXXXXXXXXX",
  version: 1,
  title: "...",
  blocks: [...],
  seo: {...},
  published_at: "...",
  published_by: "admin-001",
  notes: "Initial publish"
}
```

### cms_media
```javascript
{
  media_id: "MED-XXXXXXXXXXXX",
  media_type: "IMAGE|VIDEO_EMBED",
  file_name: "hero-banner.jpg",
  file_url: "/api/cms/media/file/{file_id}",
  file_size: 102400,
  alt_text: "Hero banner image",
  tags: ["hero", "banner"],
  uploaded_at: "...",
  uploaded_by: "admin-001"
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