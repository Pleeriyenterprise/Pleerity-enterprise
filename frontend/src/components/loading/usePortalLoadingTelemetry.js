import { useEffect, useRef } from 'react';
import { clientAPI } from '../../api/client';

function emitPortalAnalyticsEvent(body) {
  if (typeof clientAPI.postAnalyticsEvent !== 'function') return;
  try {
    const result = clientAPI.postAnalyticsEvent(body);
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  } catch {
    /* non-blocking telemetry */
  }
}

/**
 * First-party portal loading telemetry (server allowlist enforced).
 *
 * @param {{ page: 'today' | 'command_center' | 'dashboard', path: string, isLoading: boolean, ready: boolean, failed?: boolean, properties?: Record<string, unknown> }} opts
 */
export function usePortalLoadingTelemetry({ page, path, isLoading, ready, failed = false, properties = {} }) {
  const startedRef = useRef(false);
  const startMsRef = useRef(0);

  const propsRef = useRef(properties);
  propsRef.current = properties;

  useEffect(() => {
    if (!isLoading || startedRef.current) return;
    startedRef.current = true;
    startMsRef.current = performance.now();
    emitPortalAnalyticsEvent({
      event: 'portal_loading_started',
      path,
      properties: { page, ...propsRef.current },
    });
  }, [isLoading, page, path]);

  useEffect(() => {
    if (!startedRef.current || isLoading) return;
    if (!ready && !failed) return;

    const duration_ms = Math.round(performance.now() - startMsRef.current);
    emitPortalAnalyticsEvent({
      event: 'portal_loading_completed',
      path,
      properties: {
        page,
        portal_loading_duration_ms: duration_ms,
        outcome: failed ? 'failed' : 'ready',
        ...propsRef.current,
      },
    });

    startedRef.current = false;
  }, [isLoading, ready, failed, page, path]);
}
