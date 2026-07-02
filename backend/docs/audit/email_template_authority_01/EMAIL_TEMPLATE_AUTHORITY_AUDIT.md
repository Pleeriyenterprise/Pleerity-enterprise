# EMAIL-TEMPLATE-AUTHORITY-AUDIT-01

**Branch:** `develop` only  
**Date:** 2026-06-30  
**Mode:** Audit-only — no fixes implemented  
**Evidence:** [`EMAIL_TEMPLATE_AUTHORITY_EVIDENCE.json`](./EMAIL_TEMPLATE_AUTHORITY_EVIDENCE.json)

---

## Executive verdict: **C**

**Domain, colour, and greeting logic are duplicated and require a shared Email Presentation Authority.**

The platform has a well-documented canonical customer shell (`build_customer_email_layout`), and many high-volume emails use it. However, several **live production workflows** still render through legacy inline HTML, DB fragment wrappers, or code paths that omit governed tokens. The screenshot defects (AMBER colour, double greeting, `pleerity.com` footer) are explained by identifiable code — not one-off rendering glitches.

This is **not** verdict A (governed with minor defects only) because multiple parallel presentation stacks remain reachable. It is **not** verdict B alone (simple migration) because colour and greeting logic are duplicated across modules, not just layout shells.

---

## Architecture summary

### Send path (production)

All customer email should flow through:

`notification_orchestrator.send(template_key=…)` → `_render_email` → Postmark

Registry SSOT: `notification_template_seed_definitions.py` (81 EMAIL `template_key` rows).

### Render ordering (`notification_orchestrator._render_email`)

1. **Unconditional code bypass** — orchestrator calls `EmailService._build_html_body` before consulting Mongo `email_templates` (e.g. `monthly-digest`, lifecycle reminders, contractor/client operational emails).
2. **Conditional bypass** — e.g. `admin-manual` when `message` is already a full `<html>` document (lead automation gap emails).
3. **DB-first** — active `email_templates` row with placeholder substitution, then `finalize_db_email_html` (wraps fragments in canonical shell with `greeting=U+00A0`).
4. **EmailService fallback** — when no active DB row (includes legacy `ADMIN_MANUAL` shell).

Metadata per alias: `services/email_template_runtime_metadata.py`.

### Canonical layout (intended SSOT)

`email_templates/email_layout.py` → `build_customer_email_layout`:

| Token | Value |
|-------|-------|
| Header background | `#0B1D3A` |
| Primary / links / CTA | `#00B8A9` |
| Company | Pleerity Enterprise Ltd |
| Tagline | AI-Driven Solutions & Compliance |
| Website footer | `utils/branding.get_branding_website_url()` → `get_app_base_url(for_email_links=True)` |
| Support | `info@pleerityenterprise.co.uk` |

Docstring states: *"All customer-facing emails must use this layout."*

---

## Required questions (1–17)

### 1. What is the canonical email layout/template?

**`email_templates/email_layout.py` → `build_customer_email_layout`**, invoked via `EmailService._customer_email_html` and `branding_resolver_service.finalize_db_email_html` for DB fragments.

### 2. Which templates use it?

- **19 aliases** with unconditional orchestrator code bypass (see `email_template_runtime_metadata._UNCONDITIONAL_CODE_BUILT`).
- **Lifecycle reminder aliases** (`reminder`, `lifecycle-reminder-*`) — always code-built.
- **Hybrid aliases** with structured context (`payment-receipt`, `portal-ready`, `scheduled-report`, `order-intake-confirmation`).
- **DB fragments** wrapped by `finalize_db_email_html` when `admin-manual` / other DB rows contain HTML fragments (not full documents).

Full inventory: evidence JSON `template_inventory` (81 rows).

### 3. Which templates are legacy?

| Legacy stack | Location | Still reachable |
|--------------|----------|-------------------|
| ADMIN_MANUAL EmailService fallback | `email_service.py` ~1792–1821 | Yes — when no DB row or fallback path |
| Lead automation inline shell | `lead_automation_service.py` ~394–404 | Yes — compliance gap sequence |
| Risk lead nurture inline HTML | `risk_lead_email_service.py` | Yes |
| Enablement embedded greetings in fragments | `enablement_templates.py` | Yes |
| Parallel enablement compliance status email | `status_changed_awareness` | Yes — overlaps COMPLIANCE_ALERT |

### 4. Are status colours governed centrally?

**No.** Hex values are duplicated in:

- `jobs.get_status_color()` — GREEN `#22c55e`, AMBER `#f59e0b`, RED `#dc2626`
- `email_service.py` COMPLIANCE_ALERT inline spans and legend
- Deprecated `send_compliance_alert_email` colour injection (lines 2766–2767)
- `compliance_pack.py` PDF colours (separate surface)

There is no shared `email_presentation` colour module.

### 5. Why does AMBER render red?

**Root cause:** `jobs.check_compliance_status_changes` sends `affected_properties` **without** `prev_color` / `new_color`:

```1654:1660:backend/services/jobs.py
                            properties_with_changes.append({
                                "property_id": prop["property_id"],
                                "address": property_address,
                                "previous_status": previous_notified_status,
                                "new_status": new_status,
                                "reason": reason
                            })
```

`EmailService` COMPLIANCE_ALERT table uses **asymmetric defaults**:

```1038:1041:backend/services/email_service.py
                        <span style="color: {prop.get('prev_color', '#22c55e')}; font-weight: bold;">{prop.get('previous_status', 'GREEN')}</span>
...
                        <span style="color: {prop.get('new_color', '#dc2626')}; font-weight: bold;">{prop.get('new_status', 'RED')}</span>
```

- **Current = AMBER** without `new_color` → styled **red** (`#dc2626`).
- **Previous = AMBER** without `prev_color` → styled **green** (`#22c55e`).

Legend uses correct hardcoded amber (`#f59e0b`), so table vs legend diverge — matching screenshots.

The deprecated `send_compliance_alert_email` **did** inject colours correctly but is no longer the live path.

`compliance-alert` is **DB-first** in production; if the active DB row mirrors the same placeholder defaults, the defect persists there too.

### 6. Are GREEN, AMBER, RED colours consistent across all emails?

**No.** Consistent only where:

- Legend copy in COMPLIANCE_ALERT code-built body (static hex), or
- Callers manually inject colours (deprecated path).

Enablement `status_changed_awareness` shows plain text `{{old_status}}` / `{{new_status}}` without colour semantics. Gap emails do not use RAG colours.

### 7. Is salutation generated centrally or per-template?

**Per-template / per-path.** Partial centralization:

- `_format_greeting(client_name)` → `Hello {first},` or `Hello,` for empty/`there`/`customer`
- COMPLIANCE_ALERT → `Hello {client_name|'there'},`
- Enablement fragments → `Hi {{first_name}},`
- Lead automation gap → `Hello {{first_name}},`
- ADMIN_MANUAL legacy → `Hello {client_name|'there'},`
- DB fragments → shell greeting `U+00A0` (NBSP) plus any greeting inside fragment

### 8. Is recipient name fallback governed?

**No single authority.**

| Path | Fallback when name missing |
|------|---------------------------|
| `_format_greeting` | `Hello,` |
| COMPLIANCE_ALERT | `Hello there,` |
| ADMIN_MANUAL legacy | `Hello there,` |
| Enablement `first_name` | empty → `Hi ,` |
| Lifecycle reminders | `Valued Customer` |

### 9. Are any emails using "Hello there" and "Hi" together?

**Yes — Document Verified (confirmed).**

1. `enablement_templates.document_verified_value` body includes `<p>Hi {{first_name}},</p>`.
2. `enablement_service.deliver_email` sends only `{subject, message}` — **no `client_name`**.
3. When DB row absent, `EmailService` ADMIN_MANUAL fallback renders:

```1813:1816:backend/services/email_service.py
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    {ref_line}
                    <p>{body_content}</p>
```

Screenshot header **"Compliance Vault Pro"** (not governed layout title) confirms this legacy fallback path.

### 10. Are any production emails hardcoding `https://pleerity.com`?

**Yes** (customer-facing send paths):

| File | Usage |
|------|-------|
| `lead_automation_service.py:401` | Footer in compliance gap / automation emails |
| `risk_lead_email_service.py:66` | Risk nurture footer link |
| `lead_followup_service.py:227` | Markdown body reference |

Test/staging `@pleerity.com` addresses and CMS copy are out of scope for live customer sends but exist in repo.

### 11. Are domains sourced from APP_BASE_URL or hardcoded?

**Partially governed.**

- **Governed:** `get_app_base_url(for_email_links=True)` default `https://pleerityenterprise.co.uk`; `get_branding_website_url()`; canonical layout footer; lead automation **CTA** uses `app_base`.
- **Hardcoded:** Legacy inline footers above; `utils/branding.WEBSITE_URL` constant exists as backward-compat but canonical paths use resolver.

### 12. Are footers consistent?

**No.** Four distinct footer families (see evidence `footer_matrix`):

1. Canonical — company, tagline, support sentence, website from APP_BASE_URL, security note
2. Legacy ADMIN_MANUAL — `_build_email_footer`
3. Lead automation one-liner with `pleerity.com`
4. Risk lead disclaimer + `pleerity.com`

### 13. Are CTA labels consistent?

**No.** Examples:

| Label | Context |
|-------|---------|
| Open portal to review | COMPLIANCE_ALERT |
| Open portal for details | Lifecycle reminders |
| Continue | Compliance gap automation |
| Start Compliance Monitoring | Risk nurture |
| Go to your dashboard | Portal ready |

### 14. Are unsubscribe / notification preference links consistent?

**No.**

- COMPLIANCE_ALERT code path: `show_preferences_link=True` → `/settings/notifications`
- Lifecycle reminders: same pattern
- Legacy gap emails, enablement, ADMIN_MANUAL fallback: **no** preferences link
- Tenant invite: explicitly `show_preferences_link=False`

### 15. Are emails clear that the portal is authoritative where required?

**Partial.**

COMPLIANCE_ALERT code-built body includes:

> *"This email is informational. The portal remains authoritative for obligation state, evidence, and when scores last recalculated."*

Enablement `status_changed_awareness` has weaker wording. Compliance gap emails omit portal authority statement.

### 16. Are old templates still reachable from live workflows?

**Yes.**

| Workflow | Template | Legacy aspect |
|----------|----------|---------------|
| `jobs.check_compliance_status_changes` | COMPLIANCE_ALERT | Missing colour injection |
| Enablement DOCUMENT_VERIFIED | ENABLEMENT_DELIVERY | Double greeting / legacy shell |
| `lead_automation_service` compliance_gap | LEAD_FOLLOWUP | Inline shell + pleerity.com |
| Risk lead nurture | LEAD_FOLLOWUP / custom HTML | Inline shell + pleerity.com |
| Any admin-manual without DB row | ADMIN_MANUAL | Compliance Vault Pro header |

### 17. Which templates are production-facing?

81 EMAIL `template_key` values in seed. ~69 are client, contractor, or lead-facing. Internal-only keys include `INTERNAL_ALERT`, `PENDING_VERIFICATION_DIGEST`, `COMPLIANCE_SLA_ALERT`, auth admin MFA, provisioning/Stripe failure admin alerts, etc. (see evidence `template_inventory.production_facing`).

---

## Screenshot correlation

| User observation | Code explanation |
|------------------|------------------|
| AMBER in table appears red | `new_color` default `#dc2626` |
| AMBER previous appears green | `prev_color` default `#22c55e` |
| Legend AMBER correct | Static `#f59e0b` in legend HTML |
| Document Verified: Hello there + Hi , | ADMIN_MANUAL fallback + enablement `Hi {{first_name}}` with empty name |
| Gap emails: older look + pleerity.com | `lead_automation_service` inline HTML |
| Gap reminder: same | Step 2 same shell |

---

## Shell classification (81 template keys)

| Shell class | Count | Notes |
|-------------|-------|-------|
| `canonical_code_built` | 19 | Orchestrator bypass → EmailService + `build_customer_email_layout` |
| `hybrid` | 7 | Context-dependent bypass |
| `legacy_or_db_fragment` | 32 | `admin-manual` family — DB fragment, full HTML bypass, or legacy fallback |
| `db_first_with_code_fallback` | 22 | Includes COMPLIANCE_ALERT, onboarding, auth emails |
| `internal_layout` | 1 | `internal-alert` |

---

## Key source files

| File | Role |
|------|------|
| `email_templates/email_layout.py` | Canonical shell |
| `services/email_service.py` | Code-built bodies, legacy ADMIN_MANUAL |
| `services/notification_orchestrator.py` | Render ordering, send |
| `services/branding_resolver_service.py` | DB fragment wrapping |
| `notification_template_seed_definitions.py` | template_key ↔ alias |
| `services/jobs.py` | COMPLIANCE_ALERT trigger |
| `services/enablement_templates.py` / `enablement_service.py` | Enablement email content + send |
| `services/lead_automation_service.py` | Compliance gap sequence |
| `services/risk_lead_email_service.py` | Risk nurture emails |
| `utils/app_urls.py` / `utils/branding.py` | Domain and footer URL authority |

---

## Production impact

**Severity:** medium–high (user-visible branding/trust defects)

- Misleading RAG colours in compliance alerts (accessibility and compliance communication risk).
- Unprofessional double greeting on document verified emails.
- Wrong public domain on gap/risk emails (`pleerity.com` vs `pleerityenterprise.co.uk`).
- Inconsistent portal authority messaging.

**Affected live workflows:** listed in evidence `production_impact.affected_live_workflows`.

---

## Recommended global fix (do not implement in this audit)

Introduce an **Email Presentation Authority** module — not per-template patches:

1. **`status_colors.for_rag(status) -> hex`** — single map; used by `jobs`, `email_service`, any DB template generators.
2. **`greeting.for_client(client_doc) -> str`** — one governed pattern; ban greetings inside enablement HTML fragments.
3. **`shell.render_customer_email(...)`** — thin wrapper over `build_customer_email_layout`; **prohibit new inline `<html>` shells** in services.
4. **`jobs.check_compliance_status_changes`** — enrich `affected_properties` with `prev_color`/`new_color` at send time (or shared enricher in orchestrator).
5. **`enablement_service.deliver_email`** — pass `client_name` / resolved greeting; strip `Hi` from fragments.
6. **`lead_automation_service` + `risk_lead_email_service`** — migrate to orchestrator + canonical shell; remove `pleerity.com` literals.
7. **`notification_orchestrator`** — add `compliance-alert` code bypass (like `monthly-digest`) **or** enforce colour enrichment before DB render.
8. **DB governance** — align `compliance-alert` / `admin-manual` rows with code SSOT; prevent ENABLEMENT from falling through to legacy ADMIN_MANUAL fallback.

---

## Acceptance

**Verdict C proven:** Multiple legacy templates remain reachable; domain, colour, and greeting logic are duplicated and require a shared Email Presentation Authority.

No code fixes were made during this audit. No production changes. No merge to `main`.
