/**
 * User-facing domain labels — mirrors backend/presentation/label_service.py.
 * Data: ./domain_labels.json (keep in sync with backend copy).
 */
import raw from './domain_labels.json';

const data = raw;

function audienceKey(audience) {
  return (audience || 'client').toLowerCase() === 'admin' ? 'admin_label' : 'client_label';
}

export function normalizeRequirementCode(code) {
  if (code == null || code === '') return '';
  return String(code)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

export function titleFromSnake(s) {
  if (!s) return '';
  const specials = { eicr: 'EICR', epc: 'EPC', pat: 'PAT', hmo: 'HMO', cp12: 'CP12', co: 'CO' };
  return s
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((p) => specials[p.toLowerCase()] || p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
    .join(' ');
}

export function requirementLabel(code, audience = 'client') {
  const key = normalizeRequirementCode(code);
  if (!key) return 'Requirement';
  const req = (data.requirement_codes || {})[key];
  if (req && typeof req === 'object') {
    return String(req.display_label || req.short_label || key).trim();
  }
  return titleFromSnake(key);
}

/**
 * Titles from API `requirement_display` (backend-owned). Returns null when absent.
 * @param {'compact'|'detail'} mode compact = cards/tasks/drivers; detail = full official name
 */
export function requirementDisplayTitle(display, mode = 'compact') {
  const d = display && typeof display === 'object' ? display : null;
  if (!d) return null;
  const cn = String(d.canonical_name || '').trim();
  const sn = String(d.short_name || '').trim();
  if (mode === 'detail') return cn || sn || null;
  return sn || cn || null;
}

/** Body copy only — never concatenate into titles. */
export function requirementDisplayDescription(display) {
  const d = display && typeof display === 'object' ? display : null;
  if (!d) return null;
  const s = String(d.description || '').trim();
  return s || null;
}

/**
 * Unified requirement title selection per surface.
 * requirement_display is authoritative when present; legacy fields are defensive fallback only.
 * @param {Record<string, unknown>|null|undefined} row
 * @param {'compact'|'detail'} mode
 */
export function requirementTitleFromRow(row, mode = 'compact') {
  const r = row && typeof row === 'object' ? row : {};
  const display = r.requirement_display && typeof r.requirement_display === 'object' ? r.requirement_display : null;
  const fromDisplay = requirementDisplayTitle(display, mode);
  if (fromDisplay) return fromDisplay;
  const code = r.requirement_code || r.requirement_type || r.code;
  const fallbackLabel = code ? requirementLabel(code) : null;
  if (mode === 'detail') {
    return String(r.title || fallbackLabel || r.display_label || r.description || r.name || 'Requirement');
  }
  return String(fallbackLabel || r.display_label || r.title || r.description || r.name || 'Requirement');
}

export function requirementActionPhrase(code) {
  const key = normalizeRequirementCode(code);
  const req = key ? (data.requirement_codes || {})[key] : null;
  if (req && req.action_label) return String(req.action_label);
  return `Complete this requirement: ${requirementLabel(code)}`;
}

/** Subline under “Awaiting verification” chips (who acts next + automation). */
export function documentVerificationAwaitingSubline() {
  const block = data.document_verification_copy || {};
  return String(block.awaiting_verification_subline || '').trim() || '';
}

/**
 * Short upload CTA when the requirement type is known (Compliance / Documents / Operating).
 * Only "Upload document" when the requirement type cannot be resolved.
 */
export function requirementDocumentUploadLabel(code) {
  const key = normalizeRequirementCode(code);
  if (!key) return 'Upload document';
  const reportKeys = new Set([
    'eicr',
    'fire_risk_assessment',
    'legionella',
    'portable_appliance_test',
    'electrical_safety',
  ]);
  const certificateKeys = new Set([
    'epc',
    'gas_safety',
    'gas_safety_certificate',
    'co_alarms',
    'smoke_alarms',
    'fire_alarm',
    'fire_detection',
    'hmo_license',
  ]);
  const proofKeys = new Set(['deposit_pi', 'right_to_rent', 'how_to_rent', 'tenancy_agreement']);
  if (reportKeys.has(key)) return 'Upload report';
  if (certificateKeys.has(key)) return 'Upload certificate';
  if (proofKeys.has(key)) return 'Upload proof';
  if (data.requirement_codes && data.requirement_codes[key]) return 'Upload proof';
  return 'Upload document';
}

/** Extra maintenance issue statuses when not in domain_labels.json */
const ISSUE_STATUS_FALLBACK = {
  pending: 'Pending',
  snoozed: 'Snoozed',
  deferred: 'Deferred',
  escalated: 'Escalated',
};

export function issueStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toLowerCase();
  if (!s) return 'Open';
  const block = (data.issue_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  if (ISSUE_STATUS_FALLBACK[s]) return ISSUE_STATUS_FALLBACK[s];
  return 'Open';
}

/** Extra job statuses when not in domain_labels.json */
const WORK_ORDER_STATUS_FALLBACK = {
  PENDING: 'Pending',
  ON_HOLD: 'On hold',
  HOLD: 'On hold',
  PAUSED: 'Paused',
  AWAITING_QUOTE: 'Awaiting quote',
  AWAITING_APPROVAL: 'Awaiting approval',
  BLOCKED: 'Blocked',
};

export function workOrderStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return 'Open';
  const block = (data.work_order_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  if (WORK_ORDER_STATUS_FALLBACK[s]) return WORK_ORDER_STATUS_FALLBACK[s];
  return 'Open';
}

export function slaStateLabel(state, audience = 'client') {
  const s = String(state || '').trim().toLowerCase();
  const block = (data.sla_presentations || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  return '—';
}

export function riskTypeLabelClient(riskType) {
  const rt = String(riskType || '').trim();
  if (!rt) return 'Issue needs review';
  const block = (data.risk_types || {})[rt];
  if (block && block.client_label) return String(block.client_label);
  if (/^[A-Z0-9_]+$/.test(rt.replace(/\s/g, ''))) return titleFromSnake(rt.toLowerCase());
  return rt;
}

export function riskTypeLabelAdmin(riskType) {
  const rt = String(riskType || '').trim();
  if (!rt) return 'Flagged issue';
  const block = (data.risk_types || {})[rt];
  if (block && block.admin_label) return String(block.admin_label);
  return rt;
}

export function recommendedActionClient(riskType, storedAction) {
  const rt = String(riskType || '').trim();
  const block = (data.risk_types || {})[rt];
  if (block && block.recommended_action_client) return String(block.recommended_action_client);
  const rawA = String(storedAction || '').trim();
  if (rawA) return rawA.endsWith('.') ? rawA : `${rawA}.`;
  return 'Review the issue.';
}

/** Portfolio-level traffic-light status (property row), not per-requirement status. */
export function propertyComplianceRagLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return '—';
  const block = (data.property_compliance_rag || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  return 'Not assessed';
}

export function propertyTypeLabel(raw, audience = 'client') {
  if (raw == null || raw === '') return '—';
  if (String(raw).trim().toUpperCase() === 'N/A') return '—';
  const key = normalizeRequirementCode(raw);
  const block = key ? (data.property_types || {})[key] : null;
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || titleFromSnake(key));
  }
  return titleFromSnake(key || String(raw).trim().toLowerCase());
}

const COMPLIANCE_REQUIREMENT_STATUS_FALLBACK = {
  MISSING_EVIDENCE: 'No document uploaded',
  PENDING_VERIFICATION: 'Awaiting verification',
  INVALID: 'Invalid',
  UNKNOWN: '—',
};

export function complianceRequirementStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return '—';
  const block = (data.compliance_requirement_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  if (COMPLIANCE_REQUIREMENT_STATUS_FALLBACK[s]) return COMPLIANCE_REQUIREMENT_STATUS_FALLBACK[s];
  return 'Needs attention';
}

export function documentTypeLabel(raw) {
  if (raw == null || raw === '') return 'Document';
  const s = String(raw).trim();
  const low = normalizeRequirementCode(s);
  const req = (data.requirement_codes || {})[low];
  if (req && typeof req === 'object') {
    return String(req.display_label || req.short_label || s);
  }
  if (s.includes('_') || s === s.toLowerCase()) return requirementLabel(s);
  return s;
}

export function suggestedActionLabel(code, audience = 'client') {
  const c = String(code || '').trim().toLowerCase();
  const block = (data.suggested_action_codes || {})[c];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    const lab = block[k] || block.client_label;
    if (lab) return String(lab);
  }
  return 'Next action';
}

/** Inbox / dashboard urgency (not the same as portfolio “risk level” wording). */
export function urgencyLevelLabel(level) {
  const v = String(level || '').trim().toLowerCase();
  const map = {
    critical: 'Critical',
    high: 'High priority',
    medium: 'Medium',
    low: 'Low',
  };
  if (map[v]) return map[v];
  if (!v) return 'Medium';
  return 'Medium';
}

/** Risk signal row severity (critical / high / medium / low). */
export function riskSignalLevelLabel(level) {
  const v = String(level || '').trim().toLowerCase();
  const map = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
  return map[v] || (v ? v.charAt(0).toUpperCase() + v.slice(1) : '');
}

export function issueSeverityLabel(severity) {
  const v = String(severity || '').trim().toLowerCase();
  if (!v) return '—';
  const map = { low: 'Low', medium: 'Medium', high: 'High', urgent: 'Urgent', critical: 'Critical' };
  return map[v] || 'Medium';
}

/**
 * Predictive / portfolio “issue” row lifecycle (not the maintenance issues queue).
 * Avoids raw API tokens in UI.
 */
export function predictiveIssueStatusLabel(raw) {
  const s = String(raw || '').trim().toLowerCase();
  const map = {
    active: 'Active',
    acknowledged: 'Acknowledged',
    resolved: 'Resolved',
    dismissed: 'Dismissed',
    suppressed: 'Suppressed',
    expired: 'Expired',
    open: 'Open',
    closed: 'Closed',
  };
  if (map[s]) return map[s];
  return 'Updated';
}

/** Job operational hold codes shown on badges and command centre. */
export function operationalExceptionLabel(raw) {
  const u = String(raw || '')
    .trim()
    .toUpperCase()
    .replace(/\s+/g, '_');
  const map = {
    NO_ACCESS: 'No access',
    RESCHEDULE_REQUIRED: 'Reschedule required',
    AWAITING_PARTS: 'Awaiting parts',
    AWAITING_CLIENT: 'Awaiting client',
    AWAITING_CONTRACTOR: 'Awaiting contractor',
    WEATHER: 'Weather hold',
    PAYMENT_HOLD: 'Payment hold',
    CLIENT_HOLD: 'Client hold',
  };
  if (map[u]) return map[u];
  if (!u) return '';
  return 'On hold';
}

/** Today / inbox card source line (distinct from maintenance issues). */
export function inboxSourceTypeLabel(sourceType) {
  const st = String(sourceType || '').trim().toLowerCase();
  const map = {
    requirement: 'Requirement',
    risk_signal: 'Potential issue',
    work_order: 'Job',
    approval: 'Approval',
    issue: 'Maintenance issue',
    priority_action: 'Suggested action',
    compliance: 'Compliance',
    document: 'Document',
    maintenance: 'Maintenance',
  };
  if (map[st]) return map[st];
  return 'Item';
}

/** Today timeline / snack labels for user actions on tasks (not domain enums). */
export function inboxTimelineActionLabel(act) {
  const a = String(act || '').trim().toLowerCase();
  const map = {
    snooze: 'Today item snoozed',
    dismiss: 'Today item hidden from Today',
    done: 'Today inbox marked done (legacy)',
    reviewed: 'Today item marked reviewed in Today only',
    restore: 'Today item restored to Today',
    hide: 'Hidden',
    unhide: 'Unhidden',
  };
  if (map[a]) return map[a];
  if (!a) return '—';
  return 'Updated';
}

/**
 * Document list row status badge (API document record), separate from requirement matrix chips.
 */
export function documentListStatusLabel(status) {
  const key = String(status || '').trim().toUpperCase();
  const map = {
    PENDING: 'Awaiting confirmation',
    UPLOADED: 'Received (confirm to apply)',
    VERIFIED: 'Confirmed',
    REJECTED: 'Rejected',
    EXPIRED: 'Expired',
    PROCESSING: 'Processing',
    FAILED: 'Failed',
  };
  if (map[key]) return map[key];
  return 'Awaiting confirmation';
}

const INBOX_TITLE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Remove trailing " (requirement_code)" when it duplicates metadata — avoids "Label (label) (code)" in inbox. */
function stripTrailingMatchingRequirementParen(title, meta) {
  let t = String(title || '').trim();
  if (!t || !meta || typeof meta !== 'object') return t;
  const codes = [meta.requirement_type, meta.requirement_code, meta.code].filter(
    (c) => c != null && String(c).trim() !== '',
  );
  for (const c of codes) {
    const esc = String(c).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\s+\\(${esc}\\)\\s*$`, 'i');
    if (re.test(t)) {
      t = t.replace(re, '').trim();
      break;
    }
    const nk = normalizeRequirementCode(String(c));
    if (nk) {
      const re2 = new RegExp(`\\s+\\(${nk.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\)\\s*$`, 'i');
      if (re2.test(t)) {
        t = t.replace(re2, '').trim();
        break;
      }
    }
  }
  return t;
}

/**
 * When the API uses a bare requirement code as title, show the catalogue label instead.
 */
export function inboxTitleForDisplay(task) {
  let raw = String(task?.title || '').trim();
  if (!raw) return 'Task';
  if (INBOX_TITLE_UUID_RE.test(raw)) return 'Task';
  const meta = task?.metadata || {};
  raw = stripTrailingMatchingRequirementParen(raw, meta);
  // Today projection sets action-oriented titles; strip duplicate codes only — keep full sentence.
  if (meta.today_action_title) return raw;
  const code = meta.requirement_type || meta.requirement_code || meta.code;
  if (code && typeof code === 'string') {
    const lbl = requirementLabel(code);
    if (lbl && lbl !== 'Requirement') return lbl;
  }
  if (/^[a-z][a-z0-9_]*$/i.test(raw) && raw.includes('_')) {
    const lbl = requirementLabel(raw);
    if (lbl !== 'Requirement') return lbl;
  }
  return raw;
}
