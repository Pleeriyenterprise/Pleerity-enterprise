import { useContext, useMemo } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { useLifecycleRuntime } from '../contexts/LifecycleRuntimeContext';

/**
 * Display-only portfolio usage (plan cap from Runtime Contract).
 * Consumes lifecycle-runtime plan material — does not call legacy /client/entitlements*.
 * Safe outside AuthProvider (returns null context when unauthenticated).
 */
export function usePortfolioUsageContext() {
  const auth = useContext(AuthContext);
  const user = auth?.user;
  const isClient =
    user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  const { runtime, runtimeAvailable, loading, refetch } = useLifecycleRuntime();

  const usageContext = useMemo(() => {
    if (!isClient || !runtimeAvailable) {
      return null;
    }
    const plan = runtime?.plan;
    if (!plan) {
      return null;
    }
    const maxProperties =
      typeof plan.max_properties === 'number' ? plan.max_properties : null;
    return {
      property_count: null,
      max_properties: maxProperties,
      at_property_limit: null,
      plan: plan.plan_code || null,
      plan_name: plan.plan_name || null,
      is_active: runtime?.lifecycle_state === 'ACTIVE' || runtime?.lifecycle_state === 'TRIAL',
      read_api_base_path: '/api/client-data/v1',
    };
  }, [isClient, runtime, runtimeAvailable]);

  return {
    usageContext,
    loading: Boolean(isClient && loading),
    refetch,
  };
}
