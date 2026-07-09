import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import { evaluateCapabilityGrant } from './capabilityRuntime';
import { ACCOUNT_CAPABILITY } from './accountCapabilityAccess';
import { REPORT_CAPABILITY } from './reportCapabilityAccess';

/** Runtime Contract capability ids for tenant operations domain. */
export const TENANT_CAPABILITY = {
  PORTAL: ACCOUNT_CAPABILITY.TENANT_PORTAL,
  MANAGE: 'CAP_TENANT_MANAGE',
  MESSAGES: 'CAP_TENANT_MESSAGES',
};

export function useTenantCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canAccessTenantPortal: capabilityAllowed(TENANT_CAPABILITY.PORTAL, 'read'),
      canViewTenants: capabilityAllowed(TENANT_CAPABILITY.MANAGE, 'read'),
      canManageTenants: capabilityAllowed(TENANT_CAPABILITY.MANAGE, 'write'),
      canViewTenantMessages: capabilityAllowed(TENANT_CAPABILITY.MESSAGES, 'read'),
      canWriteTenantMessages: capabilityAllowed(TENANT_CAPABILITY.MESSAGES, 'write'),
      canViewTenantDeliveries: capabilityAllowed(TENANT_CAPABILITY.MANAGE, 'read'),
      canSendTenantDelivery:
        capabilityAllowed(TENANT_CAPABILITY.MANAGE, 'write') &&
        capabilityAllowed(REPORT_CAPABILITY.GENERATE_PDF, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function evaluateTenantCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canAccessTenantPortal: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.PORTAL, 'read').allowed,
    canViewTenants: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MANAGE, 'read').allowed,
    canManageTenants: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MANAGE, 'write').allowed,
    canViewTenantMessages: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MESSAGES, 'read').allowed,
    canWriteTenantMessages: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MESSAGES, 'write').allowed,
    canViewTenantDeliveries: evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MANAGE, 'read').allowed,
    canSendTenantDelivery:
      evaluateCapabilityGrant(caps, TENANT_CAPABILITY.MANAGE, 'write').allowed &&
      evaluateCapabilityGrant(caps, REPORT_CAPABILITY.GENERATE_PDF, 'write').allowed,
  };
}
