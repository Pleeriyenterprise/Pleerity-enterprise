# Stage Z2 — Zoho Feasibility Assessment

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT

## Assessment scale

| Rating | Meaning |
|--------|---------|
| Feasibility | Technical ability to integrate safely |
| Value | Business/operational benefit vs existing capability |
| Complexity | Implementation and ongoing cost |
| Lock-in | Exit difficulty |

---

## Customer & Sales

### Zoho CRM

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | **High** — REST API, webhooks |
| Integration complexity | **High** — duplicate CRM model, sync conflicts |
| Business value | **Low–Medium** — sales team familiarity only |
| Operational value | Medium for outbound sales ops |
| Scalability | Medium — sync layer must scale with leads |
| Maintenance | **High** — field mapping, conflict resolution |
| Security | OAuth secrets, PII export to third party |
| Vendor lock-in | **High** if two-way sync |
| **Recommendation** | **Do Not Integrate** as SoR; optional **one-way read replica** (see CRM doc) |

### Zoho Campaigns

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Medium |
| Business value | Medium — marketing broadcasts |
| Operational value | Medium vs Postmark sequences + Kit |
| Scalability | High (Zoho-hosted) |
| Maintenance | Medium — list hygiene, unsubscribe sync |
| Security | Marketing PII leaves platform |
| Vendor lock-in | Medium |
| **Recommendation** | **Event-driven one-way** audience export OR **Do Not Integrate** until Kit/lead nurture gap proven |

### Zoho Marketing Automation

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | **High** — overlaps `lead_automation_service.py`, nurture jobs |
| Business value | Medium |
| Operational value | **Low** — Pleerity already runs behavioural sequences |
| Vendor lock-in | High |
| **Recommendation** | **Do Not Integrate** — duplicate nurture authority |

### Zoho SalesIQ

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | **High** |
| Business value | Low–Medium |
| Operational value | **Negative** — conflicts `SupportChatWidget.js`, `support_chatbot.py` |
| **Recommendation** | **Do Not Integrate** on authenticated portal; isolated marketing-site embed only if ever needed |

### Zoho Forms

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Low (webhook ingest) |
| Business value | Low |
| Operational value | **Low** — 10+ public lead endpoints already exist |
| **Recommendation** | **Do Not Integrate** — use Pleerity forms; webhook adapter only for external microsites |

### Zoho Analytics

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Medium |
| Business value | Medium — executive BI |
| Operational value | Medium — supplements `reporting_service.py` |
| Vendor lock-in | Low if read-only |
| **Recommendation** | **Read only** — scheduled export / API feed from Pleerity |

### Zoho PageSense

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Medium |
| Business value | Low–Medium |
| Operational value | A/B testing — `consent.py` cookie implications |
| **Recommendation** | **Do Not Integrate** initially; revisit after consent framework review |

---

## Customer Service

### Zoho Desk

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | **Very High** |
| Business value | **Low** |
| Operational value | **Negative** — mature in-house support module |
| Maintenance | **Very High** |
| **Recommendation** | **Do Not Integrate** — retain Pleerity support as SoR |

---

## Documents & Agreements

### Zoho WorkDrive

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | **Very High** for compliance vault |
| Business value | Low for customer compliance docs |
| Operational value | Medium for **internal** Pleerity team files only |
| **Recommendation** | **Do Not Integrate** for customer document SoR; optional internal ops folder |

### Zoho Sign

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Medium |
| Business value | Medium — B2B contracts beyond click-wrap |
| Operational value | Medium — complements `agreement_acceptance_service.py` |
| **Recommendation** | **Event-driven one-way** — Sign completes → webhook → Pleerity audit record; subscription checkout stays Pleerity |

---

## Finance

### Zoho Books

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | High if customer billing |
| Business value | **Low** for CVP customer subscriptions |
| Operational value | Medium for **Pleerity Ltd internal accounting** only |
| **Recommendation** | **Do Not Integrate** with customer Stripe billing; optional internal finance sync (out of platform scope) |

---

## Integration

### Zoho Flow

| Dimension | Assessment |
|-----------|------------|
| Technical feasibility | High |
| Integration complexity | Medium |
| Business value | Medium |
| Operational value | **Low** if Pleerity builds governed integration layer |
| Vendor lock-in | **High** — logic in Zoho |
| **Recommendation** | **Do Not Integrate** as primary orchestrator; use Pleerity-owned sync service with optional Flow as **non-authoritative** trigger |

---

## Stripe position

**Stripe remains preferred payment processor.** No Zoho Books/Billing replacement identified. Zoho Finance apps do not improve subscription lifecycle, capability gating, or webhook convergence already validated in production.
