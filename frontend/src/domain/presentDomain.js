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
  if (!key) return 'Compliance item';
  const req = (data.requirement_codes || {})[key];
  if (req && typeof req === 'object') {
    return String(req.display_label || req.short_label || key).trim();
  }
  return titleFromSnake(key);
}

export function requirementActionPhrase(code) {
  const key = normalizeRequirementCode(code);
  const req = key ? (data.requirement_codes || {})[key] : null;
  if (req && req.action_label) return String(req.action_label);
  return `Complete this obligation: ${requirementLabel(code)}`;
}

/** Subline under “Awaiting verification” chips (who acts next + automation). */
export function documentVerificationAwaitingSubline() {
  const block = data.document_verification_copy || {};
  return String(block.awaiting_verification_subline || '').trim() || '';
}

/**
 * Short upload CTA when the obligation type is known (Compliance / Documents / Operating).
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

export function issueStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toLowerCase();
  if (!s) return 'Open';
  const block = (data.issue_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || s);
  }
  return titleFromSnake(s);
}

export function workOrderStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return 'Open';
  const block = (data.work_order_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || s);
  }
  return titleFromSnake(s.toLowerCase());
}

export function slaStateLabel(state, audience = 'client') {
  const s = String(state || '').trim().toLowerCase();
  const block = (data.sla_presentations || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || s);
  }
  return titleFromSnake(s);
}

export function riskTypeLabelClient(riskType) {
  const rt = String(riskType || '').trim();
  if (!rt) return 'Risk requires review';
  const block = (data.risk_types || {})[rt];
  if (block && block.client_label) return String(block.client_label);
  if (/^[A-Z0-9_]+$/.test(rt.replace(/\s/g, ''))) return titleFromSnake(rt.toLowerCase());
  return rt;
}

export function riskTypeLabelAdmin(riskType) {
  const rt = String(riskType || '').trim();
  if (!rt) return 'Risk signal';
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
  return 'Review this signal and choose the next best step.';
}

/** Portfolio-level traffic-light status (property row), not per-requirement status. */
export function propertyComplianceRagLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return '—';
  const block = (data.property_compliance_rag || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || titleFromSnake(s.toLowerCase()));
  }
  return titleFromSnake(s.toLowerCase());
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

export function complianceRequirementStatusLabel(status, audience = 'client') {
  const s = String(status || '').trim().toUpperCase();
  if (!s) return '—';
  const block = (data.compliance_requirement_statuses || {})[s];
  if (block && typeof block === 'object') {
    const k = audienceKey(audience);
    return String(block[k] || block.client_label || titleFromSnake(s.toLowerCase()));
  }
  return titleFromSnake(s.toLowerCase());
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
    return String(block[k] || block.client_label || titleFromSnake(c));
  }
  return titleFromSnake(c);
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
  return titleFromSnake(v);
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
  return map[v] || titleFromSnake(v);
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
    if (lbl && lbl !== 'Compliance item') return lbl;
  }
  if (/^[a-z][a-z0-9_]*$/i.test(raw) && raw.includes('_')) {
    const lbl = requirementLabel(raw);
    if (lbl !== 'Compliance item') return lbl;
  }
  return raw;
}
