import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import {
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  GRANT_ALLOW,
  GRANT_DENY,
  GRANT_READ,
} from './capabilityRuntime';

/** Governed Runtime Contract capability ids for Evidence Registry UI. */
export const EVIDENCE_CAPABILITY = {
  VIEW: 'CAP_EVIDENCE_VIEW',
  DOWNLOAD: 'CAP_EVIDENCE_DOWNLOAD',
};

/**
 * Runtime Contract capability consumption for property evidence registry UI.
 */
export function useEvidenceCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewEvidence: capabilityAllowed(EVIDENCE_CAPABILITY.VIEW, 'read'),
      canDownloadEvidence: capabilityAllowed(EVIDENCE_CAPABILITY.DOWNLOAD, 'read'),
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

export const EVIDENCE_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_EVIDENCE_VIEW: GRANT_ALLOW,
    CAP_EVIDENCE_DOWNLOAD: GRANT_ALLOW,
  },
  TRIAL: {
    CAP_EVIDENCE_VIEW: GRANT_ALLOW,
    CAP_EVIDENCE_DOWNLOAD: GRANT_ALLOW,
  },
  GRACE_PERIOD: {
    CAP_EVIDENCE_VIEW: GRANT_ALLOW,
    CAP_EVIDENCE_DOWNLOAD: GRANT_ALLOW,
  },
  CANCELLATION_SCHEDULED: {
    CAP_EVIDENCE_VIEW: GRANT_ALLOW,
    CAP_EVIDENCE_DOWNLOAD: GRANT_ALLOW,
  },
  CANCELLED_IMMEDIATE: {
    CAP_EVIDENCE_VIEW: GRANT_READ,
    CAP_EVIDENCE_DOWNLOAD: GRANT_READ,
  },
  SUBSCRIPTION_EXPIRED: {
    CAP_EVIDENCE_VIEW: GRANT_READ,
    CAP_EVIDENCE_DOWNLOAD: GRANT_READ,
  },
  READ_ONLY: {
    CAP_EVIDENCE_VIEW: GRANT_READ,
    CAP_EVIDENCE_DOWNLOAD: GRANT_READ,
  },
  SUSPENDED: {
    CAP_EVIDENCE_VIEW: GRANT_DENY,
    CAP_EVIDENCE_DOWNLOAD: GRANT_DENY,
  },
  ARCHIVED: {
    CAP_EVIDENCE_VIEW: GRANT_DENY,
    CAP_EVIDENCE_DOWNLOAD: GRANT_DENY,
  },
  UNKNOWN: {
    CAP_EVIDENCE_VIEW: GRANT_DENY,
    CAP_EVIDENCE_DOWNLOAD: GRANT_DENY,
  },
};

export function evaluateEvidenceCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewEvidence: evaluateCapabilityGrant(caps, EVIDENCE_CAPABILITY.VIEW, 'read').allowed,
    canDownloadEvidence: evaluateCapabilityGrant(caps, EVIDENCE_CAPABILITY.DOWNLOAD, 'read').allowed,
  };
}
