import React from 'react';
import { ProtectedRoute } from '../utils/ProtectedRoute';
import ClientPortalLayout from './ClientPortalLayout';

/**
 * Wraps client portal pages with auth and shared layout (nav, CRN, footer).
 * Use for every route under /dashboard, /properties, etc.
 */
export default function ClientPortal({ children, crn }) {
  return (
    <ProtectedRoute>
      <ClientPortalLayout crn={crn}>
        {children}
      </ClientPortalLayout>
    </ProtectedRoute>
  );
}
