# Phase 5 Staging Smoke Report

**Run tag:** `20260629T115845Z`
**Verdict:** `PHASE_5_TIER1_STAGING_ACCEPTED`

**Phase 5 Tier 1 staging accepted:** **Yes**

## Deploy

{
  "aligned": true,
  "commit_sha": "b6edbb27fe1f9a3ae39cdbade166a9d04c9f4662",
  "attempts": 1
}

## Feature flag matrix (expected staging)

| Flag | Expected |
|------|----------|
| COMPLIANCE_EVIDENCE_GRAPH_MODE | enabled |
| COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED | false |
| AI_ENABLED | false |

## Tier 1 smoke

- tier1_explain_decision: pass
- tier1_replay_decision: pass
- tier1_compare_decision: pass
- tier1_trace_evidence: pass
- tier1_trace_operational_impact: pass
- tier1_insufficient_safe: pass
- tier1_cross_tenant_blocked: pass
- tier1_no_tier2_when_narration_disabled: pass
- tier1_no_new_narration_records: pass
- tier1_read_only_graph_health_ok: pass

## Tier 2 controlled

{
  "mode": "local_mocked_llm",
  "passed_checks": 5
}

## Regression

{
  "exit_code": 0,
  "passed": 72,
  "failed": 0
}

## Remaining risks

- Tier 2 HTTP on staging deferred until narration flags explicitly enabled.
- Tier 2 local mock validates citation pipeline without live LLM on staging.
- No customer-facing intelligence UI shipped.
- Production flags unchanged.
- Do not proceed to Tier 2 staging, AI narration, or next Phase 5 slice without explicit approval.

**Next slice:** Phase 5 Tier 1 staging accepted. Do not proceed to Tier 2, AI narration, or next slice without explicit approval.
