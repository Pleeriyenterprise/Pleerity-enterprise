import React, { useEffect, useRef } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const isStaffRole = (role) => role === 'ROLE_OWNER' || role === 'ROLE_ADMIN';

export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  const hasLoggedBlock = useRef(false);
  const pathname = location.pathname;
  const isClientPath = pathname.startsWith('/app');
  const isAdminPath = pathname.startsWith('/admin');

  // Log admin route guard blocks (non-staff trying to access admin)
  useEffect(() => {
    if (!loading && user && requireAdmin && !isStaffRole(user.role) && !hasLoggedBlock.current) {
      hasLoggedBlock.current = true;
      apiClient.post('/auth/log-route-guard-block', {
        attempted_path: pathname
      }).catch(() => {});
    }
  }, [loading, user, requireAdmin, pathname]);

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

  // Staff (OWNER/ADMIN) on client path -> redirect to admin dashboard
  if (isClientPath && isStaffRole(user.role)) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  // Client role on admin path -> redirect to client dashboard
  if (isAdminPath && !isStaffRole(user.role)) {
    return <Navigate to="/app/dashboard" replace />;
  }

  // Admin route protection - allow only OWNER and ADMIN
  if (requireAdmin && !isStaffRole(user.role)) {
    return <Navigate to="/app/dashboard" replace />;
  }

  // Tenant routing - redirect to tenant dashboard if not already there
  if (user.role === 'ROLE_TENANT' && !location.pathname.startsWith('/app/tenant')) {
    return <Navigate to="/app/tenant" replace />;
  }

  return children;
};
