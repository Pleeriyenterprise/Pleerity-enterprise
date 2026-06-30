# Presentation authority chain

**Programme:** PRESENTATION-AUTHORITY-ALIGNMENT-01  
**Status:** Active on `develop`  
**Backend KPI authority:** `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` (unchanged)

This document governs how **user-facing copy and counts** must reflect backend lifecycle authority without re-deriving business rules in React.

---

## Presentation authority chain

```text
Backend lifecycle / KPI authority
  ├── requirement_evidence_authority (evidence_authority.state)
  ├── client_requirement_lifecycle (client_lifecycle_state)
  ├── requirement_client_runtime_surface (projection + counts)
  ├── onboarding_checklist_service (setup + setup_presentation)
  ├── client_priority_stream → unified_tasks (operational next actions)
  └── calculate_compliance_score.stats (KPI recommendations)
        ↓
Presentation modules (copy only — no inference)
  ├── backend/services/lifecycle_authority_copy.py
  ├── frontend/src/utils/lifecycleAuthorityCopy.js
  ├── frontend/src/utils/presentationAuthority.js
  ├── frontend/src/utils/reportingSemanticsLabels.js
  └── frontend/src/utils/workspaceOrientationCopy.js
        ↓
Surfaces (consume API fields + presentation modules)
```

---

## Count semantics

| Field | Meaning | Use in UI |
|-------|---------|-----------|
| `requirements_count` | Legacy raw Mongo materialised rows | Fallback only when semantic fields absent |
| `requirements_runtime_visible_count` | Client-surface-visible after runtime filter | Secondary identified total |
| `requirements_tracked_attention_count` | DOCUMENT/JOB tracked attention | **Primary headline count** |
| `requirements_count_semantics` | Explains tracked lens | Footnote when raw > tracked |

**Rule:** Never show raw count alone when semantic fields exist. Always explain divergence.

---

## Recommendation hierarchy

Multiple recommendation lenses are **intentional**. Label them:

| Lens | Authority | Surface |
|------|-----------|---------|
| Onboarding checklist | `onboarding_checklist_service` | Dashboard setup overlay |
| Operational inbox | `client_priority_stream` | Today |
| Portfolio triage | `command_center_service` urgent slice | Command Centre |
| KPI recommendations | `calculate_compliance_score` | Compliance score page / digest drivers |

Frontend must not re-rank urgent tasks in a way that contradicts backend `take_action` without documenting presentation-only ordering.

---

## Lifecycle wording standards

| State | Approved customer language | Forbidden conflation |
|-------|---------------------------|----------------------|
| Missing evidence | Evidence required / No document uploaded | Compliance breach |
| Pending verification | Awaiting verification / Platform verification pending | Missing evidence (KPI) |
| Calendar overdue | Past effective expiry — renew or confirm dates | Legal non-compliance verdict |
| Confirmed breach | Only when backend explicitly models confirmed non-compliance | Used for PENDING/MISSING |

Central copy: `lifecycleAuthorityCopy.js` / `lifecycle_authority_copy.py`.

---

## Risk wording

Risk signals are **operational prioritisation**, not KPI truth or legal findings.

- Prefer `risk_type_label_client` from API.
- Fallback headlines must not say “Safety concern” or “Compliance breach” unless backend supplies that label.

---

## Related governance

- `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md`
- `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`
- `backend/docs/audit/onboarding_experience_lifecycle_authority_01/` (audit that motivated this programme)
