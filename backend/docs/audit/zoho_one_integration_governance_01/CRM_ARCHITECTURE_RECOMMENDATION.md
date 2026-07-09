# Stage Z7 — CRM Architecture Recommendation

**Programme:** STAGE Z — ZOHO ONE INTEGRATION GOVERNANCE & ARCHITECTURE AUDIT  
**Date:** 2026-07-09

## Proposed architecture (under review)

```
Website → Pleerity CRM (Authoritative) → Integration/Sync Layer → Zoho CRM
```

## Verdict

**The proposed architecture is technically sound and should be adopted** — with the critical constraint that sync is **one-way (Pleerity → Zoho)** in all initial phases, and Zoho CRM is explicitly **non-authoritative**.

---

## Evaluation criteria

### Should Pleerity CRM remain authoritative?

**Yes — unconditionally.**

| Evidence | Finding |
|----------|---------|
| `lead_service.py` | Full CRUD, deduplication, conversion governance, Stripe attribution |
| `routes/leads.py` | Public capture + admin API |
| Conversion governance | `test_lead_conversion_governance.py` — governed client creation |
| Discovery import | `DiscoveryImportService` — single governed path to leads |
| Automation hooks | Lead events feed `lead_automation_service.py` |
| Admin UI | `AdminLeadsPage.js` — production operator surface |
| E2E audits | Lead management audit packs exist |

Pleerity CRM is not a stub; it is a **production CRM with pipeline, scoring, nurture, and conversion**. Replacing or demoting it would:

- Break conversion → `clients` governance
- Split automation triggers
- Introduce sync conflicts on the primary revenue funnel
- Violate ILP authority stack (lifecycle derives from Pleerity clients, not Zoho)

### Should Zoho CRM operate as operational / engagement platform?

**Conditionally yes — as a read-oriented sales workspace only.**

Zoho CRM provides value when:

- Outbound sales team prefers Zoho UI for call logging and pipeline views
- Marketing/sales leadership wants Zoho-native dashboards
- No Zoho-side lead creation or conversion is permitted

Zoho CRM must be treated as a **downstream replica**, not a co-master.

### One-way or two-way sync?

| Phase | Sync direction | Rationale |
|-------|----------------|-----------|
| **Phase 0 (now)** | None | No integration exists |
| **Phase 1** | **Pleerity → Zoho only** | Lowest conflict risk; proven pattern |
| **Phase 2+** | Evaluate selective Zoho → Pleerity | Only for **non-authoritative** fields (e.g. sales call notes) via governed webhook adapter |
| **Never** | Zoho → Pleerity for leads/contacts/clients | Would bypass dedup and conversion governance |

**Recommendation: One-way sync default; two-way deferred indefinitely for core entities.**

### Data ownership boundaries

| Entity / field | Owner | Zoho CRM |
|----------------|-------|----------|
| Lead identity (email, name) | Pleerity | Mirror |
| Lead stage / score | Pleerity | Mirror (read) |
| Lead conversion | Pleerity only | Receive notification event |
| Client record | Pleerity `clients` | Optional linked account (read) |
| Properties | Pleerity | Do not sync (compliance scope) |
| Billing / subscription | Stripe + Pleerity | Do not sync |
| Sales activity notes | Pleerity or Zoho | Zoho-owned **only if** stored as supplementary metadata linked by Pleerity lead ID |
| Custom fields | Pleerity schema wins | Map explicitly in integration registry |

**Golden rule:** Pleerity `lead_id` / `client_id` is the foreign key in all Zoho records — never the reverse.

### Retain or retire existing CRM functionality?

| Component | Action |
|-----------|--------|
| `LeadService` + admin UI | **Retain** — authoritative |
| Lead automation | **Retain** |
| Discovery → leads import | **Retain** |
| Risk-check → leads sync | **Retain** |
| Public lead endpoints | **Retain** |
| Zoho CRM as replacement | **Reject** |

No retirement of Pleerity CRM functionality is warranted.

---

## Recommended CRM integration design

```
┌──────────────────────────────────────────────────────────┐
│                    Pleerity CRM (SoR)                     │
│  leads │ lead_automation │ conversion │ AdminLeadsPage   │
└────────────────────────────┬─────────────────────────────┘
                             │ events: created, updated,
                             │ stage_changed, converted
                             ▼
┌──────────────────────────────────────────────────────────┐
│           Pleerity Integration Service (new)              │
│  - idempotent outbound                                    │
│  - field mapping registry                                 │
│  - dead-letter queue                                      │
│  - audit_logs per batch                                   │
└────────────────────────────┬─────────────────────────────┘
                             │ REST (OAuth)
                             ▼
┌──────────────────────────────────────────────────────────┐
│              Zoho CRM (Operational Replica)               │
│  Leads/Contacts/Deals — read + sales activity only        │
└──────────────────────────────────────────────────────────┘
```

### Sync triggers (Phase 1)

| Event | Action |
|-------|--------|
| Lead created | Upsert Zoho Lead |
| Lead updated (stage, score) | Patch Zoho Lead |
| Lead converted | Create/update Zoho Account + link; close deal |
| Lead deleted / GDPR erase | Delete or anonymise in Zoho |

### Anti-patterns (prohibited)

- Zoho webhook creating Pleerity leads
- Zoho deal stage driving Pleerity pipeline stage
- Dual conversion (Zoho + Pleerity)
- Zoho as login/identity for operators (use Pleerity admin auth)

---

## Alternative architectures considered

| Alternative | Why rejected |
|-------------|--------------|
| Zoho CRM as SoR | Breaks conversion governance, duplicates mature Pleerity CRM |
| Two-way real-time sync | High conflict rate; expensive maintenance |
| Zoho CRM only for marketing leads | Still duplicates capture; no net simplification |
| No Zoho CRM at all | Valid if sales team uses Pleerity admin only — **lowest risk default** |

---

## Final recommendation

| Decision | Recommendation |
|----------|----------------|
| Pleerity CRM authoritative? | **Yes** |
| Proposed architecture sound? | **Yes**, with one-way sync |
| Integrate Zoho CRM? | **Optional Phase 2** — only if sales team need Zoho UI |
| Default if no sales demand | **Do Not Integrate** — Pleerity admin CRM is sufficient |
| Two-way sync | **No** in Phase 1–2 |
| Retire Pleerity CRM features | **No** |

**Preferred path:** Complete governance programme → build integration service → pilot one-way lead export → measure sales adoption before expanding scope.
