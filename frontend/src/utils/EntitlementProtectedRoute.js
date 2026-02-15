import React from 'react';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';

/**
 * Renders children only if the client has the required feature entitlement.
 * If not entitled, shows UpgradeRequired (no ErrorBoundary, no crash).
 * Use for routes that are fully gated: tenants, integrations, branding.
 */
export function EntitlementProtectedRoute({ requiredFeature, children }) {
  const { hasFeature, loading } = useEntitlements();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!hasFeature(requiredFeature)) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50" data-testid="entitlement-gate">
        <div className="w-full max-w-md">
          <UpgradeRequired feature={requiredFeature} showBackToDashboard variant="card" />
        </div>
      </div>
    );
  }

  return children;
}
