/**
 * Dashboard Quick Actions score-widget labels and renewal display (DASHBOARD-SCORE-WIDGET-LABEL-CONVERGENCE-01).
 * Score-projection semantics only — does not alter scoring or registry logic.
 */

import { filterRequirementsForAttentionViews } from './portalRequirementAttention';
import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';
import {
  getTimelineSortDateIso,
  isTimelineEstimated,
} from './complianceTimelinePresentation';

export const SCORE_WIDGET_LABEL_OBLIGATIONS = 'Score-tracked obligations';
export const SCORE_WIDGET_LABEL_VALID = 'Valid for scoring';
export const SCORE_WIDGET_LABEL_RENEWAL = 'Next renewal';

export const SCORE_WIDGET_TOOLTIP_OBLIGATIONS =
  'Obligations counted in the compliance score after grouping similar rules. See Requirements for the full registry.';

export const SCORE_WIDGET_TOOLTIP_VALID =
  'Items currently counted as valid in the score model. This may differ from the full Requirements page, which also shows recorded and pending assurance states.';

export const SCORE_WIDGET_TOOLTIP_RENEWAL =
  'Nearest future renewal or expiry date used by the score model. Estimated dates are shown as forecasts, not urgent expiry warnings.';

const RENEWAL_ELIGIBLE_STATUSES = new Set(['COMPLIANT', 'VALID', 'PENDING', 'EXPIRING_SOON']);

/**
 * @param {unknown} value
 * @returns {Date|null}
 */
function parseDueDate(value) {
  if (value == null || value === '') return null;
  try {
    const s = typeof value === 'string' ? value.replace('Z', '+00:00') : String(value);
    const dt = new Date(s);
    return Number.isNaN(dt.getTime()) ? null : dt;
  } catch {
    return null;
  }
}

/**
 * @param {Record<string, unknown>|null|undefined} req
 * @returns {boolean}
 */
export function isRequirementExpiryEstimated(req) {
  if (!req || typeof req !== 'object') return false;
  if (isTimelineEstimated(req)) return true;
  if (req.date_source === 'SYSTEM_ESTIMATED') return true;
  const ea = req.evidence_authority;
  if (ea && typeof ea === 'object' && ea.effective_expiry_is_estimated === true) return true;
  return false;
}

/**
 * Nearest future renewal among score-eligible rows (mirrors compliance_score stats loop).
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 * @returns {{ daysUntil: number|null, isEstimated: boolean, requirementId?: string }}
 */
export function pickNearestRenewalFromRequirements(requirements) {
  if (!Array.isArray(requirements) || requirements.length === 0) {
    return { daysUntil: null, isEstimated: false };
  }
  const now = Date.now();
  let best = null;
  let bestEstimated = false;
  let bestId;
  for (const r of requirements) {
    const st = String(r.status || '').toUpperCase();
    if (!RENEWAL_ELIGIBLE_STATUSES.has(st)) continue;
    const dueIso = getTimelineSortDateIso(r);
    const due = dueIso ? parseDueDate(dueIso) : (
      parseDueDate(r.due_date) ||
      parseDueDate(r.confirmed_expiry_date) ||
      parseDueDate(r.extracted_expiry_date) ||
      parseDueDate(r.evidence_authority?.effective_expiry_date)
    );
    if (!due) continue;
    const days = Math.floor((due.getTime() - now) / (24 * 60 * 60 * 1000));
    if (days < 0) continue;
    if (best == null || days < best) {
      best = days;
      bestEstimated = isRequirementExpiryEstimated(r);
      bestId = r.requirement_id;
    }
  }
  return { daysUntil: best, isEstimated: bestEstimated, requirementId: bestId };
}

/**
 * @param {number|null|undefined} daysUntil
 * @param {{ isEstimated?: boolean }} [opts]
 * @returns {{ headline: string, detail: string|null, ariaLabel: string }}
 */
export function formatNextRenewalDisplay(daysUntil, opts = {}) {
  const isEstimated = Boolean(opts.isEstimated);
  if (daysUntil == null || daysUntil === undefined || Number.isNaN(Number(daysUntil))) {
    return {
      headline: 'No upcoming renewal',
      detail: null,
      ariaLabel: 'No upcoming renewal date in the score model',
    };
  }
  const days = Number(daysUntil);
  if (days > 365) {
    const headline = isEstimated ? '1+ year estimated' : '1+ year';
    return {
      headline,
      detail: `${days} days until nearest date in score model`,
      ariaLabel: headline,
    };
  }
  const headline = String(days);
  const suffix = isEstimated ? ' (estimated)' : '';
  return {
    headline,
    detail: isEstimated ? 'Forecast date from score model' : null,
    ariaLabel: `Next renewal in ${days} days${suffix}`,
  };
}

/**
 * @param {number|null|undefined} apiDays
 * @param {Array<Record<string, unknown>>|null|undefined} requirementsList
 * @param {string|null|undefined} [nearestExpiryType]
 * @returns {{ headline: string, detail: string|null, ariaLabel: string, daysUntil: number|null, isEstimated: boolean }}
 */
export function resolveScoreWidgetRenewalDisplay(apiDays, requirementsList, nearestExpiryType) {
  const picked = pickNearestRenewalFromRequirements(requirementsList);
  let daysUntil = apiDays;
  let isEstimated = picked.isEstimated;
  if (daysUntil == null || daysUntil === undefined) {
    daysUntil = picked.daysUntil;
  } else if (picked.daysUntil != null && picked.daysUntil === daysUntil) {
    isEstimated = picked.isEstimated;
  } else if (daysUntil > 365) {
    isEstimated = isEstimated || picked.isEstimated;
  }
  const formatted = formatNextRenewalDisplay(daysUntil, { isEstimated });
  if (nearestExpiryType && formatted.detail) {
    return { ...formatted, daysUntil, isEstimated };
  }
  return { ...formatted, daysUntil, isEstimated };
}

/**
 * @param {Array<Record<string, unknown>>|null|undefined} requirementsList
 * @returns {number|null}
 */
export function countRegistryTrackedRequirements(requirementsList) {
  const n = filterRequirementsForAttentionViews(requirementsList).length;
  return n > 0 ? n : null;
}

/**
 * @param {string} actionText
 * @param {Record<string, unknown>|null|undefined} [requirementRow]
 * @returns {boolean}
 */
export function isAssuranceQuickAction(actionText, requirementRow) {
  const text = String(actionText || '');
  if (/self-recorded|awaiting (platform )?verification|awaiting platform verification|satisfied.*verification|assurance/i.test(text)) {
    return true;
  }
  if (requirementRow) {
    const state = resolveClientRequirementLifecycle(requirementRow).state;
    if (state === 'SATISFIED_UNVERIFIED' || state === 'PENDING_REVIEW') return true;
  }
  return false;
}

/**
 * Avoid stale "Upload and verify…" on assurance / satisfied rows.
 * @param {string} actionText
 * @param {Record<string, unknown>|null|undefined} requirementRow
 * @param {string} [displayLabel]
 * @param {Array<Record<string, unknown>>|null|undefined} [candidateRows]
 * @returns {string}
 */
export function resolveQuickActionDisplayText(actionText, requirementRow, displayLabel, candidateRows) {
  const base = String(actionText || '').trim();
  const lbl =
    displayLabel ||
    requirementRow?.display_label ||
    requirementRow?.requirement_type ||
    'this obligation';
  const rows = [requirementRow, ...(Array.isArray(candidateRows) ? candidateRows : [])].filter(Boolean);
  for (const row of rows) {
    if (!isAssuranceQuickAction(base, row)) continue;
    if (/upload and verify/i.test(base)) {
      const rowLbl = row?.display_label || row?.requirement_type || lbl;
      return `Review assurance status for ${rowLbl}`;
    }
    return base;
  }
  return base;
}

/**
 * @param {boolean} isAssuranceAction
 * @returns {string}
 */
export function quickActionSupportingCopy(isAssuranceAction) {
  return isAssuranceAction
    ? 'Score reflects assurance confidence — not an active legal breach.'
    : 'Completing this can help improve your score.';
}
