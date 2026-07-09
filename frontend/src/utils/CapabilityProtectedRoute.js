import React from 'react';
import { useLifecycleRuntime, LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE } from '../contexts/LifecycleRuntimeContext';
import { usePortalMode } from '../contexts/LifecycleRuntimeContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import { LifecycleCapabilityDenial } from '../components/lifecycle/LifecycleCapabilityDenial';
import { Button } from '../components/ui/button';
import { isLifecycleRestrictedPortalMode } from './lifecycleRecoveryCopy';
import { OPERATIONAL_ROUTE_CAPABILITY } from './operationalCapabilityAccess';
import { ACCOUNT_ROUTE_CAPABILITY } from './accountCapabilityAccess';

export const ROUTE_CAPABILITY = {
  ...OPERATIONAL_ROUTE_CAPABILITY,
  ...ACCOUNT_ROUTE_CAPABILITY,
};

/**
 * Renders children only when the Runtime Contract grants the required capability.
 * Presentation upgrade card uses legacy feature display metadata when configured.
 */
export function CapabilityProtectedRoute({
  capabilityId,
  action = 'read',
  presentationFeature = null,
  children,
}) {
  const { capabilityAllowed, loading, runtimeAvailable, error, refetch } = useLifecycleRuntime();
  const { portalMode } = usePortalMode();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!runtimeAvailable && error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50" data-testid="capability-runtime-load-error">
        <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-sm text-center space-y-4">
          <p className="text-gray-700 text-sm">{LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE}</p>
          <Button type="button" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => refetch?.()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!capabilityAllowed(capabilityId, action)) {
    if (isLifecycleRestrictedPortalMode(portalMode)) {
      return <LifecycleCapabilityDenial testId="capability-gate" />;
    }
    const featureKey =
      presentationFeature ||
      Object.entries(ROUTE_CAPABILITY).find(([, r]) => r.capabilityId === capabilityId)?.[0] ||
      'maintenance_workflows';
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50" data-testid="capability-gate">
        <div className="w-full max-w-md">
          <UpgradeRequired feature={featureKey} showBackToDashboard variant="card" />
        </div>
      </div>
    );
  }

  return children;
}

/**
 * Route gate keyed by legacy presentation feature id (permission via Runtime Contract).
 */
export function AccountCapabilityProtectedRoute({ requiredFeature, children }) {
  const route = ROUTE_CAPABILITY[requiredFeature];
  if (!route) {
    return children;
  }
  return (
    <CapabilityProtectedRoute
      capabilityId={route.capabilityId}
      action={route.action}
      presentationFeature={route.presentationFeature || requiredFeature}
    >
      {children}
    </CapabilityProtectedRoute>
  );
}

/**
 * Route gate keyed by legacy operational presentation feature id.
 */
export function OperationalCapabilityProtectedRoute({ requiredFeature, children }) {
  const route = OPERATIONAL_ROUTE_CAPABILITY[requiredFeature];
  if (!route) {
    return children;
  }
  return (
    <CapabilityProtectedRoute
      capabilityId={route.capabilityId}
      action={route.action}
      presentationFeature={route.presentationFeature}
    >
      {children}
    </CapabilityProtectedRoute>
  );
}
