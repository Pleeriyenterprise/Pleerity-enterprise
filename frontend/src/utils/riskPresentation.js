const RISK_TYPE_LABELS = {
  'Boiler Failure Risk': 'Boiler reliability concerns',
  'Damp / Moisture Risk': 'Damp or moisture concerns',
  'Electrical Risk': 'Electrical safety concerns',
  'Recurring Repairs Risk': 'Repeated repair pattern detected',
  'SLA Breach Risk': 'Contractor delays affecting service',
  'Compliance Churn Risk': 'Compliance gaps detected',
  'Maintenance Frequency Risk': 'Maintenance activity is unusually high',
  'Certificate Expiry Soon': 'Certificate renewal needed soon',
};

const ACTION_KEYWORDS = [
  { test: /boiler|heating/i, text: 'Book a boiler inspection and review replacement options.' },
  { test: /damp|moisture|mould/i, text: 'Arrange a damp inspection and resolve the root cause.' },
  { test: /electrical|eicr/i, text: 'Arrange an electrical safety check and update records.' },
  { test: /sla|contractor/i, text: 'Review contractor performance and re-prioritise delayed jobs.' },
  { test: /compliance|certificate|evidence/i, text: 'Upload missing documents and schedule required renewals.' },
  { test: /recurring|repeat/i, text: 'Investigate the recurring issue and plan a permanent fix.' },
];

export function humanRiskType(riskType) {
  if (!riskType) return 'Risk requires review';
  return RISK_TYPE_LABELS[riskType] || riskType;
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
  if (value === 'resolved') return 'Resolved';
  return status || 'Open';
}

export function humanAction(actionText, riskType) {
  const raw = String(actionText || '').trim();
  for (const rule of ACTION_KEYWORDS) {
    if (rule.test.test(raw) || rule.test.test(String(riskType || ''))) {
      return rule.text;
    }
  }
  if (!raw) return 'Review this issue and choose the next best action.';
  return raw.endsWith('.') ? raw : `${raw}.`;
}

export function presentPropertyName(signalOrRow, fallback = 'Property in portfolio') {
  return signalOrRow?.property_name || signalOrRow?.property_label || signalOrRow?.address_line_1 || fallback;
}

export function presentClientName(signalOrRow, fallback = 'Client account') {
  return signalOrRow?.client_name || signalOrRow?.company_name || signalOrRow?.full_name || fallback;
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

