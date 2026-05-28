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
  return env?.list_guidance || null;
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
  return cont.summary || prog.step || prog.recommended_action || null;
}
