import {
  recommendedActionClient,
  requirementLabel,
  riskTypeLabelAdmin,
  riskTypeLabelClient,
} from '../domain/presentDomain';
import { operationalLabelForToken } from './presentationLanguage';

/**
 * @param {string|object|null|undefined} riskTypeOrSignal — raw risk_type string, or signal object with API labels
 * @param {string} [audience] — 'client' | 'admin' for fallback mapping
 */
export function humanRiskType(riskTypeOrSignal, audience = 'client') {
  const signal =
    typeof riskTypeOrSignal === 'object' && riskTypeOrSignal !== null ? riskTypeOrSignal : null;
  const riskType = signal ? signal.risk_type : riskTypeOrSignal;
  if (signal && audience === 'admin' && signal.risk_type_label_admin) {
    return signal.risk_type_label_admin;
  }
  if (signal && signal.risk_type_label_client && audience !== 'admin') {
    return signal.risk_type_label_client;
  }
  if (!riskType) return 'Risk requires review';
  return audience === 'admin' ? riskTypeLabelAdmin(riskType) : riskTypeLabelClient(riskType);
}

export function humanSeverity(level) {
  const value = String(level || '').toLowerCase();
  if (value === 'critical' || value === 'high') return 'Urgent';
  if (value === 'medium') return 'Needs attention';
  if (value === 'low') return 'Monitor';
  return 'Needs attention';
}

export function severityBadgeClass(level) {
  const value = humanSeverity(level);
  if (value === 'Urgent') return 'bg-red-100 text-red-800';
  if (value === 'Needs attention') return 'bg-amber-100 text-amber-800';
  return 'bg-gray-100 text-gray-700';
}

export function humanStatus(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'active') return 'Open';
  if (value === 'acknowledged') return 'In progress';
  if (value === 'remediation_in_progress') return 'Remediation in progress';
  if (value === 'resolved') return 'Resolved';
  if (!status) return 'Open';
  return operationalLabelForToken(status, { emptyLabel: 'Open' });
}

export function humanTrend(trend) {
  const v = String(trend || '').trim().toLowerCase();
  if (v === 'rising') return 'Rising';
  if (v === 'stable') return 'Stable';
  if (v === 'improving') return 'Improving';
  if (!v) return 'Stable';
  return v.charAt(0).toUpperCase() + v.slice(1);
}

const ACTION_KEYWORDS = [
  { test: /boiler|heating/i, text: 'Book a boiler inspection and review replacement options.' },
  { test: /damp|moisture|mould/i, text: 'Arrange a damp inspection and resolve the root cause.' },
  { test: /electrical|eicr/i, text: 'Arrange an electrical safety check and update records.' },
  { test: /sla|contractor/i, text: 'Review contractor performance and re-prioritise delayed jobs.' },
  { test: /compliance|certificate|evidence/i, text: 'Upload missing documents and schedule required renewals.' },
  { test: /recurring|repeat/i, text: 'Investigate the recurring issue and plan a permanent fix.' },
];

/**
 * @param {string|null|undefined} actionText
 * @param {string|object|null|undefined} riskTypeOrSignal
 */
export function humanAction(actionText, riskTypeOrSignal) {
  const signal =
    typeof riskTypeOrSignal === 'object' && riskTypeOrSignal !== null ? riskTypeOrSignal : null;
  const riskType = signal ? signal.risk_type : riskTypeOrSignal;
  if (signal && signal.recommended_action_client) {
    const c = String(signal.recommended_action_client).trim();
    return c.endsWith('.') ? c : `${c}.`;
  }
  const raw = String(actionText || '').trim();
  for (const rule of ACTION_KEYWORDS) {
    if (rule.test.test(raw) || rule.test.test(String(riskType || ''))) {
      return rule.text;
    }
  }
  const mapped = recommendedActionClient(riskType, raw);
  if (mapped && mapped !== 'Review this signal and choose the next best step.') return mapped;
  if (!raw) return 'Review this issue and choose the next best action.';
  return raw.endsWith('.') ? raw : `${raw}.`;
}

export function presentPropertyName(signalOrRow, fallback = 'Property in portfolio') {
  return signalOrRow?.property_name || signalOrRow?.property_label || signalOrRow?.address_line_1 || fallback;
}

export function presentClientName(signalOrRow, fallback = 'Client account') {
  return signalOrRow?.client_name || signalOrRow?.company_name || signalOrRow?.full_name || fallback;
}

/** Turn `gas_safety expiring soon` into readable obligation copy for risk cards. */
export function humanizeRiskReasonBullet(line) {
  const s = String(line || '').trim();
  if (!s) return s;
  const lower = s.toLowerCase();
  const words = lower.split(/\s+/);
  const code = words[0].replace(/[^a-z0-9_]/g, '');
  if (/^[a-z][a-z0-9_]*$/.test(code) && words.length > 1) {
    return `${requirementLabel(code)} ${words.slice(1).join(' ')}`;
  }
  if (/^[a-z][a-z0-9_]*$/.test(lower) && words.length === 1) {
    return requirementLabel(code);
  }
  return s;
}

export function groupSignalsByProperty(signals = []) {
  const map = new Map();
  for (const signal of signals) {
    const key = signal.property_id || signal.property_name || 'unknown';
    if (!map.has(key)) {
      map.set(key, {
        key,
        propertyName: presentPropertyName(signal),
        clientName: presentClientName(signal),
        issues: [],
      });
    }
    map.get(key).issues.push(signal);
  }
  return Array.from(map.values()).sort((a, b) => b.issues.length - a.issues.length);
}
