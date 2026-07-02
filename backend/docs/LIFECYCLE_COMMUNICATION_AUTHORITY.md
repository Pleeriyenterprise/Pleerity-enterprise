# Lifecycle Communication Authority

**Programme:** `LIFECYCLE-COMMUNICATION-AUTHORITY-01`  
**Authority version:** `lifecycle_communication_v1`  
**Branch:** `develop`

## Purpose

Single governed presentation layer that transforms authoritative lifecycle state into consistent customer-facing communication (WHY / WHAT / WHEN / HOW / WHAT NEXT).

Does **not** define lifecycle rules, requirement determination, reminder schedules, notification routing, or scoring.

## Module

| Module | Responsibility |
|--------|----------------|
| `lifecycle_communication/resolver.py` | `resolve_customer_communication()` — canonical resolver |
| `lifecycle_communication/context.py` | Family inference from authoritative row fields |
| `lifecycle_communication/copy.py` | Reason, action, digest, risk copy |
| `lifecycle_communication/verbs.py` | Governed lifecycle verbs |
| `lifecycle_communication/headings.py` | Section and surface headings |
| `lifecycle_communication/completion.py` | Completion and next-step wording |
| `lifecycle_communication/registry.py` | Lifecycle Communication Registry |
| `lifecycle_communication/authority.py` | `LifecycleCommunicationAuthority` facade |

## Authority chain

```
Lifecycle Authority (technical SSOT)
    ↓ attention_kind, lifecycle_semantics, client_lifecycle_label
Requirement Authority
    ↓ requirement metadata, evidence modes
Navigation Authority
    ↓ take_action routes (unchanged)
Lifecycle Communication Authority  ← this programme
    ↓ governed customer wording
Presentation Authority / Email Presentation Authority
    ↓ layout, colours, shell (unchanged)
Customer surfaces
```

## Rules

1. **Consume, do not reclassify** — use `lifecycle_attention_kind`, `lifecycle_semantics`, `client_lifecycle_label`, `take_action`.
2. **No generic unsupported reasons** — avoid bare "Action required" when family-specific reason exists.
3. **No certificate/expiry leakage** — declarations, reviews, operational items use family verbs.
4. **CTA consumption** — `take_action` routes unchanged; LCA governs label wording via `primary_cta`.
5. **No per-requirement hardcoding** — family-level models only (requirement-specific CTAs remain in action resolver where already governed).

## Integration points

| Consumer | Integration |
|----------|-------------|
| `requirement_action_resolver` | `customer_communication` on API envelope; LCA CTA labels |
| `requirement_truth` | Attaches `customer_communication` to client rows |
| `email_service` | Grouped reminder headings, semantic lines, lifecycle intros |
| `lifecycle_reminder_template_registry` | Reminder spec/subject delegation |
| `enablement_service` + `enablement_templates` | LCA template context tokens |
| `monthly_digest_operational_intelligence` | Family-aware digest posture labels |
| `risk_signal_service` | Governed `recommended_action` copy |
| `frontend/evidenceStatus.js` | Consumes API `customer_communication` for chips |

## Registry

`LifecycleCommunicationAuthority.registry_as_list()` — 14 lifecycle families × supported surfaces.

## Explicitly out of scope

- Reminder scheduling and timing
- Notification routing and orchestration
- Lifecycle rule changes
- Requirement determination / scoring
- Today Authority bucket semantics
- Email Presentation Authority (shell/greeting/colours)

## Related audits

- `docs/audit/lifecycle_communication_authority_01/LIFECYCLE_COMMUNICATION_AUTHORITY_AUDIT.md`
- `docs/audit/lifecycle_communication_authority_01/LIFECYCLE_COMMUNICATION_AUTHORITY_IMPLEMENTATION_REPORT.md`
- `docs/EMAIL_PRESENTATION_AUTHORITY.md`
