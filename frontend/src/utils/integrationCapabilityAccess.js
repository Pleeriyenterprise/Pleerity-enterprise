import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import { evaluateCapabilityGrant } from './capabilityRuntime';

/** Runtime Contract capability ids for integrations domain. */
export const INTEGRATION_CAPABILITY = {
  WEBHOOKS: 'CAP_INTEGRATION_WEBHOOKS',
  READ_API: 'CAP_INTEGRATION_READ_API',
  EXPORT_API: 'CAP_EXPORT_API',
};

export function useIntegrationCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewWebhooks: capabilityAllowed(INTEGRATION_CAPABILITY.WEBHOOKS, 'read'),
      canWriteWebhooks: capabilityAllowed(INTEGRATION_CAPABILITY.WEBHOOKS, 'write'),
      canViewReadApiKeys: capabilityAllowed(INTEGRATION_CAPABILITY.READ_API, 'read'),
      canWriteReadApiKeys: capabilityAllowed(INTEGRATION_CAPABILITY.READ_API, 'write'),
      canUseExportApi: capabilityAllowed(INTEGRATION_CAPABILITY.EXPORT_API, 'read'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function evaluateIntegrationCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewWebhooks: evaluateCapabilityGrant(caps, INTEGRATION_CAPABILITY.WEBHOOKS, 'read').allowed,
    canWriteWebhooks: evaluateCapabilityGrant(caps, INTEGRATION_CAPABILITY.WEBHOOKS, 'write').allowed,
    canViewReadApiKeys: evaluateCapabilityGrant(caps, INTEGRATION_CAPABILITY.READ_API, 'read').allowed,
    canWriteReadApiKeys: evaluateCapabilityGrant(caps, INTEGRATION_CAPABILITY.READ_API, 'write').allowed,
    canUseExportApi: evaluateCapabilityGrant(caps, INTEGRATION_CAPABILITY.EXPORT_API, 'read').allowed,
  };
}
