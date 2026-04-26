/**
 * Human-facing labels for requirement workflow / evidence tokens.
 * Prefer API `workflow_status_label` / `compliance_state_label` when present; these are client fallbacks.
 */

const WORKFLOW_STATUS_LABELS = {
  NOT_APPLICABLE: 'Not applicable',
  IN_PROGRESS: 'In progress',
  COMPLIANT: 'Compliant',
  OVERDUE: 'Overdue',
  ACTION_REQUIRED: 'Action required',
};

const COMPLIANCE_STATE_LABELS = {
  NOT_APPLICABLE: 'Not applicable',
  PENDING_VERIFICATION: 'Pending verification',
  VALID: 'Verified and current',
  OVERDUE: 'Overdue',
  MISSING: 'Evidence missing',
  EXPIRING: 'Expiring soon',
};

const EVIDENCE_STATE_LABELS = {
  VERIFIED_CURRENT: 'Verified and current',
  MISSING: 'Evidence missing',
  OVERDUE: 'Overdue',
  AWAITING_USER_CONFIRM: 'Awaiting your confirmation',
  MISMATCH_FLAGGED: 'Mismatch flagged',
};

function titleCaseToken(raw) {
  const k = String(raw || '').trim().toUpperCase();
  if (!k) return '—';
  return k
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ');
}

/** @param {string|undefined|null} raw */
export function humanWorkflowStatusLabel(raw) {
  const k = String(raw || '').trim().toUpperCase();
  return WORKFLOW_STATUS_LABELS[k] || titleCaseToken(k);
}

/** @param {string|undefined|null} raw */
export function humanComplianceStateLabel(raw) {
  const k = String(raw || '').trim().toUpperCase();
  return COMPLIANCE_STATE_LABELS[k] || titleCaseToken(k);
}

/** @param {string|undefined|null} raw */
export function humanEvidenceStateLabel(raw) {
  const k = String(raw || '').trim().toUpperCase();
  return EVIDENCE_STATE_LABELS[k] || titleCaseToken(k);
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @returns {{ workflow: string, compliance: string }}
 */
export function requirementWorkflowDisplayPair(requirement) {
  if (!requirement || typeof requirement !== 'object') {
    return { workflow: '—', compliance: '—' };
  }
  const ws = String(requirement.workflow_status || '').trim();
  const cs = String(requirement.compliance_state || '').trim();
  const wsLabel =
    typeof requirement.workflow_status_label === 'string' && requirement.workflow_status_label.trim()
      ? String(requirement.workflow_status_label).trim()
      : humanWorkflowStatusLabel(ws);
  const csLabel =
    typeof requirement.compliance_state_label === 'string' && requirement.compliance_state_label.trim()
      ? String(requirement.compliance_state_label).trim()
      : humanComplianceStateLabel(cs);
  return { workflow: wsLabel, compliance: csLabel };
}
