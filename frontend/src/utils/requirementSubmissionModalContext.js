/**
 * REQUIREMENT-SUBMISSION-MODAL-ACTION-CONVERGENCE-01 — context-aware modal actions.
 * Display-only UX; does not mutate lifecycle, scoring, or assurance-tier authority.
 */

import { isViewExistingSubmissionCta } from './complianceEvidenceSubmissionView';
import {
  requirementHasPersistedClientSubmission,
  resolveClientRequirementLifecycleForPresentation,
} from './clientPersistedSubmissionPresentation';
import { primaryLabelSuggestsInitialObligation } from './requirementLifecyclePresentation';
import { getOperationalCognition, truthWarningsFromCognition } from './operationalCognition';
import { ASSURANCE_SELF_RECORDED, resolveAssuranceTier } from './assurancePresentation';

/** @typedef {'satisfy_requirement'|'view_submission'|'view_verified_evidence'} RequirementSubmissionModalContext */

export const MODAL_CONTEXT = {
  SATISFY_REQUIREMENT: 'satisfy_requirement',
  VIEW_SUBMISSION: 'view_submission',
  VIEW_VERIFIED_EVIDENCE: 'view_verified_evidence',
};

/** @typedef {'update_submission'|'add_supporting_evidence'|'view_documents'|'view_evidence'|'satisfy'|'close'} ModalFooterActionKey */

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
function hasVerifiedEvidenceAuthority(row) {
  if (!row || typeof row !== 'object') return false;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const eaState = String(ea?.state || '').toUpperCase();
  if (eaState === 'VERIFIED_CURRENT' || eaState === 'EA_VERIFIED_CURRENT') return true;
  if (String(row.truth_presentation_stage || '').trim().toLowerCase() === 'verified') return true;
  return false;
}

/**
 * @param {Record<string, unknown>|null|undefined} merged
 * @param {Record<string, unknown>|null|undefined} resolved
 */
function isViewVerifiedEvidenceIntent(merged, resolved) {
  if (hasVerifiedEvidenceAuthority(merged)) return true;
  const lifecycle = resolveClientRequirementLifecycleForPresentation(merged);
  if (lifecycle?.state === 'VERIFIED') return true;
  const label = String(resolved?.primary_action_label || '').trim();
  if (/^view verified evidence$/i.test(label)) return true;
  const route = String(resolved?.primary_route || '');
  if (lifecycle?.state === 'SATISFIED_UNVERIFIED' && route.includes('/documents')) {
    return /^view evidence$/i.test(label);
  }
  return false;
}

/**
 * @param {{
 *   merged?: Record<string, unknown>|null,
 *   hasSubmission?: boolean,
 *   initialFocusSubmission?: boolean,
 *   resolved?: Record<string, unknown>|null,
 * }} input
 * @returns {{ context: RequirementSubmissionModalContext, lifecycle: ReturnType<typeof resolveClientRequirementLifecycleForPresentation> }}
 */
export function resolveRequirementSubmissionModalContext(input = {}) {
  const merged = input.merged && typeof input.merged === 'object' ? input.merged : null;
  const resolved = input.resolved && typeof input.resolved === 'object' ? input.resolved : null;
  const hasSubmission = Boolean(
    input.hasSubmission || (merged && requirementHasPersistedClientSubmission(merged)),
  );
  const initialFocusSubmission = Boolean(input.initialFocusSubmission);
  const lifecycle = resolveClientRequirementLifecycleForPresentation(merged);
  const state = lifecycle?.state || 'ACTION_REQUIRED';

  const viewingExisting =
    initialFocusSubmission && hasSubmission;

  if (viewingExisting) {
    if (isViewVerifiedEvidenceIntent(merged, resolved)) {
      return { context: MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE, lifecycle };
    }
    return { context: MODAL_CONTEXT.VIEW_SUBMISSION, lifecycle };
  }

  if (
    hasSubmission &&
    (isViewExistingSubmissionCta(resolved) || isViewVerifiedEvidenceIntent(merged, resolved))
  ) {
    if (isViewVerifiedEvidenceIntent(merged, resolved)) {
      return { context: MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE, lifecycle };
    }
    return { context: MODAL_CONTEXT.VIEW_SUBMISSION, lifecycle };
  }

  if (state === 'ACTION_REQUIRED' && !hasSubmission) {
    return { context: MODAL_CONTEXT.SATISFY_REQUIREMENT, lifecycle };
  }

  if (!hasSubmission) {
    return { context: MODAL_CONTEXT.SATISFY_REQUIREMENT, lifecycle };
  }

  if (
    resolved &&
    primaryLabelSuggestsInitialObligation(String(resolved.primary_action_label || ''))
  ) {
    return { context: MODAL_CONTEXT.VIEW_SUBMISSION, lifecycle };
  }

  return { context: MODAL_CONTEXT.SATISFY_REQUIREMENT, lifecycle };
}

/**
 * @param {{
 *   context: RequirementSubmissionModalContext,
 *   lifecycle: ReturnType<typeof resolveClientRequirementLifecycleForPresentation>,
 *   merged?: Record<string, unknown>|null,
 *   statusEvidenceLine?: string|null,
 * }} input
 * @returns {{ headline: string, subline: string, primaryLabel: string, warningMessage?: string|null, useServerHero: boolean, showHeroPrimary?: boolean }}
 */
export function resolveModalHeroPresentation(input) {
  const { context, lifecycle, merged, statusEvidenceLine } = input;
  const state = lifecycle?.state || 'ACTION_REQUIRED';
  const cognition = getOperationalCognition(merged);
  const truthWarnings = truthWarningsFromCognition(cognition);
  const warningMessage = truthWarnings[0]?.message || null;

  if (context === MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE) {
    return {
      headline: 'Evidence verified',
      subline: 'This evidence is accepted for this requirement.',
      primaryLabel: 'View evidence',
      warningMessage: null,
      useServerHero: false,
      showHeroPrimary: false,
    };
  }

  if (context === MODAL_CONTEXT.VIEW_SUBMISSION) {
    if (state === 'PENDING_REVIEW') {
      return {
        headline: 'Awaiting platform review',
        subline: 'Your submission is waiting for review.',
        primaryLabel: 'Update submission',
        warningMessage,
        useServerHero: false,
        showHeroPrimary: false,
      };
    }
    const assurance = resolveAssuranceTier(merged);
    const subline =
      String(statusEvidenceLine || '').trim() ||
      'Your record is on file. You can update it or add supporting evidence.';
    return {
      headline: 'Submission recorded',
      subline,
      primaryLabel: 'Update submission',
      warningMessage: assurance === ASSURANCE_SELF_RECORDED ? warningMessage : warningMessage,
      useServerHero: false,
      showHeroPrimary: false,
    };
  }

  return {
    headline: '',
    subline: '',
    primaryLabel: '',
    warningMessage: null,
    useServerHero: true,
    showHeroPrimary: true,
  };
}

/**
 * @param {{
 *   context: RequirementSubmissionModalContext,
 *   resolved?: Record<string, unknown>|null,
 *   showEditDatesAndApplicability?: boolean,
 *   showUploadSecondary?: boolean,
 * }} input
 * @returns {Array<{ key: ModalFooterActionKey, label: string, variant?: 'primary'|'secondary'|'link' }>}
 */
export function resolveModalFooterActions(input) {
  const { context, resolved, showEditDatesAndApplicability, showUploadSecondary } = input;
  const primaryLabel = String(resolved?.primary_action_label || '').trim() || 'Take action';

  if (context === MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE) {
    /** @type {Array<{ key: ModalFooterActionKey, label: string, variant?: 'primary'|'secondary'|'link' }>} */
    const actions = [
      { key: 'view_evidence', label: 'View evidence', variant: 'primary' },
      { key: 'add_supporting_evidence', label: 'Add supporting evidence', variant: 'link' },
      { key: 'view_documents', label: 'View documents', variant: 'link' },
    ];
    if (showEditDatesAndApplicability) {
      actions.push({ key: 'edit_dates', label: 'Edit dates and applicability', variant: 'link' });
    }
    actions.push({ key: 'close', label: 'Close', variant: 'secondary' });
    return actions;
  }

  if (context === MODAL_CONTEXT.VIEW_SUBMISSION) {
    /** @type {Array<{ key: ModalFooterActionKey, label: string, variant?: 'primary'|'secondary'|'link' }>} */
    const actions = [
      { key: 'update_submission', label: 'Update submission', variant: 'primary' },
      { key: 'add_supporting_evidence', label: 'Add supporting evidence', variant: 'link' },
      { key: 'view_documents', label: 'View documents', variant: 'link' },
    ];
    if (showEditDatesAndApplicability) {
      actions.push({ key: 'edit_dates', label: 'Edit dates and applicability', variant: 'link' });
    }
    actions.push({ key: 'close', label: 'Close', variant: 'secondary' });
    return actions;
  }

  /** @type {Array<{ key: ModalFooterActionKey, label: string, variant?: 'primary'|'secondary'|'link' }>} */
  const actions = [{ key: 'satisfy', label: primaryLabel, variant: 'primary' }];
  if (showUploadSecondary) {
    actions.push({ key: 'add_supporting_evidence', label: 'Upload document', variant: 'link' });
  }
  actions.push({ key: 'view_documents', label: 'View documents', variant: 'link' });
  if (showEditDatesAndApplicability) {
    actions.push({ key: 'edit_dates', label: 'Edit dates and applicability', variant: 'link' });
  }
  actions.push({ key: 'close', label: 'Close', variant: 'secondary' });
  return actions;
}

/**
 * Whether duplicate "View submission" link should be suppressed in footer.
 * @param {RequirementSubmissionModalContext} context
 * @param {boolean} initialFocusSubmission
 */
export function shouldSuppressViewSubmissionLink(context, initialFocusSubmission) {
  if (initialFocusSubmission) return true;
  return context === MODAL_CONTEXT.VIEW_SUBMISSION || context === MODAL_CONTEXT.VIEW_VERIFIED_EVIDENCE;
}
