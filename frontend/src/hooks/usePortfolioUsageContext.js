import { useCallback, useContext, useEffect, useState } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { clientAPI } from '../api/client';

/**
 * Display-only portfolio usage (property count vs plan cap).
 * Fetches GET /client/entitlements/context — backend gated by CAP_DASHBOARD_VIEW, not legacy hasFeature().
 * Safe outside AuthProvider (returns null context when unauthenticated).
 */
export function usePortfolioUsageContext() {
  const auth = useContext(AuthContext);
  const user = auth?.user;
  const isClient =
    user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  const [usageContext, setUsageContext] = useState(null);
  const [loading, setLoading] = useState(Boolean(isClient));

  const refetch = useCallback(async () => {
    if (!isClient) {
      setUsageContext(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    try {
      const res = await clientAPI.getEntitlementsContext();
      setUsageContext(res?.data ?? null);
      return res?.data ?? null;
    } catch {
      setUsageContext(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [isClient]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { usageContext, loading, refetch };
}
