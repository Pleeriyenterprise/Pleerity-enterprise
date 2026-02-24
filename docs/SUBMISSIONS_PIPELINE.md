# Submissions Pipeline

This document describes the inbound submission management for **Lead Management**, **Talent Pool**, **Partnership Enquiries**, and **Contact Enquiries**: events, statuses, fields, security, and dedupe rules.

## Overview

- **Four collections** are used: `leads`, `talent_pool`, `partnership_enquiries`, `contact_submissions`. There is no single `submissions` collection; the admin API unifies list/get/patch/notes/export by **type** and **composite id** (`type-id`).
- **Public endpoints** (no auth): `POST /api/public/contact`, `/api/public/lead`, `/api/public/talent`, `/api/public/partnership`. Each returns `{ ok, submission_id, message }`.
- **Admin endpoints** (admin only): `GET/PATCH /api/admin/submissions`, `GET /api/admin/submissions/{composite_id}`, `POST .../notes`, `POST .../mark-spam`, `GET .../export/csv`.

## Events and statuses

| Type        | Typical statuses |
|------------|------------------|
| contact    | NEW, IN_PROGRESS, RESPONDED, CLOSED, SPAM |
| talent     | NEW, REVIEWED, SHORTLISTED, ARCHIVED, SPAM |
| partnership| NEW, REVIEWED, APPROVED, REJECTED, ARCHIVED, SPAM |
| lead       | ACTIVE, CONVERTED, LOST, MERGED, UNSUBSCRIBED (lead pipeline) |

Mark-spam sets `status` to `SPAM` and appends an audit entry.

## Fields (per type)

- **contact_submissions**: submission_id, full_name, email, phone, company_name, contact_reason, subject, message, status, admin_notes, admin_reply, replied_by, replied_at, created_at, updated_at, source_ip, user_agent, consent (marketing_opt_in, privacy_accepted), source (page, referrer, utm), dedupe_key, notes[], audit[].
- **talent_pool**: submission_id, full_name, email, country, phone, interest_areas, professional_summary, years_experience, skills_tools, availability, work_style, consent_accepted, status, admin_notes, tags, created_at, updated_at, source_ip, user_agent, dedupe_key, notes[], audit[].
- **partnership_enquiries**: enquiry_id, first_name, last_name, work_email, phone, company_name, partnership_type, org_description, problem_solved, additional_notes, status, admin_notes, tags, created_at, updated_at, source_ip, user_agent, dedupe_key, notes[], audit[], ack_email_sent (only if PARTNERSHIP_SEND_ACK_EMAIL=true).
- **leads**: lead_id, name, email, phone, company_name, source_platform, service_interest, message_summary, status, stage, assigned_to, created_at, updated_at, etc. (see lead_service / lead_models).

## Security and validation

- **Server-side validation**: Pydantic models with max lengths (e.g. message ≤ 2000, name ≤ 200). Contact uses Field(..., max_length=…).
- **HTML sanitization**: `utils/submission_utils.sanitize_html()` strips tags and script-like content before storage. Used for contact message/subject, talent free text, partnership additional_notes, lead message_summary.
- **Dedupe**: `dedupe_key = sha256(type | normalized_email | normalized_phone | message_snippet_80 | day_bucket)`. If a document with the same dedupe_key exists within the last 24 hours, the public endpoint returns the existing submission_id and does not insert again (contact, talent, partnership). Leads use LeadService.find_duplicate (email/phone/source_metadata).
- **Rate limiting**: In-memory, per-endpoint key (contact, talent, partnership, lead). Default 5 requests per 60 seconds per IP. Implemented in `utils/submission_utils.check_rate_limit(ip, key)`.
- **Honeypot**: Optional field `honeypot` on contact and lead; if non-empty, request is treated as bot and a generic success response is returned without storing.
- **No auto-email to leads**: Partnership acknowledgement email is sent only when `PARTNERSHIP_SEND_ACK_EMAIL` is set to `true` (default off).
- **Consent and source**: Contact stores consent (marketing_opt_in, privacy_accepted) and source (page, referrer, utm). Stored with each submission where applicable; timestamp in created_at.

## Admin API

- **List**: `GET /api/admin/submissions?type=contact|talent|partnership|lead&status=&q=&from_date=&to_date=&page=&page_size=`. Returns `{ items, total, page, page_size }` with normalized rows (composite_id, date, name, email, phone, status, source, assigned_to).
- **Get one**: `GET /api/admin/submissions/{composite_id}` e.g. `contact-CONTACT-ABC123`. Returns full document plus `composite_id` and `_type`.
- **Update**: `PATCH /api/admin/submissions/{composite_id}` body `{ status?, assigned_to?, tags? }`. Appends an audit entry with at, by, changes.
- **Notes**: `POST /api/admin/submissions/{composite_id}/notes` body `{ note }`. Appends to `notes[]`.
- **Mark spam**: `POST /api/admin/submissions/{composite_id}/mark-spam`. Sets status to SPAM and pushes audit entry.
- **Export CSV**: `GET /api/admin/submissions/export/csv?type=contact|talent|partnership|lead&status=&from_date=&to_date=`. Returns CSV file; auth required.

All admin submission endpoints are protected with `admin_route_guard` (RBAC).

## Frontend

- **List pages**: Contact Enquiries (`/admin/inbox/enquiries`), Talent Pool (`/admin/talent-pool`), Partnership Enquiries (`/admin/partnership-enquiries`). Each has Export CSV (authenticated download).
- **Detail**: Single route `/admin/submissions/:type/:id` (e.g. `/admin/submissions/contact/CONTACT-ABC123`). Detail page shows contact info, message (rendered as text, no HTML), admin reply, status update, add note, mark spam, audit log. View links from list pages point to this route.
- **Message display**: Submission message/content is shown as plain text (whitespace-pre-wrap); no raw HTML to avoid XSS.

## Indexes

- **contact_submissions**: submission_id (unique), (dedupe_key, created_at), created_at, status.
- **talent_pool**: submission_id (unique), (dedupe_key, created_at), created_at, status.
- **partnership_enquiries**: enquiry_id (unique), (dedupe_key, created_at), created_at, status.

Defined in `backend/database.py` `_create_indexes()`.

## Optional

- **ADMIN_NOTIFY_EMAIL**: Not implemented; can be added to send an internal “New submission” email on insert.
- **require_owner_or_admin**: Admin uses `admin_route_guard`; if the project standard is `require_owner_or_admin` for sensitive data, submission admin can be switched to that.

## References

- Audit and recommendations: `docs/SUBMISSIONS_PIPELINE_AUDIT.md`
- Backend: `backend/routes/public.py`, `backend/routes/admin_submissions.py`, `backend/utils/submission_utils.py`, `backend/routes/talent_pool.py`, `backend/routes/partnerships.py`, `backend/routes/admin_modules.py` (contact admin), `backend/services/lead_service.py`
