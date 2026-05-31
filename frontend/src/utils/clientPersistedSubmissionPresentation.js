/**
 * OPS / TRUST-01 + CER Phase 1: truth-surface presentation for persisted submissions.
 * Does not change backend authority — consumes governance fields when present.
 */

import { resolveGovernanceAwareLifecycle, isQueueBackedReview, resolveTruthPresentationSubline } from './cerGovernancePresentation';
import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function requirementHasPersistedClientSubmission(row) {
  if (!row || typeof row !== 'object') return false;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const primaryId = String(
    ea?.primary_evidence_record_id || row.primary_evidence_record_id || row.latest_evidence_record_id || '',
  ).trim();
  if (primaryId) return true;
  if (String(row.evidence_record_id || '').trim()) return true;
  if (row.evidence_doc_id || String(row.document_id || '').trim()) return true;
  return false;
}

/**
 * Queue-backed review pending (not generic operational incompleteness).
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isSubmissionAwaitingReview(row) {
  if (!requirementHasPersistedClientSubmission(row)) return false;
  if (isQueueBackedReview(row)) return true;
  const reqStatus = String(row.status || '').trim().toUpperCase();
  if (reqStatus === 'COMPLIANT') return false;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const eaState = String(ea?.state || '').toUpperCase();
  if (eaState === 'VERIFIED_CURRENT' || eaState === 'VERIFIED') return false;
  if (eaState === 'PENDING_ADMIN_REVIEW') return true;
  const lc = String(row.client_lifecycle_state || '').trim().toUpperCase();
  if (lc === 'PENDING_REVIEW' && row?.governance_family === 'PLATFORM_VERIFIED') return true;
  return false;
}

/**
 * Presentation lifecycle for client surfaces (lists, modals, chips).
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {ReturnType<typeof resolveClientRequirementLifecycle>}
 */
export function resolveClientRequirementLifecycleForPresentation(row) {
  if (row?.truth_presentation_label) {
    return resolveGovernanceAwareLifecycle(row);
  }
  const base = resolveClientRequirementLifecycle(row);
  if (!isSubmissionAwaitingReview(row)) return base;
  if (base.state === 'PENDING_REVIEW' || base.state === 'VERIFIED' || base.state === 'SATISFIED_UNVERIFIED') {
    return base;
  }
  if (isQueueBackedReview(row)) {
    const owner = String(row?.review_owner || '');
    let label = 'Platform verification pending';
    if (owner === 'org_admin') label = 'Organisation review pending';
    if (owner === 'platform_admin_escalation') label = 'Escalated for platform review';
    return {
      ...base,
      state: 'PENDING_REVIEW',
      label,
      reasonCodes: [...(base.reasonCodes || []), 'QUEUE_BACKED_REVIEW'],
      source: 'presentation',
    };
  }
  return base;
}

/**
 * @param {string|null|undefined} badgeLabel
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveSubmissionAwareEvidenceBadgeLabel(badgeLabel, row) {
  const raw = String(badgeLabel || '').trim();
  if (!raw) return null;
  if (!requirementHasPersistedClientSubmission(row)) return raw;
  if (/^not uploaded$/i.test(raw) || /^no document uploaded$/i.test(raw)) {
    return 'Submission on file';
  }
  if (/^submission received$/i.test(raw)) {
    return 'Submission on file';
  }
  return raw;
}

/**
 * @param {Record<string, unknown>|null|undefined} row
 */
export function submissionAwaitingReviewSubline(row) {
  const fromApi = resolveTruthPresentationSubline(row);
  if (fromApi) return fromApi;
  if (!isSubmissionAwaitingReview(row)) return null;
  const owner = String(row?.review_owner || '');
  if (owner === 'platform_admin') {
    return 'Document submitted — Pleerity verification in progress.';
  }
  if (owner === 'org_admin') {
    return 'Your organisation admin can verify this record when required.';
  }
  return null;
}

/** @typedef {{ requirement_id: string; property_id?: string; at?: number; document_count?: number }} SupportingUploadAttributionDetail */

export const COMPLIANCE_SUPPORTING_UPLOAD_EVENT = 'compliance-supporting-upload';

const SUPPORTING_UPLOAD_SESSION_PREFIX = 'cvp_recent_supporting_upload:';

export function dispatchSupportingUploadAttribution(detail) {
  if (typeof window === 'undefined' || !detail?.requirement_id) return;
  const payload = { at: Date.now(), ...detail };
  try {
    sessionStorage.setItem(
      `${SUPPORTING_UPLOAD_SESSION_PREFIX}${detail.requirement_id}`,
      JSON.stringify(payload),
    );
  } catch {
    /* ignore quota / private mode */
  }
  window.dispatchEvent(
    new CustomEvent(COMPLIANCE_SUPPORTING_UPLOAD_EVENT, {
      detail: payload,
    }),
  );
}

/**
 * @returns {Record<string, number>}
 */
export function readRecentSupportingUploadAttributionFromSession() {
  if (typeof window === 'undefined' || !window.sessionStorage) return {};
  const out = {};
  try {
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (!key || !key.startsWith(SUPPORTING_UPLOAD_SESSION_PREFIX)) continue;
      const rid = key.slice(SUPPORTING_UPLOAD_SESSION_PREFIX.length);
      const raw = sessionStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      if (parsed?.at) out[rid] = Number(parsed.at);
    }
  } catch {
    return out;
  }
  return out;
}

/**
 * @param {string|null|undefined} requirementId
 * @param {Record<string, number>|null|undefined} recentByRequirementId ms timestamp per requirement_id
 */
export function recentSupportingUploadAttributionSubline(requirementId, recentByRequirementId) {
  const rid = String(requirementId || '').trim();
  if (!rid || !recentByRequirementId || !recentByRequirementId[rid]) return null;
  return 'Additional supporting document uploaded — does not replace your submission on file.';
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 */
export function resolveStaticSupportingUploadDisclaimer(requirement) {
  const hasSubmission = requirementHasPersistedClientSubmission(requirement);
  const lines = [
    'Uploading supporting files here saves them to your vault only.',
    'It does not submit or update your formal requirement record until you complete the structured form and press Submit evidence.',
  ];
  if (hasSubmission) {
    lines.push(
      'Your authoritative submission is already on file. New supporting files supplement that record — they do not create a new submission.',
    );
  }
  return lines;
}
