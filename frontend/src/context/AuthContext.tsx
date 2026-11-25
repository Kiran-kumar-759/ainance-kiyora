import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi } from '../services/authApi';
import { AuthResponse, User, UserPreferences } from '../types/auth';

interface AuthContextType {
  user: User | null;
  preferences: UserPreferences | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (fullName: string, email: string, password: string) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updatePreferences: (pref: Partial<UserPreferences>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authApi.getCsrf();
      const me = await authApi.getMe();
      setUser(me);
      try {
        const prefs = await authApi.getPreferences();
        setPreferences(prefs);
      } catch {
        // Fallback default
      }
    } catch {
      setUser(null);
      setPreferences(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  useEffect(() => {
    const handleSessionExpired = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      setUser(null);
      setPreferences(null);
      setError(detail || 'Your session has expired. Please sign in again.');
    };
    window.addEventListener('pfm:session-expired', handleSessionExpired);
    return () => {
      window.removeEventListener('pfm:session-expired', handleSessionExpired);
    };
  }, []);

  const login = async (email: string, password: string): Promise<void> => {
    setError(null);
    const res = await authApi.login(email, password);
    setUser(res.user);
    try {
      const prefs = await authApi.getPreferences();
      setPreferences(prefs);
    } catch {
      // Ignored
    }
  };

  const register = async (
    fullName: string,
    email: string,
    password: string
  ): Promise<AuthResponse> => {
    setError(null);
    return await authApi.register(fullName, email, password);
  };

  const logout = async (): Promise<void> => {
    try {
      await authApi.logout();
    } catch {
      // Clear client state even if network fails
    } finally {
      setUser(null);
      setPreferences(null);
    }
  };

  const refreshUser = async (): Promise<void> => {
    try {
      const me = await authApi.getMe();
      setUser(me);
      const prefs = await authApi.getPreferences();
      setPreferences(prefs);
    } catch {
      setUser(null);
    }
  };

  const handleUpdatePreferences = async (pref: Partial<UserPreferences>): Promise<void> => {
    const updated = await authApi.updatePreferences(pref);
    setPreferences(updated);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        preferences,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        register,
        logout,
        refreshUser,
        updatePreferences: handleUpdatePreferences,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
