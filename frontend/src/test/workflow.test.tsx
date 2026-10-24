import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideosPage from '@/app/videos/page';
import CandidatesPage from '@/app/candidates/page';
import { AuthProvider } from '@/context/AuthContext';
import { api } from '@/lib/api';
import {
  TEST_FIXTURE_USER,
  TEST_FIXTURE_MEMBERSHIPS,
  TEST_FIXTURE_TENANT_A,
} from './fixtures';
import { CandidateIdentity } from '@/types/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/videos',
}));

describe('Workflows & Security Boundary Checks', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('reid_auth_token', 'test-token');
    localStorage.setItem('reid_active_tenant_id', 'tnt-test-facility-a');

    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_MEMBERSHIPS);
    vi.spyOn(api.videos, 'list').mockResolvedValue([]);
    vi.spyOn(api.jobs, 'list').mockResolvedValue([]);
    vi.spyOn(api.cameras, 'list').mockResolvedValue([]);
    vi.spyOn(api.candidates, 'list').mockResolvedValue([]);
    vi.spyOn(api.workers, 'list').mockResolvedValue([]);
    vi.spyOn(api.passage, 'getEvents').mockResolvedValue([]);
  });

  it('rejects video files exceeding 150MB limit before network upload', async () => {
    render(
      <AuthProvider>
        <VideosPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Upload CCTV Video')).toBeInTheDocument();
    });

    const fileInput = screen.getByLabelText(/Select CCTV Video File/i);
    const oversizedFile = new File(['x'.repeat(100)], 'huge_cctv.mp4', { type: 'video/mp4' });
    Object.defineProperty(oversizedFile, 'size', { value: 160 * 1024 * 1024 });

    fireEvent.change(fileInput, { target: { files: [oversizedFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/exceeds the 150 MB limit/i)).toBeInTheDocument();
    });
  });

  it('rejects unsupported file formats before submission', async () => {
    render(
      <AuthProvider>
        <VideosPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Upload CCTV Video')).toBeInTheDocument();
    });

    const fileInput = screen.getByLabelText(/Select CCTV Video File/i);
    const textFile = new File(['test script'], 'malicious.exe', { type: 'application/x-msdownload' });

    fireEvent.change(fileInput, { target: { files: [textFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/Invalid video format/i)).toBeInTheDocument();
    });
  });

  it('submits candidate review decision and updates review status', async () => {
    const testCandidate: CandidateIdentity = {
      id: 'cand-001',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
      candidate_code: 'CAND-2026-0001',
      first_seen_at: '2026-10-24T09:00:00Z',
      last_seen_at: '2026-10-24T09:30:00Z',
      review_status: 'PENDING_REVIEW',
      created_at: '2026-10-24T09:00:00Z',
      updated_at: '2026-10-24T09:00:00Z',
    };

    vi.spyOn(api.candidates, 'list').mockResolvedValue([testCandidate]);
    const reviewSpy = vi.spyOn(api.candidates, 'review').mockResolvedValue({
      ...testCandidate,
      review_status: 'PROMOTED',
      notes: 'Verified contractor',
    });

    render(
      <AuthProvider>
        <CandidatesPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('CAND-2026-0001')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('CAND-2026-0001'));

    await waitFor(() => {
      expect(screen.getByText('Approve & Promote')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Approve & Promote'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Promote Candidate to Official Staff')).toBeInTheDocument();
    });

    const notesInput = screen.getByPlaceholderText(/Enter audit rationale/i);
    fireEvent.change(notesInput, { target: { value: 'Verified contractor' } });

    fireEvent.click(screen.getByText('Confirm PROMOTED'));

    await waitFor(() => {
      expect(reviewSpy).toHaveBeenCalledWith('cand-001', {
        review_status: 'PROMOTED',
        notes: 'Verified contractor',
        approved_worker_id: undefined,
      });
    });
  });
});
