import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { clientAPI } from '../api/client';

const EntitlementsContext = createContext(null);

export function EntitlementsProvider({ children }) {
  const { user } = useAuth();
  const [entitlements, setEntitlements] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEntitlements = useCallback(async () => {
    const isClient = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;
    if (!isClient) {
      setEntitlements(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await clientAPI.getEntitlements();
      setEntitlements(response.data);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Failed to load entitlements');
      setEntitlements(null);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchEntitlements();
  }, [fetchEntitlements]);

  const hasFeature = useCallback(
    (featureKey) => Boolean(entitlements?.features?.[featureKey]?.enabled),
    [entitlements]
  );

  const value = {
    entitlements,
    loading,
    error,
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
      loading: false,
      error: null,
      hasFeature: () => false,
      plan: null,
      planName: null,
      subscriptionStatus: null,
      isActive: false,
      refetch: () => {},
    };
  }
  return ctx;
}
