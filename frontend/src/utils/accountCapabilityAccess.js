import { useCallback, useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import {
  evaluateCapabilityGrant,
  extractCapabilityDeniedFromError,
  GRANT_ALLOW,
  GRANT_DENY,
  GRANT_LIMITED,
  GRANT_READ,
} from './capabilityRuntime';
import { BILLING_CAPABILITY } from './billingCapabilityAccess';
import { REPORT_CAPABILITY } from './reportCapabilityAccess';
import { OPS_CAPABILITY } from './operationalCapabilityAccess';

/** Runtime Contract capability ids for profile, support, and account settings. */
export const ACCOUNT_CAPABILITY = {
  PROFILE_VIEW: 'CAP_PROFILE_VIEW',
  PROFILE_EDIT: 'CAP_PROFILE_EDIT',
  PROFILE_JURISDICTION: 'CAP_PROFILE_JURISDICTION',
  SUPPORT_ACCESS: 'CAP_SUPPORT_ACCESS',
  SUPPORT_REQUEST: 'CAP_SUPPORT_REQUEST',
  KNOWLEDGE_CENTRE: 'CAP_KNOWLEDGE_CENTRE',
  NOTIF_SMS: 'CAP_NOTIF_SMS',
  BRANDING_VIEW: 'CAP_BRANDING_VIEW',
  BRANDING_EDIT: 'CAP_BRANDING_EDIT',
  BRANDING_WHITE_LABEL: 'CAP_BRANDING_WHITE_LABEL',
  TENANT_PORTAL: 'CAP_TENANT_PORTAL',
};

/**
 * Legacy portal nav feature keys → primary Runtime Contract capability (read gate).
 * Presentation feature metadata unchanged; permission uses capabilities only.
 */
export const NAV_FEATURE_CAPABILITY = {
  maintenance_workflows: { capabilityId: OPS_CAPABILITY.OPS_MAINTENANCE, action: 'read' },
  contractor_network: { capabilityId: OPS_CAPABILITY.OPS_CONTRACTORS, action: 'read' },
  predictive_maintenance: { capabilityId: OPS_CAPABILITY.OPS_PREDICTIVE, action: 'read' },
  rent_operations: { capabilityId: OPS_CAPABILITY.OPS_RENT, action: 'read' },
  invoicing: { capabilityId: OPS_CAPABILITY.OPS_APPROVALS, action: 'read' },
  tenant_portal: { capabilityId: ACCOUNT_CAPABILITY.TENANT_PORTAL, action: 'read' },
  white_label_reports: { capabilityId: ACCOUNT_CAPABILITY.BRANDING_WHITE_LABEL, action: 'read' },
  sms_reminders: { capabilityId: ACCOUNT_CAPABILITY.NOTIF_SMS, action: 'read' },
};

export function useProfileCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewProfile: capabilityAllowed(ACCOUNT_CAPABILITY.PROFILE_VIEW, 'read'),
      canEditProfile: capabilityAllowed(ACCOUNT_CAPABILITY.PROFILE_EDIT, 'write'),
      canViewJurisdiction: capabilityAllowed(ACCOUNT_CAPABILITY.PROFILE_JURISDICTION, 'read'),
      canEditJurisdiction: capabilityAllowed(ACCOUNT_CAPABILITY.PROFILE_JURISDICTION, 'write'),
      canUseSmsNotifications: capabilityAllowed(ACCOUNT_CAPABILITY.NOTIF_SMS, 'read'),
      canWriteSmsNotifications: capabilityAllowed(ACCOUNT_CAPABILITY.NOTIF_SMS, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function useSupportCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canAccessSupport: capabilityAllowed(ACCOUNT_CAPABILITY.SUPPORT_ACCESS, 'read'),
      canRequestSupport: capabilityAllowed(ACCOUNT_CAPABILITY.SUPPORT_REQUEST, 'write'),
      canViewKnowledgeCentre: capabilityAllowed(ACCOUNT_CAPABILITY.KNOWLEDGE_CENTRE, 'read'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function useBrandingCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewBranding: capabilityAllowed(ACCOUNT_CAPABILITY.BRANDING_VIEW, 'read'),
      canEditBranding: capabilityAllowed(ACCOUNT_CAPABILITY.BRANDING_EDIT, 'write'),
      canUseWhiteLabelBranding: capabilityAllowed(ACCOUNT_CAPABILITY.BRANDING_WHITE_LABEL, 'read'),
      canWriteWhiteLabelBranding: capabilityAllowed(ACCOUNT_CAPABILITY.BRANDING_WHITE_LABEL, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

/**
 * Portal navigation capability consumption — replaces entitlement navHasFeature().
 */
export function usePortalNavigationCapabilities() {
  const { capabilityAllowed } = useLifecycleRuntime();

  const navHasFeature = useCallback(
    (featureKey) => {
      const mapping = NAV_FEATURE_CAPABILITY[featureKey];
      if (!mapping) return true;
      return capabilityAllowed(mapping.capabilityId, mapping.action);
    },
    [capabilityAllowed],
  );

  return useMemo(
    () => ({
      navHasFeature,
      showReports:
        capabilityAllowed(REPORT_CAPABILITY.VIEW, 'read') ||
        capabilityAllowed(REPORT_CAPABILITY.GENERATE_PDF, 'read') ||
        capabilityAllowed(REPORT_CAPABILITY.GENERATE_CSV, 'read') ||
        capabilityAllowed(REPORT_CAPABILITY.DOWNLOAD, 'read'),
      showBilling: capabilityAllowed(BILLING_CAPABILITY.VIEW, 'read'),
      invoicingEnabled: capabilityAllowed(OPS_CAPABILITY.OPS_APPROVALS, 'read'),
    }),
    [capabilityAllowed, navHasFeature],
  );
}

export function getCapabilityDeniedMessage(error, fallback = 'Action not permitted') {
  const detail = extractCapabilityDeniedFromError(error);
  return detail?.message || fallback;
}

export function isCapabilityDeniedApiError(error) {
  return Boolean(extractCapabilityDeniedFromError(error));
}

export const ACCOUNT_LIFECYCLE_GRANT_FIXTURES = {
  ACTIVE: {
    CAP_PROFILE_VIEW: GRANT_ALLOW,
    CAP_PROFILE_EDIT: GRANT_ALLOW,
    CAP_PROFILE_JURISDICTION: GRANT_ALLOW,
    CAP_SUPPORT_ACCESS: GRANT_ALLOW,
    CAP_SUPPORT_REQUEST: GRANT_ALLOW,
    CAP_KNOWLEDGE_CENTRE: GRANT_ALLOW,
    CAP_NOTIF_SMS: GRANT_ALLOW,
    CAP_BRANDING_VIEW: GRANT_ALLOW,
    CAP_BRANDING_EDIT: GRANT_ALLOW,
    CAP_BRANDING_WHITE_LABEL: GRANT_ALLOW,
    CAP_TENANT_PORTAL: GRANT_ALLOW,
  },
  READ_ONLY: {
    CAP_PROFILE_VIEW: GRANT_READ,
    CAP_PROFILE_EDIT: GRANT_DENY,
    CAP_PROFILE_JURISDICTION: GRANT_DENY,
    CAP_SUPPORT_ACCESS: GRANT_READ,
    CAP_SUPPORT_REQUEST: GRANT_DENY,
    CAP_KNOWLEDGE_CENTRE: GRANT_READ,
    CAP_NOTIF_SMS: GRANT_DENY,
    CAP_BRANDING_VIEW: GRANT_READ,
    CAP_BRANDING_EDIT: GRANT_DENY,
    CAP_BRANDING_WHITE_LABEL: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  SUSPENDED: {
    CAP_PROFILE_VIEW: GRANT_DENY,
    CAP_PROFILE_EDIT: GRANT_DENY,
    CAP_PROFILE_JURISDICTION: GRANT_DENY,
    CAP_SUPPORT_ACCESS: GRANT_DENY,
    CAP_SUPPORT_REQUEST: GRANT_DENY,
    CAP_KNOWLEDGE_CENTRE: GRANT_DENY,
    CAP_NOTIF_SMS: GRANT_DENY,
    CAP_BRANDING_VIEW: GRANT_DENY,
    CAP_BRANDING_EDIT: GRANT_DENY,
    CAP_BRANDING_WHITE_LABEL: GRANT_DENY,
    CAP_TENANT_PORTAL: GRANT_DENY,
  },
  GRACE_PERIOD: {
    CAP_PROFILE_VIEW: GRANT_ALLOW,
    CAP_PROFILE_EDIT: GRANT_LIMITED,
    CAP_PROFILE_JURISDICTION: GRANT_LIMITED,
    CAP_SUPPORT_ACCESS: GRANT_ALLOW,
    CAP_SUPPORT_REQUEST: GRANT_ALLOW,
    CAP_KNOWLEDGE_CENTRE: GRANT_ALLOW,
    CAP_NOTIF_SMS: GRANT_LIMITED,
    CAP_BRANDING_VIEW: GRANT_READ,
    CAP_BRANDING_EDIT: GRANT_LIMITED,
    CAP_BRANDING_WHITE_LABEL: GRANT_LIMITED,
    CAP_TENANT_PORTAL: GRANT_LIMITED,
  },
};

export function evaluateProfileCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewProfile: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.PROFILE_VIEW, 'read').allowed,
    canEditProfile: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.PROFILE_EDIT, 'write').allowed,
    canViewJurisdiction: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.PROFILE_JURISDICTION, 'read').allowed,
    canEditJurisdiction: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.PROFILE_JURISDICTION, 'write').allowed,
    canUseSmsNotifications: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.NOTIF_SMS, 'read').allowed,
    canWriteSmsNotifications: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.NOTIF_SMS, 'write').allowed,
  };
}

export function evaluateSupportCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canAccessSupport: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.SUPPORT_ACCESS, 'read').allowed,
    canRequestSupport: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.SUPPORT_REQUEST, 'write').allowed,
    canViewKnowledgeCentre: evaluateCapabilityGrant(caps, ACCOUNT_CAPABILITY.KNOWLEDGE_CENTRE, 'read').allowed,
  };
}

export function evaluateNavFeatureAllowedFromMap(capabilities, featureKey) {
  const mapping = NAV_FEATURE_CAPABILITY[featureKey];
  if (!mapping) return true;
  return evaluateCapabilityGrant(capabilities || {}, mapping.capabilityId, mapping.action).allowed;
}
