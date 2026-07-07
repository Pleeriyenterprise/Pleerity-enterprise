import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { clientAPI } from '../api/client';
import {
  evaluateCapabilityGrant,
  formatApiErrorDetail,
  normalizeCustomerExperience,
  parseLifecycleResponseDetail,
} from '../utils/capabilityRuntime';
import {
  applySessionRuntimeFromContract,
  applySessionRuntimeFromUser,
  registerSessionRuntimeRefreshHandler,
} from '../utils/sessionRuntimeStore';
import {
  broadcastRuntimeInvalidation,
  isDocumentOnline,
  subscribeSessionRuntimeSync,
} from '../utils/sessionRuntimeSync';

const LifecycleRuntimeContext = createContext(null);
const PortalModeContext = createContext(null);

export const LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE =
  'Account status could not be loaded. Your session is valid; retry shortly or refresh the page.';

const GOVERNED_FALLBACK = {
  contract_version: null,
  runtime_version: null,
  lifecycle_state: null,
  portal_mode: null,
  capabilities: EMPTY_CAPABILITIES,
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
    support_guidance: 'Contact support if this issue persists.',
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

const EMPTY_CAPABILITIES = Object.freeze({});

const REFRESH_THROTTLE_MS = 5000;
const VISIBILITY_THROTTLE_MS = 15000;
const FOCUS_THROTTLE_MS = 10000;
const OFFLINE_RETRY_MS = 30000;

function isClientUser(user) {
  return Boolean(
    user &&
      (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') &&
      user.client_id,
  );
}

function applyRuntimePayload(payload, sessionRuntime, setters) {
  const { setRuntime, setContractVersion, setRuntimeVersion, setSessionRuntime, setError } = setters;
  const normalizedPayload =
    payload && typeof payload === 'object'
      ? {
          ...payload,
          customer_experience: normalizeCustomerExperience(payload.customer_experience),
        }
      : payload;
  setRuntime(normalizedPayload);
  setContractVersion(payload?.contract_version || null);
  setRuntimeVersion(payload?.runtime_version ?? null);
  setSessionRuntime(sessionRuntime || null);
  applySessionRuntimeFromContract(payload, sessionRuntime);
  setError(null);
}

export function LifecycleRuntimeProvider({ children }) {
  const { user, loginWithToken, logout } = useAuth();
  const [runtime, setRuntime] = useState(null);
  const [sessionRuntime, setSessionRuntime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [contractVersion, setContractVersion] = useState(null);
  const [runtimeVersion, setRuntimeVersion] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [offline, setOffline] = useState(false);
  const lastFetchRef = useRef(0);
  const refreshLockRef = useRef(false);
  const lastRefreshAttemptRef = useRef(0);
  const runtimeRef = useRef(null);
  const sessionRuntimeRef = useRef(null);

  runtimeRef.current = runtime;
  sessionRuntimeRef.current = sessionRuntime;

  const fetchRuntime = useCallback(
    async (options = {}) => {
      const { reason = 'fetch', force = false } = options;
      if (!isClientUser(user)) {
        setRuntime(null);
        setSessionRuntime(null);
        setLoading(false);
        setError(null);
        setContractVersion(null);
        setRuntimeVersion(null);
        return false;
      }

      if (!isDocumentOnline()) {
        setOffline(true);
        setError('You appear to be offline. Permissions will refresh when connectivity returns.');
        return false;
      }
      setOffline(false);

      const now = Date.now();
      if (!force && now - lastRefreshAttemptRef.current < REFRESH_THROTTLE_MS && reason !== 'login') {
        return false;
      }
      if (refreshLockRef.current && !force) {
        return false;
      }

      refreshLockRef.current = true;
      lastRefreshAttemptRef.current = now;
      if (!runtimeRef.current || reason === 'login') {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      setError(null);

      try {
        const res = await clientAPI.getLifecycleRuntime();
        const payload = res.data?.lifecycle_runtime || null;
        const headerContract =
          res.headers?.['x-lifecycle-contract-version'] ||
          res.headers?.['X-Lifecycle-Contract-Version'] ||
          payload?.contract_version;
        const headerRuntime =
          res.headers?.['x-lifecycle-runtime-version'] ||
          res.headers?.['X-Lifecycle-Runtime-Version'] ||
          payload?.runtime_version;

        applyRuntimePayload(payload, sessionRuntimeRef.current, {
          setRuntime,
          setContractVersion: (v) => setContractVersion(v || headerContract || null),
          setRuntimeVersion: (v) => setRuntimeVersion(v ?? headerRuntime ?? null),
          setSessionRuntime,
          setError,
        });
        setContractVersion(headerContract || payload?.contract_version || null);
        setRuntimeVersion(headerRuntime ?? payload?.runtime_version ?? null);
        lastFetchRef.current = Date.now();
        return true;
      } catch (err) {
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[lifecycle-runtime] fetch failed', err);
        }
        const detail = err?.response?.data?.detail;
        const parsed = parseLifecycleResponseDetail(detail);
        const code = typeof detail === 'object' ? detail?.error_code : null;
        if (code === 'SESSION_FORCE_REAUTH' || code === 'SESSION_TERMINATED') {
          logout();
          return false;
        }
        if (parsed?.customer_experience) {
          setRuntime(null);
          setContractVersion(parsed.contract_version || null);
          setRuntimeVersion(parsed.runtime_version ?? null);
          setError(formatApiErrorDetail(parsed.message, LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE));
          return false;
        }
        setError(LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE);
        setRuntime(null);
        return false;
      } finally {
        setLoading(false);
        setRefreshing(false);
        refreshLockRef.current = false;
      }
    },
    [user, logout],
  );

  const refreshSession = useCallback(
    async (reason = 'manual') => {
      if (!isClientUser(user)) return false;
      if (!isDocumentOnline()) {
        setOffline(true);
        return false;
      }
      const now = Date.now();
      if (now - lastRefreshAttemptRef.current < REFRESH_THROTTLE_MS) {
        return false;
      }
      if (refreshLockRef.current) return false;

      refreshLockRef.current = true;
      lastRefreshAttemptRef.current = now;
      setRefreshing(true);
      try {
        const res = await clientAPI.refreshSessionRuntime(reason);
        const payload = res.data?.lifecycle_runtime;
        const session = res.data?.session_runtime;
        if (payload) {
          applyRuntimePayload(payload, session, {
            setRuntime,
            setContractVersion,
            setRuntimeVersion,
            setSessionRuntime,
            setError,
          });
          setContractVersion(payload.contract_version || null);
          setRuntimeVersion(payload.runtime_version ?? null);
        }
        if (res.data?.access_token && res.data?.user) {
          loginWithToken(res.data.access_token, res.data.user);
          applySessionRuntimeFromUser(res.data.user);
        }
        lastFetchRef.current = Date.now();
        broadcastRuntimeInvalidation({ reason, runtime_version: payload?.runtime_version });
        return true;
      } catch (err) {
        const detail = err?.response?.data?.detail;
        const code = typeof detail === 'object' ? detail?.error_code : null;
        if (code === 'SESSION_FORCE_REAUTH' || code === 'SESSION_TERMINATED') {
          logout();
          return false;
        }
        return fetchRuntime({ reason: 'refresh_fallback', force: true });
      } finally {
        setRefreshing(false);
        refreshLockRef.current = false;
      }
    },
    [user, fetchRuntime, loginWithToken, logout],
  );

  const fetchRuntimeRef = useRef(fetchRuntime);
  fetchRuntimeRef.current = fetchRuntime;

  useEffect(() => {
    applySessionRuntimeFromUser(user);
    fetchRuntimeRef.current({ reason: 'login', force: true });
  }, [user, user?.portal_user_id, user?.client_id, user?.role]);

  useEffect(() => {
    registerSessionRuntimeRefreshHandler(refreshSession);
    return () => registerSessionRuntimeRefreshHandler(null);
  }, [refreshSession]);

  useEffect(() => {
    return subscribeSessionRuntimeSync((event) => {
      if (!isClientUser(user)) return;
      if (event.type === 'auth_sync' && event.reason === 'logout') return;
      const since = lastFetchRef.current;
      if (event.at && since && event.at <= since) return;
      refreshSession(event.reason || event.type || 'tab_sync');
    });
  }, [user, refreshSession]);

  useEffect(() => {
    const pollingEnabled = runtime?.polling_policy?.enabled;
    if (!pollingEnabled || !isClientUser(user)) return undefined;
    const timer = setInterval(() => {
      fetchRuntime({ reason: 'poll' });
    }, 120000);
    return () => clearInterval(timer);
  }, [runtime?.polling_policy?.enabled, fetchRuntime, user]);

  useEffect(() => {
    let lastVisibilityRefetch = 0;
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible' || !isClientUser(user)) return;
      const now = Date.now();
      if (now - lastVisibilityRefetch < VISIBILITY_THROTTLE_MS) return;
      lastVisibilityRefetch = now;
      fetchRuntime({ reason: 'visibility' });
    };
    const onFocus = () => {
      if (!isClientUser(user)) return;
      const now = Date.now();
      if (now - lastVisibilityRefetch < FOCUS_THROTTLE_MS) return;
      lastVisibilityRefetch = now;
      fetchRuntime({ reason: 'focus' });
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('focus', onFocus);
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('focus', onFocus);
    };
  }, [fetchRuntime, user]);

  useEffect(() => {
    const onOnline = () => {
      setOffline(false);
      if (isClientUser(user)) {
        refreshSession('online');
      }
    };
    const onOffline = () => setOffline(true);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, [user, refreshSession]);

  useEffect(() => {
    if (!offline || !isClientUser(user)) return undefined;
    const timer = setInterval(() => {
      if (isDocumentOnline()) refreshSession('offline_retry');
    }, OFFLINE_RETRY_MS);
    return () => clearInterval(timer);
  }, [offline, user, refreshSession]);

  const effectiveRuntime = runtime || GOVERNED_FALLBACK;
  const runtimeAvailable = Boolean(runtime?.capabilities);
  const portalMode = effectiveRuntime.portal_mode || (runtimeAvailable ? 'FULL_ACCESS' : null);
  const capabilities = runtime?.capabilities ?? EMPTY_CAPABILITIES;

  const capabilityAllowed = useCallback(
    (capabilityId, action = 'read') =>
      evaluateCapabilityGrant(capabilities, capabilityId, action).allowed,
    [capabilities],
  );

  const getCapabilityGrant = useCallback(
    (capabilityId, action = 'read') => evaluateCapabilityGrant(capabilities, capabilityId, action),
    [capabilities],
  );

  const lifecycleValue = useMemo(
    () => ({
      runtime: effectiveRuntime,
      rawRuntime: runtime,
      sessionRuntime,
      runtimeAvailable,
      loading,
      refreshing,
      offline,
      error,
      contractVersion: contractVersion || effectiveRuntime.contract_version,
      runtimeVersion: runtimeVersion || effectiveRuntime.runtime_version,
      lifecycleState: effectiveRuntime.lifecycle_state,
      portalMode,
      capabilities,
      capabilityAllowed,
      getCapabilityGrant,
      customerExperience: effectiveRuntime.customer_experience || GOVERNED_FALLBACK.customer_experience,
      navigationPolicy: effectiveRuntime.navigation_policy || GOVERNED_FALLBACK.navigation_policy,
      warnings: effectiveRuntime.warnings || [],
      pollingPolicy: effectiveRuntime.polling_policy || GOVERNED_FALLBACK.polling_policy,
      sessionPolicy: effectiveRuntime.session_policy || null,
      refetch: () => fetchRuntime({ reason: 'manual', force: true }),
      refreshSession,
    }),
    [
      effectiveRuntime,
      runtime,
      sessionRuntime,
      runtimeAvailable,
      loading,
      refreshing,
      offline,
      error,
      contractVersion,
      runtimeVersion,
      portalMode,
      capabilities,
      capabilityAllowed,
      getCapabilityGrant,
      fetchRuntime,
      refreshSession,
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
      sessionRuntime: null,
      runtimeAvailable: false,
      loading: false,
      refreshing: false,
      offline: false,
      error: null,
      contractVersion: null,
      runtimeVersion: null,
      lifecycleState: null,
      portalMode: 'FULL_ACCESS',
      capabilities: EMPTY_CAPABILITIES,
      capabilityAllowed: () => false,
      getCapabilityGrant: () => ({ allowed: false, grant: 'HIDDEN', effectiveSemantic: 'HIDDEN' }),
      customerExperience: GOVERNED_FALLBACK.customer_experience,
      navigationPolicy: GOVERNED_FALLBACK.navigation_policy,
      warnings: [],
      pollingPolicy: GOVERNED_FALLBACK.polling_policy,
      sessionPolicy: null,
      refetch: async () => false,
      refreshSession: async () => false,
    };
  }
  return ctx;
}

/**
 * Runtime Contract capability check — uses lifecycle-runtime capabilities map only.
 * @param {string} capabilityId
 * @param {'read'|'write'} [action='read']
 */
export function useCapability(capabilityId, action = 'read') {
  const { capabilities, runtimeAvailable } = useLifecycleRuntime();
  return useMemo(
    () => ({
      ...evaluateCapabilityGrant(capabilities, capabilityId, action),
      runtimeAvailable,
      capabilityId,
      action,
    }),
    [capabilities, capabilityId, action, runtimeAvailable],
  );
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
