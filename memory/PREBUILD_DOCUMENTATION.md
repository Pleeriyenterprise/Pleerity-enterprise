# Pleerity Enterprise Ltd - Public Website & Platform Expansion
## Pre-Build Documentation v1.0

**Document Status:** PENDING APPROVAL  
**Date:** January 2026  
**Author:** E1 Development Agent  
**Approved By:** [Awaiting Approval]

---

## Table of Contents

1. [Architecture Diagram](#1-architecture-diagram)
2. [Data Model for New Collections](#2-data-model-for-new-collections)
3. [Workflow State Machine for Orders](#3-workflow-state-machine-for-orders)
4. [Routes & Sitemap Plan](#4-routes--sitemap-plan)
5. [SEO Plan](#5-seo-plan)
6. [Risk Register](#6-risk-register)

---

## 1. Architecture Diagram

### System Boundary Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PLEERITY PLATFORM                                     │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                           PUBLIC WEBSITE (NEW)                                      │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │ │
│  │  │  Home   │ │Services │ │ Pricing │ │ Booking │ │ Insights│ │  About  │          │ │
│  │  │    /    │ │/services│ │/pricing │ │/booking │ │/insights│ │ /about  │          │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │ │
│  │                                                                                     │ │
│  │  Routes: /*, /services/*, /compliance-vault-pro, /pricing, /booking, /insights/*,  │ │
│  │          /about, /careers, /partnerships, /contact, /legal/*                       │ │
│  │                                                                                     │ │
│  │  [NO AUTH REQUIRED] [SEO-OPTIMIZED] [REACT-HELMET FOR META]                        │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                               │
│                                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                          SHARED INFRASTRUCTURE                                      │ │
│  │                                                                                     │ │
│  │   React Frontend (port 3000)          FastAPI Backend (port 8001)                  │ │
│  │   ├── /app/* (Client Portal)          ├── /api/public/* (NEW - Public APIs)       │ │
│  │   ├── /admin/* (Admin Portal)         ├── /api/client/* (Client APIs)             │ │
│  │   └── /* (Public Website - NEW)       ├── /api/admin/* (Admin APIs)               │ │
│  │                                        ├── /api/orders/* (NEW - Orders APIs)       │ │
│  │   [Tailwind CSS + Shadcn/UI]          └── /api/blog/* (NEW - Blog APIs)           │ │
│  │                                                                                     │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                               │
│         ┌────────────────────────────────┼────────────────────────────────┐             │
│         │                                │                                │              │
│         ▼                                ▼                                ▼              │
│  ┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐    │
│  │ COMPLIANCE VAULT │           │   ORDERS SYSTEM  │           │   ADMIN CRM      │    │
│  │   PRO (CVP)      │           │      (NEW)       │           │     (NEW)        │    │
│  │   🔒 LOCKED      │           │                  │           │                  │    │
│  ├──────────────────┤           ├──────────────────┤           ├──────────────────┤    │
│  │ • clients        │           │ • orders         │           │ • blog_posts     │    │
│  │ • properties     │           │ • workflow_exec  │           │ • contact_subs   │    │
│  │ • requirements   │           │ • service_inq    │           │ • service_inq    │    │
│  │ • documents      │           │                  │           │                  │    │
│  │ • portal_users   │           │ Statuses:        │           │ Pipeline View    │    │
│  │ • client_billing │           │ CREATED→PAID→    │           │ Timeline View    │    │
│  │ • audit_logs     │           │ QUEUED→IN_PROG→  │           │ Manual Controls  │    │
│  │                  │           │ DRAFT_READY→     │           │                  │    │
│  │ [DO NOT MODIFY]  │           │ INTERNAL_REVIEW→ │           │ [ADMIN ONLY]     │    │
│  │                  │           │ COMPLETED        │           │                  │    │
│  └──────────────────┘           └──────────────────┘           └──────────────────┘    │
│                                          │                                               │
└──────────────────────────────────────────┼───────────────────────────────────────────────┘
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                                            │
│                                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   STRIPE    │  │  POSTMARK   │  │   GEMINI    │  │   TWILIO    │  │  CALENDLY   │    │
│  │  Payments   │  │   Emails    │  │  AI (LLM)   │  │    SMS      │  │   Booking   │    │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤    │
│  │ • Checkout  │  │ • Transact  │  │ • Doc AI    │  │ • SMS       │  │ • Embed     │    │
│  │ • Webhooks  │  │ • Templates │  │ • Assistant │  │ • Notifs    │  │ • Callback  │    │
│  │ • Portal    │  │ • Lifecycle │  │ • Analysis  │  │             │  │             │    │
│  │ • Subscrip  │  │             │  │             │  │             │  │             │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                                           │
│  [API KEY CONFIG IN .env]  [WEBHOOK SIGNING]  [EMERGENT LLM KEY]  [RATE LIMITED]         │
│                                                                                           │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### Authority Boundaries

| Domain | Source of Truth | Who Can Modify | Notes |
|--------|-----------------|----------------|-------|
| **Compliance Decisions** | CVP (requirements collection) | System only | Rule-based, no AI decisions |
| **Billing/Entitlements** | Stripe → client_billing | Stripe webhooks only | Server-authoritative |
| **Order Workflow State** | orders collection | System + Admin (fallback) | All transitions audit-logged |
| **Document Storage** | CVP documents collection | Client upload + AI extraction | CVP handles compliance docs |
| **Blog/Insights Content** | blog_posts collection | Admin only | CMS via Admin Dashboard |
| **Contact/Inquiries** | contact_submissions / service_inquiries | Public submission | Admin read/respond |

### Data Flow

```
                    PUBLIC WEBSITE
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   Contact Form    Service Inquiry   Blog View
         │               │               │
         ▼               ▼               ▼
  contact_submissions  service_inquiries  blog_posts (read)
         │               │
         │    If paid    │
         │    service    │
         │       │       │
         │       ▼       │
         │    orders ────┼──────────────────────────────────┐
         │       │                                          │
         │       ▼                                          │
         │   workflow_executions                            │
         │       │                                          │
         │       │ (if CVP onboarding)                      │
         │       │                                          │
         │       ▼                                          │
         │   ┌───────────────────────────────────────────┐  │
         │   │  CVP BOUNDARY (DO NOT CROSS DIRECTLY)     │  │
         │   │                                           │  │
         │   │  Only triggers:                           │  │
         │   │  1. Create client record                  │  │
         │   │  2. Trigger provisioning service          │  │
         │   │                                           │  │
         │   │  CVP manages its own:                     │  │
         │   │  - Properties, Requirements, Documents    │  │
         │   │  - Compliance calculations                │  │
         │   │  - Client billing/entitlements            │  │
         │   └───────────────────────────────────────────┘  │
         │                                                  │
         ▼                                                  ▼
   Admin Dashboard ◄────────────────────────────────────────┘
   (Pipeline View, Timeline, Controls)
```

---

## 2. Data Model for New Collections

### 2.1 `orders` Collection

Handles all non-CVP service fulfilment. CVP subscriptions are **not** orders - they go directly to CVP provisioning.

```python
# Schema: orders
{
    "_id": ObjectId,
    "order_id": str,              # Format: ORD-YYYY-XXXXXX (unique)
    "order_type": str,            # "MARKET_RESEARCH" | "DOCUMENT_PACK" | "COMPLIANCE_AUDIT" | "CLEANING" | "AI_WORKFLOW"
    
    # Customer Info (may or may not be existing CVP client)
    "customer": {
        "email": str,             # Required
        "full_name": str,         # Required
        "phone": str | None,
        "company_name": str | None,
        "existing_client_id": str | None,  # Links to CVP client if they have account
    },
    
    # Service Details
    "service_code": str,          # e.g., "AUDIT_HMO_FULL", "RESEARCH_AREA"
    "service_name": str,          # Human-readable
    "service_category": str,      # "research" | "documents" | "audit" | "cleaning" | "workflow"
    "parameters": dict,           # Service-specific params (property address, postcode area, etc.)
    
    # Pricing
    "pricing": {
        "base_price": int,        # In pence (e.g., 9900 = £99)
        "vat_amount": int,
        "total_amount": int,
        "currency": "gbp",
        "stripe_payment_intent_id": str | None,
        "stripe_checkout_session_id": str | None,
    },
    
    # Status & Workflow
    "status": str,                # See state machine below
    "sla_hours": int | None,      # Target delivery time (pauses during CLIENT_INPUT_REQUIRED)
    "sla_paused_at": datetime | None,
    "sla_pause_duration_hours": int,  # Accumulated pause time
    
    # Deliverables
    "deliverables": [
        {
            "type": str,          # "pdf" | "docx" | "json" | "report"
            "filename": str,
            "storage_path": str,
            "generated_at": datetime,
            "version": int,
            "status": str,        # "draft" | "approved" | "delivered"
        }
    ],
    
    # Tracking
    "created_at": datetime,
    "updated_at": datetime,
    "completed_at": datetime | None,
    "delivered_at": datetime | None,
    
    # Internal Notes (never exposed to customer)
    "internal_notes": str | None,
}

# Indexes
db.orders.create_index("order_id", unique=True)
db.orders.create_index("status")
db.orders.create_index("customer.email")
db.orders.create_index("customer.existing_client_id")
db.orders.create_index([("status", 1), ("created_at", -1)])
db.orders.create_index("service_category")
```

### 2.2 `workflow_executions` Collection

Audit log for every state transition in an order.

```python
# Schema: workflow_executions
{
    "_id": ObjectId,
    "execution_id": str,          # Format: WFE-XXXXXX (unique)
    "order_id": str,              # Foreign key to orders
    
    # Transition Details
    "previous_state": str | None, # Null for initial creation
    "new_state": str,
    "transition_type": str,       # "system" | "admin_manual" | "customer_action"
    
    # Actor
    "triggered_by": {
        "type": str,              # "system" | "admin" | "customer"
        "user_id": str | None,    # Admin user ID if manual
        "user_email": str | None,
    },
    
    # Context
    "reason": str | None,         # Required for admin manual transitions
    "notes": str | None,
    "metadata": dict | None,      # Additional context (e.g., regen instructions)
    
    # Timing
    "created_at": datetime,
}

# Indexes
db.workflow_executions.create_index("order_id")
db.workflow_executions.create_index("execution_id", unique=True)
db.workflow_executions.create_index([("order_id", 1), ("created_at", 1)])
db.workflow_executions.create_index("triggered_by.user_id")
```

### 2.3 `blog_posts` Collection

Admin-managed content for /insights.

```python
# Schema: blog_posts
{
    "_id": ObjectId,
    "post_id": str,               # Format: POST-XXXXXX (unique)
    "slug": str,                  # URL slug (unique, lowercase, hyphenated)
    
    # Content
    "title": str,
    "excerpt": str,               # Short description (max 200 chars)
    "content": str,               # Markdown content
    "featured_image": str | None, # URL to image
    
    # Categorization
    "category": str,              # "landlord-compliance" | "ai-automation" | "industry-news" | "guides"
    "tags": [str],
    
    # SEO
    "meta_title": str | None,     # Override for <title>, defaults to title
    "meta_description": str | None,  # Override for meta description
    "canonical_url": str | None,  # If republished content
    
    # Publishing
    "status": str,                # "draft" | "published" | "archived"
    "published_at": datetime | None,
    "author": {
        "name": str,
        "email": str,             # Admin email
    },
    
    # Tracking
    "created_at": datetime,
    "updated_at": datetime,
    "view_count": int,            # Analytics
}

# Indexes
db.blog_posts.create_index("post_id", unique=True)
db.blog_posts.create_index("slug", unique=True)
db.blog_posts.create_index("status")
db.blog_posts.create_index("category")
db.blog_posts.create_index([("status", 1), ("published_at", -1)])
db.blog_posts.create_index("tags")
```

### 2.4 `service_inquiries` Collection

Pre-sales inquiries for services (not yet paid).

```python
# Schema: service_inquiries
{
    "_id": ObjectId,
    "inquiry_id": str,            # Format: INQ-XXXXXX (unique)
    
    # Contact Info
    "email": str,
    "full_name": str,
    "phone": str | None,
    "company_name": str | None,
    
    # Inquiry Details
    "service_interest": str,      # Which service they're asking about
    "message": str,               # Their question/inquiry
    "source_page": str,           # Which page they came from
    
    # Status
    "status": str,                # "new" | "contacted" | "converted" | "closed"
    
    # Admin Response
    "admin_notes": str | None,
    "responded_by": str | None,   # Admin email
    "responded_at": datetime | None,
    
    # Tracking
    "created_at": datetime,
    "updated_at": datetime,
    
    # Conversion
    "converted_to_order_id": str | None,
}

# Indexes
db.service_inquiries.create_index("inquiry_id", unique=True)
db.service_inquiries.create_index("status")
db.service_inquiries.create_index("email")
db.service_inquiries.create_index([("status", 1), ("created_at", -1)])
```

### 2.5 `contact_submissions` Collection

General contact form submissions.

```python
# Schema: contact_submissions
{
    "_id": ObjectId,
    "submission_id": str,         # Format: CONTACT-XXXXXX (unique)
    
    # Contact Info
    "email": str,
    "full_name": str,
    "phone": str | None,
    "company_name": str | None,
    
    # Message
    "subject": str,
    "message": str,
    "contact_reason": str,        # "general" | "support" | "partnership" | "press" | "careers"
    
    # Status
    "status": str,                # "new" | "read" | "replied" | "archived"
    
    # Admin Response
    "admin_notes": str | None,
    "responded_by": str | None,
    "responded_at": datetime | None,
    
    # Tracking
    "created_at": datetime,
    "updated_at": datetime,
}

# Indexes
db.contact_submissions.create_index("submission_id", unique=True)
db.contact_submissions.create_index("status")
db.contact_submissions.create_index("email")
db.contact_submissions.create_index([("status", 1), ("created_at", -1)])
db.contact_submissions.create_index("contact_reason")
```

---

## 3. Workflow State Machine for Orders

### 3.1 State Diagram

```
                                    ┌──────────────────────────────────────────────┐
                                    │                    TERMINAL                   │
                                    │                                               │
                                    │  ┌────────────┐  ┌────────────┐              │
                                    │  │ COMPLETED  │  │  FAILED    │              │
                                    │  │ (success)  │  │ (blocked)  │              │
                                    │  └────────────┘  └────────────┘              │
                                    │         ▲              ▲                      │
                                    │         │              │                      │
                                    │         │    ┌────────────┐                  │
                                    │         │    │ CANCELLED  │                  │
                                    │         │    │(admin only)│                  │
                                    │         │    └────────────┘                  │
                                    │         │         ▲                          │
                                    └─────────┼─────────┼──────────────────────────┘
                                              │         │
┌─────────────────────────────────────────────┼─────────┼─────────────────────────────┐
│                               DELIVERY      │         │                             │
│                                             │         │                             │
│    ┌─────────────┐     ┌─────────────┐     │         │                             │
│    │ FINALISING  │────►│ DELIVERING  │─────┘         │                             │
│    │(final build)│     │(email send) │               │                             │
│    └─────────────┘     └─────────────┘               │                             │
│           ▲                                          │                             │
└───────────┼──────────────────────────────────────────┼─────────────────────────────┘
            │                                          │
┌───────────┼──────────────────────────────────────────┼─────────────────────────────┐
│           │              REVIEW PHASE                │                             │
│           │                                          │                             │
│    ┌──────┴──────┐                                   │                             │
│    │   approve   │                                   │                             │
│    │             │                                   │                             │
│    │  ┌─────────────────────┐                        │                             │
│    └──│  INTERNAL_REVIEW    │◄───────────────────────┼─────────────────┐           │
│       │  (human gate)       │                        │                 │           │
│       └─────────────────────┘                        │                 │           │
│              │         │                             │                 │           │
│       ┌──────┘         └──────┐                      │                 │           │
│       │ regen                 │ request_info         │                 │           │
│       ▼                       ▼                      │                 │           │
│  ┌────────────────┐   ┌─────────────────────┐        │                 │           │
│  │REGEN_REQUESTED │   │CLIENT_INPUT_REQUIRED│        │                 │           │
│  │(notes captured)│   │   (SLA paused)      │        │                 │           │
│  └────────────────┘   └─────────────────────┘        │                 │           │
│         │                       │                    │                 │           │
│         ▼                       │ client_responded   │                 │           │
│  ┌────────────────┐             └─────────────────────────────────────►│           │
│  │ REGENERATING   │                                  │                 │           │
│  │(system regen)  │──────────────────────────────────┘                 │           │
│  └────────────────┘                                                    │           │
│                                                                        │           │
└────────────────────────────────────────────────────────────────────────┼───────────┘
                                                                         │
┌────────────────────────────────────────────────────────────────────────┼───────────┐
│                              EXECUTION PHASE                           │           │
│                                                                        │           │
│  ┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │ QUEUED  │────►│ IN_PROGRESS │────►│ DRAFT_READY │─────┘             │           │
│  │(waiting)│     │ (running)   │     │(draft done) │                   │           │
│  └─────────┘     └─────────────┘     └─────────────┘                   │           │
│       ▲                                                                │           │
└───────┼────────────────────────────────────────────────────────────────┘           │
        │                                                                            │
┌───────┼────────────────────────────────────────────────────────────────────────────┘
│       │              PAYMENT & INTAKE
│       │
│  ┌─────────┐     ┌─────────┐
│  │ CREATED │────►│  PAID   │
│  │(pending)│     │(ref gen)│
│  └─────────┘     └─────────┘
│
└─────────────────────────────────────────────────────────────────────────────────────
```

### 3.2 Status Definitions

| Status | Description | Entry Condition | Exit Conditions |
|--------|-------------|-----------------|-----------------|
| `CREATED` | Order record created, pending payment | Order submitted | Payment confirmed → `PAID` |
| `PAID` | Payment confirmed, reference generated | Stripe payment success | System queues → `QUEUED` |
| `QUEUED` | Ready to execute, waiting worker | Auto after `PAID` | Worker picks up → `IN_PROGRESS` |
| `IN_PROGRESS` | Generation/execution running | Worker starts | Complete → `DRAFT_READY`, Error → `FAILED` |
| `DRAFT_READY` | Draft produced and stored | Generation complete | Auto → `INTERNAL_REVIEW` |
| `INTERNAL_REVIEW` | Human gate (admin reviews) | Draft ready | Approve → `FINALISING`, Regen → `REGEN_REQUESTED`, Need info → `CLIENT_INPUT_REQUIRED` |
| `REGEN_REQUESTED` | Admin requested changes | Admin action with notes | System starts → `REGENERATING` |
| `REGENERATING` | System regenerating | Auto after regen request | Complete → `INTERNAL_REVIEW` |
| `CLIENT_INPUT_REQUIRED` | Paused, waiting on client | Admin requests info | Client responds → `INTERNAL_REVIEW` |
| `FINALISING` | Approved, final assembly | Admin approves | Assembly complete → `DELIVERING` |
| `DELIVERING` | Email send in progress | Final doc ready | Send success → `COMPLETED`, Send fail → retry or `FAILED` |
| `COMPLETED` | Delivered successfully | Email delivered | **Terminal** |
| `FAILED` | Blocked error state | Unrecoverable error | **Terminal** (needs admin manual intervention) |
| `CANCELLED` | Admin cancelled | Admin action only | **Terminal** |

### 3.3 Transition Rules

```python
# Valid state transitions
ALLOWED_TRANSITIONS = {
    "CREATED": ["PAID", "CANCELLED"],
    "PAID": ["QUEUED", "CANCELLED"],
    "QUEUED": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["DRAFT_READY", "FAILED"],
    "DRAFT_READY": ["INTERNAL_REVIEW"],
    "INTERNAL_REVIEW": ["FINALISING", "REGEN_REQUESTED", "CLIENT_INPUT_REQUIRED", "CANCELLED"],
    "REGEN_REQUESTED": ["REGENERATING"],
    "REGENERATING": ["INTERNAL_REVIEW", "FAILED"],
    "CLIENT_INPUT_REQUIRED": ["INTERNAL_REVIEW"],
    "FINALISING": ["DELIVERING", "FAILED"],
    "DELIVERING": ["COMPLETED", "FAILED"],
    # Terminal states - no transitions out
    "COMPLETED": [],
    "FAILED": [],  # Admin can manually move to CANCELLED or re-queue
    "CANCELLED": [],
}

# Transitions requiring manual admin action
ADMIN_ONLY_TRANSITIONS = {
    ("INTERNAL_REVIEW", "FINALISING"),       # Approve
    ("INTERNAL_REVIEW", "REGEN_REQUESTED"),  # Request regen
    ("INTERNAL_REVIEW", "CLIENT_INPUT_REQUIRED"),  # Request info
    ("*", "CANCELLED"),                      # Cancel from any non-terminal
    ("FAILED", "QUEUED"),                    # Re-queue failed order (recovery)
}

# Transitions that pause SLA
SLA_PAUSE_TRANSITIONS = {
    ("*", "CLIENT_INPUT_REQUIRED"),  # Pause SLA
}

# Transitions that resume SLA
SLA_RESUME_TRANSITIONS = {
    ("CLIENT_INPUT_REQUIRED", "INTERNAL_REVIEW"),  # Resume SLA
}
```

### 3.4 Audit Logging Requirements

Every state transition MUST create a `workflow_executions` record with:

```python
{
    "execution_id": generate_execution_id(),
    "order_id": order.order_id,
    "previous_state": current_status,
    "new_state": new_status,
    "transition_type": "system" | "admin_manual" | "customer_action",
    "triggered_by": {
        "type": actor_type,
        "user_id": admin_user_id if manual else None,
        "user_email": admin_email if manual else None,
    },
    "reason": mandatory_reason if admin_manual else None,
    "notes": optional_notes,
    "metadata": { /* additional context */ },
    "created_at": datetime.utcnow(),
}
```

---

## 4. Routes & Sitemap Plan

### 4.1 URL Structure (Final Slugs)

| URL | Page Type | Component | Notes |
|-----|-----------|-----------|-------|
| `/` | Home | `HomePage.js` | Hero + value props + CTAs |
| `/compliance-vault-pro` | Product | `CVPLandingPage.js` | Main product page (SEO focus) |
| `/services` | Hub | `ServicesHubPage.js` | All services overview |
| `/services/ai-workflow-automation` | Service | `ServiceAIWorkflowPage.js` | AI workflow service |
| `/services/market-research` | Service | `ServiceMarketResearchPage.js` | Market research service |
| `/services/document-packs` | Service | `ServiceDocumentPacksPage.js` | Document pack service |
| `/services/compliance-audits` | Service | `ServiceComplianceAuditsPage.js` | Compliance audit hub |
| `/services/compliance-audits/hmo` | Service | `ServiceHMOAuditPage.js` | HMO-specific audit |
| `/services/compliance-audits/full` | Service | `ServiceFullAuditPage.js` | Full audit |
| `/services/cleaning` | Service | `ServiceCleaningPage.js` | Cleaning (separate visual) |
| `/pricing` | Pricing | `PricingPage.js` | All pricing tiers |
| `/booking` | Booking | `BookingPage.js` | Calendly embed |
| `/insights` | Blog Hub | `InsightsHubPage.js` | Blog listing |
| `/insights/:slug` | Blog Post | `InsightsPostPage.js` | Individual post |
| `/insights/category/:category` | Category | `InsightsCategoryPage.js` | Posts by category |
| `/about` | About | `AboutPage.js` | Company info |
| `/careers` | Careers | `CareersPage.js` | Job listings |
| `/partnerships` | Partnerships | `PartnershipsPage.js` | Partner info |
| `/contact` | Contact | `ContactPage.js` | Contact form |
| `/legal/privacy` | Legal | `PrivacyPage.js` | Privacy policy |
| `/legal/terms` | Legal | `TermsPage.js` | Terms of service |
| `/login` | Auth | `LoginPage.js` | **Existing** |
| `/intake/start` | Onboarding | `IntakePage.js` | **Existing** |
| `/app/*` | Client Portal | Various | **Existing - DO NOT MODIFY** |
| `/admin/*` | Admin Portal | Various | **Existing - DO NOT MODIFY** |

### 4.2 Internal Linking Strategy

```
                              HOME (/)
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
    CVP Landing          Services Hub            Pricing
(/compliance-vault-pro)   (/services)           (/pricing)
          │                     │                     │
          │         ┌───────────┼───────────┐         │
          │         │           │           │         │
          │         ▼           ▼           ▼         │
          │    AI Workflow  Research   Doc Packs      │
          │         │           │           │         │
          │         │           │           │         │
          ▼         ▼           ▼           ▼         ▼
        ┌─────────────────────────────────────────────┐
        │              CONVERSION POINTS              │
        │                                             │
        │   /booking (Calendly)    /intake/start      │
        │         ▲                      ▲            │
        │         │                      │            │
        │   Every page has CTA to one of these       │
        └─────────────────────────────────────────────┘
                              ▲
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   /insights/*           /about            /contact
   (blog posts)                         (inquiry form)
        │
        └── Each post links to relevant service page
            and /compliance-vault-pro
```

### 4.3 Navigation Structure

**Primary Navigation (Desktop):**
```
┌────────────────────────────────────────────────────────────────────────────────┐
│  [LOGO]    Platform ▼    Services ▼    Pricing    Insights    About    [Login] │
│                                                                   [Book Now]   │
└────────────────────────────────────────────────────────────────────────────────┘

Platform Dropdown:
├── Compliance Vault Pro
├── How It Works
└── Pricing

Services Dropdown:
├── AI Workflow Automation
├── Market Research
├── Document Packs
├── Compliance Audits
│   ├── HMO Audit
│   └── Full Audit
└── Cleaning Services
```

**Footer Navigation:**
```
┌────────────────────────────────────────────────────────────────────────────────┐
│  PLATFORM          SERVICES           COMPANY          LEGAL                   │
│  ─────────         ────────           ───────          ─────                   │
│  Compliance        AI Workflows       About Us         Privacy Policy          │
│  Vault Pro         Market Research    Careers          Terms of Service        │
│  Pricing           Document Packs     Partnerships                             │
│  Book a Demo       Compliance Audits  Contact                                  │
│                    Cleaning                                                    │
│                                                                                │
│  ──────────────────────────────────────────────────────────────────────────── │
│  © 2026 Pleerity Enterprise Ltd. All rights reserved.                         │
│  Company No: XXXXXXXX | Registered in England and Wales                       │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Backend API Routes (New)

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| **Public APIs** |
| `GET` | `/api/public/services` | None | List all services with pricing |
| `GET` | `/api/public/services/:code` | None | Single service details |
| `POST` | `/api/public/contact` | None | Submit contact form |
| `POST` | `/api/public/service-inquiry` | None | Submit service inquiry |
| **Blog APIs** |
| `GET` | `/api/blog/posts` | None | List published posts (paginated) |
| `GET` | `/api/blog/posts/:slug` | None | Single post by slug |
| `GET` | `/api/blog/categories` | None | List categories with counts |
| `POST` | `/api/blog/posts` | Admin | Create post |
| `PUT` | `/api/blog/posts/:id` | Admin | Update post |
| `DELETE` | `/api/blog/posts/:id` | Admin | Archive post |
| **Order APIs** |
| `POST` | `/api/orders/create` | None | Create order (returns order_id) |
| `POST` | `/api/orders/:id/checkout` | None | Create Stripe checkout for order |
| `GET` | `/api/orders/:id/status` | Token | Check order status (customer view) |
| **Admin Order APIs** |
| `GET` | `/api/admin/orders` | Admin | List all orders (with filters) |
| `GET` | `/api/admin/orders/:id` | Admin | Full order details + timeline |
| `POST` | `/api/admin/orders/:id/transition` | Admin | Manual state transition |
| `POST` | `/api/admin/orders/:id/notes` | Admin | Add internal notes |
| **Admin CRM APIs** |
| `GET` | `/api/admin/contacts` | Admin | List contact submissions |
| `GET` | `/api/admin/inquiries` | Admin | List service inquiries |
| `POST` | `/api/admin/inquiries/:id/respond` | Admin | Mark as responded |
| `POST` | `/api/admin/inquiries/:id/convert` | Admin | Convert to order |

---

## 5. SEO Plan

### 5.1 Title & Meta Description Templates

| Page Type | Title Template | Meta Description Template |
|-----------|----------------|---------------------------|
| Home | `Pleerity Enterprise - AI-Powered Landlord Compliance & Workflow Automation` | `Streamline UK landlord compliance with Compliance Vault Pro. AI-powered document management, automated reminders, and professional audit services.` |
| CVP Landing | `Compliance Vault Pro - UK Landlord Compliance Management Platform` | `The all-in-one compliance platform for UK landlords. Track certificates, automate reminders, and stay compliant with Gas Safety, EICR, EPC regulations.` |
| Services Hub | `Property Compliance Services - Pleerity Enterprise` | `Professional compliance services for UK landlords: market research, document preparation, HMO audits, and cleaning services.` |
| Service Page | `{Service Name} - Pleerity Enterprise` | `{Service-specific description}` |
| Pricing | `Pricing - Compliance Vault Pro Plans | Pleerity Enterprise` | `Transparent pricing for Compliance Vault Pro. Choose from Solo (£19/mo), Portfolio (£39/mo), or Professional (£79/mo) plans.` |
| Booking | `Book a Consultation - Pleerity Enterprise` | `Schedule a free consultation with our compliance experts. Learn how Compliance Vault Pro can simplify your landlord compliance.` |
| Blog Hub | `Insights - UK Landlord Compliance News & Guides | Pleerity` | `Expert insights on UK landlord compliance, property regulations, and HMO requirements. Stay informed with Pleerity Enterprise.` |
| Blog Post | `{Post Title} | Pleerity Insights` | `{Post excerpt - first 155 chars}` |
| About | `About Pleerity Enterprise - AI-Driven Compliance Solutions` | `Learn about Pleerity Enterprise, a UK-based company providing AI-powered compliance and workflow automation for landlords and letting agents.` |
| Contact | `Contact Us - Pleerity Enterprise` | `Get in touch with Pleerity Enterprise. Questions about Compliance Vault Pro or our services? We're here to help.` |

### 5.2 Schema.org Implementation

```javascript
// Organization (site-wide, in layout)
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Pleerity Enterprise Ltd",
  "url": "https://pleerity.com",
  "logo": "https://pleerity.com/logo.png",
  "sameAs": [
    "https://linkedin.com/company/pleerity",
    "https://twitter.com/pleerity"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "+44-XXX-XXX-XXXX",
    "contactType": "customer service",
    "areaServed": "GB"
  }
}

// Product (on /compliance-vault-pro)
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Compliance Vault Pro",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "offers": {
    "@type": "AggregateOffer",
    "lowPrice": "19",
    "highPrice": "79",
    "priceCurrency": "GBP",
    "offerCount": 3
  }
}

// Service (on each service page)
{
  "@context": "https://schema.org",
  "@type": "Service",
  "name": "{Service Name}",
  "provider": {
    "@type": "Organization",
    "name": "Pleerity Enterprise Ltd"
  },
  "areaServed": {
    "@type": "Country",
    "name": "United Kingdom"
  }
}

// Article (on blog posts)
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{Post Title}",
  "datePublished": "{ISO Date}",
  "dateModified": "{ISO Date}",
  "author": {
    "@type": "Organization",
    "name": "Pleerity Enterprise"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Pleerity Enterprise Ltd",
    "logo": {
      "@type": "ImageObject",
      "url": "https://pleerity.com/logo.png"
    }
  }
}

// FAQPage (on relevant pages)
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What certificates do UK landlords need?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "UK landlords typically need: Gas Safety Certificate (annual), EICR (every 5 years), EPC (every 10 years), and potentially HMO licence depending on property type."
      }
    }
  ]
}
```

### 5.3 Technical SEO

**sitemap.xml Generation:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- Static Pages -->
  <url>
    <loc>https://pleerity.com/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://pleerity.com/compliance-vault-pro</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://pleerity.com/services</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <!-- Dynamic: Blog posts -->
  <url>
    <loc>https://pleerity.com/insights/{slug}</loc>
    <lastmod>{updated_at}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>
```

**robots.txt:**
```
User-agent: *
Allow: /
Disallow: /app/
Disallow: /admin/
Disallow: /api/
Disallow: /intake/
Disallow: /checkout/
Disallow: /set-password
Disallow: /onboarding-status

Sitemap: https://pleerity.com/sitemap.xml
```

**Canonical Rules:**
- Every page MUST have a `<link rel="canonical" href="..." />` tag
- Self-referencing canonical on all original content
- No trailing slashes (redirect `/services/` to `/services`)
- HTTPS only (redirect HTTP to HTTPS)
- www to non-www redirect (or vice versa - pick one)

**OpenGraph & Twitter Cards:**
```html
<!-- Every page -->
<meta property="og:site_name" content="Pleerity Enterprise" />
<meta property="og:type" content="website" />
<meta property="og:title" content="{Page Title}" />
<meta property="og:description" content="{Meta Description}" />
<meta property="og:image" content="{Featured Image or Default OG Image}" />
<meta property="og:url" content="{Canonical URL}" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{Page Title}" />
<meta name="twitter:description" content="{Meta Description}" />
<meta name="twitter:image" content="{Featured Image or Default OG Image}" />
```

---

## 6. Risk Register

### Top 10 Risks & Mitigations

| # | Risk | Probability | Impact | Mitigation | Owner |
|---|------|-------------|--------|------------|-------|
| **R1** | **CVP modification during website build** - Accidental changes to production compliance system | Medium | Critical | **HARD RULE: No modifications to existing /app/backend/routes/client.py, properties.py, documents.py, etc. All new code in separate files. PR review checklist.** | Agent |
| **R2** | **Order workflow state corruption** - Invalid state transitions or lost audit trail | Medium | High | Strict state machine with whitelist transitions. All transitions through single `transition_order_state()` function. DB transaction with audit write. | Agent |
| **R3** | **SEO implementation breaks React SPA** - Client-side rendering not indexed by Google | Medium | Medium | Use `react-helmet-async` for meta tags. Verify with Google Search Console. Future-proof for SSR/Next.js migration. | Agent |
| **R4** | **Stripe webhook duplicate processing** - Same payment processed twice | Low | High | Idempotency via `stripe_events` collection (existing pattern). Order-level idempotency key. | Agent |
| **R5** | **Blog content injection** - XSS via admin-created blog posts | Low | High | Sanitize markdown on server render. CSP headers. Admin-only write access with audit. | Agent |
| **R6** | **Contact form spam** - Bot submissions overwhelming system | High | Medium | Rate limiting (5/min/IP). Honeypot field. Optional reCAPTCHA. | Agent |
| **R7** | **SLA calculation errors** - Incorrect pause/resume tracking | Medium | Medium | All SLA changes logged with timestamps. Admin override available. Automated alerts for SLA breach. | Agent |
| **R8** | **Service inquiry to order conversion loss** - Customer data lost during conversion | Low | Medium | Atomic conversion with rollback. Pre-fill order from inquiry data. | Agent |
| **R9** | **Public API abuse** - DoS via public endpoints | Medium | Medium | Rate limiting on all public endpoints. Cloudflare protection (production). | Agent |
| **R10** | **Broken internal links** - Dead links after URL changes | Medium | Low | Centralized route constants. Automated link checker in CI. | Agent |

### Release Strategy (Risk Mitigation)

**Phase 1: Infrastructure (No User Impact)**
1. Create new collections (orders, workflow_executions, blog_posts, etc.)
2. Create new backend routes (public, orders, blog) - NO modifications to existing
3. Create new frontend components for public pages
4. Add new routes to App.js - NO modifications to existing routes

**Phase 2: Soft Launch (Internal)**
1. Deploy public website pages
2. Internal testing of all conversion flows
3. Verify CVP continues to work unchanged
4. Admin workflow monitor testing

**Phase 3: Production (Gradual)**
1. Enable public website
2. Monitor for errors
3. Gradual rollout of order system
4. Blog content population

**Rollback Plan:**
- Each phase is independently revertable
- Public website routes can be disabled without affecting CVP
- Order system has manual override at every step
- No data migration from CVP = no rollback risk to compliance data

---

## Approval Checklist

Before building, please confirm:

- [ ] Architecture diagram accurately represents the system boundaries
- [ ] Data models cover all required fields and relationships
- [ ] Workflow state machine matches operational requirements
- [ ] URL structure is correct and SEO-friendly
- [ ] SEO plan meets ranking goals
- [ ] Risk register addresses main concerns
- [ ] "Do not modify CVP" rule is clearly understood

**Approval Status:** ✅ APPROVED (January 2026)

---

## Amendments (Post-Approval)

### CVP Isolation — AMENDED
- **Hard rule**: No route, function, background job, or worker may write to any CVP collection under any circumstance.
- **Read-only linkage allowed**: Orders may store `cvp_user_ref` as a string identifier only (for display). This reference must never be required for order completion and must not trigger CVP writes.

### Workflow States — AMENDED
- **New state added**: `DELIVERY_FAILED` (System) — used only when delivery fails (email rejected/bounced/API error). Must preserve error payload + retry/manual fallback.
- **Admin notification**: When order reaches `INTERNAL_REVIEW`, system sends immediate email + SMS notification to admin.

### Admin Visibility — AMENDED
- **No implicit state changes** except: the three Internal Review buttons (Approve/Regen/Request Info) + Admin Manual Fallback actions. All other UI actions must not mutate workflow state.

### Stripe Idempotency — AMENDED
- **Signature verification required**: Stripe webhooks must include signature verification. Unverified events are rejected and logged.

### SEO — AMENDED
- **Phase 1**: Best-effort SPA SEO (react-helmet-async, schema.org, sitemap, fast load).
- **Phase 2** (if ranking priority): Migrate public pages to SSR (Next.js) or pre-rendering.

---

*Document generated by E1 Development Agent for Pleerity Enterprise Ltd*
