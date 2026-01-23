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

### Phase 3: 24/7 Support System (Complete - Jan 2026)
- [x] AI chatbot with Gemini integration
- [x] Tawk.to live chat widget
- [x] Email ticket creation via Postmark
- [x] WhatsApp handoff functionality
- [x] Knowledge Base (public & admin)
- [x] Admin canned responses management

### Phase 4: Lead Management System (Complete - Jan 23, 2026)
- [x] Lead entity model (separate from Client)
- [x] Lead capture endpoints (chatbot, contact form, document services, WhatsApp, intake abandoned)
- [x] Lead listing API with filters and pagination
- [x] Admin Lead Dashboard UI at `/admin/leads`
- [x] Lead stats and conversion tracking
- [x] Manual lead creation and actions (assign, contact, convert, mark lost)
- [x] Follow-up email templates
- [x] SLA tracking for leads (24-hour default)
- [x] **HIGH Intent Lead Notifications** - Admins receive email alerts
- [x] **SLA Breach Notifications** - Email alerts for overdue leads
- [x] Abandoned intake detection (scheduled job)
- [x] Follow-up queue processing
- [x] Lead notifications API

### Phase 5: Admin Intake Schema Manager (Complete - Jan 23, 2026)
- [x] Schema versioning with version history
- [x] Draft/Publish workflow
- [x] Rollback to previous versions
- [x] Discard draft functionality
- [x] Reset to defaults
- [x] Full audit logging

### Phase 6: Unified Admin Console (Complete - Jan 23, 2026)
- [x] **Consolidated navigation** - All 12+ admin pages accessible from single sidebar
- [x] **Grouped navigation sections**:
  - Dashboard (Overview, Analytics)
  - Customers (Lead Management, Clients, Orders Pipeline)
  - Products & Services (Service Catalogue, Intake Schema, Pricing)
  - Content Management (Knowledge Base, Blog, Canned Responses)
  - Support (Support Dashboard, Postal Tracking)
  - Settings & System (Team, Rules, Templates, Audit Logs)
- [x] **Real-time badge notifications** for leads and postal orders
- [x] **Quick search** in header
- [x] **AI Assistant** quick access button
- [x] **Mobile responsive** design
- [x] **Collapsible sidebar**

### Phase 7: Postal Tracking UI (Complete - Jan 23, 2026)
- [x] Dedicated `/admin/postal-tracking` page
- [x] Stats cards (Pending Print, Printed, In Transit, Delivered)
- [x] Order list with search and filter
- [x] Update status modal with carrier and tracking number
- [x] Set delivery address modal
- [x] Empty state handling

---

## Admin Pages & Navigation

| Page | Path | Section |
|------|------|---------|
| Dashboard Overview | `/admin/dashboard` | Dashboard |
| Analytics | `/admin/analytics` | Dashboard |
| Lead Management | `/admin/leads` | Customers |
| Clients | `/admin/dashboard?tab=clients` | Customers |
| Orders Pipeline | `/admin/orders` | Customers |
| Service Catalogue | `/admin/services` | Products |
| Intake Schema | `/admin/intake-schema` | Products |
| Billing | `/admin/billing` | Products |
| Knowledge Base | `/admin/knowledge-base` | Content |
| Blog | `/admin/blog` | Content |
| Canned Responses | `/admin/support/responses` | Content |
| Support Dashboard | `/admin/support` | Support |
| Postal Tracking | `/admin/postal-tracking` | Support |
| Team Management | `/admin/dashboard?tab=admins` | Settings |
| Automation Rules | `/admin/dashboard?tab=rules` | Settings |
| Email Templates | `/admin/dashboard?tab=templates` | Settings |
| Audit Logs | `/admin/dashboard?tab=audit` | Settings |
| AI Assistant | `/admin/assistant` | Quick Access |

---

## Key Components

### UnifiedAdminLayout
- Location: `/app/frontend/src/components/admin/UnifiedAdminLayout.js`
- Features: Collapsible sidebar, grouped navigation, badge notifications, mobile responsive

### AdminPostalTrackingPage
- Location: `/app/frontend/src/pages/AdminPostalTrackingPage.js`
- Features: Stats cards, order list, status updates, address management

---

## Upcoming Features

### P1: Enhanced Email Delivery
- Configure real Postmark credentials for production
- Test HIGH intent and SLA breach email notifications

### P2: Address Autocomplete
- getaddress.io integration
- Postcode lookup in intake wizard

### P3: Technical Debt
- Move lead_models.py from services/ to models/
- Deprecate legacy V1 service files

---

## Technical Architecture

### Backend
- FastAPI with async/await
- MongoDB for data storage
- APScheduler for background jobs
- Postmark for transactional emails
- Stripe for payments
- Gemini for AI features

### Frontend
- React with React Router
- Shadcn/UI components
- Tailwind CSS
- Axios for API calls

### Key Collections
- `clients` - Paying customers
- `leads` - Pre-sale prospects
- `lead_audit_logs` - Lead activity tracking
- `orders` - Service orders
- `service_catalogue_v2` - Service definitions
- `intake_schema_customizations` - Schema overrides
- `intake_schema_versions` - Version history
- `kb_articles`, `kb_categories` - Knowledge base
- `canned_responses` - Support response templates

---

## Credentials
- Admin: admin@pleerity.com / Admin123!
- Client: test@pleerity.com / TestClient123!

## Environment
- Backend: FastAPI on port 8001
- Frontend: React on port 3000
- Database: MongoDB (compliance_vault_pro)

## Mocked/Test Configurations
- **Postmark**: Token `leadsquared` is a placeholder
- **Stripe**: Uses test keys
- **WhatsApp**: Uses test number for handoff

---

*Last updated: January 23, 2026*
