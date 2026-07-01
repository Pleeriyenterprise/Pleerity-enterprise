/**
 * Canonical lifecycle-aware evidence navigation resolver (REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-01).
 * Presentation routing only — does not change lifecycle, evidence authority, or scoring.
 *
 * Document Operations (/documents) = upload, linkage, pending review.
 * Property Evidence Registry = settled / verified linked evidence and submission inspect.
 */
import { normalizeRouteId, resolveDocumentsPath, resolvePropertyPath } from './clientPortalNavigation';
import { resolveClientRequirementLifecycleForPresentation } from './clientPersistedSubmissionPresentation';
import { DOCUMENT_VISIBILITY_STATES } from './documentVisibilityRegistry';
import {
  requirementAuthoritativeEvidenceIsRecordPrimary,
  requirementHasLinkedAuthoritativeDocument,
} from './authoritativeEvidenceView';

export const EVIDENCE_NAV_INTENT = {
  UPLOAD_EVIDENCE: 'upload_evidence',
  VIEW_SETTLED_EVIDENCE: 'view_settled_evidence',
  REVIEW_UPLOADED_DOCUMENT: 'review_uploaded_document',
  VIEW_SUBMISSION: 'view_submission',
};

const VIEW_SETTLED_INTENT_ALIASES = new Set([
  EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE,
  'view_verified_evidence',
]);

/**
 * @param {string|null|undefined} propertyId
 * @param {string|null|undefined} requirementId
 * @param {{ openIntel?: boolean, focusSubmission?: boolean }} [opts]
 */
function buildPropertyEvidenceRegistryPath(propertyId, requirementId, opts = {}) {
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
 */
export function requirementNeedsLinkageReview(requirement) {
  if (!requirement || typeof requirement !== 'object') return false;
  const linkage = String(
    requirement.document_linkage_state ||
      requirement.evidence_authority?.document_linkage_state ||
      '',
  ).toUpperCase();
  if (linkage === 'RECONCILIATION_REQUIRED' || linkage === 'BROKEN_LINKAGE') return true;
  const attention = String(requirement.requirement_attention_reason || '').toLowerCase();
  if (attention.includes('linkage') || attention.includes('reconciliation')) return true;
  const resolution = String(requirement.requirement_resolution_status || '').toUpperCase();
  if (resolution === 'RECONCILIATION_PENDING') return true;
  return false;
}

/**
 * @param {string|null|undefined} intent
 */
function normalizeEvidenceNavIntent(intent) {
  const raw = String(intent || '').trim().toLowerCase();
  if (!raw) return null;
  if (VIEW_SETTLED_INTENT_ALIASES.has(raw)) return EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE;
  return raw;
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} [ta]
 * @param {string|null} [lifecycleOverride]
 */
export function inferEvidenceNavigationIntent(requirement, ta = null, lifecycleOverride = null) {
  const lifecycle =
    lifecycleOverride || resolveClientRequirementLifecycleForPresentation(requirement).state;
  const intentRaw = normalizeEvidenceNavIntent(ta?.primary_intent);
  const label = String(ta?.primary_action_label || '').trim().toLowerCase();

  if (intentRaw === EVIDENCE_NAV_INTENT.UPLOAD_EVIDENCE && lifecycle === 'VERIFIED' && /^view/.test(label)) {
    return EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE;
  }
  if (intentRaw) return intentRaw;

  if (/^upload/.test(label)) return EVIDENCE_NAV_INTENT.UPLOAD_EVIDENCE;
  if (/view submission|review submission/.test(label)) return EVIDENCE_NAV_INTENT.VIEW_SUBMISSION;
  if (lifecycle === 'PENDING_REVIEW') return EVIDENCE_NAV_INTENT.REVIEW_UPLOADED_DOCUMENT;
  if (/review.*document|review uploaded|review evidence|awaiting review|confirm details|resolve linkage/.test(label)) {
    return EVIDENCE_NAV_INTENT.REVIEW_UPLOADED_DOCUMENT;
  }
  if (/view.*evidence/.test(label)) return EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE;

  if (lifecycle === 'ACTION_REQUIRED') return EVIDENCE_NAV_INTENT.UPLOAD_EVIDENCE;
  if (lifecycle === 'VERIFIED' || lifecycle === 'SATISFIED_UNVERIFIED') {
    if (requirementAuthoritativeEvidenceIsRecordPrimary(requirement)) {
      return EVIDENCE_NAV_INTENT.VIEW_SUBMISSION;
    }
    return EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE;
  }
  return null;
}

/**
 * @param {string|null|undefined} pid
 * @param {string|null|undefined} rid
 * @param {{ upload?: boolean }} [opts]
 */
function buildDocumentsOperationsPath(pid, rid, opts = {}) {
  if (!pid) return '/documents';
  const extra = rid ? { requirement_id: rid } : {};
  if (opts.upload) extra.focus = 'upload';
  return resolveDocumentsPath(pid, extra);
}

/**
 * @param {string} route
 */
function isNonEvidenceOperationalRoute(route) {
  const r = String(route || '').trim();
  if (!r) return false;
  if (r.startsWith('/operations/')) return true;
  if (r.includes('#compliance')) return true;
  if (r.startsWith('/requirements') && !r.includes('tab=evidence')) return true;
  return false;
}

/**
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {{
 *   pagePropertyId?: string|null,
 *   latestCer?: Record<string, unknown>|null,
 *   ta?: Record<string, unknown>|null,
 *   intent?: string|null,
 *   lifecycle?: string|null,
 * }} [options]
 * @returns {string|null}
 */
export function resolveEvidenceNavigationTarget(requirement, options = {}) {
  if (!requirement || typeof requirement !== 'object') return null;

  const {
    pagePropertyId = null,
    latestCer = null,
    ta = null,
    intent: intentOverride = null,
    lifecycle: lifecycleOverride = null,
  } = options;

  const pid = normalizeRouteId(pagePropertyId || requirement.property_id);
  const rid = normalizeRouteId(requirement.requirement_id || requirement.id);
  const lifecycle =
    lifecycleOverride || resolveClientRequirementLifecycleForPresentation(requirement).state;
  const intent = normalizeEvidenceNavIntent(
    intentOverride || inferEvidenceNavigationIntent(requirement, ta, lifecycle),
  );
  const visibility = String(requirement.document_client_visibility_state || '').toUpperCase();
  const primaryRoute = ta?.primary_route != null ? String(ta.primary_route).trim() : '';

  if (primaryRoute && isNonEvidenceOperationalRoute(primaryRoute)) {
    return primaryRoute;
  }

  if (visibility === DOCUMENT_VISIBILITY_STATES.HISTORICAL_OR_SUPERSEDED && pid && rid) {
    return buildPropertyEvidenceRegistryPath(pid, rid);
  }

  if (requirementNeedsLinkageReview(requirement)) {
    return buildDocumentsOperationsPath(pid, rid, { upload: false });
  }

  if (lifecycle === 'ACTION_REQUIRED' || intent === EVIDENCE_NAV_INTENT.UPLOAD_EVIDENCE) {
    return buildDocumentsOperationsPath(pid, rid, { upload: true });
  }

  if (lifecycle === 'PENDING_REVIEW') {
    if (intent === EVIDENCE_NAV_INTENT.VIEW_SUBMISSION) {
      if (!pid || !rid) return null;
      return buildPropertyEvidenceRegistryPath(pid, rid, { openIntel: true, focusSubmission: true });
    }
    return buildDocumentsOperationsPath(pid, rid, { upload: false });
  }

  const viewIntent =
    intent === EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE ||
    intent === EVIDENCE_NAV_INTENT.VIEW_SUBMISSION ||
    lifecycle === 'VERIFIED' ||
    lifecycle === 'SATISFIED_UNVERIFIED';

  if (viewIntent) {
    if (!pid || !rid) return null;

    if (
      requirementAuthoritativeEvidenceIsRecordPrimary(requirement, latestCer) ||
      intent === EVIDENCE_NAV_INTENT.VIEW_SUBMISSION
    ) {
      return buildPropertyEvidenceRegistryPath(pid, rid, { openIntel: true, focusSubmission: true });
    }

    if (requirementHasLinkedAuthoritativeDocument(requirement)) {
      const settledVisibility =
        visibility === DOCUMENT_VISIBILITY_STATES.ACTIVE_EVIDENCE ||
        visibility === '' ||
        lifecycle === 'VERIFIED' ||
        lifecycle === 'SATISFIED_UNVERIFIED';
      if (settledVisibility) {
        return buildPropertyEvidenceRegistryPath(pid, rid);
      }
    }

    if (lifecycle === 'VERIFIED' || lifecycle === 'SATISFIED_UNVERIFIED') {
      return buildPropertyEvidenceRegistryPath(pid, rid, {
        openIntel: lifecycle === 'SATISFIED_UNVERIFIED',
        focusSubmission: false,
      });
    }
  }

  if (
    primaryRoute.includes('/documents') &&
    lifecycle === 'VERIFIED' &&
    requirementHasLinkedAuthoritativeDocument(requirement) &&
    pid &&
    rid
  ) {
    return buildPropertyEvidenceRegistryPath(pid, rid);
  }

  return null;
}

/**
 * Best navigation target for "View evidence" when not already inside the intel modal.
 * @param {Record<string, unknown>|null|undefined} requirement
 * @param {Record<string, unknown>|null|undefined} [latestCer]
 * @param {string|null|undefined} [pagePropertyId]
 * @returns {string|null}
 */
export function resolveAuthoritativeEvidenceViewPath(requirement, latestCer = null, pagePropertyId = null) {
  return resolveEvidenceNavigationTarget(requirement, {
    pagePropertyId,
    latestCer,
    intent: EVIDENCE_NAV_INTENT.VIEW_SETTLED_EVIDENCE,
  });
}
