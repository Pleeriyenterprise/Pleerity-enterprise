import React from 'react';
import { getBuildMetadata } from '../utils/buildMetadata';

/**
 * On-screen debug panel shown only when ?debug=1 is in the URL.
 * Shows: build SHA, deployment env, backend URL, last API error.
 */
function DebugPanel() {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  if (params.get('debug') !== '1') return null;

  const { buildSha, deploymentEnv, apiBaseUrl } = getBuildMetadata();
  const lastError = window.__CVP_LAST_API_ERROR;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 bg-gray-900 text-gray-100 text-xs p-3 font-mono z-[9999] border-t border-gray-700"
      data-testid="debug-panel"
    >
      <div className="max-w-4xl mx-auto flex flex-wrap gap-4 items-center">
        <span data-testid="debug-build-sha">
          <strong>Build:</strong> {buildSha}
        </span>
        <span data-testid="debug-deployment-env">
          <strong>Env:</strong> {deploymentEnv}
        </span>
        <span data-testid="debug-backend-url">
          <strong>Backend URL:</strong> {apiBaseUrl}
        </span>
        {lastError && (
          <span>
            <strong>Last API error:</strong> {lastError.status ?? '—'}{' '}
            {lastError.message ? `— ${String(lastError.message).slice(0, 80)}` : ''}
          </span>
        )}
      </div>
    </div>
  );
}

export default DebugPanel;
