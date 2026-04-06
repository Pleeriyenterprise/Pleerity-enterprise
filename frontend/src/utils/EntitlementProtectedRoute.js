import React from 'react';
import { useEntitlements, ENTITLEMENTS_UNAVAILABLE_USER_MESSAGE } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import { Button } from '../components/ui/button';

/**
 * Renders children only if the client has the required feature entitlement.
 * If not entitled, shows UpgradeRequired (no ErrorBoundary, no crash).
 * Use for routes that are fully gated: tenants, integrations, branding.
 */
export function EntitlementProtectedRoute({ requiredFeature, children }) {
  const { hasFeature, loading, entitlementsLoadFailed, refetch } = useEntitlements();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (entitlementsLoadFailed) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50" data-testid="entitlement-load-error">
        <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-sm text-center space-y-4">
          <p className="text-gray-700 text-sm">{ENTITLEMENTS_UNAVAILABLE_USER_MESSAGE}</p>
          <Button type="button" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
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
