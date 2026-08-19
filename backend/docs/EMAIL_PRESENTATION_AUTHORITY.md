# Email Presentation Authority

**Programme:** EMAIL-PRESENTATION-AUTHORITY-01  
**Authority version:** `1.0.0`  
**Branch:** `develop`

## Purpose

Single governed presentation layer for all production-facing customer emails. This authority owns **presentation only** — not notification lifecycle, scheduling, routing, or business logic.

## Module

`backend/email_presentation/`

| Module | Responsibility |
|--------|----------------|
| `authority.py` | `EmailPresentationAuthority` facade |
| `brand.py` | Company, colours, support email, website (`APP_BASE_URL`) |
| `greeting.py` | `resolve_greeting()` — `Hello {First},` or `Hello,` |
| `status_colors.py` | GREEN / AMBER / RED **hex** (scoring unchanged). Customer-visible labels: In order / Needs review / Needs attention via `customer_facing_status_label`. |
| `cta.py` | Governed CTA labels and button HTML |
| `copy.py` | Portal authority and informational disclaimers |
| `shell.py` | Canonical shell via `build_customer_email_layout` |
| `context.py` | `enrich_presentation_context()` at render time |
| `registry.py` | Email Presentation Registry (all EMAIL `template_key` rows) |

## Rules

1. **No hardcoded production domains** — use `get_app_base_url(for_email_links=True)` / `get_branding_website_url()`.
2. **No `Hello there,` / `Hi ,`** — use `resolve_greeting()`.
3. **No RAG colour defaults that map AMBER → RED** — use `color_for_rag()` / `enrich_affected_properties()`.
4. **No inline customer email shells** — use `render_customer_email` or `render_fragment_email`.
5. **No embedded greetings in HTML fragments** — strip via `strip_embedded_greetings()`; shell owns greeting.
6. **CTA labels** — reference `email_presentation.cta` keys, do not invent per template.

## Integration points

- `services/email_service.py` — code-built templates
- `services/notification_orchestrator.py` — `enrich_presentation_context` + `compliance-alert` code path
- `services/branding_resolver_service.py` — DB fragment wrapping **imports** `resolve_greeting` / `strip_embedded_greetings` (Cleanup 05; missing import was a send-blocker)
- `services/lead_automation_service.py` — lead sequences
- `services/risk_lead_email_service.py` — footer/CTA domain
- `services/enablement_service.py` — passes `client_name` for enablement emails
- `services/jobs.py` — `get_status_color()` delegates to authority

## Registry

```python
from email_presentation.registry import iter_registry_entries, get_registry_entry
```

Every EMAIL `template_key` from `notification_template_seed_definitions` is registered with `presentation_family`, `shell_version`, `authority_version`, etc.

## Related audit

- `docs/audit/email_template_authority_01/` — pre-implementation audit (Verdict C)
- `docs/audit/email_presentation_authority_01/` — implementation evidence
