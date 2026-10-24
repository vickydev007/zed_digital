import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { TEST_FIXTURE_TOKEN_RESPONSE, TEST_FIXTURE_USER } from './fixtures';
import { api, getApiAuth } from '@/lib/api';

function TestConsumer() {
  const { user, currentTenant, userRole, isAuthenticated, login, logout, switchTenant } = useAuth();
  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'LOGGED_IN' : 'LOGGED_OUT'}</div>
      <div data-testid="user-email">{user?.email || 'none'}</div>
      <div data-testid="active-tenant">{currentTenant?.name || 'none'}</div>
      <div data-testid="active-role">{userRole || 'none'}</div>
      <button onClick={() => login('admin@zeddigital.com', 'Admin@123456')}>Login</button>
      <button onClick={() => switchTenant('tnt-test-facility-b')}>Switch Facility</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

describe('Authentication & Tenant Context', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('initializes in logged-out state when no token in localStorage', async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_OUT');
    });
  });

  it('successfully authenticates and sets tenant context on login', async () => {
    vi.spyOn(api.auth, 'login').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE);
    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE.tenants);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Login'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_IN');
      expect(screen.getByTestId('user-email').textContent).toBe('admin@zeddigital.com');
      expect(screen.getByTestId('active-tenant').textContent).toBe('Test Facility Alpha');
      expect(screen.getByTestId('active-role').textContent).toBe('OWNER');
    });

    const { token, tenantId } = getApiAuth();
    expect(token).toBe('test.jwt.token.xyz');
    expect(tenantId).toBe('tnt-test-facility-a');
  });

  it('updates active tenant and role when user switches facility', async () => {
    vi.spyOn(api.auth, 'login').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE);
    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE.tenants);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Login'));

    await waitFor(() => {
      expect(screen.getByTestId('active-tenant').textContent).toBe('Test Facility Alpha');
    });

    fireEvent.click(screen.getByText('Switch Facility'));

    await waitFor(() => {
      expect(screen.getByTestId('active-tenant').textContent).toBe('Test Facility Bravo');
    });

    const { tenantId } = getApiAuth();
    expect(tenantId).toBe('tnt-test-facility-b');
  });

  it('clears credentials from state and storage on logout', async () => {
    vi.spyOn(api.auth, 'login').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE);
    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_TOKEN_RESPONSE.tenants);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    fireEvent.click(screen.getByText('Login'));
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_IN');
    });

    fireEvent.click(screen.getByText('Logout'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_OUT');
      expect(screen.getByTestId('active-tenant').textContent).toBe('none');
    });

    const { token, tenantId } = getApiAuth();
    expect(token).toBeNull();
    expect(tenantId).toBeNull();
  });
});
