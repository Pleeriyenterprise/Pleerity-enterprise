/**
 * ClearForm App Layout
 * 
 * Wraps all ClearForm routes with the auth provider.
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ClearFormAuthProvider } from './contexts/ClearFormAuthContext';
import ClearFormProtectedRoute from './ClearFormProtectedRoute';
import {
  ClearFormLandingPage,
  ClearFormAuthPage,
  ClearFormDashboard,
  ClearFormCreatePage,
  ClearFormDocumentPage,
} from './pages';

const ClearFormApp = () => {
  return (
    <ClearFormAuthProvider>
      <Routes>
        {/* Public Routes */}
        <Route index element={<ClearFormLandingPage />} />
        <Route path="login" element={<ClearFormAuthPage />} />
        <Route path="register" element={<ClearFormAuthPage />} />
        
        {/* Protected Routes */}
        <Route
          path="dashboard"
          element={
            <ClearFormProtectedRoute>
              <ClearFormDashboard />
            </ClearFormProtectedRoute>
          }
        />
        <Route
          path="create"
          element={
            <ClearFormProtectedRoute>
              <ClearFormCreatePage />
            </ClearFormProtectedRoute>
          }
        />
        <Route
          path="document/:documentId"
          element={
            <ClearFormProtectedRoute>
              <ClearFormDocumentPage />
            </ClearFormProtectedRoute>
          }
        />
        <Route
          path="vault"
          element={
            <ClearFormProtectedRoute>
              <ClearFormDashboard />
            </ClearFormProtectedRoute>
          }
        />
        <Route
          path="credits"
          element={
            <ClearFormProtectedRoute>
              <ClearFormDashboard />
            </ClearFormProtectedRoute>
          }
        />
        
        {/* Fallback */}
        <Route path="*" element={<Navigate to="/clearform" replace />} />
      </Routes>
    </ClearFormAuthProvider>
  );
};

export default ClearFormApp;
