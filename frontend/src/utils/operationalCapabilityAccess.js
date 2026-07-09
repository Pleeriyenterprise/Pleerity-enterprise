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

/** Shared Runtime Contract capability ids for operational workflow domains. */
export const OPS_CAPABILITY = {
  DASHBOARD_VIEW: 'CAP_DASHBOARD_VIEW',
  SCORE_VIEW: 'CAP_SCORE_VIEW',
  TODAY_VIEW: 'CAP_TODAY_VIEW',
  TODAY_ACT: 'CAP_TODAY_ACT',
  CMD_CTR_VIEW: 'CAP_CMD_CTR_VIEW',
  OPS_MAINTENANCE: 'CAP_OPS_MAINTENANCE',
  OPS_PREDICTIVE: 'CAP_OPS_PREDICTIVE',
  OPS_CONTRACTORS: 'CAP_OPS_CONTRACTORS',
  OPS_APPROVALS: 'CAP_OPS_APPROVALS',
  OPS_COMPLIANCE_REVIEW: 'CAP_OPS_COMPLIANCE_REVIEW',
  OPS_RENT: 'CAP_OPS_RENT',
};

/** Legacy feature keys → capability route gates (presentation feature for UpgradeRequired). */
export const OPERATIONAL_ROUTE_CAPABILITY = {
  maintenance_workflows: { capabilityId: OPS_CAPABILITY.OPS_MAINTENANCE, action: 'read', presentationFeature: 'maintenance_workflows' },
  predictive_maintenance: { capabilityId: OPS_CAPABILITY.OPS_PREDICTIVE, action: 'read', presentationFeature: 'predictive_maintenance' },
  contractor_network: { capabilityId: OPS_CAPABILITY.OPS_CONTRACTORS, action: 'read', presentationFeature: 'contractor_network' },
  invoicing: { capabilityId: OPS_CAPABILITY.OPS_APPROVALS, action: 'read', presentationFeature: 'invoicing' },
  compliance_engine: { capabilityId: OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, action: 'read', presentationFeature: 'compliance_engine' },
};

function buildOpsFlags(capabilityAllowed, getCapabilityGrant) {
  return {
    canUseOpsMaintenance: capabilityAllowed(OPS_CAPABILITY.OPS_MAINTENANCE, 'read'),
    canWriteOpsMaintenance: capabilityAllowed(OPS_CAPABILITY.OPS_MAINTENANCE, 'write'),
    canUseOpsPredictive: capabilityAllowed(OPS_CAPABILITY.OPS_PREDICTIVE, 'read'),
    canWriteOpsPredictive: capabilityAllowed(OPS_CAPABILITY.OPS_PREDICTIVE, 'write'),
    canUseOpsContractors: capabilityAllowed(OPS_CAPABILITY.OPS_CONTRACTORS, 'read'),
    canWriteOpsContractors: capabilityAllowed(OPS_CAPABILITY.OPS_CONTRACTORS, 'write'),
    canUseOpsApprovals: capabilityAllowed(OPS_CAPABILITY.OPS_APPROVALS, 'read'),
    canWriteOpsApprovals: capabilityAllowed(OPS_CAPABILITY.OPS_APPROVALS, 'write'),
    canUseOpsComplianceReview: capabilityAllowed(OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, 'read'),
    canWriteOpsComplianceReview: capabilityAllowed(OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, 'write'),
    canUseOpsRent: capabilityAllowed(OPS_CAPABILITY.OPS_RENT, 'read'),
    getCapabilityGrant,
  };
}

export function useDashboardCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewDashboard: capabilityAllowed(OPS_CAPABILITY.DASHBOARD_VIEW, 'read'),
      canViewScore: capabilityAllowed(OPS_CAPABILITY.SCORE_VIEW, 'read'),
      canViewCommandCentre: capabilityAllowed(OPS_CAPABILITY.CMD_CTR_VIEW, 'read'),
      canViewToday: capabilityAllowed(OPS_CAPABILITY.TODAY_VIEW, 'read'),
      ...buildOpsFlags(capabilityAllowed, getCapabilityGrant),
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function useTodayCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewToday: capabilityAllowed(OPS_CAPABILITY.TODAY_VIEW, 'read'),
      canActToday: capabilityAllowed(OPS_CAPABILITY.TODAY_ACT, 'write'),
      ...buildOpsFlags(capabilityAllowed, getCapabilityGrant),
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function useCommandCentreCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewCommandCentre: capabilityAllowed(OPS_CAPABILITY.CMD_CTR_VIEW, 'read'),
      ...buildOpsFlags(capabilityAllowed, getCapabilityGrant),
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

/**
 * Runtime Contract capability consumption for operational execution workflow
 * (maintenance, contractors, approvals, predictive, issues, jobs).
 */
export function useOperationalExecutionCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      ...buildOpsFlags(capabilityAllowed, getCapabilityGrant),
      canViewDocuments: capabilityAllowed('CAP_DOC_VIEW', 'read'),
      canUploadDocuments: capabilityAllowed('CAP_DOC_UPLOAD', 'write'),
      canViewEvidence: capabilityAllowed('CAP_EVIDENCE_VIEW', 'read'),
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || fallback;
}

export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

/**
 * Lifecycle grant fixtures mirroring backend wave2c2 operational matrix semantics.
 */
export const OPERATIONAL_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_DASHBOARD_VIEW: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_TODAY_VIEW: GRANT_ALLOW,
    CAP_TODAY_ACT: GRANT_ALLOW,
    CAP_CMD_CTR_VIEW: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_APPROVALS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
  },
  TRIAL: {
    CAP_DASHBOARD_VIEW: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_TODAY_VIEW: GRANT_ALLOW,
    CAP_TODAY_ACT: GRANT_ALLOW,
    CAP_CMD_CTR_VIEW: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_APPROVALS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
  },
  GRACE_PERIOD: {
    CAP_DASHBOARD_VIEW: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_TODAY_VIEW: GRANT_ALLOW,
    CAP_TODAY_ACT: GRANT_LIMITED,
    CAP_CMD_CTR_VIEW: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_LIMITED,
    CAP_OPS_PREDICTIVE: GRANT_LIMITED,
    CAP_OPS_CONTRACTORS: GRANT_LIMITED,
    CAP_OPS_APPROVALS: GRANT_LIMITED,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_LIMITED,
    CAP_OPS_RENT: GRANT_LIMITED,
  },
  CANCELLATION_SCHEDULED: {
    CAP_DASHBOARD_VIEW: GRANT_ALLOW,
    CAP_SCORE_VIEW: GRANT_ALLOW,
    CAP_TODAY_VIEW: GRANT_ALLOW,
    CAP_TODAY_ACT: GRANT_ALLOW,
    CAP_CMD_CTR_VIEW: GRANT_ALLOW,
    CAP_OPS_MAINTENANCE: GRANT_ALLOW,
    CAP_OPS_PREDICTIVE: GRANT_ALLOW,
    CAP_OPS_CONTRACTORS: GRANT_ALLOW,
    CAP_OPS_APPROVALS: GRANT_ALLOW,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_ALLOW,
    CAP_OPS_RENT: GRANT_ALLOW,
  },
  CANCELLED_IMMEDIATE: {
    CAP_DASHBOARD_VIEW: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_TODAY_VIEW: GRANT_DENY,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
  SUBSCRIPTION_EXPIRED: {
    CAP_DASHBOARD_VIEW: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_TODAY_VIEW: GRANT_DENY,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
  READ_ONLY: {
    CAP_DASHBOARD_VIEW: GRANT_READ,
    CAP_SCORE_VIEW: GRANT_READ,
    CAP_TODAY_VIEW: GRANT_READ,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_READ,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
  SUSPENDED: {
    CAP_DASHBOARD_VIEW: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_TODAY_VIEW: GRANT_DENY,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
  ARCHIVED: {
    CAP_DASHBOARD_VIEW: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_TODAY_VIEW: GRANT_DENY,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
  UNKNOWN: {
    CAP_DASHBOARD_VIEW: GRANT_DENY,
    CAP_SCORE_VIEW: GRANT_DENY,
    CAP_TODAY_VIEW: GRANT_DENY,
    CAP_TODAY_ACT: GRANT_DENY,
    CAP_CMD_CTR_VIEW: GRANT_DENY,
    CAP_OPS_MAINTENANCE: GRANT_DENY,
    CAP_OPS_PREDICTIVE: GRANT_DENY,
    CAP_OPS_CONTRACTORS: GRANT_DENY,
    CAP_OPS_APPROVALS: GRANT_DENY,
    CAP_OPS_COMPLIANCE_REVIEW: GRANT_DENY,
    CAP_OPS_RENT: GRANT_DENY,
  },
};

export function evaluateDashboardCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewDashboard: evaluateCapabilityGrant(caps, OPS_CAPABILITY.DASHBOARD_VIEW, 'read').allowed,
    canViewScore: evaluateCapabilityGrant(caps, OPS_CAPABILITY.SCORE_VIEW, 'read').allowed,
    canViewCommandCentre: evaluateCapabilityGrant(caps, OPS_CAPABILITY.CMD_CTR_VIEW, 'read').allowed,
    canViewToday: evaluateCapabilityGrant(caps, OPS_CAPABILITY.TODAY_VIEW, 'read').allowed,
    canUseOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'read').allowed,
    canWriteOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'write').allowed,
    canUseOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'read').allowed,
    canUseOpsContractors: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_CONTRACTORS, 'read').allowed,
    canUseOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'read').allowed,
  };
}

export function evaluateTodayCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewToday: evaluateCapabilityGrant(caps, OPS_CAPABILITY.TODAY_VIEW, 'read').allowed,
    canActToday: evaluateCapabilityGrant(caps, OPS_CAPABILITY.TODAY_ACT, 'write').allowed,
    canUseOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'read').allowed,
    canWriteOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'write').allowed,
    canUseOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'read').allowed,
    canUseOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'read').allowed,
    canWriteOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'write').allowed,
    canUseOpsRent: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_RENT, 'read').allowed,
  };
}

export function evaluateCommandCentreCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewCommandCentre: evaluateCapabilityGrant(caps, OPS_CAPABILITY.CMD_CTR_VIEW, 'read').allowed,
    canUseOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'read').allowed,
    canUseOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'read').allowed,
    canUseOpsContractors: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_CONTRACTORS, 'read').allowed,
    canUseOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'read').allowed,
    canUseOpsComplianceReview: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, 'read').allowed,
  };
}

export function evaluateOperationalExecutionCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canUseOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'read').allowed,
    canWriteOpsMaintenance: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_MAINTENANCE, 'write').allowed,
    canUseOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'read').allowed,
    canWriteOpsPredictive: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_PREDICTIVE, 'write').allowed,
    canUseOpsContractors: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_CONTRACTORS, 'read').allowed,
    canWriteOpsContractors: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_CONTRACTORS, 'write').allowed,
    canUseOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'read').allowed,
    canWriteOpsApprovals: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_APPROVALS, 'write').allowed,
    canUseOpsComplianceReview: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, 'read').allowed,
    canWriteOpsComplianceReview: evaluateCapabilityGrant(caps, OPS_CAPABILITY.OPS_COMPLIANCE_REVIEW, 'write').allowed,
    canViewDocuments: evaluateCapabilityGrant(caps, 'CAP_DOC_VIEW', 'read').allowed,
    canUploadDocuments: evaluateCapabilityGrant(caps, 'CAP_DOC_UPLOAD', 'write').allowed,
    canViewEvidence: evaluateCapabilityGrant(caps, 'CAP_EVIDENCE_VIEW', 'read').allowed,
  };
}
