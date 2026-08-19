# Tenant and support verification 05

## Tenant invite

`TENANT_INVITE` no longer lists GREEN/AMBER/RED or RAG. Copy describes records that look in order, need a review, or need action. Setup CTA unchanged (`setup_link`).

`TENANT_COMPLIANCE_PACKAGE_DELIVERY` remains a PDF-attached pack with a delivery reference. It does not dump landlord RAG scores or internal requirement ids in the email body.

Scoring is unchanged.

## Support acknowledgement

`SUPPORT_TICKET_CONFIRMATION` now states:

* request received
* ticket reference
* team will review and reply by email
* **no guaranteed response time** (no governed customer SLA exists)
* refer using the ticket reference
* CTA: Open Help → `/help` (authenticated Help Centre / chat widget). There is **no** customer ticket-detail route.

Public ticket-created API `response_window` matches that wording.

Chatbot FAQ copy that still mentions 24 hours is **deferred** (different surface; not this email).

## CTA class

| Template | CTA | Verdict |
| --- | --- | --- |
| TENANT_INVITE | Set Up Your Access | ACTION_RESOLVES_END_TO_END (token setup; prior 01/02) |
| SUPPORT_TICKET_CONFIRMATION | Open Help | DESTINATION_ONLY — help surface, not ticket-id deep-link |
