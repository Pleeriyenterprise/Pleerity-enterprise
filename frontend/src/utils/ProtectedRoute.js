import React, { useEffect, useRef } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  const hasLoggedBlock = useRef(false);

  // Log admin route guard blocks
  useEffect(() => {
    if (!loading && user && requireAdmin && user.role !== 'ROLE_ADMIN' && !hasLoggedBlock.current) {
      hasLoggedBlock.current = true;
      // Fire and forget - don't block navigation
      apiClient.post('/auth/log-route-guard-block', {
        attempted_path: location.pathname
      }).catch(() => {
        // Silently ignore errors - audit logging shouldn't break the app
      });
    }
  }, [loading, user, requireAdmin, location.pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Admin route protection - block non-admin users
  if (requireAdmin && user.role !== 'ROLE_ADMIN') {
    return <Navigate to="/app/dashboard" replace />;
  }

  // Redirect admin to admin dashboard when accessing client routes
  if (!requireAdmin && user.role === 'ROLE_ADMIN') {
    return <Navigate to="/admin/dashboard" replace />;
  }

  // Tenant routing - redirect to tenant dashboard if not already there
  if (user.role === 'ROLE_TENANT' && !location.pathname.startsWith('/app/tenant')) {
    return <Navigate to="/app/tenant" replace />;
  }

  return children;
};
