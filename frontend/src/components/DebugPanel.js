import React from 'react';

/**
 * On-screen debug panel shown only when ?debug=1 is in the URL.
 * Shows: build SHA, backend URL, last API error (status + message).
 * Runtime-safe: no crash if window or URL is missing.
 */
function DebugPanel() {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  if (params.get('debug') !== '1') return null;

  const backendUrl = window.__CVP_BACKEND_URL ?? '(not set)';
  const buildSha = typeof process !== 'undefined' && process.env && process.env.REACT_APP_BUILD_SHA
    ? process.env.REACT_APP_BUILD_SHA
    : (window.__CVP_BUILD_SHA ?? '(not set)');
  const lastError = window.__CVP_LAST_API_ERROR;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 bg-gray-900 text-gray-100 text-xs p-3 font-mono z-[9999] border-t border-gray-700"
      data-testid="debug-panel"
    >
      <div className="max-w-4xl mx-auto flex flex-wrap gap-4 items-center">
        <span><strong>Build:</strong> {buildSha}</span>
        <span><strong>Backend URL:</strong> {backendUrl}</span>
        {lastError && (
          <span>
            <strong>Last API error:</strong> {lastError.status ?? '—'} {lastError.message ? `— ${String(lastError.message).slice(0, 80)}` : ''}
          </span>
        )}
      </div>
    </div>
  );
}

export default DebugPanel;
