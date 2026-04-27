import React from 'react';
import { ProtectedRoute } from '../utils/ProtectedRoute';
import ClientPortalLayout from './ClientPortalLayout';
import { GuidedEvidenceModalProvider } from '../context/GuidedEvidenceModalContext';

/**
 * Wraps client portal pages with auth and shared layout (nav, CRN, footer).
 * Use for every route under /today, /dashboard, /properties, etc.
 */
export default function ClientPortal({ children, crn }) {
  return (
    <ProtectedRoute>
      <GuidedEvidenceModalProvider>
        <ClientPortalLayout crn={crn}>
          {children}
        </ClientPortalLayout>
      </GuidedEvidenceModalProvider>
    </ProtectedRoute>
  );
}
