import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { clientAPI } from '../api/client';

/**
 * @deprecated Legacy entitlement fetch — customer permission authority is LifecycleRuntimeContext.
 * Retained for admin tooling references only; not mounted in customer App tree after ILP-4 completion.
 */

/** Shown in UI only — never forward API exception text or `detail` to users. */
export const ENTITLEMENTS_UNAVAILABLE_USER_MESSAGE =
  "We couldn't load your plan information. Please try again in a moment.";

export function EntitlementsProvider({ children }) {
  const { user } = useAuth();
  const [entitlements, setEntitlements] = useState(null);
  const [usageContext, setUsageContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEntitlements = useCallback(async () => {
    const isClient = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;
    if (!isClient) {
      setEntitlements(null);
      setUsageContext(null);
      setLoading(false);
      setError(null);
      return false;
    }
    setLoading(true);
    setError(null);
    try {
      const [entRes, ctxRes] = await Promise.all([
        clientAPI.getEntitlements(),
        clientAPI.getEntitlementsContext().catch(() => null),
      ]);
      setEntitlements(entRes.data);
      setUsageContext(ctxRes?.data ?? null);
      setError(null);
      return true;
    } catch (err) {
      if (process.env.NODE_ENV !== 'production') {
        console.warn('[entitlements] fetch failed', err);
      }
      setError(ENTITLEMENTS_UNAVAILABLE_USER_MESSAGE);
      setEntitlements(null);
      setUsageContext(null);
      return false;
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchEntitlements();
  }, [fetchEntitlements]);

  // Refetch when window gains focus so client sees menu changes after admin toggles (without full refresh)
  useEffect(() => {
    let lastFocusRefetch = 0;
    const throttleMs = 10000; // at most once per 10s on focus
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastFocusRefetch < throttleMs) return;
      lastFocusRefetch = now;
      fetchEntitlements();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [fetchEntitlements]);

  const hasFeature = useCallback(
    (featureKey) => Boolean(entitlements?.features?.[featureKey]?.enabled),
    [entitlements]
  );

  const entitlementsLoadFailed = Boolean(error);

  const value = {
    entitlements,
    usageContext,
    loading,
    error,
    entitlementsLoadFailed,
    hasFeature,
    plan: entitlements?.plan ?? null,
    planName: entitlements?.plan_name ?? null,
    subscriptionStatus: entitlements?.subscription_status ?? null,
    isActive: entitlements?.is_active ?? false,
    refetch: fetchEntitlements,
  };

  return (
    <EntitlementsContext.Provider value={value}>
      {children}
    </EntitlementsContext.Provider>
  );
}

export function useEntitlements() {
  const ctx = useContext(EntitlementsContext);
  if (!ctx) {
    return {
      entitlements: null,
      usageContext: null,
      loading: false,
      error: null,
      entitlementsLoadFailed: false,
      hasFeature: () => false,
      plan: null,
      planName: null,
      subscriptionStatus: null,
      isActive: false,
      refetch: async () => false,
    };
  }
  return ctx;
}
