/**
 * CER governance truth-surface presentation — Phase 1.
 * Prefers server-authoritative governance fields; falls back safely for legacy rows.
 */

import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';

const GENERIC_REVIEW_LABELS = /^awaiting review$|^review pending$/i;

/**
 * @param {string} stage
 * @param {boolean} queueBacked
 * @returns {'ACTION_REQUIRED'|'PENDING_REVIEW'|'SATISFIED_UNVERIFIED'|'VERIFIED'|'NOT_APPLICABLE'}
 */
export function mapTruthStageToLifecycleState(stage, queueBacked) {
  const s = String(stage || '').trim();
  if (s === 'verified') return 'VERIFIED';
  if (s === 'platform_verification_pending' || s === 'escalation_review') return 'PENDING_REVIEW';
  if (queueBacked && s === 'awaiting_review') return 'PENDING_REVIEW';
  if (s === 'followup_required' || s === 'operational_incomplete' || s === 'action_required') {
    return 'ACTION_REQUIRED';
  }
  if (
    s === 'declaration_recorded' ||
    s === 'assessment_recorded' ||
    s === 'evidence_recorded' ||
    s === 'recorded_on_file'
  ) {
    return 'SATISFIED_UNVERIFIED';
  }
  if (s === 'supporting_upload_only') return 'ACTION_REQUIRED';
  return 'ACTION_REQUIRED';
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function hasGovernanceTruthSurface(row) {
  return Boolean(String(row?.truth_presentation_label || '').trim() && String(row?.truth_presentation_stage || '').trim());
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveTruthPresentationLabel(row) {
  const fromApi = String(row?.truth_presentation_label || row?.client_lifecycle_label || '').trim();
  if (fromApi && !GENERIC_REVIEW_LABELS.test(fromApi)) return fromApi;
  if (fromApi && row?.queue_backed_review === true) return fromApi;
  return fromApi || null;
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveTruthPresentationSubline(row) {
  return String(row?.truth_presentation_subline || '').trim() || null;
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {boolean}
 */
export function isQueueBackedReview(row) {
  if (row?.queue_backed_review === true) return true;
  const owner = String(row?.review_owner || '').trim();
  return owner === 'platform_admin' || owner === 'platform_admin_escalation' || owner === 'org_admin';
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {{ text: string, className: string } | null}
 */
export function resolveGovernanceTierBadge(row) {
  const supplement = String(row?.truth_presentation_tier_supplement || '').trim();
  if (!supplement) return null;
  const primary = resolveTruthPresentationLabel(row) || '';
  if (primary && primary.toLowerCase() === supplement.toLowerCase()) return null;
  if (/follow-up|remediation|organisation verification/i.test(supplement)) {
    return {
      text: supplement,
      className: 'bg-slate-100 text-slate-900 border-slate-300',
    };
  }
  return {
    text: supplement,
    className: 'bg-slate-100 text-slate-800 border-slate-300',
  };
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {ReturnType<typeof resolveClientRequirementLifecycle>}
 */
export function resolveGovernanceAwareLifecycle(row) {
  const base = resolveClientRequirementLifecycle(row);
  if (!hasGovernanceTruthSurface(row)) return base;

  const label = resolveTruthPresentationLabel(row) || base.label;
  const queueBacked = isQueueBackedReview(row);
  const state = mapTruthStageToLifecycleState(String(row?.truth_presentation_stage || ''), queueBacked);

  return {
    ...base,
    state,
    label,
    reasonCodes: [...(base.reasonCodes || []), 'GOVERNANCE_TRUTH_SURFACE'],
    source: 'presentation',
  };
}

/**
 * @param {string|null|undefined} a
 * @param {string|null|undefined} b
 */
export function labelsDuplicateSemantics(a, b) {
  const left = String(a || '').trim().toLowerCase();
  const right = String(b || '').trim().toLowerCase();
  if (!left || !right) return false;
  if (left === right) return true;
  if (GENERIC_REVIEW_LABELS.test(left) && GENERIC_REVIEW_LABELS.test(right)) return true;
  if (/^verified$/i.test(left) && /^verified$/i.test(right)) return true;
  if (/^awaiting review$/i.test(left) && /^review pending$/i.test(right)) return true;
  return false;
}
