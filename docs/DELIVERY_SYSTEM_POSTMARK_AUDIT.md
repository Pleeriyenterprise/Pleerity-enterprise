# Delivery System (Postmark) – Codebase Audit vs Task Requirements

**Scope:** Four services (AI automation, Market research, Compliance services, Document packs).  
**Audit date:** 2025-02 (codebase state at audit).  
**Do not implement blindly:** This document compares task requirements to the existing implementation and calls out gaps, conflicts, and the safest options.

---

## 1. Task summary (requirements)

- **Implement delivery system using Postmark** for the four services.
- **Delivery rules:**
  - Delivery only after **APPROVED_FINAL**.
  - Email template **branded**.
  - **Attach PDF + optionally DOCX** (or provide secure download link).
  - **Store delivery record:** sent_at, postmark_message_id, delivery_status webhooks (delivered/bounced), opened/clicked if enabled.
  - Order moves **DELIVERING → COMPLETED only on webhook "delivered"** OR after retry policy.
- **Important:**
  - Do **not** expose admin accounts for one-time users.
  - One-time users get a **secure "View Order" page via token** (no login).

---

## 2. Current implementation overview

| Area | Location | Status |
|------|----------|--------|
| Postmark send | `notification_orchestrator`, `email_service` (PostmarkClient) | ✅ In use |
| Order delivery flow | `order_delivery_service.py` | ✅ Implemented |
| Delivery trigger | FINALISING + version_locked → send email → transition | ✅ |
| Email template | `order_email_templates.build_order_delivered_email`, ORDER_DELIVERED | ✅ Branded |
| Delivery record | `message_logs` (not `deliveries`) | ⚠️ Partial |
| Postmark webhooks | `POST /api/webhooks/postmark` | ✅ Delivered/Bounce/Spam |
| Order → COMPLETED | On **send** success | ⚠️ Conflict with task |
| One-time / token view | None | ❌ Missing |

---

## 3. Requirement-by-requirement

### 3.1 Delivery only after APPROVED_FINAL

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Gate on approved state | ✅ Yes | Codebase uses **FINALISING** with **version_locked** and **approved_document_version** set. No separate status "APPROVED_FINAL". Semantically equivalent: delivery runs only when admin has approved and locked the document version. `process_finalising_orders` and `deliver_order` both require FINALISING + version_locked + approved_document_version. |

**Naming:** Task says "APPROVED_FINAL"; codebase uses **FINALISING** (post-approval, pre-delivery). No change needed; document as mapping.

---

### 3.2 Email template branded

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Branded template | ✅ Yes | `build_order_delivered_email` and ORDER_DELIVERED alias use branded HTML (header, accent color, footer, support email). `order_email_templates` uses `_build_email_header`, `_build_email_footer`, `BRAND_COLOR_ACCENT`, `COMPANY_NAME`, `SUPPORT_EMAIL`. |

---

### 3.3 Attach PDF + optionally DOCX (or provide secure download link)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Attach PDF/DOCX | ❌ No | Delivery email uses **download_link** and **portal_link** only. `notification_orchestrator._send_email` supports `context.attachments` (list of Name, Content, ContentType), but `order_delivery_service` does **not** build or pass attachments. |
| Secure download link | ⚠️ Partial | Link is `{FRONTEND_URL}/orders/{order_id}/documents`. Client document routes (`GET /api/client/orders/{order_id}/documents`, `.../download`) require **client_route_guard** (logged-in client; email must match order.customer.email). So the link is **not** usable by one-time users (no account). No token-based download link in delivery email. |

**Gap:** Either (1) attach PDF (and optionally DOCX) to the email via `context.attachments` (fetch bytes from GridFS, base64, pass to orchestrator), or (2) provide a **token-based** secure link so one-time users can open the link without logging in. Task says "or provide secure download link" – for one-time users that implies a tokenised link.

---

### 3.4 Store delivery record: sent_at, postmark_message_id, delivery_status webhooks, opened/clicked

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| sent_at | ✅ Yes | Stored in **message_logs** when Postmark send succeeds (`postmark_message_id`, `sent_at`, status SENT). |
| postmark_message_id | ✅ Yes | Stored in **message_logs** (`provider_message_id`, `postmark_message_id`). |
| Delivery record per order | ❌ No | There is a **deliveries** collection and `DeliverySchema`/`delivery_repository`, but **nothing** in the order delivery flow inserts into `deliveries`. All tracking is in **message_logs**. message_logs does not have `order_id`; it has `client_id` and `metadata` (context), which includes `order_reference` (order_id) for ORDER_DELIVERED. So delivery is tied to order only indirectly (idempotency_key = `{order_id}_ORDER_DELIVERED`, metadata.order_reference). |
| delivery_status webhooks (delivered/bounced) | ⚠️ Partial | **Postmark webhook** (`POST /api/webhooks/postmark`) updates **message_logs** by MessageID: sets status DELIVERED (delivered_at) or BOUNCED (bounced_at, error_message). It does **not** update a `deliveries` record or **order** status. So "delivery_status" is on the message, not on a dedicated delivery record or order. |
| opened/clicked if enabled | ⚠️ Partial | Postmark send uses `TrackOpens=True`, `TrackLinks="HtmlOnly"`. Postmark can send Open/Click webhooks; the codebase does **not** handle Open/Click in `webhooks.py` or persist opened_at/clicked_at anywhere. |

**Gap:**  
- **Option A:** Keep using message_logs only; add `order_id` (or `metadata.order_id`) to the ORDER_DELIVERED message log so webhooks can resolve order and update order status / delivery status.  
- **Option B:** Create a **delivery record** per order in `deliveries` (order_id, channel, status, sent_at, postmark_message_id, etc.) when sending; have Postmark webhook find by postmark_message_id, update delivery record and optionally order.  

Safest: **Option B** – explicit delivery record per order, webhook updates it and (if desired) order status. Option A is minimal change but ties order completion to message_logs shape.

---

### 3.5 Order moves DELIVERING → COMPLETED only on webhook "delivered" OR after retry policy

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Transition on webhook "delivered" | ❌ No | Currently order moves to **COMPLETED** as soon as the **send** succeeds (`delivery_success = result.outcome in ("sent", "duplicate_ignored")`). Postmark webhook "Delivery" only updates message_logs; it does **not** transition the order to COMPLETED. |
| Transition after retry policy | ⚠️ Partial | Retry exists: DELIVERY_FAILED → admin/retry → back to FINALISING → send again. But on success we still transition to COMPLETED on send, not on webhook. So "after retry policy" is not the same as "on webhook delivered". |

**Conflict:**  
- **Task:** DELIVERING → COMPLETED **only** when (1) webhook reports "delivered", or (2) after retry policy (e.g. after N retries or timeout).  
- **Current:** DELIVERING → COMPLETED when email **send** returns success.  

**Safest approach:**  
- **Option A (strict):** Move to COMPLETED **only** when Postmark webhook fires with RecordType Delivery (or after a retry/timeout policy if webhook never arrives). While in DELIVERING, do not complete on send; store delivery record with postmark_message_id; webhook handler finds order (via delivery record or message_log order_id), updates delivery status, then transitions order to COMPLETED (and on Bounce → DELIVERY_FAILED or similar).  
- **Option B (pragmatic):** Keep COMPLETED on send for speed; add webhook handler that **also** updates delivery record and, if order is still DELIVERING, can set a "delivery_confirmed_at" or leave as-is. Then order is "completed" on send; delivery record still gets delivered/bounced for audit.  

Recommendation: **Option A** if compliance/audit requires "delivered" proof; **Option B** if product accepts "sent" as sufficient and webhook is for audit only.

---

### 3.6 Do not expose admin accounts for one-time users

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| No admin exposure | ✅ Yes | Client-facing delivery uses customer email and client_id; no admin accounts or admin-only links are sent to the customer. Admin flows are separate (admin portal, admin routes). |

---

### 3.7 One-time users get secure "View Order" page via token (no login)

| Requirement | Implemented | Notes |
|-------------|-------------|--------|
| Token-based view order | ❌ No | There is **document_access_token** for **admin** document preview (order_id, version, format, admin_email in JWT). There is **no** token type or route for a **customer/one-time** "View Order" page. Client order list and document download require **client_route_guard** (logged-in client; email matches order.customer.email). So a one-time user (e.g. guest checkout, no portal account) **cannot** view the order or download documents. |

**Gap:**  
- Add a **one-time (or short-lived) token** for "view order + download": e.g. JWT or signed token containing order_id, customer email (or hash), expiry.  
- **Public route:** e.g. `GET /api/public/orders/view?token=...` that validates token and returns order summary + secure document download links (or inline PDF).  
- **Frontend:** Public page e.g. `/view-order?token=...` (no login) that shows order status and allows viewing/downloading the delivered documents.  
- **Delivery email:** For one-time users, use this tokenised URL as the download link instead of (or in addition to) the portal link. Do **not** use admin tokens or admin routes for customers.

---

## 4. Data flow and potential bug (document source)

- **order_delivery_service** builds the document list from **order.get("document_versions", [])** and uses **approved_document_version** to pick the right version.  
- Document versions may live in **document_versions_v2** (used by template_renderer, document_generator.get_document_versions) while **order.document_versions** might be legacy or not populated.  
- **lock_approved_version** updates **order.document_versions** (array element by version); it assumes that array already exists and has the version.  

If generation only writes to **document_versions_v2** and not to **order.document_versions**, delivery could see an empty list and fail with "No documents found for approved version". **Recommendation:** In `order_delivery_service.deliver_order`, resolve document list from **document_generator.get_document_versions(order_id)** (and approved_document_version) when order.document_versions is empty or missing, so delivery works with document_versions_v2.

---

## 5. Gaps summary

| # | Gap | Severity | Recommendation |
|---|-----|----------|----------------|
| 1 | **Delivery record** (deliveries collection) | Medium | Create a delivery record per order when sending (order_id, channel, status=PENDING/SENT, sent_at, postmark_message_id). Postmark webhook updates this record (and optionally order status). |
| 2 | **COMPLETED only on webhook "delivered" (or retry)** | Medium | Either: (A) Move to COMPLETED only when webhook Delivery fires (or after timeout/retry); or (B) Keep COMPLETED on send and use webhook only for delivery record/audit. |
| 3 | **Attach PDF (and optionally DOCX) or tokenised link** | Medium | Either attach PDF (and optionally DOCX) to the email, or generate a one-time **customer** token and use a token-based download URL in the email so one-time users can access without login. |
| 4 | **One-time user: secure "View Order" via token** | High | Implement token-based view: issue token (order_id + scope + expiry), public API and page that accept token and show order + download links (no login). Use this link in delivery email for one-time users. |
| 5 | **Opened/clicked** | Low | Optional: handle Postmark Open/Click webhooks and store on delivery record or message_log. |
| 6 | **Document list source** | Medium | Ensure delivery gets document list from document_versions_v2 when order.document_versions is empty (use get_document_versions + approved_document_version). |

---

## 6. Conflicts and safe options

| Topic | Conflict | Safest option |
|-------|----------|----------------|
| COMPLETED timing | Task: only on webhook delivered (or retry). Current: on send success. | Choose explicitly: (A) Strict – COMPLETED only on webhook Delivery (and handle bounce → DELIVERY_FAILED); or (B) Keep COMPLETED on send, use webhook for delivery record and audit only. |
| Secure link | Task: attach PDF or secure link. Current: portal link only (requires login). | For one-time users, secure link must be token-based (no login). Either add attachments to email or add token-based public "View Order" + download and use that URL in the email. |
| Delivery record | Task: store delivery record with sent_at, postmark_message_id, webhook status. Current: only message_logs. | Introduce a delivery record per order in `deliveries` when sending; Postmark webhook updates it (and optionally order). Keeps order-delivery link clear and supports "complete on delivered" if chosen. |

---

## 7. What is already in place (no change needed)

- Postmark send via `notification_orchestrator` and `email_service`; `POSTMARK_SERVER_TOKEN` used.
- Order delivery flow: FINALISING → DELIVERING → send ORDER_DELIVERED email → COMPLETED or DELIVERY_FAILED.
- Branded ORDER_DELIVERED email (subject, HTML, download/portal links).
- message_logs: message_id, template_key, client_id, recipient, status, postmark_message_id, sent_at; idempotency by `{order_id}_ORDER_DELIVERED`.
- Postmark webhook: single endpoint for Delivery/Bounce/SpamComplaint; updates message_logs by MessageID; optional X-Postmark-Token check.
- Retry: DELIVERY_FAILED → retry delivery → FINALISING → send again; manual complete for admin override.
- Admin not exposed to customers; delivery is to customer email only.

---

## 8. Files reference

- **Backend:**  
  - `backend/services/order_delivery_service.py` (deliver_order, process_finalising_orders, retry_delivery, manual_complete)  
  - `backend/services/notification_orchestrator.py` (send, _send_email, message_logs, attachments support)  
  - `backend/services/order_email_templates.py` (build_order_delivered_email)  
  - `backend/routes/webhooks.py` (postmark_webhook, message_logs updates)  
  - `backend/services/document_access_token.py` (admin document token only)  
  - `backend/routes/client_orders.py` (client document list/download – auth required)  
  - `backend/repositories/services_repositories.py` (DeliveryRepository), `backend/models/services_models.py` (DeliverySchema)  
  - `backend/services/document_generator.py` (get_document_versions)  
- **Frontend:**  
  - Client order/documents: `frontend/src/pages/ClientOrdersPage.js`, client API for orders/documents.  
- **Config:**  
  - `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_TOKEN` (or POSTMARK_WEBHOOK_SECRET), `FRONTEND_URL`.

---

## 9. Recommended implementation order (if implementing)

1. **Delivery record:** When sending ORDER_DELIVERED, insert (or upsert) a record in `deliveries` (order_id, channel=email, status=SENT, sent_at, postmark_message_id, recipient). Optionally store message_id for correlation.
2. **Webhook → delivery + order:** In Postmark webhook, by MessageID find message_log and/or delivery record (by postmark_message_id). Update delivery record (delivered_at / bounced_at, status). If task is "complete only on delivered", when status=DELIVERED transition order from DELIVERING to COMPLETED; on Bounce set DELIVERY_FAILED and optionally retry path.
3. **COMPLETED timing:** Decide and implement either (A) complete only on webhook Delivery (and retry/timeout policy), or (B) keep current (complete on send) and use webhook only for delivery record.
4. **Document list from v2:** In order_delivery_service, if order.document_versions is empty or missing approved version docs, get versions from get_document_versions(order_id) and approved_document_version; build document list (and attachment list if attaching) from that.
5. **One-time token + View Order:** Add customer-facing token (e.g. order_id + email/hash + expiry); public GET route that accepts token and returns order summary + download URLs (or stream PDF); public frontend page "View Order" that uses token; in delivery email, for one-time users use this token URL as download link. Do not reuse admin document_access_token for customers.
6. **Attachments (optional):** If product wants PDF (and optionally DOCX) attached, in deliver_order fetch file bytes from GridFS for approved version, build context.attachments, pass to notification_orchestrator.send. Keep total size within Postmark limits.
7. **Opened/clicked (optional):** Add Postmark Open/Click webhook handling and persist on delivery record or message_log.

This audit reflects the current codebase and is intended to guide decisions without duplicating or conflicting with existing behaviour.
