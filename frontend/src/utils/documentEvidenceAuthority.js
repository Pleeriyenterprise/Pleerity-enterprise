/**
 * Document / evidence authority — upload eligibility, settled evidence navigation, badge composition.
 * Operations queue (/documents) is for review/linkage/action only; settled evidence lives in Property → Documents.
 */
import { resolveClientRequirementLifecycle } from './clientRequirementLifecycle';
import { resolveClientRequirementLifecycleForPresentation } from './clientPersistedSubmissionPresentation';
import { labelsDuplicateSemantics } from './cerGovernancePresentation';
import { normalizeRouteId, resolvePropertyPath } from './clientPortalNavigation';
import { resolveEvidenceNavigationTarget } from './resolveEvidenceNavigationTarget';

export function propertyIdsMatch(a, b) {
  const left = normalizeRouteId(a);
  const right = normalizeRouteId(b);
  return Boolean(left && right && left === right);
}

const DOCUMENT_UPLOAD_WORKFLOWS = new Set([
  'DOCUMENT_UPLOAD',
  'LEGACY_DOCUMENT_UPLOAD',
  'EXTERNAL_ASSESSMENT_EVIDENCE',
  'GUIDED_DECLARATION',
  'REGISTRATION_TRACKING',
  'TENANT_DELIVERY',
]);

/**
 * Whether a requirement row may appear in the Document operations upload dropdown.
 * Broader than attention views — upload targets must not depend on queue occupancy.
 * @param {Record<string, unknown>|null|undefined} req
 */
export function isRequirementEligibleForDocumentUpload(req) {
  if (!req || typeof req !== 'object') return false;
  if (req.is_tracked === false || req.tracked === false) return false;

  const { state } = resolveClientRequirementLifecycle(req);
  if (state === 'NOT_APPLICABLE') return false;

  const app = String(req.applicability || '').toUpperCase().trim();
  if (app === 'NOT_REQUIRED') return false;
  const st = String(req.status || '').toUpperCase();
  if (st === 'NOT_REQUIRED') return false;

  const cls = String(req.compliance_requirement_class || req.requirement_class || '').toUpperCase();
  if (cls === 'SYSTEM') return false;
  if (cls === 'OBLIGATION') {
    const wf = String(req.workflow_class || '').trim().toUpperCase();
    if (!DOCUMENT_UPLOAD_WORKFLOWS.has(wf)) return false;
  } else if (cls && cls !== 'DOCUMENT' && cls !== 'JOB') {
    return false;
  }

  if (state === 'VERIFIED') {
    if (st === 'EXPIRING_SOON') return true;
    const ev = String(req.evidence_state || '').toUpperCase();
    if (ev === 'AWAITING_USER_CONFIRM' || ev === 'MISMATCH_FLAGGED') return true;
    return false;
  }

  return state === 'ACTION_REQUIRED' || state === 'PENDING_REVIEW' || state === 'SATISFIED_UNVERIFIED';
}

/**
 * @param {string|null|undefined} propertyId
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 */
export function filterUploadEligibleRequirementsForProperty(propertyId, requirements) {
  if (!normalizeRouteId(propertyId)) return [];
  if (!Array.isArray(requirements)) return [];
  return requirements.filter(
    (r) => propertyIdsMatch(r.property_id, propertyId) && isRequirementEligibleForDocumentUpload(r),
  );
}

/**
 * Property Evidence Registry deep link (settled / verified evidence — not operations queue).
 * @param {string|null|undefined} propertyId
 * @param {string|null|undefined} requirementId
 * @param {{ openIntel?: boolean, focusSubmission?: boolean }} [opts]
 */
export function resolvePropertyEvidenceRegistryPath(propertyId, requirementId, opts = {}) {
  const pid = normalizeRouteId(propertyId);
  if (!pid) return '/properties';
  const q = new URLSearchParams();
  q.set('tab', 'evidence');
  const rid = normalizeRouteId(requirementId);
  if (rid) q.set('requirement_id', rid);
  if (opts.openIntel) q.set('open', 'intel');
  if (opts.focusSubmission) q.set('focus', 'submission');
  return resolvePropertyPath(pid, q.toString());
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} ta
 */
export function isViewSettledEvidenceCta(requirement, ta) {
  if (!ta || typeof ta !== 'object') return false;
  const label = String(ta.primary_action_label || '').trim();
  if (/^view (verified )?evidence$/i.test(label)) return true;
  if (/^view or update evidence$/i.test(label)) return true;
  if (/^view submission$/i.test(label)) return true;
  if (/^review submission$/i.test(label)) return true;
  const { state } = resolveClientRequirementLifecycleForPresentation(requirement);
  if (['VERIFIED', 'SATISFIED_UNVERIFIED', 'PENDING_REVIEW'].includes(state)) {
    const route = String(ta.primary_route || '');
    if (route.includes('/documents') && !String(ta.primary_intent || '').includes('upload')) {
      return true;
    }
  }
  return false;
}

/**
 * Rewrite documents-queue routes to property evidence registry when viewing settled evidence.
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} ta
 * @param {string|null|undefined} pagePropertyId
 */
export function resolveSettledEvidenceNavigationTarget(requirement, ta, pagePropertyId = null) {
  if (!requirement || !ta) return null;
  if (!isViewSettledEvidenceCta(requirement, ta)) return null;
  if (String(ta.primary_action_handler || '') === 'guided_evidence') return null;

  const { state } = resolveClientRequirementLifecycleForPresentation(requirement);
  if (state === 'ACTION_REQUIRED' && String(ta.primary_intent || '') === 'upload_evidence') {
    return null;
  }

  return resolveEvidenceNavigationTarget(requirement, { ta, pagePropertyId });
}

/**
 * Canonical requirement row badge visibility — avoid Verified + Verified + Document: Verified.
 * @param {Record<string, unknown>|null|undefined} req
 * @param {{ text?: string }|null|undefined} statusConfig
 * @param {{ text?: string }|null|undefined} tierBadge
 * @param {string|null|undefined} evidenceBadgeLabel
 */
export function composeRequirementStatusBadgeVisibility(req, statusConfig, tierBadge, evidenceBadgeLabel) {
  const { state } = resolveClientRequirementLifecycleForPresentation(req);
  const statusText = String(statusConfig?.text || '').trim();
  const tierText = String(tierBadge?.text || '').trim();
  const evidenceText = String(evidenceBadgeLabel || '').trim();

  let showTier = Boolean(tierBadge);
  let showEvidence = Boolean(evidenceText);
  let evidenceDisplay = evidenceText ? `Document: ${evidenceText}` : null;

  if (state === 'VERIFIED') {
    if (/^verified$/i.test(statusText) && /^verified$/i.test(tierText)) showTier = false;
    if (/^verified$/i.test(evidenceText) || /^valid$/i.test(evidenceText)) showEvidence = false;
    if (showEvidence && /^verified$/i.test(statusText)) showEvidence = false;
  }

  if (state === 'SATISFIED_UNVERIFIED' && /^evidence on file$/i.test(tierText) && /verified|valid|on file/i.test(evidenceText)) {
    showEvidence = false;
  }

  if (labelsDuplicateSemantics(statusText, tierText)) {
    showTier = false;
  }
  if (labelsDuplicateSemantics(statusText, evidenceText)) {
    showEvidence = false;
  }
  if (/^awaiting review$|^review pending$/i.test(tierText) && !req?.queue_backed_review) {
    showTier = false;
  }

  return { showTier, showEvidence, evidenceDisplay };
}
