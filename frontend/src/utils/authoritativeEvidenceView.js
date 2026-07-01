/**
 * POST-SUBMISSION-EVIDENCE-UX-FIX-P0 — authoritative evidence view routing.
 * Decides whether settled evidence is document-primary or record-primary (CER).
 */

import { normalizeRouteId } from './clientPortalNavigation';
import { resolvePropertyEvidenceRegistryPath } from './documentEvidenceAuthority';

export { resolveAuthoritativeEvidenceViewPath } from './resolveEvidenceNavigationTarget';

export const NON_DOCUMENT_EVIDENCE_MODES = new Set([
  'STRUCTURED_DECLARATION',
  'INSPECTION_CHECKLIST',
  'CONTRACTOR_CONFIRMATION',
]);

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 */
export function requirementHasLinkedAuthoritativeDocument(requirement) {
  if (!requirement || typeof requirement !== 'object') return false;
  const ea =
    requirement.evidence_authority && typeof requirement.evidence_authority === 'object'
      ? requirement.evidence_authority
      : null;
  const docId =
    ea?.effective_verified_document_id ||
    requirement.document_id ||
    requirement.evidence_doc_id;
  return Boolean(String(docId || '').trim());
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} [latestCer]
 */
export function requirementAuthoritativeEvidenceIsRecordPrimary(requirement, latestCer = null) {
  if (!requirement || typeof requirement !== 'object') return false;
  if (requirementHasLinkedAuthoritativeDocument(requirement)) return false;

  const mode = String(latestCer?.evidence_mode || '').trim().toUpperCase();
  if (mode && NON_DOCUMENT_EVIDENCE_MODES.has(mode)) return true;

  const ea =
    requirement.evidence_authority && typeof requirement.evidence_authority === 'object'
      ? requirement.evidence_authority
      : null;
  const cerId = String(
    ea?.primary_evidence_record_id || requirement.primary_evidence_record_id || '',
  ).trim();
  if (!cerId) return false;

  const reason = String(ea?.state_reason || '').toLowerCase();
  if (
    reason.includes('non_document') ||
    reason.includes('guided_declaration') ||
    reason.includes('declaration_not') ||
    reason.includes('assessment_recorded')
  ) {
    return true;
  }

  return Boolean(cerId);
}

/**
 * Property intel modal deep link focused on read-only submission inspection.
 * @param {string|null|undefined} propertyId
 * @param {string|null|undefined} requirementId
 */
export function resolveAuthoritativeSubmissionInspectPath(propertyId, requirementId) {
  const pid = normalizeRouteId(propertyId);
  const rid = normalizeRouteId(requirementId);
  if (!pid || !rid) return null;
  return resolvePropertyEvidenceRegistryPath(pid, rid, { openIntel: true, focusSubmission: true });
}

/**
 * When true, View evidence should scroll to the in-modal inspect panel (not navigate away).
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} [latestCer]
 */
export function shouldViewEvidenceInModalInspectPanel(requirement, latestCer = null) {
  return requirementAuthoritativeEvidenceIsRecordPrimary(requirement, latestCer);
}
