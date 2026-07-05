import { useMemo } from 'react';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';
import { evaluateCapabilityGrant } from './capabilityRuntime';

/** Runtime Contract capability ids for calendar domain. */
export const CALENDAR_CAPABILITY = {
  VIEW: 'CAP_CALENDAR_VIEW',
};

export function useCalendarCapabilities() {
  const { capabilityAllowed, getCapabilityGrant } = useLifecycleRuntime();

  return useMemo(
    () => ({
      canViewCalendar: capabilityAllowed(CALENDAR_CAPABILITY.VIEW, 'read'),
      canExportCalendar: capabilityAllowed(CALENDAR_CAPABILITY.VIEW, 'read'),
      getCapabilityGrant,
    }),
    [capabilityAllowed, getCapabilityGrant],
  );
}

export function evaluateCalendarCapabilitiesFromMap(capabilities) {
  const caps = capabilities || {};
  return {
    canViewCalendar: evaluateCapabilityGrant(caps, CALENDAR_CAPABILITY.VIEW, 'read').allowed,
    canExportCalendar: evaluateCapabilityGrant(caps, CALENDAR_CAPABILITY.VIEW, 'read').allowed,
  };
}
