# Report Presentation Authority

**Programme:** REPORT-PRESENTATION-AUTHORITY-01  
**Authority version:** `report_presentation_v1`  
**Module:** `backend/report_presentation/`

---

## Purpose

Report Presentation Authority is the **final presentation layer** for professional reports. It governs how validated compliance data is communicated to readers — it does **not** determine compliance facts.

Reports must read as professional publications suitable for landlords, insurers, lenders, solicitors, regulators, and tribunals.

---

## Authority chain

```
Requirement Authority ──┐
Lifecycle Authority  ──┼──► Report datasets (unchanged)
Evidence Authority   ──┤
Score Authority      ──┤
Navigation Authority ──┘
         │
         ▼
Email Presentation Authority (emails only)
Lifecycle Communication Authority (portal/reminders/digest copy)
         │
         ▼
Report Presentation Authority (PDF/ZIP/CSV presentation)
         │
         ▼
Customer-facing report output
```

Report Presentation Authority **consumes** upstream authorities. It must not duplicate lifecycle, requirement, evidence, or score determination logic.

---

## Owned responsibilities

| Area | Module |
|------|--------|
| Reader profiles (Executive / Operational / Evidential) | `profiles.py` |
| Business chronology & layered timeline | `timeline.py` |
| Actor labels | `actors.py` |
| Timestamp formatting | `timestamps.py` |
| Executive summary structure | `executive.py` |
| Recommended next actions | `actions.py` |
| Evidence row presentation | `evidence.py` |
| Confidence & assurance wording | `confidence.py` |
| Technical / governance appendix copy | `appendix.py` |
| Engineering language governance | `technical_language.py` |
| Facade | `authority.py` |

---

## Reader profiles

| Profile | Audience | Timeline depth | Technical appendix |
|---------|----------|----------------|-------------------|
| **Executive** | Landlords, investors, senior management | Condensed | No |
| **Operational** | Property managers, compliance teams | Standard | Yes |
| **Evidential** | Councils, solicitors, insurers, tribunals | Full | Yes |

Profiles are resolved per report class via `DEFAULT_PROFILE_BY_REPORT_CLASS` in `constants.py`.

---

## Layered chronology

Audit events are **never modified at persistence**. Presentation produces:

1. **Primary layer** — business narrative (Compliance chronology)
2. **Supporting layer** — technical audit record appendix with original actions, IDs, forensic timestamps

Engineering telemetry (`RISK_SIGNAL_REGEN_*`, `COMPLIANCE_RECALC_SLA_*`) is suppressed from the primary layer but preserved in the technical appendix.

---

## Integration points

| Consumer | Usage |
|----------|-------|
| `report_pdf_templates.py` | Compliance chronology, technical appendix, recommended actions, readiness intro |
| `report_evidence_readiness_operational.py` | Grouped operational chronology, humanize delegation |
| `professional_reports.py` | Professional Audit Log PDF executive summary + chronology |

---

## Non-goals

- Report calculation or dataset assembly
- Compliance / lifecycle / evidence determination
- Scoring logic
- Audit persistence
- Report API contract changes
- Immutable artifact bytes or manifest checksum algorithms

---

## Regression tests

`backend/tests/test_report_presentation_authority.py`  
Plus updated tests in `test_report_pdf_templates.py` and `test_report_evidence_readiness_operational.py`.

---

## Related governance

- `REPORT-PRESENTATION-AUTHORITY-AUDIT-01` — audit findings  
- `report_human_language_v1.py` — label maps (consumed, not replaced)  
- `reporting_semantics_v1.py` — export grades (unchanged)  
- `LIFECYCLE_COMMUNICATION_AUTHORITY.md` — portal/reminder copy  
- `EMAIL_PRESENTATION_AUTHORITY.md` — email shell copy
