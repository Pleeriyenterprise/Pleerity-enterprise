/**
 * Read-only projection helpers for server-authoritative operational_cognition envelopes.
 * Display-only — never infer or mutate workflow authority on the client.
 */

export function getOperationalCognition(entity) {
  const env = entity?.operational_cognition;
  return env && typeof env === 'object' ? env : null;
}

export function getListGuidance(entity) {
  const env = getOperationalCognition(entity);
  if (env?.list_guidance) return env.list_guidance;

  const ta = entity?.take_action?.primary || entity?.metadata?.take_action?.primary;
  if (ta?.label) {
    return {
      recommended_action_label: String(ta.label).trim(),
      continuation_summary: ta.continuation ? 'CONTINUATION' : undefined,
      cognition_version: 'take_action',
    };
  }

  const actions = entity?.business_actions;
  if (Array.isArray(actions) && actions.length) {
    const primary = actions.find((a) => a?.primary) || actions[0];
    if (primary?.label) {
      return {
        recommended_action_label: String(primary.label).trim(),
        cognition_version: 'business_actions',
      };
    }
  }

  return null;
}

export function heroPrimaryFromCognition(cognition) {
  if (!cognition?.primary_action) return null;
  const p = cognition.primary_action;
  return {
    key: p.key || 'next_action',
    label: p.label || 'Continue',
    hint: p.hint || '',
    url: p.url,
    continuation: Boolean(p.continuation),
    source: p.source,
  };
}

export function truthWarningsFromCognition(cognition) {
  if (!cognition) return [];
  const flags = cognition.operational_truth_flags || {};
  const warnings = Array.isArray(cognition.warnings) ? [...cognition.warnings] : [];
  if (flags.uploaded_not_verified) {
    warnings.push({ code: 'UPLOADED_NOT_VERIFIED', message: 'Uploaded is not verified.' });
  }
  if (flags.submitted_not_compliant) {
    warnings.push({ code: 'SUBMITTED_NOT_COMPLIANT', message: 'Submitted is not compliant until review confirms.' });
  }
  if (flags.assigned_not_fixed) {
    warnings.push({ code: 'ASSIGNED_NOT_FIXED', message: 'Assigned does not mean fixed.' });
  }
  if (flags.completed_not_compliant) {
    warnings.push({ code: 'COMPLETED_NOT_COMPLIANT', message: 'Completed is not the same as compliant.' });
  }
  if (flags.acknowledged_not_resolved) {
    warnings.push({ code: 'ACKNOWLEDGED_NOT_RESOLVED', message: 'Acknowledged does not mean resolved.' });
  }
  return warnings;
}

export function progressionLabel(cognition) {
  if (!cognition) return null;
  const cont = cognition.continuation_state || {};
  const prog = cognition.progression_state || {};
  const guidance = cognition.requirement_guidance_v1;
  if (guidance?.recommended_next_step_reason) {
    return guidance.recommended_next_step_reason;
  }
  return cont.summary || prog.step || prog.recommended_action || null;
}

export function getRequirementGuidance(entity) {
  const env = getOperationalCognition(entity);
  return env?.requirement_guidance_v1 || entity?.requirement_guidance_v1 || null;
}

export function progressionStepsFromCognition(entity) {
  const env = getOperationalCognition(entity);
  const steps = env?.progression_state?.steps || env?.requirement_guidance_v1?.progression_steps;
  return Array.isArray(steps) ? steps : [];
}

export function sortEvidenceModesByGuidance(modes, guidance) {
  if (!Array.isArray(modes) || modes.length <= 1) return modes || [];
  const strongest = guidance?.strongest_evidence_method;
  const weaker = new Set(guidance?.weaker_alternative_methods || []);
  return [...modes].sort((a, b) => {
    if (a === strongest) return -1;
    if (b === strongest) return 1;
    if (weaker.has(a) && !weaker.has(b)) return 1;
    if (weaker.has(b) && !weaker.has(a)) return -1;
    return 0;
  });
}
