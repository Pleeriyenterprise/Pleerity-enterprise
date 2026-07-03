import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { clientAPI } from '../api/client';

const LifecycleRuntimeContext = createContext(null);
const PortalModeContext = createContext(null);

export const LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE =
  'Account status is temporarily unavailable. You can continue using the portal; permissions are unchanged.';

const GOVERNED_FALLBACK = {
  contract_version: null,
  runtime_version: null,
  lifecycle_state: null,
  portal_mode: 'FULL_ACCESS',
  customer_experience: {
    heading: '',
    explanation: LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE,
    reason: '',
    current_state_label: '',
    available_features: [],
    unavailable_features: [],
    primary_cta: null,
    secondary_cta: null,
    recovery_guidance: '',
    support_guidance: 'Contact support if you need help.',
    expected_next_step: '',
  },
  navigation_policy: {
    landing_route: '/today',
    locked_routes: [],
    read_only_routes: [],
    hidden_routes: [],
  },
  polling_policy: { enabled: false, reason: 'fallback' },
  warnings: ['lifecycle_runtime_unavailable'],
};

function isClientUser(user) {
  return Boolean(
    user &&
      (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') &&
      user.client_id,
  );
}

export function LifecycleRuntimeProvider({ children }) {
  const { user } = useAuth();
  const [runtime, setRuntime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [contractVersion, setContractVersion] = useState(null);
  const [runtimeVersion, setRuntimeVersion] = useState(null);
  const lastFetchRef = useRef(0);

  const fetchRuntime = useCallback(async () => {
    if (!isClientUser(user)) {
      setRuntime(null);
      setLoading(false);
      setError(null);
      setContractVersion(null);
      setRuntimeVersion(null);
      return false;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await clientAPI.getLifecycleRuntime();
      const payload = res.data?.lifecycle_runtime || null;
      setRuntime(payload);
      setContractVersion(
        res.headers?.['x-lifecycle-contract-version'] ||
          res.headers?.['X-Lifecycle-Contract-Version'] ||
          payload?.contract_version ||
          null,
      );
      setRuntimeVersion(
        res.headers?.['x-lifecycle-runtime-version'] ||
          res.headers?.['X-Lifecycle-Runtime-Version'] ||
          payload?.runtime_version ||
          null,
      );
      lastFetchRef.current = Date.now();
      return true;
    } catch (err) {
      if (process.env.NODE_ENV !== 'production') {
        console.warn('[lifecycle-runtime] fetch failed', err);
      }
      setError(LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE);
      setRuntime(null);
      return false;
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchRuntime();
  }, [fetchRuntime]);

  useEffect(() => {
    const pollingEnabled = runtime?.polling_policy?.enabled;
    if (!pollingEnabled || !isClientUser(user)) return undefined;
    const timer = setInterval(() => {
      fetchRuntime();
    }, 120000);
    return () => clearInterval(timer);
  }, [runtime?.polling_policy?.enabled, fetchRuntime, user]);

  useEffect(() => {
    let lastFocusRefetch = 0;
    const throttleMs = 30000;
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastFocusRefetch < throttleMs) return;
      lastFocusRefetch = now;
      if (runtime?.polling_policy?.enabled !== false) {
        fetchRuntime();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [fetchRuntime, runtime?.polling_policy?.enabled]);

  const effectiveRuntime = runtime || GOVERNED_FALLBACK;
  const runtimeAvailable = Boolean(runtime);
  const portalMode = effectiveRuntime.portal_mode || 'FULL_ACCESS';

  const lifecycleValue = useMemo(
    () => ({
      runtime: effectiveRuntime,
      rawRuntime: runtime,
      runtimeAvailable,
      loading,
      error,
      contractVersion: contractVersion || effectiveRuntime.contract_version,
      runtimeVersion: runtimeVersion || effectiveRuntime.runtime_version,
      lifecycleState: effectiveRuntime.lifecycle_state,
      portalMode,
      customerExperience: effectiveRuntime.customer_experience || GOVERNED_FALLBACK.customer_experience,
      navigationPolicy: effectiveRuntime.navigation_policy || GOVERNED_FALLBACK.navigation_policy,
      warnings: effectiveRuntime.warnings || [],
      pollingPolicy: effectiveRuntime.polling_policy || GOVERNED_FALLBACK.polling_policy,
      refetch: fetchRuntime,
    }),
    [
      effectiveRuntime,
      runtime,
      runtimeAvailable,
      loading,
      error,
      contractVersion,
      runtimeVersion,
      portalMode,
      fetchRuntime,
    ],
  );

  const portalModeValue = useMemo(
    () => ({
      portalMode,
      runtimeAvailable,
      customerExperience: lifecycleValue.customerExperience,
      navigationPolicy: lifecycleValue.navigationPolicy,
      lifecycleState: lifecycleValue.lifecycleState,
    }),
    [portalMode, runtimeAvailable, lifecycleValue],
  );

  return (
    <LifecycleRuntimeContext.Provider value={lifecycleValue}>
      <PortalModeContext.Provider value={portalModeValue}>{children}</PortalModeContext.Provider>
    </LifecycleRuntimeContext.Provider>
  );
}

export function useLifecycleRuntime() {
  const ctx = useContext(LifecycleRuntimeContext);
  if (!ctx) {
    return {
      runtime: GOVERNED_FALLBACK,
      rawRuntime: null,
      runtimeAvailable: false,
      loading: false,
      error: null,
      contractVersion: null,
      runtimeVersion: null,
      lifecycleState: null,
      portalMode: 'FULL_ACCESS',
      customerExperience: GOVERNED_FALLBACK.customer_experience,
      navigationPolicy: GOVERNED_FALLBACK.navigation_policy,
      warnings: [],
      pollingPolicy: GOVERNED_FALLBACK.polling_policy,
      refetch: async () => false,
    };
  }
  return ctx;
}

/** Presentation-only portal mode — never use for permission checks. */
export function usePortalMode() {
  const ctx = useContext(PortalModeContext);
  if (!ctx) {
    return {
      portalMode: 'FULL_ACCESS',
      runtimeAvailable: false,
      customerExperience: GOVERNED_FALLBACK.customer_experience,
      navigationPolicy: GOVERNED_FALLBACK.navigation_policy,
      lifecycleState: null,
    };
  }
  return ctx;
}
