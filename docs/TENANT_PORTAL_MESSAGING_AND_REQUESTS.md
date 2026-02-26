# Tenant Portal: Request Certificate & Contact Landlord

## Current behaviour

- **Request certificate** and **Contact landlord** buttons are shown in the tenant dashboard UI.
- The backend endpoints **POST /api/tenant/request-certificate** and **POST /api/tenant/contact-landlord** are **disabled** (return `403` with `FEATURE_DISABLED`). The tenant portal is intentionally **view-only**: tenants can see compliance status and download compliance packs, but cannot create in-app requests or send messages.
- The error message tells the tenant to contact the landlord directly (e.g. by email or phone) for certificate updates and general contact.

So today there is **no internal notification system** and **no approval flow** for these actions; the product has chosen a view-only tenant experience.

---

## Recommended professional approach (when enabling these features)

If you decide to enable tenant → landlord messaging and certificate requests, the following is a safe, auditable, and professional pattern.

### 1. Internal notification system

- **Stored messages**: Persist every “Contact landlord” and “Request certificate” in a `tenant_messages` or `tenant_requests` table (tenant_id, property_id, type, body, status, created_at, etc.).
- **Notify the landlord**: On create, send an email to the landlord (and/or in-app notification) using the existing notification orchestrator, with a link to the admin/client view of the message.
- **Optional: notify tenant**: When the landlord replies or updates the request, send an email (and/or in-app) to the tenant so they are kept in the loop.

### 2. Approval / request flow (certificate requests)

- **Create request**: Tenant submits “Request certificate” with property_id, certificate_type, optional message → insert a row with status e.g. `PENDING`.
- **Landlord sees requests**: In the client/admin portal, show a list of tenant requests (filter by client/property) with status (Pending / In progress / Done / Declined).
- **Landlord actions**: “Mark in progress”, “Mark done”, or “Decline” (with optional note). Each state change should be stored and, if desired, trigger an email to the tenant.
- **Audit**: Log all creates and status changes (who, when, from/to status) for compliance and support.

### 3. Contact landlord (messaging)

- **Option A – In-app only**: Store messages; landlord sees them in a “Messages” or “Tenant messages” area; replies stored and visible to tenant. Notifications (email/in-app) when new message or reply.
- **Option B – Email only**: “Contact landlord” sends an email to the landlord’s address (from the client record) and optionally stores a copy for audit. No two-way thread in the app.
- **Option C – Hybrid**: Store message + send email; landlord can reply via email or (if you add it) in-app; keep a single thread per property or per tenant for clarity.

### 4. Safety and compliance

- **Access control**: Ensure tenants can only create messages/requests for properties they are assigned to (already enforced in tenant routes).
- **Audit trail**: Log all message/request creation and status updates with actor, timestamp, and metadata (e.g. request_id, property_id).
- **Data retention**: Apply the same retention and privacy rules as for the rest of the platform (e.g. PII in messages).
- **Rate limiting**: Consider rate limits on “Contact landlord” and “Request certificate” per tenant to avoid abuse.

Implementing the above would require: new (or un-disabled) backend endpoints, persistence and notification wiring, and client/admin UI to list and manage tenant messages and certificate requests.
