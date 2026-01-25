/**
 * ClearForm Protected Route
 * 
 * Wrapper for routes requiring ClearForm authentication.
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useClearFormAuth } from './contexts/ClearFormAuthContext';
import { Loader2 } from 'lucide-react';

const ClearFormProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useClearFormAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/clearform/login" state={{ from: location }} replace />;
  }

  return children;
};

export default ClearFormProtectedRoute;
