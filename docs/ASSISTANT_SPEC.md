# Compliance Vault Assistant (AI Chat) — Specification

## Purpose

The Compliance Vault Assistant lets users ask questions about their compliance data and get answers **grounded in portal data only**. It does **not** provide legal advice, legal interpretation, or compliance verdicts.

## Non-negotiables

- **No legal advice**: The assistant must not provide legal advice, legal interpretation, or compliance verdicts. It must not claim "you are compliant" or "you are non-compliant". It may state what the portal shows (e.g. "your portal currently shows X missing/expired") and recommend actions (e.g. "upload document", "book inspection").
- **Grounded responses**: Every factual claim about the user's account must be based on portal data (documents, properties, requirements) retrieved server-side.
- **No data leakage**: Strict RBAC, tenant isolation. CRN lookup is allowed only for authorized admin/owner users.
- **Full audit trail**: Every chat turn, sources used, user_id, and client_id are stored and audited.

## Allowed capabilities

- Answer questions about **what the portal shows**: missing/expired items, expiry dates, document types, requirement status.
- Recommend **portal actions**: upload a document, book an inspection, check a specific property.
- Explain **informational content** from the knowledge base (e.g. what each certificate is for, how to upload, how scoring works) — informational only, not legal interpretation.
- **Admins**: Look up a client by CRN and ask about that client's status (admin-only).

## Forbidden / legal advice policy

- Do **not** say: "you are compliant", "you are non-compliant", "you are legally required to", "this guarantees compliance", "you will be fined", "this is illegal".
- Do **not** interpret law or regulations; do not predict enforcement or penalties.
- If the user asks for a legal verdict or legal advice: refuse politely and offer a safe alternative ("Here is what the portal shows and what you can do next").
- Responses must be post-processed to block or rewrite any compliance-verdict language that the model may emit.

## Data sources

1. **Portal facts** (server-side): Client summary (CRN, plan, subscription status), property list (id, nickname, postcode — full address only when explicitly requested and authorized), requirements status per property (gas, EICR, EPC, licence, etc.) with expiry dates, latest documents (type, filename, uploaded_at, linked property, extracted expiry if confirmed). Minimal PII; no excessive personal data.
2. **Knowledge base**: Curated markdown files under `backend/docs/assistant_kb/` (e.g. `certificates_overview.md`, `how_to_upload.md`, `how_scoring_works.md`, `glossary.md`). No web scraping in MVP; external references only via a curated list of allowed URLs (e.g. gov.uk) shown as "external references".

## RBAC rules

- **Client endpoint** `POST /api/assistant/chat`: Requires authenticated portal user (client role). Uses authenticated `client_id` only; any CRN in the message is ignored. Property scope is optional (`property_id`) to limit context to one property.
- **Admin endpoint** `POST /api/admin/assistant/chat`: Requires owner or admin (`require_owner_or_admin`). Optional `crn` in body: when provided, resolve to `client_id` via `clients.customer_reference` and scope context to that client. Never expose other clients' data to non-admins.

## API contract (target)

### Client

- **POST /api/assistant/chat**  
  Body: `{ message: string, conversation_id?: string | null, property_id?: string | null }`  
  Returns: `{ conversation_id, answer, citations: [ { source_type, source_id, title } ], safety_flags: { legal_advice_request?: boolean, missing_data?: boolean } }`

### Admin

- **POST /api/admin/assistant/chat**  
  Body: `{ message: string, conversation_id?: string | null, crn?: string | null }`  
  Same return shape; CRN used only when provided to resolve client context.

## Storage and audit

- **Collections**:  
  - `assistant_conversations`: `{ _id, client_id, created_by_user_id, created_at, last_activity_at }`  
  - `assistant_messages`: `{ _id, conversation_id, client_id, user_id, role: "user" | "assistant", message, citations, safety_flags, model, prompt_version, created_at }`
- **Audit actions**:  
  - ASSISTANT_CHAT_REQUESTED  
  - ASSISTANT_CHAT_RESPONDED  
  - ASSISTANT_CHAT_REFUSED_LEGAL  
  - ASSISTANT_CHAT_ERROR  

## Rate limiting

- Per user: 20 requests / 10 minutes.
- Per client: 100 requests / day (env configurable).

## Hard guardrails (must implement)

1. **Compliance verdict language**: Post-process responses to block or rewrite phrases such as "you are compliant", "you are legally required to", "this guarantees compliance". If detected, replace with safe wording or refuse and suggest next steps.
2. **PII minimization**: By default send only nickname + postcode for properties. Include `address_line_1` only when the user explicitly asks and is authorized.
3. Rate limits as above.

---

*This spec is the single source of truth for the Compliance Vault Assistant. Implementation must align with it and must not duplicate or conflict with existing assistant behaviour without an explicit migration plan.*
