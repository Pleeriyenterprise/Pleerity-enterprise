# EMAIL-PRESENTATION-AUTHORITY-01 — Implementation Report

**Branch:** `develop` only  
**Authority version:** `1.0.0`  
**Evidence:** [`EMAIL_PRESENTATION_AUTHORITY_EVIDENCE.json`](./EMAIL_PRESENTATION_AUTHORITY_EVIDENCE.json)  
**Governance:** [`../EMAIL_PRESENTATION_AUTHORITY.md`](../EMAIL_PRESENTATION_AUTHORITY.md)

## Summary

Implemented a shared **Email Presentation Authority** (`backend/email_presentation/`) and wired it into all identified production customer email paths from audit Verdict C. Presentation-only — notification lifecycle, scheduling, routing, and business logic unchanged.

## Phases delivered

| Phase | Deliverable |
|-------|-------------|
| 1 Presentation Authority | `EmailPresentationAuthority` + submodules |
| 2 Branding | `brand.py` — APP_BASE_URL, support, colours |
| 3 Greeting | `greeting.py` — `Hello {First},` / `Hello,` |
| 4 Status colours | `status_colors.py` — governed RAG hex |
| 5 CTA | `cta.py` — governed labels + button style |
| 6 Footer | Canonical shell footer only |
| 7 Shell migration | lead automation, ADMIN_MANUAL, enablement fragments |
| 8 Registry | `registry.py` — 81 EMAIL template_keys |
| 9 Production audit | Registry + integration matrix in evidence JSON |
| 10 Content consistency | Portal authority copy via `copy.py` |
| 11 Tests | `tests/test_email_presentation_authority.py` (17 passed) |

## Defects fixed (from EMAIL-TEMPLATE-AUTHORITY-01)

| Defect | Fix |
|--------|-----|
| AMBER renders red | `enrich_affected_properties` + `rag_status_chip_html`; orchestrator `compliance-alert` code path |
| Double greeting Document Verified | `render_fragment_email` + stripped enablement `Hi`; `client_name` in enablement context |
| Gap emails `pleerity.com` | `render_lead_sequence_email` canonical shell |
| Risk nurture `pleerity.com` | Governed footer in `risk_lead_email_service` |

## Integration matrix

| Workflow | Presentation path |
|----------|-------------------|
| COMPLIANCE_ALERT | Authority colours + greeting + shell |
| ENABLEMENT_DELIVERY | Fragment + `render_fragment_email` / DB finalize |
| LEAD_FOLLOWUP / gap | `render_lead_sequence_email` |
| Risk lead nurture | Governed footer + CTA (full doc retained for content blocks) |
| Lifecycle reminders | `_format_greeting` → authority |
| DB email fragments | `finalize_db_email_html` → authority greeting + strip |

## Acceptance

All acceptance criteria from programme brief marked satisfied in evidence JSON `acceptance_checklist`.

## Out of scope (unchanged)

- Notification orchestration send rules
- Job scheduling / frequency
- Compliance / document / requirement authority
- Production deployment / `main` merge

## Tests

```bash
cd backend && python -m pytest tests/test_email_presentation_authority.py tests/test_risk_lead_email_service.py -q
```

**Result:** 17 + 7 passed on develop.
