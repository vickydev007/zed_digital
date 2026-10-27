import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import CamerasPage from '@/app/cameras/page';
import { AuthProvider } from '@/context/AuthContext';
import { api } from '@/lib/api';
import {
  TEST_FIXTURE_USER,
  TEST_FIXTURE_MEMBERSHIPS,
  TEST_FIXTURE_TENANT_A,
} from './fixtures';
import { Camera, CameraRuntimeStatus } from '@/types/api';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/cameras',
}));

describe('Cameras Page & Live Monitor', () => {
  const mockCamera: Camera = {
    id: 'cam-test-12345678',
    tenant_id: TEST_FIXTURE_TENANT_A.id,
    name: 'Gate A North Turnstile',
    location: 'Perimeter Main Gate',
    stream_fps: 25,
    status: 'ONLINE',
    has_encrypted_stream: true,
    created_at: '2026-10-24T00:00:00Z',
    updated_at: '2026-10-24T00:00:00Z',
  };

  const mockRuntimeStatus: CameraRuntimeStatus = {
    camera_id: 'cam-test-12345678',
    tenant_id: TEST_FIXTURE_TENANT_A.id,
    status: 'ONLINE',
    received_fps: 24.8,
    processed_fps: 24.5,
    received_frames: 1540,
    processed_frames: 1532,
    active_tracks: 3,
    reconnect_count: 0,
    uptime_seconds: 62.4,
    consumer_count: 1,
    last_frame_time: '2026-10-24T12:00:00Z',
    last_error: null,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('reid_auth_token', 'test-token');
    localStorage.setItem('reid_active_tenant_id', TEST_FIXTURE_TENANT_A.id);

    vi.spyOn(api.auth, 'getMe').mockResolvedValue(TEST_FIXTURE_USER);
    vi.spyOn(api.auth, 'getTenants').mockResolvedValue(TEST_FIXTURE_MEMBERSHIPS);
    vi.spyOn(api.cameras, 'list').mockResolvedValue([mockCamera]);
    vi.spyOn(api.cameras, 'getStatus').mockResolvedValue(mockRuntimeStatus);
    vi.spyOn(api.cameras, 'getPreviewToken').mockResolvedValue({
      preview_token: 'scoped.preview.token.xyz',
      expires_in_seconds: 120,
      camera_id: 'cam-test-12345678',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
    });
    vi.spyOn(api.cameras, 'getPreviewUrl').mockReturnValue('http://localhost:8001/api/v1/cameras/cam-test-12345678/preview?token=scoped.preview.token.xyz');
    vi.spyOn(api.cameras, 'revokePreviewToken').mockResolvedValue({ status: 'REVOKED', camera_id: 'cam-test-12345678' });
  });


  it('renders registered cameras with status badge and details', async () => {
    render(
      <AuthProvider>
        <CamerasPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Gate A North Turnstile')).toBeInTheDocument();
      expect(screen.getByText('Perimeter Main Gate')).toBeInTheDocument();
      expect(screen.getByText('AES-GCM Encrypted')).toBeInTheDocument();
    });
  });

  it('opens live monitor modal, fetches telemetry and displays live stream', async () => {
    render(
      <AuthProvider>
        <CamerasPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Gate A North Turnstile')).toBeInTheDocument();
    }, { timeout: 3000 });

    const liveBtn = screen.getByRole('button', { name: /Live View/i });
    fireEvent.click(liveBtn);

    await waitFor(() => {
      expect(screen.getByText(/Live Stream & Inference/i)).toBeInTheDocument();
      expect(screen.getByText('Received Rate')).toBeInTheDocument();
      expect(screen.getByText('Inference Rate')).toBeInTheDocument();
      expect(screen.getByText('Confirmed Worker')).toBeInTheDocument();
      expect(screen.getByText('Repeat Passage')).toBeInTheDocument();
    });

    expect(api.cameras.getStatus).toHaveBeenCalledWith('cam-test-12345678');

    const closeBtn = screen.getByTitle('Close Monitor');
    fireEvent.click(closeBtn);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
  });

  it('tests RTSP stream connection and displays reachability feedback', async () => {
    vi.spyOn(api.cameras, 'testConnection').mockResolvedValue({
      success: true,
      fps: 25,
      width: 1920,
      height: 1080,
      message: 'Connection successful (1920x1080 @ 25.0 FPS)',
      error: null,
    });

    render(
      <AuthProvider>
        <CamerasPage />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Register New Camera')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireEvent.click(screen.getByText('Register New Camera'));

    await waitFor(() => {
      expect(screen.getByText('Register CCTV Camera Stream')).toBeInTheDocument();
    });

    const rtspInput = screen.getByLabelText(/RTSP Stream URL/i);
    fireEvent.change(rtspInput, { target: { value: 'rtsp://user:pass@192.168.1.100:554/ch1' } });

    const testBtn = await screen.findByRole('button', { name: /Test Connection/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(screen.getByText('Connection Successful')).toBeInTheDocument();
      expect(screen.getByText(/1920x1080 @ 25.0 FPS/i)).toBeInTheDocument();
    });

    expect(api.cameras.testConnection).toHaveBeenCalledWith({
      rtsp_url: 'rtsp://user:pass@192.168.1.100:554/ch1',
    });
  });
});
