# Phase 5 Implementation — AI Intelligence Layer

**Stage:** 5 — Graph Service consumer intelligence (Tier 2 narration optional)  
**Predecessor:** Phase 3/4 (`516b27bd` on `develop`)

## Summary

- **`services/compliance_intelligence/`** — investigate orchestrator; Graph Service dispatch only (no storage imports)
- **Citation schema + post-validator** — uncited LLM paragraphs stripped
- **`compliance_ai_narrations`** — audit collection with indexes in `database.py`
- **Admin route** — `POST /api/admin/compliance/intelligence/investigate`
- **Feature flags** — Tier 1 requires `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled`; Tier 2 narration additionally requires `AI_ENABLED` + `COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED=true`

## Deliverables

| Artifact | Path |
|----------|------|
| Investigate orchestrator | `services/compliance_intelligence/investigate.py` |
| Graph dispatch | `services/compliance_intelligence/graph_dispatch.py` |
| Post-validator | `services/compliance_intelligence/post_validator.py` |
| Narration audit store | `services/compliance_intelligence/narrations.py` |
| Admin HTTP route | `routes/compliance_intelligence.py` |
| Unit tests | `tests/test_compliance_intelligence_phase5.py` |
| Access boundary | `tests/test_graph_service_access_boundary.py` (extended) |
| Staging smoke runner | `tmp_compliance_evidence_graph_phase5_staging_smoke.py` |
| Tier 1 staging acceptance | `PHASE_5_STAGING_SMOKE.json`, `PHASE_5_STAGING_SMOKE_REPORT.md` |

## Staging acceptance (Tier 1)

**Verdict:** `PHASE_5_TIER1_STAGING_ACCEPTED`  
**Staging deploy SHA:** `b6edbb27` (Phase 5 code at `4de21932`)  
**Flags:** `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled`; narration and AI disabled on staging.

Tier 2 HTTP, customer-facing intelligence, and production flags remain out of scope until explicitly approved.

## Two-tier model

| Tier | Source | LLM |
|------|--------|-----|
| Tier 1 | Graph Service envelope | Never |
| Tier 2 | Optional narration | Only when explicitly enabled + `narrate: true` |

If Graph Service returns `insufficient_evidence: true`, Tier 2 does not speculate.

## Exit criteria (plan)

- Intelligence package imports Graph Service only ✓
- Citation-required schema + post-validator ✓
- `compliance_ai_narrations` audit trail ✓
- Admin investigate route ✓
- Reproducible Tier 1 from envelope hash ✓

## Not in this slice

- Full service catalogue (`evidence_ai`, `portfolio_intelligence`, etc.) — Phase 5+ extensions
- Customer-facing intelligence surfaces — Phase 7
- Frontend investigate UI — follow-on

## Manual test

```http
POST /api/admin/compliance/intelligence/investigate
{
  "method": "explain_decision",
  "params": { "decision_id": "<id>" },
  "client_id": "<client>",
  "narrate": false
}
```

Set `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled` on staging before exercising Tier 1. Staging Tier 1 acceptance recorded in `PHASE_5_STAGING_SMOKE.json` / `PHASE_5_STAGING_SMOKE_REPORT.md`.
