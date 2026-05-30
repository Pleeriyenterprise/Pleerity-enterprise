/**
 * Governed UI presentation language for Compliance Vault Pro (Pleerity Enterprise frontend).
 * Maps backend tokens / enums to human operational labels only — never changes API payloads or stored values.
 * @see docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md
 */

/** Normalized lookup key: lowercase, underscores, trimmed. */
export function normalizePresentationKey(raw) {
  return String(raw ?? '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
}

/** Title-case each snake segment when no canonical label exists. */
export function humanizeSnakeFallback(normalizedKey) {
  const k = normalizedKey == null ? '' : String(normalizedKey);
  if (!k.trim()) return '—';
  return k
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Canonical operational phrases for known backend / workflow tokens.
 * Keys are normalized (snake, lower). Add new entries here — do not scatter `.replace(/_/g)` in UI.
 */
const OPERATIONAL_LABEL_BY_KEY = {
  // Evidence / compliance (async-honest wording)
  accepted_unverified: 'Accepted on file (not externally verified)',
  pending_verification: 'Awaiting verification',
  needs_confirmation: 'Awaiting confirmation',
  evidence_pending: 'Evidence review pending',
  pending_sync: 'Sync pending',
  recalc_pending: 'Compliance score update pending',
  score_recalc_pending: 'Compliance score update pending',
  portfolio_score_recalc_pending: 'Portfolio score update pending',
  propagation_pending: 'Updates still applying',
  propagation_in_progress: 'Updates applying',
  requirement_state_transition: 'Requirement status changing',
  contractor_confirmation: 'Awaiting contractor confirmation',

  // Maintenance / jobs
  maintenance_issue: 'Maintenance issue',
  compliance_job: 'Compliance work order',
  maintenance_job: 'Maintenance work order',
  work_order: 'Work order',
  awaiting_parts: 'Waiting for parts',
  quote_requested: 'Quote requested',
  job_scheduled: 'Job scheduled',
  overdue_requirement: 'Overdue requirement',
  unresolved_issue: 'Unresolved issue',
  sla_breached: 'SLA deadline missed',
  sla_breach: 'SLA deadline missed',
  near_sla_breach: 'Near SLA deadline',
  // SLA filter / summary tokens (query param values unchanged)
  breached: 'SLA deadline missed',
  near_breach: 'Near SLA deadline',
  on_track: 'On track',

  // Scheduled report types (display only; API values unchanged)
  compliance_summary: 'Compliance status summary',
  requirements: 'Requirements report',

  // Property / occupancy (intake-aligned)
  multi_family: 'Multi-family occupancy',
  single_family: 'Single-family occupancy',
  student: 'Student let',
  professional: 'Professional let',
  mixed_use: 'Mixed use',
  england_wales: 'England & Wales',
  scotland: 'Scotland',
  northern_ireland: 'Northern Ireland',

  // Misc workflow
  not_applicable: 'Not applicable',
  in_progress: 'In progress',
  action_required: 'Action needed',
  needs_info: 'Needs more information',
  bank_transfer: 'Bank transfer',

  // Calendar / timeline categories (internal category slugs → UI)
  scheduled_job: 'Maintenance job',

  // Quote negotiation price_status tokens
  awaiting_quote: 'Quote requested',
  quoted: 'Quote submitted',
  approved: 'Work authorised',
  rejected: 'Changes requested',
  revision_requested: 'Changes requested',
  rejected_final: 'Quote declined (final)',
};

/**
 * @param {string|number|null|undefined} raw — backend enum, slug, or mixed-case token
 * @param {{ emptyLabel?: string, allowHumanSentence?: boolean }} [opts]
 * @returns {string} Human label for display only
 */
export function operationalLabelForToken(raw, opts = {}) {
  const empty = opts.emptyLabel !== undefined ? opts.emptyLabel : '—';
  if (raw == null || raw === '') return empty;
  const s = String(raw).trim();
  if (!s || s === '—') return empty;

  // Already a human sentence from the API (no internal snake pattern)
  if (opts.allowHumanSentence !== false && !/[a-z0-9]_[a-z0-9]/i.test(s) && s.includes(' ')) {
    return s;
  }

  const k = normalizePresentationKey(s);
  if (!k) return empty;
  if (OPERATIONAL_LABEL_BY_KEY[k]) return OPERATIONAL_LABEL_BY_KEY[k];

  return humanizeSnakeFallback(k);
}
