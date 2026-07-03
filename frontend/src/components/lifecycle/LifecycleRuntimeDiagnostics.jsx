import React from 'react';
import { useLifecycleRuntime } from '../../contexts/LifecycleRuntimeContext';

/** Developer diagnostics — read-only lifecycle runtime inspection. */
export default function LifecycleRuntimeDiagnostics() {
  const {
    runtime,
    rawRuntime,
    runtimeAvailable,
    portalMode,
    lifecycleState,
    contractVersion,
    runtimeVersion,
    customerExperience,
    navigationPolicy,
    warnings,
    loading,
    error,
  } = useLifecycleRuntime();

  const enabled =
    process.env.NODE_ENV !== 'production' ||
    (typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('lifecycle_debug') === '1');

  if (!enabled) return null;

  return (
    <details
      className="mb-4 rounded border border-dashed border-gray-300 bg-gray-50 p-3 text-xs font-mono"
      data-testid="lifecycle-runtime-diagnostics"
    >
      <summary className="cursor-pointer font-sans font-medium text-gray-700">
        Lifecycle runtime diagnostics (read-only)
      </summary>
      <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-gray-800">
        {JSON.stringify(
          {
            loading,
            error,
            runtimeAvailable,
            contractVersion,
            runtimeVersion,
            lifecycleState,
            portalMode,
            warnings,
            customerExperience,
            navigationPolicy,
            runtime: rawRuntime || runtime,
          },
          null,
          2,
        )}
      </pre>
    </details>
  );
}
