/**
 * Shared job-detail primary action resolver — hero, contractor section, and previews
 * must route through the same intent + entitlement gates.
 */
import { toast } from '@/utils/portalNotifications';
import { getOperationalCognition, heroPrimaryFromCognition } from './operationalCognition';
import { normalizeOperationalPrimaryKey } from './primaryActionResolver';
import { prioritizedClientJobNextAction } from './jobWorkflowUi';

/** Keys that scroll/focus the Visit section (scheduling sub-flow). */
export const JOB_DETAIL_VISIT_SCROLL_ACTIONS = new Set([
  'request_booking',
  'propose_schedule',
  'reschedule_booking',
  'confirm_visit',
  'request_visit_reschedule',
  'cancel_booking',
  'mark_no_access',
  'mark_reschedule_required',
]);

const JOB_DETAIL_NAVIGATION_ACTIONS = new Set(['open_job', 'view_job', 'open_job_detail']);

/**
 * @param {Record<string, unknown>|null|undefined} job
 * @returns {string|null}
 */
export function resolveHeroPrimaryActionKey(job) {
  const fromCognition = heroPrimaryFromCognition(getOperationalCognition(job));
  if (fromCognition?.key) return normalizeOperationalPrimaryKey(fromCognition.key);
  const prioritized = prioritizedClientJobNextAction(job);
  if (prioritized?.id) return normalizeOperationalPrimaryKey(prioritized.id);
  return null;
}

/**
 * @param {Record<string, unknown>|null|undefined} job
 */
export function jobHasNextAction(job, actionId) {
  const id = String(actionId || '').trim();
  if (!id) return false;
  return (job?.next_actions || []).some((a) => a?.id === id);
}

/**
 * @param {Record<string, unknown>|null|undefined} job
 * @param {boolean} hasContractorNetwork
 */
export function canExecuteAssignContractor(job, hasContractorNetwork) {
  if (!hasContractorNetwork) return false;
  return jobHasNextAction(job, 'assign_contractor') || jobHasNextAction(job, 'assign');
}

/**
 * Assign is advertised (next_actions or hero) but entitlement blocks execution.
 * @param {Record<string, unknown>|null|undefined} job
 * @param {boolean} hasContractorNetwork
 */
export function isAssignContractorEntitlementBlocked(job, hasContractorNetwork) {
  if (hasContractorNetwork) return false;
  const key = resolveHeroPrimaryActionKey(job);
  if (key === 'assign_contractor') return true;
  return jobHasNextAction(job, 'assign_contractor') || jobHasNextAction(job, 'assign');
}

/**
 * @param {string|null|undefined} key
 * @returns {{ kind: 'none'|'assign_contractor'|'scroll_visit'|'navigate'|'unknown', key: string|null, url?: string }}
 */
export function jobDetailPrimaryIntentFromKey(key) {
  const k = String(key || '').trim();
  if (!k || k === 'none') return { kind: 'none', key: null };
  if (k === 'assign_contractor') return { kind: 'assign_contractor', key: k };
  if (JOB_DETAIL_VISIT_SCROLL_ACTIONS.has(k)) return { kind: 'scroll_visit', key: k };
  if (JOB_DETAIL_NAVIGATION_ACTIONS.has(k)) return { kind: 'navigate', key: k };
  return { kind: 'unknown', key: k };
}

/**
 * @param {Record<string, unknown>|null|undefined} job
 * @returns {ReturnType<typeof jobDetailPrimaryIntentFromKey>}
 */
export function resolveJobDetailPrimaryIntent(job) {
  return jobDetailPrimaryIntentFromKey(resolveHeroPrimaryActionKey(job));
}

/**
 * Hero execution gate — never offer a clickable assign without contractor_network.
 * @param {Record<string, unknown>|null|undefined} job
 * @param {boolean} hasContractorNetwork
 */
export function resolveHeroPrimaryExecution(job, hasContractorNetwork) {
  const intent = resolveJobDetailPrimaryIntent(job);
  if (intent.kind === 'none') {
    return { intent, executable: false, blockedMessage: null };
  }
  if (intent.kind === 'assign_contractor') {
    if (!hasContractorNetwork) {
      return {
        intent,
        executable: false,
        lockedUpsell: true,
        blockedMessage:
          'Contractor assignment is included on the Professional plan. Open this action to view upgrade and support options.',
      };
    }
    if (!canExecuteAssignContractor(job, hasContractorNetwork)) {
      return {
        intent,
        executable: false,
        lockedUpsell: false,
        blockedMessage: 'Contractor assignment is not available for this job right now.',
      };
    }
    if (!jobHasNextAction(job, 'assign_contractor') && !jobHasNextAction(job, 'assign')) {
      return {
        intent,
        executable: false,
        blockedMessage: 'Contractor assignment is not available for this job right now.',
      };
    }
    return { intent, executable: true, blockedMessage: null };
  }
  if (intent.kind === 'unknown') {
    return {
      intent,
      executable: false,
      blockedMessage: 'This action is not available from the job page yet. Use the sections below.',
    };
  }
  return { intent, executable: true, blockedMessage: null };
}

/**
 * Whole-job cancel — governed by next_actions lifecycle entry (not raw status alone).
 * @param {Record<string, unknown>|null|undefined} job
 */
export function canShowCancelJob(job) {
  return jobHasNextAction(job, 'cancel');
}

/**
 * @param {ReturnType<typeof resolveJobDetailPrimaryIntent>} intent
 * @param {{
 *   openAssignModal?: (opts?: { focusAdd?: boolean }) => void,
 *   scrollToVisit?: () => void,
 *   navigate?: (url: string) => void,
 *   onUnknown?: (key: string) => void,
 * }} handlers
 */
export function executeJobDetailPrimaryIntent(intent, handlers = {}) {
  if (!intent || intent.kind === 'none') return;
  if (intent.kind === 'assign_contractor') {
    handlers.openAssignModal?.();
    return;
  }
  if (intent.kind === 'scroll_visit') {
    handlers.scrollToVisit?.();
    return;
  }
  if (intent.kind === 'navigate') {
    const url =
      getOperationalCognition(handlers.job)?.primary_action?.url ||
      handlers.job?.operational_cognition?.primary_action?.url;
    if (url && handlers.navigate) {
      handlers.navigate(url);
      return;
    }
    handlers.scrollToVisit?.();
    return;
  }
  if (intent.kind === 'unknown' && intent.key) {
    if (handlers.onUnknown) handlers.onUnknown(intent.key);
    else toast.message('This action is not available from the job page yet. Use the sections below.');
  }
}

/**
 * Unified assign-contractor click — hero, contractor section, booking guard.
 * @param {Record<string, unknown>|null|undefined} job
 * @param {boolean} hasContractorNetwork
 * @param {(opts?: { focusAdd?: boolean }) => void} openAssignModal
 * @param {{ focusAdd?: boolean }} [opts]
 */
export function handleAssignContractorClick(job, hasContractorNetwork, openAssignModal, opts = {}) {
  if (!hasContractorNetwork) {
    opts.onLocked?.();
    return;
  }
  if (!canExecuteAssignContractor(job, hasContractorNetwork)) {
    toast.message('Contractor assignment is not available for this job right now.');
    return;
  }
  openAssignModal(opts);
}
