/**
 * OPS / TRUST-01: frontend presentation when persisted client submission exists but API
 * lifecycle still reads ACTION_REQUIRED / missing-evidence. Does not change backend authority.
 */

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
 * Persisted submission still in client/admin review (not verified current).
 * @param {Record<string, unknown>|null|undefined} row
 */
export function isSubmissionAwaitingReview(row) {
  if (!requirementHasPersistedClientSubmission(row)) return false;
  const lc = String(row.client_lifecycle_state || '').trim().toUpperCase();
  if (lc === 'PENDING_REVIEW') return true;
  const ea = row.evidence_authority && typeof row.evidence_authority === 'object' ? row.evidence_authority : null;
  const eaState = String(ea?.state || '').toUpperCase();
  if (eaState === 'PENDING_ADMIN_REVIEW') return true;
  const vs = String(row.verification_status || row.client_evidence_verification_status || '').toUpperCase();
  if (vs === 'PENDING_REVIEW') return true;
  if (lc === 'ACTION_REQUIRED' || eaState === 'MISSING') return true;
  return false;
}

/**
 * Presentation lifecycle for client surfaces (lists, modals, chips).
 * @param {Record<string, unknown>|null|undefined} row
 * @returns {ReturnType<typeof resolveClientRequirementLifecycle>}
 */
export function resolveClientRequirementLifecycleForPresentation(row) {
  const base = resolveClientRequirementLifecycle(row);
  if (!isSubmissionAwaitingReview(row)) return base;
  if (base.state === 'PENDING_REVIEW' || base.state === 'VERIFIED' || base.state === 'SATISFIED_UNVERIFIED') {
    return base;
  }
  return {
    ...base,
    state: 'PENDING_REVIEW',
    label: 'Awaiting review',
    reasonCodes: [...(base.reasonCodes || []), 'FRONTEND_SUBMISSION_ON_FILE'],
    source: 'presentation',
  };
}

/**
 * @param {string|null|undefined} badgeLabel
 * @param {Record<string, unknown>|null|undefined} row
 */
export function resolveSubmissionAwareEvidenceBadgeLabel(badgeLabel, row) {
  const raw = String(badgeLabel || '').trim();
  if (!raw) return null;
  if (!isSubmissionAwaitingReview(row)) return raw;
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
  if (!isSubmissionAwaitingReview(row)) return null;
  return 'Authoritative submission on file — awaiting review. Supporting uploads alone do not complete this obligation.';
}

/** @typedef {{ requirement_id: string; property_id?: string; at?: number; document_count?: number }} SupportingUploadAttributionDetail */

export const COMPLIANCE_SUPPORTING_UPLOAD_EVENT = 'compliance-supporting-upload';

/**
 * @param {SupportingUploadAttributionDetail} detail
 */
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
 * Static copy shown before evidence-resolution API finishes (OPS-VERIFY-01 Journey C).
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
