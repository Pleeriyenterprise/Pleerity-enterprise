import { useEffect, useMemo, useState } from 'react';

/**
 * Time-based stage progression for perceived progress while async work runs.
 * Does not claim real backend milestones — advances on a gentle timer only.
 */
export function usePortalLoadingStages(stageDefs, isActive, { intervalMs = 2200 } = {}) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setActiveIndex(0);
      return undefined;
    }
    setActiveIndex(0);
    const id = window.setInterval(() => {
      setActiveIndex((prev) => {
        const max = Math.max(0, stageDefs.length - 1);
        return prev >= max ? prev : prev + 1;
      });
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [isActive, stageDefs.length, intervalMs]);

  const stages = useMemo(() => {
    if (!isActive) {
      return stageDefs.map((s) => ({ ...s, status: 'complete' }));
    }
    return stageDefs.map((s, i) => {
      if (i < activeIndex) return { ...s, status: 'complete' };
      if (i === activeIndex) return { ...s, status: 'active' };
      return { ...s, status: 'pending' };
    });
  }, [stageDefs, activeIndex, isActive]);

  return stages;
}
