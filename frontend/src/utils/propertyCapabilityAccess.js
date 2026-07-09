import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import {
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  GRANT_ALLOW,
  GRANT_DENY,
  GRANT_LIMITED,
  GRANT_READ,
} from './capabilityRuntime';
import { OPS_CAPABILITY } from './operationalCapabilityAccess';
import { useDocumentCapabilities } from './documentCapabilityAccess';
import { useRequirementCapabilities } from './requirementCapabilityAccess';
import { useEvidenceCapabilities } from './evidenceCapabilityAccess';

/** Governed Runtime Contract capability ids for the Property domain. */
export const PROPERTY_CAPABILITY = {
  VIEW: 'CAP_PROP_VIEW',
  CREATE: 'CAP_PROP_CREATE',
  EDIT: 'CAP_PROP_EDIT',
  ARCHIVE: 'CAP_PROP_ARCHIVE',
  IMPORT: 'CAP_PROP_IMPORT',
};

export const SCORE_CAPABILITY = {
  VIEW: 'CAP_SCORE_VIEW',
  EXPLAIN: 'CAP_SCORE_EXPLAIN',
  TREND: 'CAP_SCORE_TREND',
  SNAPSHOT: 'CAP_SCORE_SNAPSHOT',
};

export const OPS_COMPLIANCE_CAPABILITY = {
  COMPLIANCE_REVIEW: 'CAP_OPS_COMPLIANCE_REVIEW',
};

export const TENANT_CAPABILITY = {
  PORTAL: 'CAP_TENANT_PORTAL',
};

function buildPropertyScoreFlags(capabilityAllowed, getCapabilityGrant) {
  return {
    canViewProperties: capabilityAllowed(PROPERTY_CAPABILITY.VIEW, 'read'),
    canCreateProperty: capabilityAllowed(PROPERTY_CAPABILITY.CREATE, 'write'),
    canEditProperty: capabilityAllowed(PROPERTY_CAPABILITY.EDIT, 'write'),
    canArchiveProperty: capabilityAllowed(PROPERTY_CAPABILITY.ARCHIVE, 'write'),
    canImportProperties: capabilityAllowed(PROPERTY_CAPABILITY.IMPORT, 'write'),
    canViewScore: capabilityAllowed(SCORE_CAPABILITY.VIEW, 'read'),
    canViewScoreExplain: capabilityAllowed(SCORE_CAPABILITY.EXPLAIN, 'read'),
    canViewScoreTrend: capabilityAllowed(SCORE_CAPABILITY.TREND, 'read'),
    canWriteScoreSnapshot: capabilityAllowed(SCORE_CAPABILITY.SNAPSHOT, 'write'),
    canUseOpsMaintenance: capabilityAllowed(OPS_CAPABILITY.OPS_MAINTENANCE, 'read'),
    canWriteOpsMaintenance: capabilityAllowed(OPS_CAPABILITY.OPS_MAINTENANCE, 'write'),
    canUseOpsPredictive: capabilityAllowed(OPS_CAPABILITY.OPS_PREDICTIVE, 'read'),
    canWriteOpsPredictive: capabilityAllowed(OPS_CAPABILITY.OPS_PREDICTIVE, 'write'),
    canUseOpsContractors: capabilityAllowed(OPS_CAPABILITY.OPS_CONTRACTORS, 'read'),
    canUseOpsComplianceReview: capabilityAllowed(OPS_COMPLIANCE_CAPABILITY.COMPLIANCE_REVIEW, 'read'),
    canWriteOpsComplianceReview: capabilityAllowed(OPS_COMPLIANCE_CAPABILITY.COMPLIANCE_REVIEW, 'write'),
    canUseOpsRent: capabilityAllowed(OPS_CAPABILITY.OPS_RENT, 'read'),
    canUseTenantPortal: capabilityAllowed(TENANT_CAPABILITY.PORTAL, 'read'),
    getCapabilityGrant,
  };
}

/**
 * Runtime Contract capability consumption for Property portfolio and detail UI.
 */
export function usePropertyCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => buildPropertyScoreFlags(capabilityAllowed, getCapabilityGrant),
    [capabilityAllowed, getCapabilityGrant],
  );
}

/**
 * Composed hook for the full property compliance workflow (portfolio → detail → requirements → evidence).
 */
export function usePropertyWorkflowCapabilities() {
  const property = usePropertyCapabilities();
  const requirements = useRequirementCapabilities();
  const evidence = useEvidenceCapabilities();
  const documents = useDocumentCapabilities();

  return useMemo(
    () => ({
      ...property,
      ...requirements,
      ...evidence,
      ...documents,
    }),
    [property, requirements, evidence, documents],
  );
}

export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || fallback;
}

export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

/** Tab ops capability keys used by PropertyDetailPage navigation. */
export function isPropertyTabOpsCapEnabled(opsCap, caps) {
  if (!opsCap) return true;
  if (opsCap === 'maintenance') return caps.canUseOpsMaintenance;
  if (opsCap === 'contractors') return caps.canUseOpsContractors;
  if (opsCap === 'predictive') return caps.canUseOpsPredictive;
  if (opsCap === 'assets') return caps.canUseOpsMaintenance || caps.canUseOpsPredictive;
  return true;
}

/**
 * Lifecycle grant fixtures mirroring backend property/score/ops matrix semantics.
 */
export const PROPERTY_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_PROP_VIEW: GRANT_ALLOW,
    CAP_PROP_CREATE: GRANT_ALLOW,
    CAP_PROP_EDIT: GRANT_ALLOW,
    CAP_PROP_ARCHIVE: GRANT_ALLOW,
    CAP_PROP_IMPORT: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_SCORE_EXPLAIN: GRANT_ALLOW,
    CAP_SCORE_TREND: GRANT_ALLOW,
    CAP_SCORE_SNAPSHOT: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
    CAP_TENANT_PORTAL: GRANT_ALLOW,
  },
  TRIAL: {
    CAP_PROP_VIEW: GRANT_ALLOW,
    CAP_PROP_CREATE: GRANT_ALLOW,
    CAP_PROP_EDIT: GRANT_ALLOW,
    CAP_PROP_ARCHIVE: GRANT_ALLOW,
    CAP_PROP_IMPORT: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_SCORE_EXPLAIN: GRANT_ALLOW,
    CAP_SCORE_TREND: GRANT_ALLOW,
    CAP_SCORE_SNAPSHOT: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
    CAP_TENANT_PORTAL: GRANT_ALLOW,
  },
  GRACE_PERIOD: {
    CAP_PROP_VIEW: GRANT_ALLOW,
    CAP_PROP_CREATE: GRANT_LIMITED,
    CAP_PROP_EDIT: GRANT_LIMITED,
    CAP_PROP_ARCHIVE: GRANT_LIMITED,
    CAP_PROP_IMPORT: GRANT_LIMITED,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_SCORE_EXPLAIN: GRANT_READ,
    CAP_SCORE_TREND: GRANT_DENY,
    CAP_SCORE_SNAPSHOT: GRANT_LIMITED,
    CAP_OPS_MAINTENANCE: GRANT_LIMITED,
    CAP_OPS_PREDICTIVE: GRANT_LIMITED,
    CAP_OPS_CONTRACTORS: GRANT_LIMITED,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_LIMITED,
    CAP_OPS_RENT: GRANT_LIMITED,
    CAP_TENANT_PORTAL: GRANT_LIMITED,
  },
  CANCELLATION_SCHEDULED: {
    CAP_PROP_VIEW: GRANT_ALLOW,
    CAP_PROP_CREATE: GRANT_ALLOW,
    CAP_PROP_EDIT: GRANT_ALLOW,
    CAP_PROP_ARCHIVE: GRANT_ALLOW,
    CAP_PROP_IMPORT: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_SCORE_EXPLAIN: GRANT_ALLOW,
    CAP_SCORE_TREND: GRANT_ALLOW,
    CAP_SCORE_SNAPSHOT: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
    CAP_TENANT_PORTAL: GRANT_ALLOW,
  },
  CANCELLED_IMMEDIATE: {
    CAP_PROP_VIEW: GRANT_READ,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_SCORE_EXPLAIN: GRANT_READ,
    CAP_SCORE_TREND: GRANT_READ,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  SUBSCRIPTION_EXPIRED: {
    CAP_PROP_VIEW: GRANT_READ,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_SCORE_EXPLAIN: GRANT_READ,
    CAP_SCORE_TREND: GRANT_READ,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  READ_ONLY: {
    CAP_PROP_VIEW: GRANT_READ,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_SCORE_EXPLAIN: GRANT_READ,
    CAP_SCORE_TREND: GRANT_READ,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  SUSPENDED: {
    CAP_PROP_VIEW: GRANT_DENY,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_SCORE_EXPLAIN: GRANT_DENY,
    CAP_SCORE_TREND: GRANT_DENY,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  ARCHIVED: {
    CAP_PROP_VIEW: GRANT_DENY,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_SCORE_EXPLAIN: GRANT_DENY,
    CAP_SCORE_TREND: GRANT_DENY,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  UNKNOWN: {
    CAP_PROP_VIEW: GRANT_DENY,
    CAP_PROP_CREATE: GRANT_DENY,
    CAP_PROP_EDIT: GRANT_DENY,
    CAP_PROP_ARCHIVE: GRANT_DENY,
    CAP_PROP_IMPORT: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_SCORE_EXPLAIN: GRANT_DENY,
    CAP_SCORE_TREND: GRANT_DENY,
    CAP_SCORE_SNAPSHOT: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
};

export function evaluatePropertyCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewProperties: evaluateCapabilityGrant(caps, PROPERTY_CAPABILITY.VIEW, 'read').allowed,
    canCreateProperty: evaluateCapabilityGrant(caps, PROPERTY_CAPABILITY.CREATE, 'write').allowed,
    canEditProperty: evaluateCapabilityGrant(caps, PROPERTY_CAPABILITY.EDIT, 'write').allowed,
    canArchiveProperty: evaluateCapabilityGrant(caps, PROPERTY_CAPABILITY.ARCHIVE, 'write').allowed,
    canImportProperties: evaluateCapabilityGrant(caps, PROPERTY_CAPABILITY.IMPORT, 'write').allowed,
    canViewScore: evaluateCapabilityGrant(caps, SCORE_CAPABILITY.VIEW, 'read').allowed,
    canViewScoreExplain: evaluateCapabilityGrant(caps, SCORE_CAPABILITY.EXPLAIN, 'read').allowed,
    canViewScoreTrend: evaluateCapabilityGrant(caps, SCORE_CAPABILITY.TREND, 'read').allowed,
    canWriteScoreSnapshot: evaluateCapabilityGrant(caps, SCORE_CAPABILITY.SNAPSHOT, 'write').allowed,
    canUseOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'read').allowed,
    canWriteOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'write').allowed,
    canUseOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'read').allowed,
    canUseOpsContractors: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_CONTRACTORS, 'read').allowed,
    canUseOpsComplianceReview: evaluateCapabilityGrant(caps, OPS_COMPLIANCE_CAPABILITY.COMPLIANCE_REVIEW, 'read').allowed,
  };
}
