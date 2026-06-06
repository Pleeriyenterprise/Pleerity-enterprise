import React from 'react';
import { Button } from '../ui/button';
import { ADMIN_FETCH_STATE } from '../../utils/adminFetchState';

/**
 * Distinguish loading / empty / auth failure / server failure for admin tables.
 */
export default function AdminFetchStatePanel({
  loading,
  error,
  isEmpty,
  emptyMessage = 'No records found.',
  colSpan = 5,
  onRetry,
  children,
}) {
  if (loading) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-4 py-8 text-center text-gray-500">
          Loading…
        </td>
      </tr>
    );
  }
  if (error) {
    const isAuth = error.kind === ADMIN_FETCH_STATE.AUTH_FAILURE;
    return (
      <tr>
        <td colSpan={colSpan} className="px-4 py-4">
          <div
            className={`rounded-lg border p-4 text-sm flex flex-wrap items-center justify-between gap-3 ${
              isAuth ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-red-50 border-red-200 text-red-900'
            }`}
          >
            <span>{error.message || 'Unable to load data.'}</span>
            <div className="flex gap-2">
              {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry}>
                  Retry
                </Button>
              )}
              {isAuth && (
                <Button variant="outline" size="sm" onClick={() => { window.location.href = '/login/admin'; }}>
                  Sign in
                </Button>
              )}
            </div>
          </div>
        </td>
      </tr>
    );
  }
  if (isEmpty) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-4 py-8 text-center text-gray-500">
          {emptyMessage}
        </td>
      </tr>
    );
  }
  return children;
}
