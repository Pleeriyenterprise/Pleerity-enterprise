/**
 * Shared client CTA execution for requirement rows — parity across Requirements, property compliance,
 * Needs Attention, Operating hub, and score drivers. Does not change resolver authority; only applies
 * row-level property/requirement context and consistent navigation for guided flows.
 */
import { resolveRequirementAction } from './requirementTakeActionResolver';
import { isViewExistingSubmissionCta } from './complianceEvidenceSubmissionView';
import { applyLifecycleAwareCtaPresentation } from './requirementLifecyclePresentation';

export const GUIDED_CTA_UNAVAILABLE_TITLE =
  'This obligation is configured for guided resolution but required property or requirement context is missing. Use supporting links or contact support if this persists.';

/**
 * Deep-link into property workspace with compliance tab + guided resolve intent (query consumed by PropertyDetailPage).
 * @param {string} propertyId
 * @param {string} requirementId
 * @param {{ initialEvidenceMode?: string }} [opts]
 */
export function buildPropertyComplianceResolveQueryLink(propertyId, requirementId, opts = {}) {
  if (!propertyId || !requirementId) return null;
  const q = new URLSearchParams();
  q.set('open', 'resolve');
  q.set('requirement_id', String(requirementId));
  const mode = opts.initialEvidenceMode || opts.initial_evidence_mode;
  if (mode) q.set('evidence_mode', String(mode));
  return `/properties/${encodeURIComponent(String(propertyId))}?${q.toString()}`;
}

/**
 * Resolve take_action using the same rules as {@link resolveRequirementAction}, after merging
 * `property_id` / `requirement_id` from the row onto `take_action.primary` when the API omitted them.
 * @param {Record<string, unknown>} requirement
 * @param {string|null|undefined} pagePropertyId optional page-level property (Operating / Compliance tab)
 */
export function resolveRequirementActionWithRowContext(requirement, pagePropertyId = null) {
  if (!requirement || typeof requirement !== 'object') return resolveRequirementAction(requirement, {});
  const withPagePid =
    pagePropertyId && !requirement.property_id ? { ...requirement, property_id: pagePropertyId } : requirement;
  return resolveRequirementAction(withPagePid, {});
}

/**
 * Execute primary CTA in one place. Guided flows: open modal when already on that property; otherwise navigate with resolve query.
 * @param {{
 *   requirement: Record<string, unknown>,
 *   pagePropertyId?: string|null,
 *   navigate: (to: string | object) => void,
 *   openGuidedEvidence?: (p: Record<string, unknown>) => void,
 *   openRequirementIntel?: (req: Record<string, unknown>, opts?: { scrollToSubmission?: boolean }) => void,
 *   onSubmitted?: () => void,
 *   guidedInitialOverride?: string|null,
 * }} ctx
 * @returns {{ handled: boolean, ta: ReturnType<typeof resolveRequirementAction> }}
 */
export function executeRequirementPrimaryCta(ctx) {
  const {
    requirement,
    pagePropertyId = null,
    navigate,
    openGuidedEvidence,
    openRequirementIntel,
    onSubmitted,
    guidedInitialOverride,
  } = ctx || {};
  const rawTa = resolveRequirementActionWithRowContext(requirement, pagePropertyId);
  const ta = applyLifecycleAwareCtaPresentation(requirement, rawTa);
  const rowPid = requirement?.property_id != null ? String(requirement.property_id).trim() : '';
  const rid = requirement?.requirement_id || requirement?.id;
  const effectivePid = (pagePropertyId && String(pagePropertyId).trim()) || rowPid;

  if (ta.primary_action_handler === 'guided_evidence_error') {
    return { handled: true, ta, blocked: true };
  }
  if (ta.primary_action_handler === 'guided_evidence') {
    if (isViewExistingSubmissionCta(ta) && openRequirementIntel && requirement) {
      openRequirementIntel(requirement, { scrollToSubmission: true });
      return { handled: true, ta };
    }
    const mode = guidedInitialOverride || ta.guided_initial_evidence_mode || undefined;
    if (openGuidedEvidence && effectivePid && rid) {
      openGuidedEvidence({
        propertyId: effectivePid,
        requirement,
        onSubmitted,
        initialEvidenceMode: mode,
      });
      return { handled: true, ta };
    }
    const link = buildPropertyComplianceResolveQueryLink(effectivePid, String(rid), { initialEvidenceMode: mode });
    if (link && navigate) {
      navigate(link);
      return { handled: true, ta };
    }
    return { handled: false, ta };
  }
  if (ta.primary_action_handler === 'external' && ta.primary_route) {
    window.open(ta.primary_route, '_blank', 'noopener,noreferrer');
    return { handled: true, ta };
  }
  if (ta.primary_route && navigate) {
    navigate(ta.primary_route);
    return { handled: true, ta };
  }
  return { handled: false, ta };
}
