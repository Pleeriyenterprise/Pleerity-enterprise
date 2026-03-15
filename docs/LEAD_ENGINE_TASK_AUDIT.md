# Lead Engine Task vs Codebase Audit

**Purpose:** Check the codebase against the task requirements for a unified lead generation, capture, qualification, nurture, conversion, and management system. Identify what is implemented, what is missing, and any conflicts. Propose the safest implementation path. **Do not implement blindly.**

---

## 1. Executive Summary

| Area | Current state | Task alignment |
|------|----------------|----------------|
| **Lead data model** | `leads` collection with lead_id, source_platform, service_interest, intent_score, stage, status, followup, conversion fields | **Partial** – Different field names (source_platform vs lead_source, stage set differs). Missing: full_name split, user_type, portfolio_size, risk_score/risk_level, primary_interest/secondary_interest, lead_score (numeric 0–100), last_activity_at on lead doc. |
| **Central ingestion** | `LeadService.create_lead()` in `lead_service.py`; dedup by email/phone; audit log | **Done** – Single service; duplicate returns existing; no update-by-email merge on submit. |
| **Capture points** | Chatbot, contact form, compliance checklist, document service, WhatsApp; contact form also via `/api/public/contact` | **Partial** – Missing: **compliance risk check** (uses `risk_leads` only), dedicated **pricing/consultation** capture, **automation enquiry** capture, **market research enquiry** capture, **support form** as distinct capture. |
| **Compliance risk check** | `risk_check.py` writes to **`risk_leads`** only; no write to `leads` | **Gap** – Task requires create/update lead in central system with risk_score, risk_level, lead_source=compliance_risk_check. |
| **Chatbot lead capture** | `POST /api/leads/capture/chatbot`; name, email, topic, message; source WEB_CHAT | **Done** – Intent/service_interest mapped; acknowledgement and follow-up start. |
| **Lead scoring** | `intent_score` (LOW/MEDIUM/HIGH) from `calculate_intent_score()`; no numeric 0–100 or `recalculate_lead_score()` | **Partial** – Task wants numeric lead_score, thresholds (0–19 new, 20–39 qualified, etc.), and a dedicated `lead_scoring.py` with `recalculate_lead_score(lead)`. |
| **Qualification** | user_type, portfolio_size only in context/intake; not stored on lead doc. primary_interest/secondary_interest not on lead | **Partial** – Stored only indirectly (service_interest, message_summary). |
| **Nurture flows** | `lead_nurture_service.py` – **checklist only** (COMPLIANCE_CHECKLIST, 5 emails). `lead_followup_service` – default 3-step follow-up | **Partial** – Task wants nurture **by lead_type** (compliance, document pack, automation, market research) with different sequences. |
| **Conversion** | `LeadService.convert_lead()`; status=CONVERTED, stage=WON, client_id, converted_at; Stripe webhook marks `risk_leads` converted | **Done** for `leads`. **Split** for risk: `risk_leads` converted in webhook; no sync to `leads`. |
| **Hot lead signals** | HIGH intent → `notify_high_intent_lead()`; GET `/admin/leads/notifications` (high intent, SLA breach, recent) | **Done** – Task “internal hot lead signals” largely covered. |
| **Activity log** | `lead_audit_logs` with event (LEAD_CREATED, LEAD_UPDATED, …), lead_id, actor, details, created_at | **Partial** – Task suggests `lead_activity_log` with activity_type, source, metadata. Current schema is audit-oriented; can map. |
| **Admin/CRM** | GET/PATCH `/admin/leads`, list with filters (source_platform, service_interest, stage, intent_score, status, search, dates, sla_breach), get detail, update, assign, contact, convert, mark-lost, audit log, export | **Done** – Task filters supported. last_activity_at filter not present. |
| **Duplicate/merge** | Dedup on create (email/phone); `merge_leads(primary, secondary)` | **Partial** – Task wants “update existing lead” on same email (append tags/interests, last_activity_at). Current behaviour: return existing as duplicate, no update. |
| **Consent** | marketing_consent on lead; followup_status OPTED_OUT when no consent; unsubscribe endpoint | **Done** – Nurture respects consent. |

---

## 2. Conflicting or Divergent Conventions

### 2.1 Naming: lead_source vs source_platform

- **Task:** `lead_source` with values like `website_form`, `compliance_risk_check`, `chatbot`, `pricing_page`, `document_pack_form`, `automation_enquiry`, `market_research_enquiry`, `support_form`.
- **Codebase:** `source_platform` with enum `LeadSourcePlatform`: WEB_CHAT, WHATSAPP, INTAKE_ABANDONED, DOCUMENT_SERVICES, ADMIN, CONTACT_FORM, COMPLIANCE_CHECKLIST, FACEBOOK, INSTAGRAM, LINKEDIN, EMAIL, IMPORT, REFERRAL.

**Recommendation:** Keep `source_platform` as the field name (avoids a breaking rename). Add new enum values or a mapping layer for task sources: e.g. `COMPLIANCE_RISK_CHECK` (new), `PRICING_PAGE`, `AUTOMATION_ENQUIRY`, `MARKET_RESEARCH_ENQUIRY`, `SUPPORT_FORM`. Map “website_form” → CONTACT_FORM, “chatbot” → WEB_CHAT, “document_pack_form” → DOCUMENT_SERVICES.

### 2.2 Stage values

- **Task:** new, qualified, nurturing, sales_ready, converted, inactive, lost.
- **Codebase:** `LeadStage`: NEW, CONTACTED, QUALIFIED, PROPOSAL_SENT, NEGOTIATING, WON, LOST.

**Recommendation:** Do **not** replace the existing stage set in one go. Either: (a) add a **stage mapping** (e.g. task “nurturing” → CONTACTED or a new NURTURING; “sales_ready” → QUALIFIED or new SALES_READY) and use it only where the task is implemented, or (b) extend the enum with NURTURING, SALES_READY, INACTIVE and document the mapping. Prefer extending the enum and mapping task thresholds to existing or new stages so existing admin and reports keep working.

### 2.3 Lead type vs service_interest

- **Task:** `lead_type`: compliance_monitoring, document_pack, automation_services, market_research, support_or_general, unknown.
- **Codebase:** `service_interest` (`LeadServiceInterest`): CVP, DOCUMENT_PACKS, AUTOMATION, MARKET_RESEARCH, COMPLIANCE_AUDITS, MULTIPLE, UNKNOWN.

**Recommendation:** Treat `service_interest` as the canonical field. Map task “compliance_monitoring” → CVP or COMPLIANCE_AUDITS; “document_pack” → DOCUMENT_PACKS; “support_or_general” → UNKNOWN or a new value. No need for a separate `lead_type` if service_interest is used consistently.

### 2.4 Two lead stores: `leads` vs `risk_leads`

- **Codebase:** Compliance risk check writes only to **`risk_leads`** (lead_id format RISK-xxx). Analytics and funnel use `risk_leads`. Unified lead list and lead service use **`leads`**.
- **Task:** “When a user completes the compliance risk check: create or update a **lead**” in the central system.

**Recommendation (safest):** Keep `risk_leads` for risk-check-specific data (computed_score, risk_band, flags, email sequence, activation token). **Additionally** create or update a record in **`leads`** when the risk check report is submitted: call `LeadService.create_lead()` (or an upsert-by-email helper) with source_platform=COMPLIANCE_RISK_CHECK, and store risk_score/risk_level in the lead (e.g. in source_metadata or new fields). That way: (1) risk_check flow and analytics remain unchanged, (2) central lead list and nurture get risk-check leads, (3) no need to migrate or merge the two collections.

---

## 3. Requirement-by-Requirement

### §1 Create lead data model

| Task field | In codebase? | Notes |
|------------|--------------|--------|
| lead_id | Yes | LEAD-timestamp-hex |
| first_name, last_name, full_name | Partial | `name` only; no split |
| email, phone, company_name | Yes | |
| lead_source | Partial | As source_platform (see §2.1) |
| lead_type | Partial | As service_interest (see §2.3) |
| user_type | No | Not on lead doc |
| portfolio_size | No | Not on lead doc |
| risk_score, risk_level | No | Only in risk_leads |
| primary_interest, secondary_interest | No | Only service_interest |
| consent_status | Partial | marketing_consent, followup_status |
| stage | Yes | LeadStage (different set, see §2.2) |
| lead_score | Partial | Intent only; list enriches with 0–100 for display |
| tags | Yes | |
| notes | Partial | admin_notes |
| created_at, updated_at | Yes | |
| last_activity_at | No | Not set on leads collection in create/update |
| converted_at, converted_to_client_id | Yes | converted_at, client_id |
| Suggested lead_source/lead_type/stage values | Different | See §2.1–2.3 |

**Gaps:** first_name/last_name or full_name split; user_type; portfolio_size; risk_score/risk_level on lead; primary_interest/secondary_interest; numeric lead_score persisted; last_activity_at.

---

### §2 Centralize lead ingestion

- **Implemented:** `LeadService.create_lead()` in `lead_service.py`; used by all capture endpoints. Dedup by email/phone returns existing lead (no update).
- **Gap:** “Update existing leads by email if already present” – current behaviour is create-or-return-existing without updating (e.g. tags, last_activity_at). Task also asks for “merge duplicate submissions where appropriate” – merge_leads exists; update-on-submit by email does not.

---

### §3 Capture from multiple entry points

| Entry point | Implemented? | How |
|-------------|--------------|-----|
| Website enquiry/contact forms | Yes | POST /api/public/contact → LeadService; POST /api/leads/capture/contact-form |
| Compliance risk checker | No (central leads) | risk_check.py → risk_leads only |
| Chatbot | Yes | POST /api/leads/capture/chatbot |
| Pricing/consultation forms | No | No dedicated capture; Calendly link on BookingPage |
| Document pack enquiry | Yes | POST /api/leads/capture/document-service |
| AI automation enquiry | No | No dedicated endpoint or form posting to lead capture |
| Market research enquiry | No | No dedicated capture to leads |
| Support form | Partial | Contact form can act as support; no “support_form” source |

---

### §4 Compliance risk check integration

- **Current:** POST /api/risk-check/report upserts `risk_leads`; sends email with activation link; no call to LeadService.
- **Missing:** Create/update in `leads` with lead_source=compliance_risk_check, risk_score/risk_level, and trigger nurture by type.

---

### §5 Chatbot lead capture

- **Implemented:** Chatbot capture with name, email, topic (service_interest), message; stored via LeadService; source WEB_CHAT.

---

### §6 Lead scoring engine

- **Current:** `calculate_intent_score()` in lead_service.py returns LOW/MEDIUM/HIGH from source, service_interest, phone, message, property_count, reached_payment. Admin list derives a display score (e.g. 25/50/75).
- **Missing:** Dedicated `lead_scoring.py`; numeric `lead_score` 0–100 stored on lead; `recalculate_lead_score(lead)`; stage advancement by score thresholds (0–19 new, 20–39 qualified, etc.).

---

### §7 Lead qualification logic

- **Current:** service_interest and intent_score; no user_type, portfolio_size, primary_interest, secondary_interest on lead doc.
- **Missing:** Storing user_type, portfolio_size, primary_interest, secondary_interest, and tags from capture/context where available.

---

### §8 Nurture flow triggers

- **Current:** Checklist nurture (lead_nurture_service) for COMPLIANCE_CHECKLIST only; default follow-up (lead_followup_service) for other leads.
- **Missing:** Nurture sequences **by lead_type** (compliance vs document pack vs automation vs market research) with different content and CTAs. “Do not send the same nurture flow to all leads” – current default is one size fits all except checklist.

---

### §9 Conversion logic

- **Implemented:** LeadService.convert_lead(); stage=WON, status=CONVERTED, converted_at, client_id; followup stopped. Stripe webhook marks risk_leads as converted.
- **Gap:** Conversion from risk_check (e.g. activation/subscription) does not update `leads`; only `risk_leads`. If we add risk-check → leads sync (§4), we should also call convert_lead when risk lead converts (or link by email).

---

### §10 Internal hot lead signals

- **Implemented:** notify_high_intent_lead(); GET /admin/leads/notifications (high intent, SLA breach, recent). Admin UI can show these.

---

### §11 Lead activity logging

- **Current:** `lead_audit_logs` with event, lead_id, actor, details, created_at (and ip_address).
- **Task:** Suggests `lead_activity_log` with activity_type, source, metadata, created_at. Existing audit log can serve; optionally add an alias or a thin layer that writes both “audit” and “activity” events, or map event types to activity_type.

---

### §12 Admin / CRM management

- **Implemented:** List, get, update, assign, contact, convert, mark-lost, export, stats, sources, notifications. Filters: source_platform, service_interest, stage, intent_score, status, assigned_to, search, sla_breach_only, date_from, date_to.
- **Missing:** Filter by last_activity_at (and ensure last_activity_at is set on leads where appropriate).

---

### §13 Duplicate / merge logic

- **Current:** Dedup on create (return existing); merge_leads(primary, secondary) for manual merge.
- **Task:** “If same email submits multiple forms: update existing lead, append tags/interests, update last_activity_at, optionally increase lead_score.”
- **Gap:** No “update existing” path on capture; only “return existing as duplicate.” Adding an optional upsert-by-email (update tags, last_activity_at, maybe lead_score) would align with the task.

---

### §14 Consent and preference

- **Implemented:** marketing_consent on lead; followup_status; unsubscribe endpoint; nurture checks consent.

---

## 4. Files That Exist vs Task Suggestions

| Task suggestion | Codebase | Note |
|-----------------|----------|------|
| backend/services/lead_service.py | Exists | Extend for risk sync, update-by-email, last_activity_at, lead_score. |
| backend/services/lead_scoring.py | Missing | Add for numeric score and recalculate_lead_score(). |
| backend/services/lead_nurture.py | lead_nurture_service.py (checklist only) | Extend or add nurture by lead_type. |
| backend/services/lead_conversion.py | Logic in lead_service.convert_lead | Optional extract; not required. |
| backend/routes/leads.py | Exists (public + admin) | Extend capture endpoints for new sources. |
| backend/models for lead schema | lead_models.py | Extend enums and request/response models. |
| lead_activity_log | lead_audit_logs | Use existing; optionally add activity_type alias. |
| Admin leads page | AdminLeadsPage.js | Exists; add filters (e.g. last_activity_at) if needed. |

---

## 5. Recommended Implementation Order (Safest)

1. **Model and enums (non-breaking)**  
   Add optional fields to lead doc: first_name, last_name (or keep name and derive), user_type, portfolio_size, risk_score, risk_level, primary_interest, secondary_interest, lead_score (numeric), last_activity_at. Add new source_platform values (e.g. COMPLIANCE_RISK_CHECK, PRICING_PAGE, AUTOMATION_ENQUIRY, MARKET_RESEARCH_ENQUIRY, SUPPORT_FORM). Add stage values if desired (NURTURING, SALES_READY, INACTIVE). Do not remove existing fields.

2. **Central ingestion behaviour**  
   Add optional “upsert by email” in LeadService: when create_lead finds an existing lead by email, optionally update (tags, last_activity_at, source_metadata, maybe lead_score) instead of only returning existing. Make this configurable (e.g. per source or a flag) to avoid overwriting important data.

3. **Compliance risk check → leads**  
   In risk_check.py after upserting risk_leads, call LeadService (create_lead or upsert) with source_platform=COMPLIANCE_RISK_CHECK, risk_score/risk_level in metadata or new fields, and trigger nurture by type. Keep risk_leads as-is for risk-specific flow and analytics.

4. **Lead scoring module**  
   Add lead_scoring.py with recalculate_lead_score(lead) (numeric 0–100) and optional stage advancement by thresholds. Call it from create_lead and from relevant capture paths. Persist lead_score on lead.

5. **Capture points**  
   Add or wire: pricing/consultation form → leads (e.g. PRICING_PAGE); automation enquiry form → AUTOMATION_ENQUIRY; market research enquiry → MARKET_RESEARCH_ENQUIRY; support form → SUPPORT_FORM if distinct from contact.

6. **Nurture by lead_type**  
   Define sequences per service_interest (or lead_type mapping); plug into existing lead_nurture_service / lead_followup_service so that the sequence chosen depends on lead_type/service_interest. Do not remove checklist nurture.

7. **Conversion from risk**  
   When a risk_lead is marked converted (e.g. Stripe webhook), find or create corresponding lead by email and call LeadService.convert_lead if appropriate, or link client_id to lead.

8. **Activity log**  
   Keep using lead_audit_logs; add activity_type in details or add a small set of activity types that map from existing events. Optionally add last_activity_at update on every capture and key events.

9. **Admin**  
   Add last_activity_at to list response and filters if needed; expose lead_score in list/detail.

10. **Documentation**  
    Add or update docs/LEAD_ENGINE_IMPLEMENTATION.md with sources, scoring rules, stage definitions, nurture triggers, conversion rules, duplicate handling, and admin capabilities.

---

## 6. What Not to Do

- Do **not** replace `source_platform` with `lead_source` in one go (breaking change). Map or extend.
- Do **not** remove or replace the existing `LeadStage` set without a clear migration and admin UI update.
- Do **not** merge `risk_leads` into `leads` in a big-bang migration; sync or dual-write instead.
- Do **not** build a second lead ingestion path; extend LeadService and routes.
- Do **not** send the same nurture content to every lead type; differentiate by service_interest/lead_type.

---

## 7. Summary

- **Already in place:** Central lead model and collection, LeadService create/dedup/merge/convert, multiple capture endpoints (chatbot, contact, checklist, document service, WhatsApp), intent scoring (LOW/MEDIUM/HIGH), checklist nurture, default follow-up, high-intent and SLA notifications, admin list/detail/update/assign/convert/mark-lost/export, lead_audit_logs, consent and unsubscribe.
- **Missing or partial:** Compliance risk check writing to `leads`; numeric lead_score and recalculate_lead_score(); nurture by lead_type; several capture points (pricing, automation enquiry, market research enquiry, support form); storing user_type, portfolio_size, risk_score/risk_level, primary/secondary interest; update-existing-by-email on capture; last_activity_at on lead; conversion from risk_leads to lead conversion in `leads`.
- **Conflicts:** Naming (lead_source vs source_platform, stage values, lead_type vs service_interest) and two stores (leads vs risk_leads). Resolve by extending and mapping, and by syncing risk_check into leads instead of replacing risk_leads.

Implement in the order above; extend existing code and avoid duplication or breaking renames.
