# PRELAUNCH-FIRE-ALARM-CTA-SPECIFICITY-REPAIR-01

## Root cause
resolve_take_action_envelope runs in enrich_requirement_dict before evidence_completeness and attach_cer_governance_presentation. resolve_actionability_primary_cta_label therefore sees no truth_presentation_stage or missing_components and returns None; guided primary falls back to generic Add compliance evidence. Component guidance works because it is computed later from the fully enriched row.

## Repair
Post-governance `apply_actionability_cta_override` in `enrich_requirement_dict` plus component-aware `_resolve_missing_component_cta`.

## Local simulation
- pass: True
- before: `Add compliance evidence`
- after: `Complete smoke alarm details`

## Staging API
- pass: True
- cta: `Complete smoke alarm details`

## Browser
- pass: True

## Classification
**VERIFIED_OPERATIONALLY**
