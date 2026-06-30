# PRESENTATION-AUTHORITY-ALIGNMENT-01

**Programme:** PRESENTATION-AUTHORITY-ALIGNMENT-01  
**Branch:** `develop`  
**Date:** 2026-06-30  
**Verdict:** Implementation complete on develop (staging validation recommended)  
**Production touched:** No  

---

## Executive summary

This programme closes presentation drift identified by **ONBOARDING-EXPERIENCE-LIFECYCLE-AUTHORITY-AUDIT-01 (Verdict B)** without modifying RAOD-01 backend KPI authority, reconciliation rules, or risk calendar semantics.

Central presentation modules now mirror backend lifecycle truth. High-impact surfaces (onboarding counts, documents wizard, evidence chips, digest copy, Command Centre lens labelling, dashboard risk headlines) align with governed copy.

---

## What changed

### Central presentation authority

| Module | Role |
|--------|------|
| `backend/services/lifecycle_authority_copy.py` | Digest/report governed phrases |
| `frontend/src/utils/lifecycleAuthorityCopy.js` | FE mirror — overdue sublines, risk headlines |
| `frontend/src/utils/presentationAuthority.js` | Count semantics parser, checklist documents step |

### P1 audit fixes implemented

| ID | Fix |
|----|-----|
| UX-01 | `OnboardingStatusPage` consumes semantic setup-status counts + explains 18 vs 12 |
| UX-02 | `ClientDashboard` documents wizard uses `setup_presentation.documents_step_recommended` from checklist API |
| UX-03 | `evidenceStatus.js` OVERDUE subline no longer says “affecting compliance” |

### Additional alignment

- Monthly digest: “missing evidence” → “evidence required” / “calendar overdue”
- Command Centre: triage lens subtitle + score-tracked semantics note
- Dashboard risk snippets: governed `riskSignalPresentationHeadline`
- Command Centre missing-evidence strip: “need evidence” wording
- Recommendation hierarchy documented in `workspaceOrientationCopy.js` and `PRESENTATION_AUTHORITY_CHAIN.md`

---

## Presentation matrix (before → after)

| Surface | Before | After |
|---------|--------|-------|
| Onboarding status counts | Raw `requirements_count` | Tracked primary + identified secondary + footnote |
| Documents setup wizard | FE `needsDocumentsStep` inference | Backend `setup_presentation` |
| OVERDUE chip subline | “Overdue — affecting compliance.” | Calendar overdue — not legal verdict |
| Monthly digest upload actions | “— missing evidence” | “— evidence required” |
| Command Centre header | Generic action copy | Portfolio triage lens labelled |

---

## Count semantics matrix

| Metric | Authority field | UI rule |
|--------|-----------------|---------|
| Actively tracked | `requirements_tracked_attention_count` | Primary headline |
| Identified total | `requirements_count` / runtime visible | Secondary when higher |
| Explanation | `COUNT_SEMANTICS_EXPLANATION` | Footnote when counts diverge |

---

## Recommendation hierarchy

1. **Onboarding checklist** — `next_step` from `onboarding_checklist_service`
2. **Today** — operational inbox from `client_priority_stream`
3. **Command Centre** — portfolio triage urgent slice (labelled)
4. **Compliance score** — KPI recommendations from `calculate_compliance_score`

---

## Risk wording matrix

| Context | Governed wording |
|---------|------------------|
| Calendar OVERDUE (legacy chip path) | Past effective expiry — not legal compliance verdict |
| Risk signal (no API label) | Review suggested / operational follow-up |
| Backend electrical risk | Unchanged — RAOD calendar-confirmed only |

---

## Regression tests

| Suite | Result |
|-------|--------|
| `test_presentation_authority_alignment_01.py` + RAOD drift tests | 9 passed |
| Jest: `presentationAuthority`, `lifecycleAuthorityCopy`, `evidenceStatus` | 18 passed |

---

## Governance documentation

- `docs/governance/PRESENTATION_AUTHORITY_CHAIN.md` (new)
- `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` (PAA-01 section)

---

## Remaining risks (not blocking develop)

| ID | Surface | Notes |
|----|---------|-------|
| R1 | Admin support snapshot | May still show raw `requirements_count` |
| R2 | `clientTopPriorityRanking.js` | Presentation re-rank within urgent lane — intentional, documented |
| R3 | Property detail risk cards | Extend `riskSignalPresentationHeadline` in follow-up |
| R4 | PDF export templates | Not individually re-audited this pass |

---

## Production recommendation

**Do not promote directly.** Deploy to staging, run first-login walkthrough:

1. Onboarding status shows tracked + identified counts with footnote when applicable  
2. Documents wizard appears only when checklist `upload_or_compliance_action` incomplete  
3. OVERDUE chips do not imply legal breach  
4. RAOD regression suite still green  

Then follow existing Requirement Authority staging gate.

---

## RAOD regression statement

No changes to:

- `filter_requirement_rows_for_client_runtime_surfaces`
- `requirement_authority_reconciliation_service`
- `_rule_electrical` calendar-confirmed semantics
- Portal KPI projection pipeline

Presentation-only layer added on top of existing authority.
