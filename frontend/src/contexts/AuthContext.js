import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/client';
import { applySessionRuntimeFromUser, clearSessionRuntimeVersions } from '../utils/sessionRuntimeStore';
import { broadcastAuthSync } from '../utils/sessionRuntimeSync';

export const AuthContext = createContext(null);

/** Role-based redirect path: staff -> admin dashboard, tenant -> tenant home, client -> Today (priorities inbox). */
export function getRedirectPathForRole(role) {
  if (['ROLE_OWNER', 'ROLE_ADMIN', 'ROLE_SUPPORT', 'ROLE_CONTENT', 'ROLE_AUDITOR'].includes(role)) return '/admin/dashboard';
  if (role === 'ROLE_TENANT') return '/tenant';
  return '/app/today';
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
        const parsed = JSON.parse(userData);
        setUser(parsed);
        applySessionRuntimeFromUser(parsed);
      } catch (e) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
        clearSessionRuntimeVersions();
      }
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const onStorage = (event) => {
      if (event.key === 'auth_token' && !event.newValue) {
        setUser(null);
        clearSessionRuntimeVersions();
        return;
      }
      if (event.key === 'user' && event.newValue) {
        try {
          const parsed = JSON.parse(event.newValue);
          setUser(parsed);
          applySessionRuntimeFromUser(parsed);
        } catch {
          /* ignore */
        }
      }
      if (event.key === 'auth_token' && event.newValue) {
        const userData = localStorage.getItem('user');
        if (userData) {
          try {
            const parsed = JSON.parse(userData);
            setUser(parsed);
            applySessionRuntimeFromUser(parsed);
          } catch {
            /* ignore */
          }
        }
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
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
      applySessionRuntimeFromUser(userData);
      broadcastAuthSync({ reason: 'login' });

      if (process.env.NODE_ENV === 'development') {
        const role = userData?.role || '(none)';
        const redirectPath = getRedirectPathForRole(role);
        console.log('[Auth dev] portal=', isAdmin ? 'staff' : 'client', 'endpoint=', endpoint, 'role=', role, 'redirect=', redirectPath);
      }

      return { success: true, user: userData };
    } catch (error) {
      const status = error.response?.status;
      const data = error.response?.data;
      const detail = data?.detail;
      let message = 'Login failed';
      if (typeof detail === 'string') {
        message = detail;
      } else if (detail && typeof detail === 'object' && detail.message) {
        message = detail.message;
      } else if (status === 500 && detail) {
        message = typeof detail === 'string' ? detail : (detail.message || 'Server error. Try again.');
      }
      return {
        success: false,
        error: message,
        status,
      };
    }
  };

  // Allow external components to set auth state (e.g., after password setup)
  const loginWithToken = (accessToken, userData) => {
    localStorage.setItem('auth_token', accessToken);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
    applySessionRuntimeFromUser(userData);
    broadcastAuthSync({ reason: 'token_refresh' });
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    clearSessionRuntimeVersions();
    setUser(null);
    broadcastAuthSync({ reason: 'logout' });
    window.location.href = '/';
  };

  const isAdmin = () => user?.role === 'ROLE_ADMIN';
  const isOwner = () => user?.role === 'ROLE_OWNER';
  const isStaff = () => ['ROLE_OWNER', 'ROLE_ADMIN', 'ROLE_SUPPORT', 'ROLE_CONTENT', 'ROLE_AUDITOR'].includes(user?.role);
  const isSupport = () => user?.role === 'ROLE_SUPPORT';
  const isContent = () => user?.role === 'ROLE_CONTENT';
  const isAuditor = () => user?.role === 'ROLE_AUDITOR';
  const isClient = () => user?.role === 'ROLE_CLIENT' || user?.role === 'ROLE_CLIENT_ADMIN';

  return (
    <AuthContext.Provider value={{ user, loading, login, loginWithToken, logout, isAdmin, isOwner, isStaff, isSupport, isContent, isAuditor, isClient }}>
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
