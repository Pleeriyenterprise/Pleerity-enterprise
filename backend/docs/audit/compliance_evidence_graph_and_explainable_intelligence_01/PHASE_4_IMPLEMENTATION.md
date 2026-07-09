# Phase 4 Implementation — Explain This UI & Compliance Replay

**Stage:** 4 — Graph Service consumers (admin UI)  
**Predecessor:** Phase 3 (local)

## Summary

- **`ExplainThisPanel.js`** — calls `explainDecision` / scope explain via Graph Service API
- **`ComplianceReplayDrawer.js`** — calls `replayDecision`
- **`DecisionDiffPanel.js`** — calls `compareDecisions`
- **Admin Decision Explorer** — `AdminComplianceDecisionExplorerPage.js` at `/admin/compliance/decisions` (list, explain, replay, compare)
- **API client** — `frontend/src/api/complianceGraphApi.js`
- **Admin KPI migration** — `compliance_explain_admin_service.py` delegates to `enrich_admin_compliance_explain` when `COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled`

## Deliverables

| Artifact | Path |
|----------|------|
| Explain This panel | `frontend/src/components/compliance/ExplainThisPanel.js` |
| Replay drawer | `frontend/src/components/compliance/ComplianceReplayDrawer.js` |
| Decision diff | `frontend/src/components/compliance/DecisionDiffPanel.js` |
| Decision explorer page | `frontend/src/pages/AdminComplianceDecisionExplorerPage.js` |
| Graph API client | `frontend/src/api/complianceGraphApi.js` |
| Route + nav | `App.js`, `UnifiedAdminLayout.js` |
| Admin explain enrichment | `services/compliance_explain_admin_service.py` |

## Feature flags

| Mode | Admin UI (explorer) | KPI graph enrichment |
|------|---------------------|----------------------|
| `disabled` | Routes return insufficient | Legacy explain only |
| `shadow` | Explorer usable for validation | Legacy explain only |
| `enabled` | Full consumer path | Graph-backed score decision attached |

## Exit criteria (plan)

- Admin can explain/replay/compare decisions from UI ✓
- No direct storage queries from frontend ✓
- `compliance_explain_admin_service` uses Graph Service when enabled ✓

## Manual test checklist

1. Set `COMPLIANCE_EVIDENCE_GRAPH_MODE=shadow` on staging
2. Open **Admin → Compliance → Decision Explorer**
3. Enter `client_id`, load decisions
4. Select a decision → Explain This panel loads envelope
5. Open Replay drawer → snapshot timeline visible
6. Enter two decision IDs in Diff panel → compare loads
7. With `enabled`, verify admin KPI explain includes `graph_service.latest_score_decision`
