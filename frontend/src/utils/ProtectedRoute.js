import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const { user, loading } = useAuth();

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

  if (requireAdmin && user.role !== 'ROLE_ADMIN') {
    return <Navigate to="/app/dashboard" replace />;
  }

  if (!requireAdmin && user.role === 'ROLE_ADMIN') {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return children;
};
