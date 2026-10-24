'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, Tenant, TenantMembership, Role } from '@/types/api';
import { api, setApiAuth } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  currentTenant: Tenant | null;
  userTenants: TenantMembership[];
  userRole: Role | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  switchTenant: (tenantId: string) => void;
  refreshProfile: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'reid_auth_token';
const TENANT_KEY = 'reid_active_tenant_id';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [currentTenant, setCurrentTenant] = useState<Tenant | null>(null);
  const [userTenants, setUserTenants] = useState<TenantMembership[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setCurrentTenant(null);
    setUserTenants([]);
    setApiAuth(null, null);
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TENANT_KEY);
    } catch {
      // ignore
    }
  }, []);

  const switchTenant = useCallback(
    (tenantId: string) => {
      const target = userTenants.find((m) => m.tenant_id === tenantId);
      if (target && target.tenant) {
        setCurrentTenant(target.tenant);
        setApiAuth(token, target.tenant_id);
        try {
          localStorage.setItem(TENANT_KEY, target.tenant_id);
        } catch {
          // ignore
        }
      }
    },
    [userTenants, token]
  );

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    try {
      const [userData, memberships] = await Promise.all([
        api.auth.getMe(),
        api.auth.getTenants(),
      ]);
      setUser(userData);
      setUserTenants(memberships);

      const savedTenantId = typeof window !== 'undefined' ? localStorage.getItem(TENANT_KEY) : null;
      const activeMem = memberships.find((m) => m.tenant_id === savedTenantId) || memberships[0];

      if (activeMem && activeMem.tenant) {
        setCurrentTenant(activeMem.tenant);
        setApiAuth(token, activeMem.tenant_id);
      }
    } catch {
      logout();
    }
  }, [token, logout]);

  useEffect(() => {
    const handleAuthExpired = () => {
      logout();
    };
    window.addEventListener('auth:expired', handleAuthExpired);
    return () => window.removeEventListener('auth:expired', handleAuthExpired);
  }, [logout]);

  useEffect(() => {
    const initAuth = async () => {
      try {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        const storedTenantId = localStorage.getItem(TENANT_KEY);

        if (!storedToken) {
          setIsLoading(false);
          return;
        }

        setToken(storedToken);
        setApiAuth(storedToken, storedTenantId);

        const [userData, memberships] = await Promise.all([
          api.auth.getMe(),
          api.auth.getTenants(),
        ]);

        setUser(userData);
        setUserTenants(memberships);

        const activeMem = memberships.find((m) => m.tenant_id === storedTenantId) || memberships[0];
        if (activeMem && activeMem.tenant) {
          setCurrentTenant(activeMem.tenant);
          setApiAuth(storedToken, activeMem.tenant_id);
        }
      } catch {
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, [logout]);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.auth.login(username, password);
      setToken(res.access_token);
      setUser(res.user);
      setUserTenants(res.tenants);

      const defaultTenant = res.tenants[0]?.tenant || null;
      setCurrentTenant(defaultTenant);

      const defaultTenantId = defaultTenant?.id || null;
      setApiAuth(res.access_token, defaultTenantId);

      try {
        localStorage.setItem(TOKEN_KEY, res.access_token);
        if (defaultTenantId) {
          localStorage.setItem(TENANT_KEY, defaultTenantId);
        }
      } catch {
        // ignore
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Authentication failed';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const userRole: Role | null =
    user?.is_superuser
      ? 'OWNER'
      : userTenants.find((m) => m.tenant_id === currentTenant?.id)?.role || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        currentTenant,
        userTenants,
        userRole,
        isAuthenticated: !!token && !!user,
        isLoading,
        error,
        login,
        logout,
        switchTenant,
        refreshProfile,
        clearError: () => setError(null),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
