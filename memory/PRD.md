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
- Stripe Test Card: 4242424242424242 (Exp: 12/30, CVC: 123)

## Environment
- Backend: FastAPI on port 8001
- Frontend: React on port 3000
- Database: MongoDB (compliance_vault_pro)
- Stripe: **TEST MODE** - Real test keys configured in .env files
- ClearForm: Separate product at `/clearform/*` routes

## Configuration
- `CONSENT_RETENTION_MONTHS`: 24 (default)

## E2E Testing Status
- **ClearForm Phase 1**: PASSED (Jan 25, 2026)
  - Backend: 19/19 tests passed (100%)
  - Frontend: All flows verified
  - Credit system working with FIFO expiry
  - Document generation with Gemini AI working
  - Test report: `/app/test_reports/iteration_59.json`

- **Document Pack Purchase Flow**: PASSED (Jan 24, 2026)
  - Backend: 28/28 tests passed (100%)
  - Frontend: All wizard steps verified
  - Service code naming aligned: DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_PRO
  - Checkout validation, intake draft creation, orchestrator all working

---

*Last updated: January 25, 2026*

### Phase 20: Order Processing Pipeline Fixes (Complete - Jan 24, 2026)
- [x] **Stripe Webhook Configuration Fix**
  - Identified webhook URL mismatch (old preview URL vs new)
  - Confirmed correct URL: `https://clearform-app.preview.emergentagent.com/api/webhook/stripe`
  - Signing secret verified: `whsec_jgG1IvSxCpaJM6maQQEhoOeM4YLU4R9x`
  - Webhooks now receiving `checkout.session.completed` events successfully
- [x] **Order Queue Processing Fix**
  - Fixed 9 PAID orders stuck without `workflow_state`
  - Implemented `wf1_payment_to_queue` to transition PAID → QUEUED
  - Background job scheduler now correctly picking up queued orders
- [x] **Failure Reason Persistence**
  - Fixed `transition_order_state` to save `failure_reason` and `failed_at` on FAILED transition
  - Future failed orders will have failure reason visible in Admin UI
- [x] **Admin UI Friendly Labels**
  - Created `orderLabels.js` utility with service/category/status mappings
  - `getCategoryLabel()`: Converts `ai_automation` → "AI & Automation"
  - `getServiceLabel()`: Converts `AI_WORKFLOW` → "AI Workflow Blueprint"
  - `getStatusLabel()`: Converts `FAILED` → "Failed"
  - Applied to OrderList.jsx and OrderDetailsPane.jsx
- [x] **Admin UI Error Visibility**
  - Added prominent red alert box for FAILED orders in OrderDetailsPane
  - Shows failure reason or "No failure reason recorded" message
  - Includes `failed_at` timestamp when available
- [x] **Intake Wizard URL Update Fix**
  - Service selection now updates URL query parameter
  - URL reflects selected service: `/order/intake?service=AI_WF_BLUEPRINT`
  - Enables sharing specific service links

### Phase 21: Marketing Website CMS (Complete - Jan 25, 2026)

**Phase 1 + 2: CMS Backend + Public Pages**
- [x] Extended `cms_models.py` with PageType (HUB, CATEGORY, SERVICE), CATEGORY_CONFIG, PurchaseMode
- [x] Extended `cms_service.py` with marketing functions:
  - `get_services_hub()`, `get_category_page()`, `get_service_page()`
  - `build_cta_config()` - Dynamic CTA based on purchase mode
  - `check_redirect()`, `create_redirect()` - URL redirect support
  - `unpublish_page()` - Set pages back to draft
- [x] Created `/api/marketing/*` routes for public website
- [x] Created CMS seeding script with 16 pages:
  - 1 Hub page (`/services`)
  - 4 Category pages (`/services/ai-automation`, etc.)
  - 11 Service pages linked to Service Catalogue
- [x] Frontend components: `ServicesHubPageCMS.js`, `CategoryPageCMS.js`, `ServicePageCMS.js`
- [x] Preview environment banner for non-production
- [x] CTA routing to `/order/intake?service={service_code}`

**Phase 3: Admin CMS UI**
- [x] Added "Marketing Website" tab to Admin Site Builder
- [x] Marketing pages list with page type grouping (Hub, Categories, Services)
- [x] Summary stats (Total pages, Published, Drafts, Categories)
- [x] Category expansion/collapse with nested services
- [x] Publish/Unpublish actions per page
- [x] Visibility toggle (show/hide in nav)
- [x] Edit button integration with existing page editor
- [x] External link preview buttons

**API Endpoints**:
- `GET /api/marketing/services` - Services hub data
- `GET /api/marketing/services/categories` - List categories
- `GET /api/marketing/services/category/{slug}` - Category with services
- `GET /api/marketing/services/{category}/{service}` - Service detail
- `GET /api/admin/cms/marketing/pages` - Admin page list
- `POST /api/admin/cms/marketing/pages/{id}/publish` - Publish page
- `POST /api/admin/cms/marketing/pages/{id}/unpublish` - Unpublish page
- `PUT /api/admin/cms/marketing/pages/{id}/visibility` - Toggle nav visibility

---

### Phase 22: ClearForm Product - Phase 1 MVP (Complete - Jan 25, 2026)

**Product Overview**:
ClearForm is a standalone SaaS product - an intent-driven paperwork assistant with a credit-based economy. It shares backend infrastructure with Pleerity but operates as a completely separate product with its own:
- UX and frontend (`/clearform/*` routes)
- MongoDB collections (`clearform_users`, `clearform_documents`, etc.)
- Stripe products (same account, separate products)
- User identity (ClearForm user ≠ Pleerity client)

**Architecture**: Shared Backend, Separate Frontend

**Phase 1 Features Implemented**:

**Credit System**:
- [x] Credit wallet with FIFO expiry tracking
- [x] Credit deduction on document generation
- [x] Manual top-ups via Stripe checkout
- [x] Subscription plans with monthly credit grants
- [x] Credit expiry logic (365 days default)
- [x] Transaction history with audit trail
- [x] 5 welcome bonus credits for new users

**Document Types** (8 types - Phase 1 + Phase 2):
- [x] Formal Letter (1 credit) - Professional correspondence
- [x] Complaint Letter (1 credit) - Issue resolution letters
- [x] CV/Resume (2 credits) - Professional CV generation
- [x] Complaint or Appeal Letter (1 credit) - EXPLAIN_APPEAL_REQUEST category
- [x] Statement of Circumstances (1 credit) - EXPLAIN_APPEAL_REQUEST category
- [x] Application Cover Letter (1 credit) - INTRODUCE_SUPPORT category
- [x] Reference Letter (2 credits) - INTRODUCE_SUPPORT category
- [x] Notice to Landlord (1 credit) - NOTIFY_DECLARE_AUTHORISE category

**Document Generation**:
- [x] Intent-based generation flow (user describes, AI creates)
- [x] AI generation via Gemini (emergentintegrations)
- [x] Async generation with status polling
- [x] Auto-refund on failed generation
- [x] Markdown & plain text output
- [x] **PDF Export** - Professional PDF generation via reportlab

**Document Vault**:
- [x] Document listing with pagination
- [x] Filter by type and status
- [x] Search functionality
- [x] Archive (soft delete)
- [x] Download (PDF, TXT, MD)
- [x] Copy to clipboard

**Admin-Configurable Document Types**:
- [x] Document categories (EXPLAIN_APPEAL_REQUEST, INTRODUCE_SUPPORT, NOTIFY_DECLARE_AUTHORISE)
- [x] Admin can add/modify/disable document types without code changes
- [x] Custom fields per document type (required + optional)
- [x] Per-type credit costs
- [x] Changes take effect immediately

**User Templates**:
- [x] Save document intents as reusable templates
- [x] Template CRUD operations
- [x] Usage tracking (count, last used)
- [x] Favorite templates
- [x] Workspace-scoped templates

**Workspaces (Phase 2)**:
- [x] Create/manage workspaces
- [x] Default workspace auto-creation
- [x] Workspace colors and icons
- [x] Document/template organization

**Smart Profiles (Phase 2)**:
- [x] Save personal details for auto-fill
- [x] Multiple profile types (personal, business)
- [x] Default profile per type
- [x] Usage tracking

**Subscriptions**:
- [x] 4 plans: Free, Starter (£4.99), Professional (£9.99), Unlimited (£24.99)
- [x] Monthly credit grants
- [x] Credit rollover limits by plan
- [x] Stripe subscription checkout
- [x] Cancel at period end

**Website Integration**:
- [x] ClearForm in Products dropdown (alongside CVP)
- [x] "New" badge on ClearForm
- [x] Separate branding for individuals/small businesses

**API Endpoints** (`/api/clearform/*`):
- Auth: `/auth/register`, `/auth/login`, `/auth/me`
- Credits: `/credits/wallet`, `/credits/balance`, `/credits/history`, `/credits/packages`, `/credits/purchase`
- Documents: `/documents/types`, `/documents/generate`, `/documents/vault`, `/documents/{id}`, `/documents/{id}/download`
- Document Types: `/document-types`, `/document-types/categories`, `/document-types/admin/*`
- Templates: `/templates`, `/templates/{id}`, `/templates/{id}/use`, `/templates/{id}/favorite`
- Workspaces: `/workspaces`, `/workspaces/{id}`
- Profiles: `/profiles`, `/profiles/default`, `/profiles/{id}`
- Subscriptions: `/subscriptions/plans`, `/subscriptions/current`, `/subscriptions/subscribe`, `/subscriptions/cancel`, `/subscriptions/portal`
- Webhooks: `/webhook/stripe`

**Frontend Pages**:
- [x] Landing Page (`/clearform`) - Hero, features, document types, pricing
- [x] Auth Pages (`/clearform/login`, `/clearform/register`)
- [x] Dashboard (`/clearform/dashboard`) - Credit balance, recent docs, quick actions
- [x] Create Wizard (`/clearform/create`) - Type selection, intent form, generation
- [x] Document View (`/clearform/document/:id`) - View, download, copy

**MongoDB Collections**:
- `clearform_users` - User accounts with embedded wallet
- `clearform_documents` - Generated documents
- `clearform_credit_transactions` - Credit audit trail
- `clearform_credit_expiry` - Expiry batch tracking
- `clearform_subscriptions` - Subscription records
- `clearform_credit_topups` - Top-up purchase records

**Test Credentials**:
- ClearForm: demo2@clearform.com / DemoPass123!
- ClearForm: fixtest@clearform.com / TestPass123!
- ClearForm: orgtest@clearform.com / Test123! (owns organization ORG-DADB67A3)
- ClearForm: doctest@clearform.com / Test123!

**Product Boundary Rules** (IMPORTANT):
- ClearForm does NOT use: Service Catalogue, Orders, CVP subscriptions, Document Pack Orchestrator
- ClearForm uses: Intent-based flow, Credit economy, Document vault
- No shared checkout logic with Pleerity services

### Phase 23: ClearForm Production Buildout - Phase A & B (Complete - Jan 25, 2026)

**PDF Export**:
- [x] Backend `pdf_service.py` using `reportlab` library
- [x] `/api/clearform/documents/download/pdf/{doc_id}` endpoint
- [x] Fixed 'BodyText' style conflict bug

**Dynamic Document Types (Admin-configurable)**:
- [x] `clearform_document_types` collection (code, name, category, required_fields)
- [x] `clearform_document_categories` collection
- [x] Admin CRUD endpoints for document types
- [x] Initialize defaults on startup

**Workspaces & Smart Profiles**:
- [x] `workspace_service.py` - Workspace management
- [x] `clearform_workspaces` collection
- [x] `clearform_profiles` collection (personal, business, property types)
- [x] API endpoints for workspaces and profiles

**User Templates**:
- [x] Save successful document configurations as templates
- [x] Template favorites
- [x] Use template to pre-fill creation wizard

### Phase 24: ClearForm Production Buildout - Phase C (Complete - Jan 25, 2026)

**Institutional Accounts (Organizations)**:
- [x] `organization_service.py` - Full organization management
- [x] Organization CRUD (create, get, update)
- [x] Member management (list, update role, remove)
- [x] Invitation system (create, get pending, accept)
- [x] Shared credit pool (org-level credits)
- [x] 5 organization types: Small Business, Enterprise, Nonprofit, Educational, Government
- [x] 5 member roles: Owner, Admin, Manager, Member, Viewer

**Audit Logging**:
- [x] `audit_service.py` - Comprehensive audit logging
- [x] 30+ action types across all ClearForm operations
- [x] 4 severity levels: Info, Warning, Error, Critical
- [x] User audit logs, org audit logs, document trails
- [x] Audit statistics and activity feeds

**Compliance Packs**:
- [x] Pre-built document bundles for specific use cases
- [x] Tenant Essentials, Job Seeker, Small Business starter packs
- [x] Pack pricing with discounts

**API Endpoints (Phase C)**:
- Organizations: `/api/clearform/organizations/*`
  - CRUD, members, invitations, credits, compliance-packs
- Audit: `/api/clearform/audit/*`
  - me, me/activity, me/stats, org/{id}, org/{id}/activity, document/{id}, actions, severities

**MongoDB Collections (Phase C)**:
- `clearform_organizations` - Institutional accounts with shared credit pool
- `clearform_org_members` - Organization membership records
- `clearform_org_invitations` - Pending invitations with expiry
- `clearform_audit_logs` - Complete audit trail
- `clearform_compliance_packs` - Pre-built document bundles

**Bug Fixes (Jan 25, 2026)**:
- [x] Fixed markdown code fence rendering in document view
  - Improved `cleanMarkdown()` function in `ClearFormDocumentPage.jsx`
  - Now properly strips AI preambles and code fences

### Phase 25: ClearForm UI Enhancements & Admin Integration (Complete - Jan 25, 2026)

**Pricing Page Update**:
- [x] Added product tabs (CVP | ClearForm) to pricing page
- [x] ClearForm credit top-ups: 10=£5, 25=£10, 75=£25
- [x] ClearForm subscriptions: Free (3 credits), Personal (£9.99/mo, 20 credits), Power User (£24.99/mo, 75 credits)
- [x] Credits never expire, show price before generation

**Dashboard Navigation Fix**:
- [x] Created `/clearform/vault` - Document Vault page with search/filter
- [x] Created `/clearform/credits` - Credits purchase page with packages and subscriptions
- [x] Fixed Document Vault and Buy Credits cards to navigate properly

**Unified Admin Console - ClearForm Section**:
- [x] Added ClearForm section to admin sidebar navigation
- [x] ClearForm Users page (view all users, credits, documents count)
- [x] ClearForm Documents page (view all documents, status, user)
- [x] Admin API endpoints: `/api/admin/clearform/{stats,users,documents,organizations,audit}`

**Welcome Email (ClearForm)**:
- [x] Branded email template "ClearForm by Pleerity"
- [x] Uses Pleerity green theme (#10b981)
- [x] Shows credit balance, "Create Your First Document" CTA
- [x] Includes legal disclaimer footer
- [x] Calm, reassuring, plain English tone

---

## Credentials
- Admin: admin@pleerity.com / Admin123!
- Client: test@pleerity.com / TestClient123!
- ClearForm: demo2@clearform.com / DemoPass123!
- ClearForm: orgtest@clearform.com / Test123! (Organization owner)
- ClearForm: doctest@clearform.com / Test123!
- Stripe Test Card: 4242424242424242 (Exp: 12/30, CVC: 123)