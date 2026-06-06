import { useCallback, useEffect, useState } from 'react';
import { classifyAxiosError } from '../utils/adminFetchState';

/**
 * Load authenticated admin/client data via apiClient (axios) with explicit error surfaces.
 * @param {() => Promise<{ data: unknown }>} fetcher — typically adminAPI.* call
 * @param {unknown[]} deps — refetch when deps change
 */
export function useAuthenticatedQuery(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await fetcher();
        if (cancelled) return;
        setData(res?.data ?? null);
      } catch (err) {
        if (cancelled) return;
        setData(null);
        setError(classifyAxiosError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetcher identity controlled by caller deps
  }, [...deps, reloadToken]);

  return { data, loading, error, reload };
}
