/**
 * Score-driver action presentation — trust-governed fallback tiers (Stream D / PRELAUNCH-SCORE-DRIVER-ACTION-TRUST-REPAIR-01).
 *
 * Tier A: canonical take_action.primary (server authority)
 * Tier B: safe operational navigation only — no diagnostic / implementation copy
 * Tier C: suppress action column content
 */
import { resolvePropertyEvidenceRegistryPath } from '../utils/documentEvidenceAuthority';
import { resolvePropertyPath } from '../utils/clientPortalNavigation';
import { projectResolvedRequirementSemantics } from '../utils/resolvedRequirementViewModel';
import { findRequirementRowForScoreDriver } from './ComplianceScorePage.driverRemediation';

/** @typedef {'A'|'B'|'C'} ScoreDriverActionTier */

export const SCORE_DRIVER_ACTION_LABELS = {
  openRequirement: 'Open requirement',
  reviewProperty: 'Review property',
};

/**
 * Resolve how the Action column should render for one driver row.
 *
 * @param {Record<string, unknown>|null|undefined} driver
 * @param {Array<Record<string, unknown>>|null|undefined} requirements
 * @returns {{
 *   tier: ScoreDriverActionTier,
 *   req: Record<string, unknown>|null,
 *   sem: ReturnType<typeof projectResolvedRequirementSemantics>|null,
 *   navigation?: { label: string, route: string, testId: string },
 * }}
 */
export function resolveScoreDriverActionPresentation(driver, requirements) {
  const req = findRequirementRowForScoreDriver(requirements, driver);
  const propertyId = driver?.property_id != null ? String(driver.property_id).trim() : '';
  const requirementId = driver?.requirement_id != null ? String(driver.requirement_id).trim() : '';

  const hasTakeAction = !!(req && typeof req.take_action === 'object');
  const sem =
    req && hasTakeAction
      ? projectResolvedRequirementSemantics(req, { pagePropertyId: propertyId || null })
      : null;

  if (sem?.server_take_action_primary) {
    return { tier: 'A', req, sem };
  }

  if (propertyId && requirementId) {
    return {
      tier: 'B',
      req,
      sem: null,
      navigation: {
        label: SCORE_DRIVER_ACTION_LABELS.openRequirement,
        route: resolvePropertyEvidenceRegistryPath(propertyId, requirementId),
        testId: 'score-driver-nav-requirement',
      },
    };
  }

  if (propertyId) {
    return {
      tier: 'B',
      req,
      sem: null,
      navigation: {
        label: SCORE_DRIVER_ACTION_LABELS.reviewProperty,
        route: resolvePropertyPath(propertyId),
        testId: 'score-driver-nav-property',
      },
    };
  }

  return { tier: 'C', req, sem: null };
}
