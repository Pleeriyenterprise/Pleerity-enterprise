# Stage Z4 — Duplication & Conflict Analysis

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT

## Conflict matrix

| Domain | Pleerity capability | Zoho app | Conflict severity | Prevention |
|--------|---------------------|----------|-------------------|------------|
| **CRM / leads** | `LeadService`, pipeline, nurture | Zoho CRM | **Critical** | Pleerity SoR; one-way export only; no Zoho→Pleerity lead create |
| **Contacts** | `leads`, `contact_submissions` | Zoho CRM Contacts | **High** | Single email key; dedup in Pleerity only |
| **Support** | `support_service`, AI chat | Zoho Desk | **Critical** | Do not integrate; single ticket system |
| **Live chat** | `SupportChatWidget`, SalesIQ handoff audit | Zoho SalesIQ | **High** | One chat stack per surface |
| **Documents (compliance)** | Vault + evidence authority | Zoho WorkDrive | **Critical** | No customer doc sync to WorkDrive |
| **Marketing email** | Postmark + lead automation + Kit | Campaigns / MA | **High** | Orchestrator remains Pleerity; Zoho = broadcast only with suppression sync |
| **Forms** | `/api/leads/*`, `/api/public/contact` | Zoho Forms | **Medium** | All production forms on Pleerity |
| **Billing** | Stripe + `client_billing` | Zoho Books | **Critical** | No customer subscription in Books |
| **Notifications** | `notification_orchestrator` | Zoho Campaigns/Desk | **High** | All sends through Pleerity orchestrator or explicit marketing boundary |
| **Reporting** | `reporting_service`, immutable PDFs | Zoho Analytics | **Low** | Analytics read-only; Pleerity reports stay authoritative |
| **User management** | `portal_users`, runtime contract | Zoho CRM users | **Critical** | No Zoho as identity provider for portal |
| **Workflow** | Jobs + lead automation + ILP-6 | Zoho Flow / MA | **High** | Pleerity-owned integration service; Flow non-authoritative |
| **E-sign** | Click-wrap agreements | Zoho Sign | **Medium** | Sign for B2B only; webhook → Pleerity audit |
| **Audit** | `audit_logs` | Zoho audit | **Medium** | Pleerity audit immutable; Zoho events supplementary |

---

## Data duplication risks

| Risk | Scenario | Mitigation |
|------|----------|------------|
| Duplicate leads | Zoho form + Pleerity form | Single ingest path; Zoho webhook → `LeadService.create_lead` only |
| Duplicate contacts | CRM sync both ways | **One-way** Pleerity → Zoho default |
| Stale subscription state | Books vs Stripe | Stripe only; never sync billing to Zoho for customers |
| Split support history | Desk + Pleerity tickets | One system only |
| Document version drift | WorkDrive + vault | No compliance doc sync |
| Unsubscribe desync | Campaigns + orchestrator | Export suppression from Pleerity; honour in all senders |

---

## Workflow conflicts

| Pleerity workflow | Conflicting Zoho workflow | Resolution |
|-------------------|---------------------------|------------|
| Lead convert → `clients` (governed) | Zoho deal → account | Conversion **only** in Pleerity; push event to Zoho |
| Lifecycle email suppression | Campaign blast | Check `account_customer_communication_authority` before export |
| Discovery import → leads | Zoho lead import | Discovery stays governed; no parallel Zoho prospect ingest |
| Support escalation | Desk routing | Keep Pleerity routing rules |
| Stripe webhook → lifecycle | — | No Zoho in billing path |

---

## Recommended global rules

1. **No Zoho write** to authoritative collections without governed adapter + audit.
2. **No two-way sync** on first integration phase.
3. **Email sends** for operational/lifecycle: Pleerity only.
4. **Marketing sends**: either Pleerity-orchestrated or Zoho with Pleerity suppression export — never both blind.
5. **Correct marketing/legal copy** to remove false Zoho claims before any integration goes live.
