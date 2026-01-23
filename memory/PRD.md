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

### Phase 4: Lead Management System (In Progress - Jan 2026)
- [x] Lead entity model (separate from Client)
- [x] Lead capture endpoints (chatbot, contact form, document services, WhatsApp)
- [x] Lead listing API with filters and pagination
- [x] Admin Lead Dashboard UI
- [x] Lead stats and conversion tracking
- [x] Manual lead creation and actions (assign, contact, convert, mark lost)
- [x] Follow-up email templates
- [x] SLA tracking for leads
- [ ] Abandoned intake detection (scheduled job registered, needs testing)
- [ ] Follow-up email automation (Postmark integration)
- [ ] AI lead summary generation

---

## Upcoming Features

### P0: Lead Management Completion
- Test abandoned intake detection scheduled job
- Verify follow-up email sequences with Postmark
- Test SLA breach detection and flagging
- Add HIGH intent lead notifications

### P1: Admin Intake Schema Manager
- Schema versioning with schema_version field
- Draft/publish workflow
- Rollback functionality
- Audit logging for schema changes

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

---

*Last updated: January 23, 2026*
