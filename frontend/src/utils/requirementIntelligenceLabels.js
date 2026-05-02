/**
 * Human-facing labels for requirement workflow / evidence tokens.
 * Prefer API `workflow_status_label` / `compliance_state_label` when present; these are client fallbacks.
 */

const WORKFLOW_STATUS_LABELS = {
  NOT_APPLICABLE: 'Not applicable',
  IN_PROGRESS: 'In progress',
  COMPLIANT: 'Compliant',
  OVERDUE: 'Overdue',
  ACTION_REQUIRED: 'Action needed',
};

const COMPLIANCE_STATE_LABELS = {
  NOT_APPLICABLE: 'Not applicable',
  PENDING_VERIFICATION: 'Evidence submitted and awaiting review',
  VALID: 'Verified and current',
  OVERDUE: 'Overdue',
  MISSING: 'Missing required evidence',
  EXPIRING: 'Expiring soon',
};

const EVIDENCE_STATE_LABELS = {
  VERIFIED_CURRENT: 'Verified and current',
  MISSING: 'Missing required evidence',
  OVERDUE: 'Overdue',
  AWAITING_USER_CONFIRM: 'Awaiting your confirmation',
  MISMATCH_FLAGGED: 'Mismatch flagged',
};

/** Registry `allowed_evidence_modes` → tenant-safe lines (aligned with evidence_resolution policy). */
const EVIDENCE_MODE_CLIENT_LABELS = {
  DOCUMENT_UPLOAD: 'Document upload',
  STRUCTURED_DECLARATION: 'Structured declaration',
  CONTRACTOR_CONFIRMATION: 'Contractor confirmation',
  INSPECTION_CHECKLIST: 'Inspection checklist',
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
      ? humanizeServerWorkflowLabel(String(requirement.workflow_status_label).trim())
      : humanWorkflowStatusLabel(ws);
  const csLabel =
    typeof requirement.compliance_state_label === 'string' && requirement.compliance_state_label.trim()
      ? humanizeServerComplianceLabel(String(requirement.compliance_state_label).trim())
      : humanComplianceStateLabel(cs);
  return { workflow: wsLabel, compliance: csLabel };
}

/** When API sends legacy server strings, map to client wording (no duplicate “evidence missing”). */
function humanizeServerWorkflowLabel(s) {
  const t = s.trim();
  if (/^action required$/i.test(t)) return WORKFLOW_STATUS_LABELS.ACTION_REQUIRED;
  return t;
}

function humanizeServerComplianceLabel(s) {
  const t = s.trim();
  if (/^evidence missing$/i.test(t)) return COMPLIANCE_STATE_LABELS.MISSING;
  if (/^pending verification$/i.test(t)) return COMPLIANCE_STATE_LABELS.PENDING_VERIFICATION;
  return t;
}

/**
 * If compliance and evidence rows would repeat the same “missing evidence” idea, collapse to one line.
 * @param {Record<string, unknown>|null|undefined} requirement
 * @returns {{ workflow: string, compliance: string | null, evidenceLine: string | null }}
 */
export function requirementStatusSummaryForModal(requirement) {
  const pair = requirementWorkflowDisplayPair(requirement);
  const evRaw = String(requirement?.evidence_state || '').trim().toUpperCase();
  const evLine = evRaw ? humanEvidenceStateLabel(evRaw) : null;
  const comp = pair.compliance;
  const miss = 'missing required evidence';
  const cNorm = comp.trim().toLowerCase();
  const eNorm = (evLine || '').trim().toLowerCase();
  if (evLine && (cNorm === miss || cNorm === 'evidence missing') && (eNorm === miss || eNorm === 'evidence missing')) {
    return { workflow: pair.workflow, compliance: comp, evidenceLine: null };
  }
  return { workflow: pair.workflow, compliance: comp, evidenceLine: evLine };
}

/**
 * @param {string|undefined|null} applicability
 * @returns {string}
 */
export function humanApplicabilityClientLabel(applicability) {
  const u = String(applicability || '').trim().toUpperCase();
  if (!u || u === 'UNKNOWN') {
    return 'Applies based on your current property profile. If this looks wrong, check your property details or edit dates and applicability where available.';
  }
  if (u === 'REQUIRED') return 'Required for this property under your compliance profile.';
  if (u === 'NOT_REQUIRED' || u === 'NOT_APPLICABLE') return 'Not required for this property under current rules.';
  return u
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @returns {string[]|null}
 */
export function formatAcceptedEvidenceModesForClient(requirement) {
  if (!requirement || typeof requirement !== 'object') return null;
  const meta = requirement.registry_metadata && typeof requirement.registry_metadata === 'object' ? requirement.registry_metadata : null;
  const er = meta?.evidence_resolution && typeof meta.evidence_resolution === 'object' ? meta.evidence_resolution : null;
  const modes = er?.allowed_evidence_modes;
  if (!Array.isArray(modes) || modes.length === 0) return null;
  return modes.map((m) => {
    const k = String(m || '').trim().toUpperCase();
    return EVIDENCE_MODE_CLIENT_LABELS[k] || titleCaseToken(k);
  });
}

/**
 * @param {Record<string, unknown>|null|undefined} activeJob
 * @returns {{ title: string, lines: string[], navigateJobId: string | null }}
 */
export function activeComplianceJobClientSummary(activeJob) {
  if (!activeJob || typeof activeJob !== 'object') {
    return { title: '', lines: [], navigateJobId: null };
  }
  const jid = String(activeJob.job_id || '').trim();
  const statusRaw = String(activeJob.status_label || activeJob.display_status || activeJob.status || '').trim();
  const status = statusRaw ? titleCaseToken(statusRaw.replace(/_/g, ' ')) : '';
  const contractor = String(activeJob.contractor_name || activeJob.assigned_contractor_name || '').trim();
  const next = activeJob.next_visit_at || activeJob.scheduled_visit_at || activeJob.next_appointment_at;
  const lines = [];
  if (status) lines.push(`Status: ${status}`);
  if (contractor) lines.push(`Assigned: ${contractor}`);
  const nd = formatShortDate(next);
  if (nd) lines.push(`Next visit: ${nd}`);
  if (lines.length === 0 && jid) {
    lines.push('A compliance job is open for this requirement.');
  }
  return { title: 'Active compliance job', lines, navigateJobId: jid || null };
}

function formatShortDate(value) {
  if (value == null || value === '') return null;
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}
