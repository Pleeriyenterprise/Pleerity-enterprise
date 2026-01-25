/**
 * ClearForm Auth Context
 * 
 * Manages authentication state for ClearForm users.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, getAuthToken, setAuthToken } from '../api/clearformApi';

const ClearFormAuthContext = createContext(null);

export const useClearFormAuth = () => {
  const context = useContext(ClearFormAuthContext);
  if (!context) {
    throw new Error('useClearFormAuth must be used within ClearFormAuthProvider');
  }
  return context;
};

export const ClearFormAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          const userData = await authApi.getMe();
          setUser(userData);
        } catch (error) {
          console.error('Auth check failed:', error);
          setAuthToken(null);
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = async (email, password) => {
    const response = await authApi.login(email, password);
    setUser(response.user);
    return response;
  };

  const register = async (data) => {
    const response = await authApi.register(data);
    setUser(response.user);
    return response;
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
  };

  const refreshUser = async () => {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
      return userData;
    } catch (error) {
      console.error('Failed to refresh user:', error);
      throw error;
    }
  };

  return (
    <ClearFormAuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </ClearFormAuthContext.Provider>
  );
};
