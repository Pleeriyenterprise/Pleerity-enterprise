import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/client';

const AuthContext = createContext(null);

/** Role-based redirect path: staff -> admin dashboard, client -> app (client) dashboard */
export function getRedirectPathForRole(role) {
  if (role === 'ROLE_OWNER' || role === 'ROLE_ADMIN') return '/admin/dashboard';
  return '/app/dashboard';
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing auth on mount
    const token = localStorage.getItem('auth_token');
    const userData = localStorage.getItem('user');
    
    if (token && userData) {
      try {
        setUser(JSON.parse(userData));
      } catch (e) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password, isAdmin = false) => {
    try {
      const loginMethod = isAdmin ? authAPI.adminLogin : authAPI.login;
      const endpoint = isAdmin ? '/api/auth/admin/login' : '/api/auth/login';
      const response = await loginMethod({ email, password });
      const { access_token, user: userData } = response.data;
      // Only store token/user on success; 403 (wrong portal) is not stored
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('user', JSON.stringify(userData));
      setUser(userData);

      if (process.env.NODE_ENV === 'development') {
        const role = userData?.role || '(none)';
        const redirectPath = getRedirectPathForRole(role);
        console.log('[Auth dev] portal=', isAdmin ? 'staff' : 'client', 'endpoint=', endpoint, 'role=', role, 'redirect=', redirectPath);
      }

      return { success: true, user: userData };
    } catch (error) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || 'Login failed';
      return {
        success: false,
        error: detail,
        status,
      };
    }
  };

  // Allow external components to set auth state (e.g., after password setup)
  const loginWithToken = (accessToken, userData) => {
    localStorage.setItem('auth_token', accessToken);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
    window.location.href = '/';
  };

  const isAdmin = () => user?.role === 'ROLE_ADMIN';
  const isOwner = () => user?.role === 'ROLE_OWNER';
  const isStaff = () => user?.role === 'ROLE_OWNER' || user?.role === 'ROLE_ADMIN';
  const isClient = () => user?.role === 'ROLE_CLIENT' || user?.role === 'ROLE_CLIENT_ADMIN';

  return (
    <AuthContext.Provider value={{ user, loading, login, loginWithToken, logout, isAdmin, isOwner, isStaff, isClient }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
