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

### Phase 10: Customer Enablement Automation Engine (Complete - Jan 23, 2026)
- [x] **Event-Driven Architecture**
  - Internal event bus for enablement triggers
  - 16 event types (intake complete, provisioning, first login, document verified, etc.)
  - Event emission integrated into core services
- [x] **5 Automation Categories**
  - ONBOARDING_GUIDANCE: Help users understand onboarding
  - VALUE_CONFIRMATION: Explain why actions mattered
  - COMPLIANCE_AWARENESS: Risk awareness without legal advice
  - INACTIVITY_SUPPORT: Gentle educational nudges
  - FEATURE_GATE_EXPLANATION: Explain gated features
- [x] **Multi-Channel Delivery**
  - IN_APP: In-app notifications (client_notifications collection)
  - EMAIL: Postmark email delivery
  - ASSISTANT: AI Assistant context enrichment
- [x] **Template System**
  - 16 pre-built educational templates
  - Template versioning
  - Template enable/disable toggle
  - Template reseeding on startup
- [x] **Suppression Rules**
  - Global, per-client, per-category, per-template rules
  - Admin-created with reason and expiry
  - User preference overrides
- [x] **Admin Dashboard** (`/admin/enablement`)
  - Overview tab with KPIs (Total/Delivered/Suppressed/Failed)
  - Templates tab with category filter and toggle
  - Suppressions tab with CRUD
  - Client Timeline search
  - Manual Trigger for testing
- [x] **Full Audit Logging**
  - Every action logged (SUCCESS/FAILED/SUPPRESSED)
  - Audit trail with rendered content snapshots
  - Admin observability

### Phase 11: Full Reporting System (Complete - Jan 23, 2026)
- [x] **7 Report Types**
  - Revenue Report: Revenue by orders and services
  - Orders Report: All orders with status
  - Clients Report: Client listing and details
  - Leads Report: Lead pipeline data
  - Compliance Report: Property compliance status
  - Enablement Report: Customer enablement actions
  - Consent Report: Cookie consent events
- [x] **4 Export Formats**
  - CSV: Spreadsheet compatible
  - XLSX: Microsoft Excel format (using openpyxl)
  - PDF: Professional document (using reportlab)
  - JSON: Developer friendly
- [x] **Report Preview**
  - Preview data before download
  - Configurable row limit
  - Column headers displayed
- [x] **Custom Date Ranges**
  - Preset periods: Today, 7d, 30d, 90d, YTD
  - Custom date range selection
- [x] **Scheduled Report Delivery**
  - Daily, Weekly, Monthly schedules
  - Multiple email recipients
  - Email attachment via Postmark
  - Manual "Run Now" trigger
  - Enable/disable toggle
- [x] **Admin Dashboard** (`/admin/reporting`)
  - Generate Report tab with export settings
  - Schedules tab with CRUD and execution history
  - History tab with recent downloads
  - Stats cards (Report Types, Active Schedules, Reports Sent, Exports)
- [x] **Audit Logging**
  - All report generations logged
  - Schedule operations logged

### Phase 12: Team Permissions & Role Management (Complete - Jan 23, 2026)
- [x] **5 Built-in Roles**
  - Super Admin: Full system access
  - Manager: Operational management without billing/team access
  - Viewer: Read-only access
  - Support Agent: Support tickets and client info
  - Content Manager: CMS and website content
- [x] **13 Permission Categories**
  - Dashboard, Clients, Leads, Orders, Reports, CMS
  - Support, Billing, Settings, Team, Analytics, Enablement, Consent
- [x] **Custom Role Builder**
  - Create custom roles with granular permissions
  - Select specific actions per category (view, create, edit, delete, export, manage)
  - Update and delete custom roles
- [x] **Admin User Management**
  - Create admin users with assigned roles
  - Update user roles
  - Enable/disable users
- [x] **Admin Dashboard** (`/admin/team`)
  - Users tab with role assignment
  - Roles tab with permissions view
  - Custom role creation dialog

### Phase 13: CMS Templates & Report Sharing (Complete - Jan 23, 2026)
- [x] **4 Pre-built Page Templates**
  - Landing Page: Hero, features, testimonials, CTA
  - About Us: Company story, team, values
  - Contact Us: Form, office info, FAQs
  - Pricing Page: Pricing tiers, FAQs
- [x] **Template Preview**
  - Preview template blocks before applying
  - See full block structure
- [x] **One-Click Template Application**
  - Create new page from template
  - Replace existing page content with template
- [x] **Report Sharing via Public Links**
  - Create time-limited share URLs (1-30 days)
  - Share links for leads, revenue, analytics reports
  - Public access without authentication
  - Revoke share links
  - Track access count
- [x] **Share Links Tab** in Reporting Dashboard
  - Create, view, copy, revoke share links
- [x] **Public Shared Report Page** (`/shared/report/:id`)
  - View report info
  - Download report

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
| `/api/admin/cms/templates` | GET | List 4 pre-built templates |
| `/api/admin/cms/templates/{id}` | GET | Get template with blocks |
| `/api/admin/cms/templates/{id}/preview` | GET | Preview template |
| `/api/admin/cms/templates/apply` | POST | Apply template to new/existing page |

### CMS Public (No Auth)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/public/cms/pages/{slug}` | GET | Get published page content |
| `/api/cms/media/file/{file_id}` | GET | Serve media file |

### Team Permissions (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/team/permissions` | GET | List 13 permission categories with actions |
| `/api/admin/team/roles` | GET | List all roles (5 built-in + custom) |
| `/api/admin/team/roles/{id}` | GET | Get role details with permissions |
| `/api/admin/team/roles` | POST | Create custom role |
| `/api/admin/team/roles/{id}` | PUT | Update custom role |
| `/api/admin/team/roles/{id}` | DELETE | Delete custom role |
| `/api/admin/team/users` | GET | List admin users |
| `/api/admin/team/users` | POST | Create admin user with role |
| `/api/admin/team/users/{id}` | PUT | Update admin user |
| `/api/admin/team/users/{id}` | DELETE | Deactivate admin user |
| `/api/admin/team/me/permissions` | GET | Get current user's permissions |

### Customer Enablement Engine (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/enablement/overview` | GET | System overview (templates, suppressions, recent) |
| `/api/admin/enablement/stats` | GET | Statistics with period filter |
| `/api/admin/enablement/templates` | GET | List all templates |
| `/api/admin/enablement/templates/{code}/toggle` | PUT | Toggle template active status |
| `/api/admin/enablement/templates/seed` | POST | Reseed default templates |
| `/api/admin/enablement/suppressions` | GET | List suppression rules |
| `/api/admin/enablement/suppressions` | POST | Create suppression rule |
| `/api/admin/enablement/suppressions/{id}` | DELETE | Deactivate suppression |
| `/api/admin/enablement/clients/{id}/timeline` | GET | Client enablement timeline |
| `/api/admin/enablement/clients/{id}/preferences` | GET | Get client preferences |
| `/api/admin/enablement/clients/{id}/preferences` | PUT | Update client preferences |
| `/api/admin/enablement/trigger` | POST | Manual event trigger |
| `/api/admin/enablement/actions` | GET | Query actions with filters |
| `/api/admin/enablement/events` | GET | Query events |
| `/api/admin/enablement/event-types` | GET | Get all enum types |

### Full Reporting System (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/reports/types` | GET | List available report types, formats, periods |
| `/api/admin/reports/preview/{report_type}` | GET | Preview report data before download |
| `/api/admin/reports/generate` | POST | Generate and download report (CSV/XLSX/PDF/JSON) |
| `/api/admin/reports/schedules` | GET | List all scheduled reports |
| `/api/admin/reports/schedules` | POST | Create new scheduled report |
| `/api/admin/reports/schedules/{id}/toggle` | PUT | Enable/disable schedule |
| `/api/admin/reports/schedules/{id}/run` | POST | Manually run scheduled report now |
| `/api/admin/reports/schedules/{id}` | DELETE | Delete scheduled report |
| `/api/admin/reports/history` | GET | Get report download history |
| `/api/admin/reports/executions` | GET | Get scheduled report execution history |
| `/api/admin/reports/share` | POST | Create shareable report link |
| `/api/admin/reports/shares` | GET | List share links |
| `/api/admin/reports/shares/{id}` | DELETE | Revoke share link |

### Public Report Sharing (No Auth)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/public/reports/shared/{id}` | GET | Get shared report info |
| `/api/public/reports/shared/{id}/download` | GET | Download shared report |

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

### prompt_templates
```javascript
{
  template_id: "PT-YYYYMMDDHHMMSS-XXXXXXXX",
  service_code: "AI_WF_BLUEPRINT",
  doc_type: "GENERAL_DOCUMENT",
  name: "Workflow Blueprint Generator",
  description: "...",
  version: 1,
  status: "DRAFT|TESTED|ACTIVE|DEPRECATED|ARCHIVED",
  system_prompt: "You are an AI assistant...",
  user_prompt_template: "Process:\n\n{{INPUT_DATA_JSON}}\n\nProvide JSON.",
  output_schema: {
    schema_version: "1.0",
    root_type: "object",
    strict_validation: true,
    fields: [...]
  },
  temperature: 0.3,
  max_tokens: 4000,
  tags: ["workflow", "automation"],
  last_test_status: "PASSED|FAILED|null",
  last_test_at: "...",
  test_count: 5,
  created_at: "...",
  created_by: "admin@pleerity.com",
  updated_at: "...",
  activated_at: "...",
  activated_by: "...",
  deprecated_at: "..."
}
```

### prompt_audit_log
```javascript
{
  audit_id: "AUD-YYYYMMDDHHMMSS-XXXXXXXX",
  template_id: "PT-...",
  version: 1,
  action: "CREATED|UPDATED|TESTED|TEST_PASSED|TEST_FAILED|ACTIVATED|DEPRECATED|ARCHIVED",
  changes_summary: "Created new prompt template",
  changes_detail: { ... },
  test_id: "TEST-...",  // For test actions
  test_result_snapshot: { ... },
  activation_reason: "...",  // For activation
  previous_active_version: 1,
  performed_by: "admin@pleerity.com",
  performed_at: "..."
}
```

### prompt_test_results
```javascript
{
  test_id: "TEST-YYYYMMDDHHMMSS-XXXXXXXX",
  template_id: "PT-...",
  template_version: 1,
  status: "PASSED|FAILED|PENDING|RUNNING",
  input_data: { ... },
  rendered_user_prompt: "...",
  raw_output: "...",
  parsed_output: { ... },
  schema_validation_passed: true,
  schema_validation_errors: [],
  execution_time_ms: 1234,
  prompt_tokens: 150,
  completion_tokens: 200,
  error_message: null,
  executed_at: "...",
  executed_by: "admin@pleerity.com"
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