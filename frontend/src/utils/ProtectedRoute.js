import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

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

  // Admin routing
  if (requireAdmin && user.role !== 'ROLE_ADMIN') {
    return <Navigate to="/app/dashboard" replace />;
  }

  if (!requireAdmin && user.role === 'ROLE_ADMIN') {
    return <Navigate to="/admin/dashboard" replace />;
  }

  // Tenant routing - redirect to tenant dashboard if not already there
  if (user.role === 'ROLE_TENANT' && !location.pathname.startsWith('/app/tenant')) {
    return <Navigate to="/app/tenant" replace />;
  }

  // Don't allow non-tenants to access tenant dashboard (except for development)
  // Commented out for flexibility: landlords might want to preview tenant view
  // if (user.role !== 'ROLE_TENANT' && location.pathname === '/app/tenant') {
  //   return <Navigate to="/app/dashboard" replace />;
  // }

  return children;
};
