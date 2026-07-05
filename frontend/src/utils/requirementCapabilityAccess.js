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

/** Governed Runtime Contract capability ids for Requirements UI. */
export const REQUIREMENT_CAPABILITY = {
  VIEW: 'CAP_REQ_VIEW',
  RESOLVE: 'CAP_REQ_RESOLVE',
  MARK_N_A: 'CAP_REQ_MARK_N_A',
  COMPLETE: 'CAP_REQ_COMPLETE',
};

/**
 * Runtime Contract capability consumption for Requirements UI.
 */
export function useRequirementCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewRequirements: capabilityAllowed(REQUIREMENT_CAPABILITY.VIEW, 'read'),
      canResolveRequirements: capabilityAllowed(REQUIREMENT_CAPABILITY.RESOLVE, 'write'),
      canMarkRequirementNotApplicable: capabilityAllowed(REQUIREMENT_CAPABILITY.MARK_N_A, 'write'),
      canCompleteRequirement: capabilityAllowed(REQUIREMENT_CAPABILITY.COMPLETE, 'write'),
      getCapabilityGrant,
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

export const REQUIREMENT_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_REQ_VIEW: GRANT_ALLOW,
    CAP_REQ_RESOLVE: GRANT_ALLOW,
    CAP_REQ_MARK_N_A: GRANT_ALLOW,
    CAP_REQ_COMPLETE: GRANT_ALLOW,
  },
  TRIAL: {
    CAP_REQ_VIEW: GRANT_ALLOW,
    CAP_REQ_RESOLVE: GRANT_ALLOW,
    CAP_REQ_MARK_N_A: GRANT_ALLOW,
    CAP_REQ_COMPLETE: GRANT_ALLOW,
  },
  GRACE_PERIOD: {
    CAP_REQ_VIEW: GRANT_ALLOW,
    CAP_REQ_RESOLVE: GRANT_LIMITED,
    CAP_REQ_MARK_N_A: GRANT_LIMITED,
    CAP_REQ_COMPLETE: GRANT_LIMITED,
  },
  CANCELLATION_SCHEDULED: {
    CAP_REQ_VIEW: GRANT_ALLOW,
    CAP_REQ_RESOLVE: GRANT_ALLOW,
    CAP_REQ_MARK_N_A: GRANT_ALLOW,
    CAP_REQ_COMPLETE: GRANT_ALLOW,
  },
  CANCELLED_IMMEDIATE: {
    CAP_REQ_VIEW: GRANT_READ,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
  SUBSCRIPTION_EXPIRED: {
    CAP_REQ_VIEW: GRANT_READ,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
  READ_ONLY: {
    CAP_REQ_VIEW: GRANT_READ,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
  SUSPENDED: {
    CAP_REQ_VIEW: GRANT_DENY,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
  ARCHIVED: {
    CAP_REQ_VIEW: GRANT_DENY,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
  UNKNOWN: {
    CAP_REQ_VIEW: GRANT_DENY,
    CAP_REQ_RESOLVE: GRANT_DENY,
    CAP_REQ_MARK_N_A: GRANT_DENY,
    CAP_REQ_COMPLETE: GRANT_DENY,
  },
};

export function evaluateRequirementCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewRequirements: evaluateCapabilityGrant(caps, REQUIREMENT_CAPABILITY.VIEW, 'read').allowed,
    canResolveRequirements: evaluateCapabilityGrant(caps, REQUIREMENT_CAPABILITY.RESOLVE, 'write').allowed,
    canMarkRequirementNotApplicable: evaluateCapabilityGrant(caps, REQUIREMENT_CAPABILITY.MARK_N_A, 'write').allowed,
    canCompleteRequirement: evaluateCapabilityGrant(caps, REQUIREMENT_CAPABILITY.COMPLETE, 'write').allowed,
  };
}
