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

### Phase 14: Enterprise Prompt Manager (Complete - Jan 23, 2026)
- [x] **Prompt Template Management**
  - Create, read, update, archive prompt templates
  - Single `{{INPUT_DATA_JSON}}` injection pattern (no scattered placeholders)
  - Service code + doc type categorization
  - Tags for organization
- [x] **Prompt Versioning & Lifecycle**
  - Draft → Tested → Active workflow (never overwrite active)
  - DRAFT: Editable, not used in production
  - TESTED: Passed schema validation, ready for activation
  - ACTIVE: Currently in use for document generation
  - DEPRECATED: Replaced by newer version, preserved for audit
  - ARCHIVED: Soft-deleted, hidden from normal views
- [x] **Output Schema Validation**
  - Define expected output fields (name, type, required)
  - Schema validation REQUIRED before marking as TESTED
  - Schema validation REQUIRED before activation
  - Supports: string, number, boolean, array, object types
- [x] **Prompt Playground**
  - Test prompts with sample input data
  - Real LLM execution (Gemini via Emergent LLM Key)
  - View raw and parsed output
  - Schema validation results with error details
  - Execution time and token tracking
- [x] **Audit Trail**
  - Full audit log: who, what, when, evidence
  - Actions logged: CREATED, UPDATED, TESTED, TEST_PASSED, TEST_FAILED, ACTIVATED, DEPRECATED, ARCHIVED
  - Test result snapshots stored
  - Activation reasons recorded
- [x] **Super Admin Only Access**
  - All endpoints require ROLE_ADMIN
  - Least privilege enforcement
- [x] **Provider-Agnostic LLM Interface**
  - Gemini default via emergentintegrations
  - Designed for easy provider swap
- [x] **Admin Dashboard** (`/admin/prompts`)
  - Templates tab with filters (service, status, search)
  - Test Playground dialog with live LLM execution
  - Activation dialog with reason requirement
  - Audit Log tab with action timeline
  - Guide tab with documentation

### Phase 15: Prompt Manager Integration & Analytics (Complete - Jan 23, 2026)
- [x] **Document Orchestrator Integration**
  - PromptManagerBridge connects Prompt Manager to document generation
  - ACTIVE prompts take priority over legacy gpt_prompt_registry
  - Fallback to legacy registry if no managed prompt exists
  - `{{INPUT_DATA_JSON}}` pattern used for managed prompts
- [x] **prompt_version_used Tracking (Audit Compliance)**
  - Stored permanently on `orchestration_executions` collection
  - Stored permanently on `orders` collection
  - Contains: template_id, version, service_code, doc_type, name, source
  - Immutable - existing outputs never mutate
- [x] **Prompt Execution Metrics**
  - Records every document generation execution
  - Tracks: execution_time_ms, prompt_tokens, completion_tokens, success/failure
  - Stored in `prompt_execution_metrics` collection
- [x] **Prompt Performance Analytics Dashboard**
  - Total executions, success rate, tokens used
  - Per-prompt breakdown with detailed metrics
  - Top performing prompts table (sortable by executions, success rate, tokens)
  - Configurable time range (7, 14, 30, 90 days)
- [x] **Analytics API Endpoints**
  - `GET /api/admin/prompts/analytics/performance` - Aggregated metrics
  - `GET /api/admin/prompts/analytics/top-prompts` - Ranked prompts
  - `GET /api/admin/prompts/analytics/execution-timeline` - Daily breakdown

### Phase 16: Architectural Alignment (Complete - Jan 24, 2026)
- [x] **Canonical Service Code → Doc Type Rule**
  - service_code MUST equal service catalogue code
  - doc_type MUST equal service_code (canonical rule)
  - No generic document types for production documents
  - Prompt selection resolves via (service_code, doc_type) pair
- [x] **Service Catalogue Validation Enforcement**
  - Prompts cannot be CREATED if service_code not in catalogue
  - Prompts cannot be ACTIVATED if service_code/doc_type mismatch
  - Backend validation: `assert prompt.service_code in service_catalogue`
  - Backend validation: `assert prompt.doc_type in allowed_doc_types`
- [x] **AI_WF_BLUEPRINT Canonical Prompt**
  - Service Code: AI_WF_BLUEPRINT
  - Document Type: AI_WF_BLUEPRINT
  - Name: "Workflow Automation Blueprint – Master Generator"
  - Status: ACTIVE (v1)
  - Template ID: PT-20260124000025-8921A7DC
  - Uses approved system/user prompts with JSON output enforcement
- [x] **Stripe → Order → Prompt → Document Alignment**
  - Payment metadata contains order_id
  - Order contains service_code from checkout
  - Orchestrator uses canonical doc_type == service_code rule
  - Generated documents store service_code, doc_type, prompt_version_used

### Phase 17: Service Catalogue Prompt Population (Complete - Jan 24, 2026)
- [x] **AI Automation Services Prompts (3 Active)**
  - AI_WF_BLUEPRINT / AI_WF_BLUEPRINT - "Workflow Automation Blueprint – Master Generator"
  - AI_PROC_MAP / BUSINESS_PROCESS_MAPPING - "Business Process Mapping – Master Generator"
  - AI_TOOL_RECOMMENDATION / AI_TOOL_RECOMMENDATION_REPORT - "AI Tool Recommendation – Master Generator"
- [x] **Market Research Services Prompts (2 Active)**
  - MR_BASIC / MARKET_RESEARCH_BASIC - "Market Research – Basic – Master Generator"
  - MR_ADV / MARKET_RESEARCH_ADVANCED - "Market Research – Advanced – Master Generator"
- [x] **Compliance Services Prompts (3 Active)**
  - FULL_COMPLIANCE_AUDIT / FULL_COMPLIANCE_AUDIT_REPORT - "Full Compliance Audit Report – Master Generator"
  - HMO_COMPLIANCE_AUDIT / HMO_COMPLIANCE_AUDIT_REPORT - "HMO Compliance Audit Report – Master Generator"
  - MOVE_IN_OUT_CHECKLIST / MOVE_IN_MOVE_OUT_CHECKLIST - "Move-In / Move-Out Checklist – Master Generator"
- [x] **Essential Landlord Document Pack Prompts (5 Active)**
  - DOC_PACK_ESSENTIAL / RENT_ARREARS_LETTER - "Rent Arrears Letter – Essential Pack"
  - DOC_PACK_ESSENTIAL / DEPOSIT_REFUND_EXPLANATION_LETTER - "Deposit Refund / Explanation Letter – Essential Pack"
  - DOC_PACK_ESSENTIAL / TENANT_REFERENCE_LETTER - "Tenant Reference Letter – Essential Pack"
  - DOC_PACK_ESSENTIAL / RENT_RECEIPT - "Rent Receipt – Essential Pack"
  - DOC_PACK_ESSENTIAL / GDPR_INFORMATION_NOTICE - "GDPR / Data Processing Notice – Essential Pack"
- [x] **Tenancy Legal & Notices Pack Prompts (5 Active)**
  - DOC_PACK_PLUS / TENANCY_AGREEMENT_AST - "Assured Shorthold Tenancy (AST) Agreement – Plus Pack"
  - DOC_PACK_PLUS / TENANCY_RENEWAL - "Tenancy Renewal / Extension Document – Plus Pack"
  - DOC_PACK_PLUS / NOTICE_TO_QUIT - "Notice to Quit (Template) – Plus Pack"
  - DOC_PACK_PLUS / GUARANTOR_AGREEMENT - "Guarantor Agreement Template – Plus Pack"
  - DOC_PACK_PLUS / RENT_INCREASE_NOTICE - "Rent Increase Notice (Template) – Plus Pack"
- [x] **Ultimate Document Pack Prompts (4 Active)**
  - DOC_PACK_PRO / INVENTORY_CONDITION_REPORT - "Inventory & Condition Report – Pro Pack"
  - DOC_PACK_PRO / DEPOSIT_INFORMATION_PACK - "Deposit Information Pack – Pro Pack"
  - DOC_PACK_PRO / PROPERTY_ACCESS_NOTICE - "Property Access Notice – Pro Pack"
  - DOC_PACK_PRO / ADDITIONAL_LANDLORD_NOTICE - "Additional Landlord Notice – Pro Pack"
- [x] **All 22 Production Prompts**
  - Registered, tested, and activated via Enterprise Prompt Manager
  - Schema validation passed for all prompts
  - Full audit trail with activation reasons
  - Complete coverage: AI Services (3), Market Research (2), Compliance (3), Document Packs (14)

### Phase 18: Document Pack Orchestrator (Complete - Jan 24, 2026)
- [x] **Pack Inheritance Model**
  - DOC_PACK_ESSENTIAL = Essential docs only (5 docs)
  - DOC_PACK_PLUS = Essential + Plus docs (10 docs)
  - DOC_PACK_PRO = Essential + Plus + Pro docs (14 docs)
- [x] **Canonical Ordering (Server-Side Enforced)**
  - Fixed order per pack tier, sorted by canonical_index
  - Even partial selections maintain canonical order
- [x] **Document Registry**
  - 14 document types with doc_key, doc_type, pack_tier, output_keys
  - Maps to Prompt Manager templates
- [x] **Entitlement + Selection Filtering**
  - Filter 1: Pack tier determines allowed documents
  - Filter 2: Client selection determines which to generate
  - Result: intersection(allowed_docs, selected_docs)
- [x] **Per-Document Versioning**
  - Each document is a separate DocumentItem with own version
  - prompt_version_used and input_snapshot_hash stored for audit
  - version_history preserved on regeneration
- [x] **Regeneration Support**
  - Per-document regeneration with required reason
  - Previous versions never overwritten
  - regen_reason and regen_notes stored
- [x] **Review Workflow**
  - PENDING → GENERATING → COMPLETED → APPROVED/REJECTED
  - Individual approve/reject per document
- [x] **API Endpoints**
  - Registry, canonical order, pack info endpoints
  - Create/get document items
  - Generate single or all documents
  - Regenerate with reason
  - Approve/reject documents
  - Get delivery bundle

### Phase 19: Stripe Integration & Checkout Validation (Complete - Jan 24, 2026)
- [x] **Stripe Product Setup Script** (`/app/backend/scripts/setup_stripe_products.py`)
  - Auto-creates products/prices for all services
  - Sets metadata (service_code, pack_tier, inherits_from)
  - Supports --dry-run, --force-update, --sync-db flags
  - Creates standard, fast_track, printed variants
- [x] **Document Pack Webhook Handler**
  - Specialized handler for DOC_PACK_* orders
  - Extracts selected_documents from intake
  - Creates document items via orchestrator
  - Updates order with pack_info and status
- [x] **Checkout Validation API** (`/api/checkout/*`)
  - POST /validate - Pre-checkout validation
  - GET /service-info/{code} - Service details for checkout
  - GET /document-packs - List all packs with inheritance
  - GET /validate-stripe-alignment - Check Stripe configuration
- [x] **Webhook Integration**
  - checkout.session.completed routes to Document Pack handler
  - Automatic document item creation on payment
  - Order status: CREATED → PAID → QUEUED
  - Pack metadata stored on order
- [x] **Frontend Checkout Integration**
  - checkoutApi.js utility with validation functions
  - UnifiedIntakeWizard validates before Stripe redirect
  - ServiceOrderPage validates document pack orders
  - Warnings displayed via toast notifications

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

### Enterprise Prompt Manager (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/prompts` | GET | List templates with filters (service_code, status, search) |
| `/api/admin/prompts` | POST | Create new template (DRAFT) |
| `/api/admin/prompts/{id}` | GET | Get template by ID |
| `/api/admin/prompts/{id}` | PUT | Update template (DRAFT in-place, others create version) |
| `/api/admin/prompts/{id}` | DELETE | Archive template (soft delete) |
| `/api/admin/prompts/test` | POST | Execute test in Playground (calls Gemini LLM) |
| `/api/admin/prompts/test/{id}/results` | GET | Get test results history |
| `/api/admin/prompts/{id}/mark-tested` | POST | Mark DRAFT as TESTED (requires passing test) |
| `/api/admin/prompts/{id}/activate` | POST | Activate TESTED template (deprecates previous) |
| `/api/admin/prompts/active/{service}/{doc_type}` | GET | Get active template for service/doc_type |
| `/api/admin/prompts/history/{service}/{doc_type}` | GET | Get version history |
| `/api/admin/prompts/audit/log` | GET | Get audit log entries |
| `/api/admin/prompts/stats/overview` | GET | Get stats (total, by_status, tests_last_24h) |
| `/api/admin/prompts/reference/service-codes` | GET | Get available service codes |
| `/api/admin/prompts/reference/doc-types` | GET | Get available document types |

### Document Pack Orchestrator (Admin - ROLE_ADMIN only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/document-packs/registry` | GET | Get full document registry (14 docs) |
| `/api/admin/document-packs/canonical-order` | GET | Get canonical order lists per pack tier |
| `/api/admin/document-packs/pack-info/{service_code}` | GET | Get pack info with allowed docs |
| `/api/admin/document-packs/items` | POST | Create document items for order |
| `/api/admin/document-packs/items/order/{order_id}` | GET | Get all items for order (canonical order) |
| `/api/admin/document-packs/items/{item_id}` | GET | Get single document item |
| `/api/admin/document-packs/items/{item_id}/generate` | POST | Generate single document |
| `/api/admin/document-packs/order/{order_id}/generate-all` | POST | Generate all pending docs |
| `/api/admin/document-packs/items/{item_id}/regenerate` | POST | Regenerate with reason |
| `/api/admin/document-packs/items/{item_id}/approve` | POST | Approve completed document |
| `/api/admin/document-packs/items/{item_id}/reject` | POST | Reject document |
| `/api/admin/document-packs/order/{order_id}/bundle` | GET | Get delivery bundle |
| `/api/admin/document-packs/stats` | GET | Get orchestration statistics |

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

*Last updated: January 24, 2026*