import React from 'react';
import { useLifecycleRuntime, LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE } from '../../contexts/LifecycleRuntimeContext';
import { UpgradeRequired } from '../UpgradePrompt';
import { Button } from '../ui/button';

/**
 * In-page capability gate — explicit denial instead of false-empty chrome.
 * Use when the route is not wrapped in CapabilityProtectedRoute.
 */
export function InPageCapabilityGate({
  allowed,
  capabilityId = null,
  presentationFeature = 'maintenance_workflows',
  loading = false,
  children,
  testId = 'in-page-capability-gate',
}) {
  const { loading: runtimeLoading, runtimeAvailable, error, refetch } = useLifecycleRuntime();

  if (loading || runtimeLoading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center" data-testid={`${testId}-loading`}>
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!runtimeAvailable && error) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center p-6" data-testid={`${testId}-runtime-unavailable`}>
        <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-sm text-center space-y-4">
          <p className="text-gray-700 text-sm">{LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE}</p>
          <Button type="button" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => refetch?.()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center p-6 bg-gray-50" data-testid={testId}>
        <div className="w-full max-w-md">
          <UpgradeRequired feature={presentationFeature} showBackToDashboard variant="card" />
          {capabilityId ? (
            <p className="text-xs text-gray-500 text-center mt-3" data-testid={`${testId}-cap`}>
              Access requires {capabilityId} on your account.
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  return children;
}
