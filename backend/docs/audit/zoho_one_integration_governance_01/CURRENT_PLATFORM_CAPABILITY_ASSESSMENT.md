# Stage Z1 — Current Platform Capability Assessment

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Method:** Codebase verification (routes, services, tests, admin UI, audits) — not documentation alone  
**Date:** 2026-07-09

## Executive summary

Pleerity is a **mature, authority-governed platform** with first-party implementations across CRM (leads), support, billing, compliance, documents, notifications, and reporting. **No Zoho integration exists** in code (`PRIVACY_POLICY_ALIGNMENT_CHECK.md` confirms policy/marketing copy is ahead of implementation).

---

## Capability matrix

| Capability | Maturity | Operational readiness | Uniqueness | Remain platform-owned? | Zoho integration value |
|------------|----------|----------------------|------------|------------------------|------------------------|
| **Authentication** | High | Production | Session runtime + ILP-5 | **Yes** | None — identity must stay Pleerity |
| **RBAC (customer)** | High | Production | Runtime contract CAP_* (ILP-4) | **Yes** | None |
| **RBAC (admin)** | High | Production | `UserRole` + `custom_roles` | **Yes** | None for portal access |
| **Organisations / clients** | High | Production | `clients` + lifecycle resolver | **Yes** | None as SoR |
| **Users** | High | Production | `portal_users` separate from ClearForm | **Yes** | None |
| **Lead management (CRM)** | **High** | Production + E2E audits | Full pipeline, scoring, nurture, conversion governance | **Yes** | Low–medium (sales visibility only) |
| **Properties** | High | Production | Compliance-centric property model | **Yes** | None |
| **Compliance engine** | High | Production | Requirements, evidence authority, CEG/CIE | **Yes** | None |
| **Document management** | High | Production | Vault + `requirement_evidence_authority` | **Yes** | Low (internal ops only) |
| **Audit logs** | High | Production | `audit_logs` + operational evidence (derived) | **Yes** | Read-only export only |
| **Notification engine** | High | Production | `notification_orchestrator` single entry | **Yes** | Partial (marketing sends) |
| **Stripe billing** | High | Production | Stripe SoR + `client_billing` mirror | **Yes** | None for customer billing |
| **Subscription lifecycle** | High | Production | ILP stack + Stripe webhooks | **Yes** | None |
| **Reporting** | High | Production | PDF/CSV + immutable artifacts | **Yes** | BI read connector |
| **Support / tickets** | **High** | Production | AI chat, tickets, KB, 14+ tests | **Yes** | **Negative** (duplication) |
| **Marketing CMS** | Medium | Production | Website content via CMS routes | **Yes** | Low |
| **Newsletter** | Medium | Production | Kit (ConvertKit) sync, admin UI | **Yes** | Medium (vs Zoho Campaigns) |
| **Discovery (prospecting)** | Medium–High | Staging/production | Governed import → leads only | **Yes** | Low |
| **E-sign / agreements** | Medium | Production | Click-wrap + issued PDFs (no DocuSign) | **Yes** | Medium (Zoho Sign adjunct) |
| **Ops invoicing** | Medium | Production | Maintenance `invoices` (not Stripe) | **Yes** | Internal Books only |
| **Workflow automation** | High | Production | Lead automation, background runtime authority | **Yes** | Orchestration layer only |

---

## Verified implementations (evidence paths)

### CRM / leads
- `backend/services/lead_service.py` — CRUD, dedup, convert→client, governance
- `backend/routes/leads.py` — public capture + admin CRUD
- `frontend/src/pages/AdminLeadsPage.js` — operator UI
- Tests: `test_lead_management_iter51.py`, `test_lead_conversion_governance.py`, E2E audit pack

### Billing
- `backend/services/stripe_webhook_service.py`, `billing_stripe_sync_service.py`
- `backend/services/account_lifecycle_state_resolver.py` — billing → lifecycle
- Stripe remains payment truth; `client_billing` internal SoR

### Support
- `backend/services/support_service.py`, `support_chatbot.py`
- `frontend/src/pages/AdminSupportPage.js`
- 14+ backend tests

### Documents
- `backend/routes/documents.py`, `requirement_evidence_authority.py`
- Local vault `DATA_DIR/data/documents` — no cloud DMS

### Notifications
- `backend/services/notification_orchestrator.py` — mandatory single send path
- Lifecycle-gated via `account_customer_communication_authority.py`

### Authority stack
- `backend/docs/ACCOUNT_PLATFORM_AUTHORITY_STACK.md` — ILP-1 through ILP-10

---

## Policy / marketing misalignment (verified)

| Document | Claims Zoho | Code reality |
|----------|-------------|--------------|
| `PRIVACY_POLICY_ALIGNMENT_CHECK.md` | Zoho One in privacy copy | **Not integrated** |
| `ABOUT_PAGE_ALIGNMENT_CHECK.md` | Zoho as partner | **Not integrated** |
| `COOKIE_POLICY_ALIGNMENT_CHECK.md` | Zoho cookies | **Not integrated** |

**Action (non-Zoho):** Legal/marketing copy should be corrected independently of integration programme.

---

## Stage Z1 conclusion

Pleerity should **remain authoritative** for all customer-facing operational domains. Zoho can add value only in **adjacent business operations** (internal finance, optional sales visibility, marketing tooling) — not as a replacement for implemented platform capabilities.
