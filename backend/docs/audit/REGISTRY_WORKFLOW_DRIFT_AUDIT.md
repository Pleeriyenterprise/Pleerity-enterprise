# Live registry / runtime workflow drift audit

**Findings (deduped):** 127
**Scenarios:** 128 (canonical codes × jurisdictions)

**Scope note:** No published-registry Mongo overlay — uses code defaults + decision-record `client_workflow_class` fallbacks only. Production drift may differ where registry publishes `registry_metadata.evidence_resolution`.

## Methodology

Synthetic requirement rows per canonical code × jurisdiction; effective_evidence_resolution + resolve_take_action_envelope + enrich_take_action_envelope_for_client; compute_workflow_mismatch_flags with decision-record reference (no published registry overlay); explicit policy-vs-reference checks; engine vs external-assessment heuristic for lead_testing.

## Counts by drift type

- **WORKFLOW_CLASS_DRIFT:** 62
- **EVIDENCE_MODE_DRIFT:** 28
- **REPORTING_SEMANTIC_DRIFT:** 18
- **CTA_DRIFT:** 8
- **JURISDICTION_DRIFT:** 7
- **CANONICAL_IDENTITY_DRIFT:** 4

## Counts by severity

- **HIGH:** 73
- **MEDIUM:** 43
- **LOW:** 8
- **CRITICAL:** 3

## Findings by workflow class (runtime)

### EXTERNAL_ASSESSMENT_EVIDENCE

- **HIGH** [JURISDICTION_DRIFT] `lead_testing` (england): LEAD_TESTING_UNSUPPORTED_JURISDICTION — lead_testing surfaced outside Scotland (jurisdiction='england').
- **HIGH** [JURISDICTION_DRIFT] `lead_testing` (wales): LEAD_TESTING_UNSUPPORTED_JURISDICTION — lead_testing surfaced outside Scotland (jurisdiction='wales').
- **HIGH** [JURISDICTION_DRIFT] `lead_testing` (northern_ireland): LEAD_TESTING_UNSUPPORTED_JURISDICTION — lead_testing surfaced outside Scotland (jurisdiction='northern_ireland').
- **HIGH** [WORKFLOW_CLASS_DRIFT] `lead_testing` (england): ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE — compliance_requirement_engine defaults lead_testing to certificate-style engine spec; workflow reference is EXTERNAL_ASSESSMENT_EVIDENCE — surfaces may present 
- **HIGH** [WORKFLOW_CLASS_DRIFT] `lead_testing` (scotland): ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE — compliance_requirement_engine defaults lead_testing to certificate-style engine spec; workflow reference is EXTERNAL_ASSESSMENT_EVIDENCE — surfaces may present 
- **HIGH** [WORKFLOW_CLASS_DRIFT] `lead_testing` (wales): ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE — compliance_requirement_engine defaults lead_testing to certificate-style engine spec; workflow reference is EXTERNAL_ASSESSMENT_EVIDENCE — surfaces may present 
- **HIGH** [WORKFLOW_CLASS_DRIFT] `lead_testing` (northern_ireland): ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE — compliance_requirement_engine defaults lead_testing to certificate-style engine spec; workflow reference is EXTERNAL_ASSESSMENT_EVIDENCE — surfaces may present 
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_cleaning` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_cleaning` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_cleaning` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_cleaning` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_fire_doors` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_fire_doors` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_fire_doors` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `communal_fire_doors` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `emergency_lighting` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `emergency_lighting` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `emergency_lighting` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `emergency_lighting` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_extinguisher` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_extinguisher` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_extinguisher` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_extinguisher` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=REMEDIATION_JOB but enriched workflow_class=EXTERNAL_ASSESSMENT_EVIDENCE (after LEGACY≈DOCUMENT normalization: REMEDIATION_JOB vs EXTERNAL_ASSES

### GUIDANCE_ONLY

- **CRITICAL** [EVIDENCE_MODE_DRIFT] `occupation_contract` (england): POLICY_FALLBACK_VS_REFERENCE_GUIDED — effective_evidence_resolution falls back to LEGACY_DOCUMENT_UPLOAD while decision-record reference is GUIDED_DECLARATION — structured-first defaults missing for
- **CRITICAL** [EVIDENCE_MODE_DRIFT] `occupation_contract` (scotland): POLICY_FALLBACK_VS_REFERENCE_GUIDED — effective_evidence_resolution falls back to LEGACY_DOCUMENT_UPLOAD while decision-record reference is GUIDED_DECLARATION — structured-first defaults missing for
- **CRITICAL** [EVIDENCE_MODE_DRIFT] `occupation_contract` (northern_ireland): POLICY_FALLBACK_VS_REFERENCE_GUIDED — effective_evidence_resolution falls back to LEGACY_DOCUMENT_UPLOAD while decision-record reference is GUIDED_DECLARATION — structured-first defaults missing for
- **HIGH** [CTA_DRIFT] `fitness_for_human_habitation` (england): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `fitness_for_human_habitation` (scotland): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `fitness_for_human_habitation` (wales): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `fitness_for_human_habitation` (northern_ireland): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `repairing_standard` (england): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `repairing_standard` (scotland): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `repairing_standard` (wales): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [CTA_DRIFT] `repairing_standard` (northern_ireland): CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY — Condition standards must not resolve to document-upload-primary CTA.
- **HIGH** [EVIDENCE_MODE_DRIFT] `fitness_for_human_habitation` (england): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `fitness_for_human_habitation` (scotland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `fitness_for_human_habitation` (wales): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `fitness_for_human_habitation` (northern_ireland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (england): WALES_OCCUPATION_CONTRACT_GUIDED_DECLARATION_DOCUMENT_ONLY — Wales occupation contract expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_r
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (england): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=GUIDED_DECLARATION: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (england): GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD — GUIDED_DECLARATION reference but allowed_evidence_modes lacks STRUCTURED_DECLARATION
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (scotland): WALES_OCCUPATION_CONTRACT_GUIDED_DECLARATION_DOCUMENT_ONLY — Wales occupation contract expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_r
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (scotland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=GUIDED_DECLARATION: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (scotland): GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD — GUIDED_DECLARATION reference but allowed_evidence_modes lacks STRUCTURED_DECLARATION
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (northern_ireland): WALES_OCCUPATION_CONTRACT_GUIDED_DECLARATION_DOCUMENT_ONLY — Wales occupation contract expects STRUCTURED_DECLARATION + DOCUMENT_UPLOAD but only DOCUMENT_UPLOAD is allowed (published registry override or legacy evidence_r
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (northern_ireland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=GUIDED_DECLARATION: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `occupation_contract` (northern_ireland): GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD — GUIDED_DECLARATION reference but allowed_evidence_modes lacks STRUCTURED_DECLARATION
- **HIGH** [EVIDENCE_MODE_DRIFT] `repairing_standard` (england): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `repairing_standard` (scotland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `repairing_standard` (wales): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [EVIDENCE_MODE_DRIFT] `repairing_standard` (northern_ireland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=CONDITION_STANDARD_ACTIVE_STANDARD: evidence_modes allow document-only completion path but this workflow class requires structured-first resoluti
- **HIGH** [JURISDICTION_DRIFT] `fitness_for_human_habitation` (scotland): CONDITION_STANDARD_UNSUPPORTED_JURISDICTION — fitness_for_human_habitation surfaced in Scotland where planner support is not expected.
- **HIGH** [JURISDICTION_DRIFT] `repairing_standard` (england): CONDITION_STANDARD_UNSUPPORTED_JURISDICTION — repairing_standard surfaced outside Scotland (jurisdiction='england').
- **HIGH** [JURISDICTION_DRIFT] `repairing_standard` (wales): CONDITION_STANDARD_UNSUPPORTED_JURISDICTION — repairing_standard surfaced outside Scotland (jurisdiction='wales').
- **HIGH** [JURISDICTION_DRIFT] `repairing_standard` (northern_ireland): CONDITION_STANDARD_UNSUPPORTED_JURISDICTION — repairing_standard surfaced outside Scotland (jurisdiction='northern_ireland').
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fitness_for_human_habitation` (england): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fitness_for_human_habitation` (scotland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fitness_for_human_habitation` (wales): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fitness_for_human_habitation` (northern_ireland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (england): WORKFLOW_COMPLETION_SEMANTIC_DRIFT — heuristic: completion / obligation / remediation meanings may be conflated (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md — Workflow Execution & System Behaviour Semanti
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (england): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (scotland): WORKFLOW_COMPLETION_SEMANTIC_DRIFT — heuristic: completion / obligation / remediation meanings may be conflated (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md — Workflow Execution & System Behaviour Semanti
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (scotland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (northern_ireland): WORKFLOW_COMPLETION_SEMANTIC_DRIFT — heuristic: completion / obligation / remediation meanings may be conflated (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md — Workflow Execution & System Behaviour Semanti
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `occupation_contract` (northern_ireland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `repairing_standard` (england): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `repairing_standard` (scotland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `repairing_standard` (wales): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `repairing_standard` (northern_ireland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [WORKFLOW_CLASS_DRIFT] `occupation_contract` (england): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=guidance; runtime=workflow_class=GUIDANCE_ONLY; action_type=OBLIGATION; primary_intent=view_guidance; primary_kind=naviga
- **HIGH** [WORKFLOW_CLASS_DRIFT] `occupation_contract` (scotland): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=guidance; runtime=workflow_class=GUIDANCE_ONLY; action_type=OBLIGATION; primary_intent=view_guidance; primary_kind=naviga
- **HIGH** [WORKFLOW_CLASS_DRIFT] `occupation_contract` (northern_ireland): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=guidance; runtime=workflow_class=GUIDANCE_ONLY; action_type=OBLIGATION; primary_intent=view_guidance; primary_kind=naviga
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `occupation_contract` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=GUIDED_DECLARATION but enriched workflow_class=GUIDANCE_ONLY (after LEGACY≈DOCUMENT normalization: GUIDED_DECLARATION vs GUIDANCE_ONLY).
- … 2 more

### GUIDED_DECLARATION

- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (england): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (scotland): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (wales): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)
- **LOW** [CANONICAL_IDENTITY_DRIFT] `deposit_pi` (northern_ireland): ALIAS_LEGACY_STORAGE_SLUG — documented legacy storage slug 'deposit_prescribed_info' maps to canonical 'deposit_pi' (data hygiene / migration; workflow aligns when resolver uses canonical)

### GUIDED_EVIDENCE_RESOLUTION

- **LOW** [WORKFLOW_CLASS_DRIFT] `smoke_heat_alarms` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **LOW** [WORKFLOW_CLASS_DRIFT] `smoke_heat_alarms` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **LOW** [WORKFLOW_CLASS_DRIFT] `smoke_heat_alarms` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **LOW** [WORKFLOW_CLASS_DRIFT] `smoke_heat_alarms` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk_evidence` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk_evidence` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk_evidence` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_fire_risk_evidence` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=GUIDED_EVIDENCE_RESOLUTION (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs GUIDED_EVIDENCE_RE

### LEGACY_DOCUMENT_UPLOAD

- **HIGH** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (england): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=MULTI_EVIDENCE: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (scotland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=MULTI_EVIDENCE: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (wales): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=MULTI_EVIDENCE: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (northern_ireland): WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION — governance key=MULTI_EVIDENCE: evidence_modes allow document-only completion path but this workflow class requires structured-first resolution
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fire_risk_assessment` (england): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fire_risk_assessment` (scotland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fire_risk_assessment` (wales): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [REPORTING_SEMANTIC_DRIFT] `fire_risk_assessment` (northern_ireland): WORKFLOW_SEMANTIC_COLLAPSE_RISK — heuristic: evidence/upload/primary-CTA shape suggests collapsing distinct lifecycle meanings (see WORKFLOW_BEHAVIOUR_GOVERNANCE.md)
- **HIGH** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (england): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=DOCUMENT; primary_intent=upload_evidence; primary_ki
- **HIGH** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (scotland): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=DOCUMENT; primary_intent=upload_evidence; primary_ki
- **HIGH** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (wales): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=DOCUMENT; primary_intent=upload_evidence; primary_ki
- **HIGH** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (northern_ireland): RESOLVER_CTA_MISMATCH — reference_family=guided runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=DOCUMENT; primary_intent=upload_evidence; primary_ki
- **HIGH** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (england): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (scotland): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (wales): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (northern_ireland): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `property_classification` (england): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `property_classification` (scotland): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `property_classification` (wales): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **HIGH** [WORKFLOW_CLASS_DRIFT] `property_classification` (northern_ireland): RESOLVER_CTA_MISMATCH — reference_family=guidance runtime_family=document; runtime=workflow_class=LEGACY_DOCUMENT_UPLOAD; action_type=OBLIGATION; primary_intent=?; primary_kind=?; evid
- **MEDIUM** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (england): MULTI_EVIDENCE_DOCUMENT_ONLY — reference expects multi-mode evidence but only DOCUMENT_UPLOAD is allowed
- **MEDIUM** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (scotland): MULTI_EVIDENCE_DOCUMENT_ONLY — reference expects multi-mode evidence but only DOCUMENT_UPLOAD is allowed
- **MEDIUM** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (wales): MULTI_EVIDENCE_DOCUMENT_ONLY — reference expects multi-mode evidence but only DOCUMENT_UPLOAD is allowed
- **MEDIUM** [EVIDENCE_MODE_DRIFT] `fire_risk_assessment` (northern_ireland): MULTI_EVIDENCE_DOCUMENT_ONLY — reference expects multi-mode evidence but only DOCUMENT_UPLOAD is allowed
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `fire_risk_assessment` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=MULTI_EVIDENCE but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: MULTI_EVIDENCE vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `hmo_classification` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `property_classification` (england): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `property_classification` (scotland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `property_classification` (wales): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
- **MEDIUM** [WORKFLOW_CLASS_DRIFT] `property_classification` (northern_ireland): REFERENCE_VS_RUNTIME_WORKFLOW_CLASS — reference_class=HIDDEN_SYSTEM but enriched workflow_class=LEGACY_DOCUMENT_UPLOAD (after LEGACY≈DOCUMENT normalization: HIDDEN_SYSTEM vs DOCUMENT_UPLOAD).
