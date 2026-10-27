import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';
import { AuthProvider } from '@/context/AuthContext';
import { CategoryBadge } from '@/components/CategoryBadge';
import { api } from '@/lib/api';
import { TEST_FIXTURE_DASHBOARD_STATS, TEST_FIXTURE_USER, TEST_FIXTURE_MEMBERSHIPS } from './fixtures';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/',
}));

describe('Dashboard Component & Category Precedence', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('reid_auth_token', 'test-token');
    localStorage.setItem('reid_active_tenant_id', 'tnt-test-facility-a');

    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_MEMBERSHIPS);
    vi.spyOn(api.dashboard, 'getStats').mockResolvedValue(TEST_FIXTURE_DASHBOARD_STATS);
    vi.spyOn(api.media, 'fetchBlobUrl').mockResolvedValue('blob:test-image-url');
  });

  it('renders four key metric counters accurately from API response', async () => {
    render(
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('24')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
    });

    expect(screen.getByText('Active Official Workers')).toBeInTheDocument();
    expect(screen.getByText('New Candidate Identities')).toBeInTheDocument();
    expect(screen.getByText('Repeat Passage Events')).toBeInTheDocument();
    expect(screen.getByText('Unknown Observations')).toBeInTheDocument();
  });

  it('renders recent passage events table with correct category labels', async () => {
    render(
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Recent Passage Events')).toBeInTheDocument();
      expect(screen.getAllByText('Repeat Passage').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Official Worker').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('New Person (First Seen)').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Unknown / Ambiguous').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('CategoryBadge strictly enforces repeat-passage yellow precedence', () => {
    const { container: repeatContainer } = render(
      <CategoryBadge identityStatus="OFFICIAL_WORKER" passageStatus="REPEAT_PASSAGE" />
    );
    expect(repeatContainer.querySelector('.badge-repeat')).toBeInTheDocument();
    expect(screen.getByText('Repeat Passage')).toBeInTheDocument();

    const { container: officialContainer } = render(
      <CategoryBadge identityStatus="OFFICIAL_WORKER" passageStatus="FIRST_ENTRY" />
    );
    expect(officialContainer.querySelector('.badge-official')).toBeInTheDocument();
  });

  it('displays API error banner when telemetry request fails', async () => {
    vi.spyOn(api.dashboard, 'getStats').mockRejectedValue(new Error('Network gateway timeout'));

    render(
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Network gateway timeout')).toBeInTheDocument();
    });
  });
});
