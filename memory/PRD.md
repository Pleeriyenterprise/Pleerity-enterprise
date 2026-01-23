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
- [x] Lead capture endpoints:
  - Chatbot (`POST /api/leads/capture/chatbot`)
  - Contact form (`POST /api/leads/capture/contact-form`)
  - Document services (`POST /api/leads/capture/document-services`)
  - WhatsApp (`POST /api/leads/capture/whatsapp`)
  - Intake abandoned (`POST /api/leads/capture/intake-abandoned`)
- [x] Lead listing API with filters and pagination
- [x] Admin Lead Dashboard UI at `/admin/leads`
- [x] Lead stats and conversion tracking
- [x] Manual lead creation and actions (assign, contact, convert, mark lost)
- [x] Follow-up email templates
- [x] SLA tracking for leads (24-hour default)
- [x] **HIGH Intent Lead Notifications** - Admins receive email alerts for high-value leads
- [x] **SLA Breach Notifications** - Email alerts when leads aren't contacted in time
- [x] Abandoned intake detection (scheduled job)
- [x] Follow-up queue processing
- [x] Lead notifications API (`GET /api/admin/leads/notifications`)
- [x] Test endpoints for all automation features

### Phase 5: Admin Intake Schema Manager (Complete - Jan 23, 2026)
- [x] Schema versioning with version history
- [x] Draft/Publish workflow
- [x] Rollback to previous versions
- [x] Discard draft functionality
- [x] Reset to defaults
- [x] Full audit logging for all schema changes
- [x] Preview merged schema

---

## API Endpoints Summary

### Lead Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/leads/capture/{source}` | POST | Create lead from various sources |
| `/api/admin/leads` | GET | List leads with filters, pagination, stats |
| `/api/admin/leads/{lead_id}` | GET | Get single lead details |
| `/api/admin/leads/{lead_id}` | PUT | Update lead |
| `/api/admin/leads/{lead_id}/assign` | POST | Assign lead to team member |
| `/api/admin/leads/{lead_id}/contact` | POST | Log contact attempt |
| `/api/admin/leads/{lead_id}/convert` | POST | Convert lead to client |
| `/api/admin/leads/{lead_id}/mark-lost` | POST | Mark lead as lost |
| `/api/admin/leads/notifications` | GET | Get HIGH intent alerts & SLA breaches |
| `/api/admin/leads/test/abandoned-intake` | POST | Test abandoned intake detection |
| `/api/admin/leads/test/followup-queue` | POST | Test follow-up processing |
| `/api/admin/leads/test/sla-check` | POST | Test SLA breach detection |

### Intake Schema Manager
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/intake-schema/services` | GET | List configurable services |
| `/api/admin/intake-schema/{service_code}` | GET | Get schema for editing |
| `/api/admin/intake-schema/{service_code}` | PUT | Save schema overrides |
| `/api/admin/intake-schema/{service_code}/publish` | POST | Publish draft to live |
| `/api/admin/intake-schema/{service_code}/discard-draft` | POST | Discard draft changes |
| `/api/admin/intake-schema/{service_code}/versions` | GET | Get version history |
| `/api/admin/intake-schema/{service_code}/rollback/{version}` | POST | Rollback to version |
| `/api/admin/intake-schema/{service_code}/reset` | POST | Reset to defaults |

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
- Code cleanup and documentation

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
- **Postmark**: Token `leadsquared` is a placeholder - notifications log warnings but don't send
- **Stripe**: Uses test keys
- **WhatsApp**: Uses test number for handoff

---

*Last updated: January 23, 2026*
