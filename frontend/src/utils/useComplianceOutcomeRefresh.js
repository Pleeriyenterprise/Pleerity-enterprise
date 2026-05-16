import { useEffect } from 'react';

/**
 * Refetch portfolio/property requirement data when any surface completes a compliance action.
 * @param {() => void} onRefresh
 * @param {unknown[]} deps
 */
export function useComplianceOutcomeRefresh(onRefresh, deps = []) {
  useEffect(() => {
    if (typeof onRefresh !== 'function') return undefined;
    const handler = () => onRefresh();
    window.addEventListener('compliance-outcome', handler);
    return () => window.removeEventListener('compliance-outcome', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- caller supplies stable onRefresh + domain deps
  }, deps);
}
