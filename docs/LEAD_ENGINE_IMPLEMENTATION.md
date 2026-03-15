# Lead Engine Implementation

This document describes the unified lead generation, capture, qualification, nurture, conversion, and management system for Pleerity.

---

## 1. Lead data model

**Collection:** `leads`

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| lead_id | string | Unique ID (LEAD-timestamp-hex) |
| first_name, last_name, full_name, name | string | Contact name (name derived from first/last/full if needed) |
| email, phone, company_name | string | Contact details |
| source_platform | enum | Where the lead came from (see Lead sources) |
| service_interest | enum | Primary interest (CVP, DOCUMENT_PACKS, AUTOMATION, MARKET_RESEARCH, etc.) |
| user_type | string | Optional (e.g. landlord, agent) |
| portfolio_size | int | Optional (e.g. property count) |
| risk_score, risk_level | number/string | From compliance risk check when synced |
| primary_interest, secondary_interest | string | Optional qualification |
| intent_score | enum | LOW, MEDIUM, HIGH (legacy) |
| lead_score | int | Numeric 0–100 (persisted; used for stage bands) |
| stage | enum | NEW, CONTACTED, QUALIFIED, NURTURING, SALES_READY, PROPOSAL_SENT, NEGOTIATING, WON, LOST, INACTIVE |
| status | enum | ACTIVE, CONVERTED, LOST, MERGED, UNSUBSCRIBED |
| tags | array | e.g. checklist_download, consultation_request, pricing_requested |
| marketing_consent | bool | Consent for nurture emails |
| followup_status, followup_sequence, followup_step | - | Follow-up automation state |
| created_at, updated_at, last_activity_at | ISO datetime | Timestamps |
| converted_at, client_id | - | Set when lead converts to client |

---

## 2. Lead sources (source_platform)

| Value | Description |
|-------|-------------|
| WEB_CHAT | Chatbot capture |
| CONTACT_FORM | Website contact form |
| COMPLIANCE_CHECKLIST | Lead magnet: UK Landlord Compliance Master Checklist |
| COMPLIANCE_RISK_CHECK | Full risk check report (synced from risk_leads) |
| DOCUMENT_SERVICES | Document pack / document service enquiry |
| PRICING_PAGE | Pricing or consultation request |
| AUTOMATION_ENQUIRY | AI automation / workflow enquiry |
| MARKET_RESEARCH_ENQUIRY | Market research enquiry |
| SUPPORT_FORM | Support-specific form |
| WHATSAPP | WhatsApp handoff |
| INTAKE_ABANDONED | Abandoned intake draft |
| ADMIN, IMPORT, REFERRAL, etc. | Other |

---

## 3. Scoring rules (lead_scoring.py)

**Numeric lead_score (0–100)** is computed from:

- **Intent score (base):** HIGH=40, MEDIUM=25, LOW=10
- **Compliance risk check completed:** +20
- **High risk level:** +15
- **Moderate risk level:** +10
- **Portfolio size ≥ 2:** +15
- **Document pack interest:** +10
- **Automation enquiry:** +20
- **Pricing requested (source or tag):** +15
- **Consultation request (tag):** +25
- **Nurture CTA clicked (tag):** +10
- **Nurture email opened (tag):** +5

**Stage bands (suggested stage from score):**

- 0–19 → NEW
- 20–39 → QUALIFIED
- 40–59 → NURTURING
- 60+ → SALES_READY

Stage is updated automatically from score only when current stage is NEW (existing stages are not overwritten). `recalculate_lead_score(lead)` returns `{ lead_score, suggested_stage }`; the service persists `lead_score` and optionally updates stage.

---

## 4. Central ingestion (LeadService)

- **create_lead(request, …, upsert_by_email=False)**  
  Creates a new lead or, if `upsert_by_email=True` and a duplicate is found by email, updates the existing lead (tags, last_activity_at, source_metadata, risk/portfolio/interest fields, optional name/phone/company/service_interest).  
  After create or upsert, **lead_score** is recalculated and persisted; stage may be advanced from NEW using score bands.

- **Duplicate key:** Email (primary); phone and social platform IDs (e.g. Facebook/Instagram/LinkedIn) are also used when provided.

- **Merge:** Manual merge via `merge_leads(primary_lead_id, secondary_lead_id)`; secondary is marked MERGED and linked to primary.

---

## 5. Capture points

All capture endpoints use **LeadService.create_lead** with **upsert_by_email=True** where appropriate.

| Entry point | Endpoint | source_platform |
|-------------|----------|-----------------|
| Website contact form | POST /api/leads/capture/contact-form | CONTACT_FORM |
| Chatbot | POST /api/leads/capture/chatbot | WEB_CHAT |
| Compliance checklist (lead magnet) | POST /api/leads/capture/compliance-checklist | COMPLIANCE_CHECKLIST |
| Document service | POST /api/leads/capture/document-service | DOCUMENT_SERVICES |
| Pricing / consultation | POST /api/leads/capture/pricing | PRICING_PAGE |
| Automation enquiry | POST /api/leads/capture/automation-enquiry | AUTOMATION_ENQUIRY |
| Market research enquiry | POST /api/leads/capture/market-research-enquiry | MARKET_RESEARCH_ENQUIRY |
| Support form | POST /api/leads/capture/support-form | SUPPORT_FORM |
| WhatsApp handoff | POST /api/leads/capture/whatsapp | WHATSAPP |
| Compliance risk check | POST /api/risk-check/report (then sync to leads) | COMPLIANCE_RISK_CHECK |

Compliance risk check: after upserting **risk_leads**, the backend creates or updates a lead in **leads** with source_platform=COMPLIANCE_RISK_CHECK, risk_score/risk_level, portfolio_size, and source_metadata (risk_lead_id, risk_band). risk_leads is unchanged and continues to drive risk-check email sequence and activation.

---

## 6. Nurture trigger rules

- **followup_sequence** is set at create from source and service_interest:
  - INTAKE_ABANDONED → `abandoned_intake`
  - DOCUMENT_PACKS → `document_pack`
  - AUTOMATION → `automation`
  - MARKET_RESEARCH → `market_research`
  - CVP or COMPLIANCE_RISK_CHECK → `compliance`
  - Else → `default`

- **Checklist leads (COMPLIANCE_CHECKLIST):** Handled by **lead_nurture_service** (5-email checklist sequence). Other sequences use **lead_followup_service** (default or abandoned_intake steps). Type-specific content for document_pack, automation, market_research can be added later; they currently use the default sequence steps.

- Nurture is only sent when **marketing_consent** is true and lead is not CONVERTED/LOST/MERGED/UNSUBSCRIBED.

---

## 7. Conversion rules

- **Manual:** Admin calls POST /api/admin/leads/{lead_id}/convert with client_id. **LeadService.convert_lead** sets status=CONVERTED, stage=WON, client_id, converted_at, stops follow-up, and links client to lead.

- **Risk-check flow:** On Stripe checkout.session.completed, when a **risk_lead** is marked converted (by lead_id in metadata or by customer email), the backend finds the corresponding central **lead** (by source_metadata.risk_lead_id or email + source_platform=COMPLIANCE_RISK_CHECK) and calls **LeadService.convert_lead** for that lead with the new client_id. Nurture/follow-up for that lead is stopped.

- **Converted leads:** converted_at and converted_to_client_id (client_id) are set; follow-up status is STOPPED.

---

## 8. Duplicate handling

- **On capture:** If the same email submits again and **upsert_by_email=True**, the existing lead is updated (tags merged, last_activity_at set, optional fields updated), lead_score is recalculated, and the same lead is returned with `is_duplicate: true`.

- **Merge key:** Email is the primary key for “update existing”; phone and social IDs are used for duplicate detection.

- **Manual merge:** merge_leads(primary, secondary) marks secondary as MERGED and appends its data to primary; activity history is preserved via audit log.

---

## 9. Admin / CRM management

- **List leads:** GET /api/admin/leads with filters: source_platform, service_interest, stage, intent_score, status, assigned_to, search, sla_breach_only, date_from, date_to, **last_activity_from**, **last_activity_to**, **lead_score_min**, **lead_score_max**, page, limit.

- **Detail:** GET /api/admin/leads/{lead_id} (lead, audit log, contacts, transcript).

- **Update:** PUT /api/admin/leads/{lead_id} (including stage, notes, lead_score).

- **Assign:** POST /api/admin/leads/{lead_id}/assign.

- **Log contact:** POST /api/admin/leads/{lead_id}/contact.

- **Convert:** POST /api/admin/leads/{lead_id}/convert (client_id, conversion_notes).

- **Mark lost:** POST /api/admin/leads/{lead_id}/mark-lost.

- **Merge:** POST /api/admin/leads/{lead_id}/merge/{secondary_lead_id}.

- **Export:** GET /api/admin/leads/export (CSV).

- **Notifications:** GET /api/admin/leads/notifications returns high_intent_alerts, **sales_ready_alerts** (lead_score ≥ 60 or consultation/pricing tags), sla_breach_alerts, recent_leads.

List response uses **persisted lead_score** when present; otherwise a display score is derived from intent_score. Score band (High/Medium/Low) uses 60+ = High, 20+ = Medium.

---

## 10. Activity / audit log

- **Collection:** lead_audit_logs (event, lead_id, actor_id, actor_type, details, ip_address, created_at).

- **Events** include: LEAD_CREATED, LEAD_UPDATED, LEAD_ASSIGNED, LEAD_CONTACTED, LEAD_STAGE_CHANGED, LEAD_CONVERTED, LEAD_MARKED_LOST, LEAD_MERGED, FOLLOWUP_EMAIL_SENT, FOLLOWUP_EMAIL_FAILED, FOLLOWUP_STOPPED, MARKETING_CONSENT_UPDATED, SLA_BREACH, RISK_CHECK_COMPLETED, CHATBOT_CAPTURE, PRICING_REQUESTED, NURTURE_STARTED, CTA_CLICKED.

- **last_activity_at** is set on create and on update/contact so leads can be filtered by recent activity.

---

## 11. Consent and preferences

- **marketing_consent** is stored on the lead; nurture/follow-up only runs when consent is true.

- **followup_status** OPTED_OUT is set when consent is withdrawn; POST /api/leads/unsubscribe/{lead_id} sets marketing_consent=false and followup_status=OPTED_OUT.

- System-critical (e.g. transactional) emails are not gated by marketing consent.

---

## 12. Files reference

| Area | File(s) |
|------|--------|
| Models, enums | backend/services/lead_models.py |
| Central service | backend/services/lead_service.py |
| Scoring | backend/services/lead_scoring.py |
| Nurture (checklist) | backend/services/lead_nurture_service.py |
| Follow-up | backend/services/lead_followup_service.py |
| Capture & admin routes | backend/routes/leads.py |
| Risk check sync | backend/routes/risk_check.py |
| Risk lead conversion → lead | backend/services/stripe_webhook_service.py |
| Indexes | backend/database.py (leads, lead_audit_logs) |

---

## 13. Remaining gaps / runtime testing

- **Frontend:** Wire new capture endpoints (pricing, automation-enquiry, market-research-enquiry, support-form) from the relevant pages/forms if not already present.

- **Nurture content by type:** Document pack, automation, and market research sequences currently use the default follow-up steps; copy and variants can be added in lead_followup_service and referenced by followup_sequence.

- **CTA/open tracking:** Implemented.
  - **POST /api/leads/activity** – body: `lead_id`, `activity_type` (`nurture_cta_clicked`, `nurture_email_opened`, `pricing_requested`, `consultation_request`).
  - **GET /track/lead-activity** (frontend) – query: `lead_id`, `activity_type`, optional `redirect_url`; records activity then redirects.
  - **GET /api/leads/track-open?lead_id=xxx** – for email open tracking: records `nurture_email_opened` and returns a 1×1 transparent GIF. Use as `<img src="https://your-api/api/leads/track-open?lead_id=LEAD-xxx" />` in nurture emails. Default follow-up and checklist nurture emails include this pixel automatically (set **BACKEND_URL** or **API_URL** so the pixel URL is correct).

- **Admin UI:** Admin leads page includes filters for last_activity_at (date range) and lead_score (min–max), and an alerts section for high intent, sales ready, and SLA breach leads (from GET /admin/leads/notifications).

- **Tests:** Add or extend tests for create_lead with upsert_by_email, risk_check sync, scoring, and Stripe conversion sync.
