import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import { evaluateCapabilityGrant } from './capabilityRuntime';

/** Runtime Contract capability ids for AI assistant domain. */
export const ASSISTANT_CAPABILITY = {
  ASSISTANT: 'CAP_AI_ASSISTANT',
};

export function useAssistantCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewAssistant: capabilityAllowed(ASSISTANT_CAPABILITY.ASSISTANT, 'read'),
      canUseAssistant: capabilityAllowed(ASSISTANT_CAPABILITY.ASSISTANT, 'write'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function evaluateAssistantCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewAssistant: evaluateCapabilityGrant(caps, ASSISTANT_CAPABILITY.ASSISTANT, 'read').allowed,
    canUseAssistant: evaluateCapabilityGrant(caps, ASSISTANT_CAPABILITY.ASSISTANT, 'write').allowed,
  };
}
