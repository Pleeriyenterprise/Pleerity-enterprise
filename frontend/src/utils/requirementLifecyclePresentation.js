/**
 * Shared lifecycle-driven **presentation** (row chrome, badges, CTA copy) for requirement rows.
 * Uses {@link resolveClientRequirementLifecycle} only — does not change backend authority.
 */

import { resolveClientRequirementLifecycleForPresentation } from './clientPersistedSubmissionPresentation';
import {
  authorityPermitsVerifiedPresentationLanguage,
  isRightToRentMixedEvidencePendingReview,
  isRightToRentRequirement,
  resolveRightToRentMixedEvidenceCtaPresentation,
} from './rightToRentTrustPresentation';

/**
 * @param {string} label
 * @returns {boolean} true when copy reads like “first-time record/upload” obligation
 */
export function primaryLabelSuggestsInitialObligation(label) {
  const s = String(label || '').trim();
  if (!s) return false;
  if (/^record\b/i.test(s)) return true;
  if (/^upload\b/i.test(s)) return true;
  if (/^add compliance evidence\b/i.test(s)) return true;
  return false;
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} cta from {@link resolveRequirementActionWithRowContext}
 * @returns {Record<string, unknown>} shallow clone with display-only label overrides
 */
export function applyLifecycleAwareCtaPresentation(requirement, cta) {
  if (!cta || typeof cta !== 'object') return cta || {};
  const rtrCta = resolveRightToRentMixedEvidenceCtaPresentation(requirement, cta);
  if (rtrCta) return rtrCta;
  const { state } = resolveClientRequirementLifecycleForPresentation(requirement);
  if (state === 'ACTION_REQUIRED' || state === 'NOT_APPLICABLE') {
    return cta;
  }
  const baseLabel = String(cta.primary_action_label || '');
  if (!primaryLabelSuggestsInitialObligation(baseLabel)) {
    return cta;
  }
  const route = String(cta.primary_route || '');
  const handler = String(cta.primary_action_handler || '');
  let primary_action_label = baseLabel;
  if (state === 'PENDING_REVIEW') {
    if (handler === 'guided_evidence') primary_action_label = 'View submission';
    else if (route.includes('/documents')) primary_action_label = 'View evidence';
    else primary_action_label = 'Review submission';
  } else if (state === 'SATISFIED_UNVERIFIED') {
    primary_action_label = handler === 'guided_evidence' ? 'View or update evidence' : 'View evidence';
  } else if (state === 'VERIFIED') {
    const suppressVerified =
      isRightToRentMixedEvidencePendingReview(requirement) ||
      (isRightToRentRequirement(requirement) && !authorityPermitsVerifiedPresentationLanguage(requirement));
    if (suppressVerified && handler === 'guided_evidence') {
      primary_action_label = 'View evidence under review';
    } else if (suppressVerified) {
      primary_action_label = 'View evidence';
    } else {
      primary_action_label = handler === 'guided_evidence' ? 'View verified evidence' : 'View evidence';
    }
  }
  let secondary_action = cta.secondary_action;
  if (secondary_action && typeof secondary_action === 'object') {
    const secLabel = String(secondary_action.label || '');
    if (state === 'PENDING_REVIEW' && /^upload\b/i.test(secLabel) && !/additional/i.test(secLabel)) {
      secondary_action = { ...secondary_action, label: 'Upload additional evidence' };
    }
  }
  return { ...cta, primary_action_label, secondary_action };
}

/**
 * Row / list container — left accent + soft panel tint by lifecycle tier.
 * @param {Record<string, unknown>|null|undefined} row
 */
export function getRequirementLifecycleRowSurfaceClass(row) {
  const { state } = resolveClientRequirementLifecycleForPresentation(row);
  switch (state) {
    case 'ACTION_REQUIRED':
      return 'border-l-4 border-l-red-600 bg-white';
    case 'PENDING_REVIEW':
      return 'border-l-4 border-l-amber-500 bg-amber-50/55';
    case 'SATISFIED_UNVERIFIED':
      return 'border-l-4 border-l-emerald-600 bg-emerald-50/45';
    case 'VERIFIED':
      return 'border-l-4 border-l-green-700 bg-green-50/40';
    case 'NOT_APPLICABLE':
      return 'border-l-4 border-l-slate-300 bg-slate-50/60';
    default:
      return 'border-l-4 border-l-gray-300 bg-white';
  }
}

/**
 * Card shell (Operating hub, compact lists).
 * @param {Record<string, unknown>|null|undefined} row
 */
export function getRequirementLifecycleCardShellClass(row) {
  const { state } = resolveClientRequirementLifecycleForPresentation(row);
  const base = 'rounded-xl border min-w-0 shadow-sm';
  switch (state) {
    case 'ACTION_REQUIRED':
      return `${base} border-red-200 bg-white`;
    case 'PENDING_REVIEW':
      return `${base} border-amber-300 bg-amber-50/50`;
    case 'SATISFIED_UNVERIFIED':
      return `${base} border-emerald-200 bg-emerald-50/40`;
    case 'VERIFIED':
      return `${base} border-green-200 bg-green-50/35`;
    case 'NOT_APPLICABLE':
      return `${base} border-slate-200 bg-slate-50/50`;
    default:
      return `${base} border-gray-200 bg-white`;
  }
}

/**
 * Optional secondary badge (lifecycle tier) — use beside status chip when not redundant.
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {{ text: string, className: string } | null}
 */
export function getLifecycleTierBadge(row) {
  const { state } = resolveClientRequirementLifecycleForPresentation(row);
  if (state === 'PENDING_REVIEW') {
    return {
      text: 'Awaiting review',
      className: 'bg-amber-100 text-amber-950 border-amber-300',
    };
  }
  if (state === 'SATISFIED_UNVERIFIED') {
    return {
      text: 'Evidence on file',
      className: 'bg-emerald-100 text-emerald-950 border-emerald-300',
    };
  }
  if (state === 'VERIFIED') {
    return {
      text: 'Verified',
      className: 'bg-green-100 text-green-900 border-green-300',
    };
  }
  return null;
}

/**
 * Icon well (left avatar) tone for requirement rows.
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {'red'|'amber'|'emerald'|'green'|'slate'|'gray'}
 */
export function getRequirementLifecycleIconTone(row) {
  const { state } = resolveClientRequirementLifecycleForPresentation(row);
  if (state === 'ACTION_REQUIRED') return 'red';
  if (state === 'PENDING_REVIEW') return 'amber';
  if (state === 'SATISFIED_UNVERIFIED') return 'emerald';
  if (state === 'VERIFIED') return 'green';
  if (state === 'NOT_APPLICABLE') return 'slate';
  return 'gray';
}
