import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, setApiAuth } from '@/lib/api';
import { TEST_FIXTURE_DASHBOARD_STATS } from './fixtures';

describe('Centralized Typed API Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    setApiAuth('test-token-123', 'test-tenant-abc');
  });

  afterEach(() => {
    global.fetch = originalFetch;
    setApiAuth(null, null);
    vi.restoreAllMocks();
  });

  it('attaches Bearer token and X-Tenant-ID headers to outgoing requests', async () => {
    let capturedHeaders: Record<string, string> = {};

    global.fetch = vi.fn().mockImplementation((url, options) => {
      capturedHeaders = options.headers as Record<string, string>;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(TEST_FIXTURE_DASHBOARD_STATS),
      });
    });

    const stats = await api.dashboard.getStats();

    expect(stats.active_workers_present).toBe(12);
    expect(capturedHeaders['Authorization']).toBe('Bearer test-token-123');
    expect(capturedHeaders['X-Tenant-ID']).toBe('test-tenant-abc');
  });

  it('throws ApiError with detail message on non-ok responses', async () => {
    global.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: () => Promise.resolve({ detail: 'Cross-tenant access forbidden' }),
      });
    });

    await expect(api.dashboard.getStats()).rejects.toThrow('Cross-tenant access forbidden');
  });

  it('dispatches auth:expired event when 401 response is received', async () => {
    let expiredEventFired = false;
    const listener = () => {
      expiredEventFired = true;
    };
    window.addEventListener('auth:expired', listener);

    global.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: () => Promise.resolve({ detail: 'Token expired' }),
      });
    });

    try {
      await api.dashboard.getStats();
    } catch {
    }

    expect(expiredEventFired).toBe(true);
    window.removeEventListener('auth:expired', listener);
  });

  it('constructs authenticated media paths correctly', () => {
    expect(api.media.getCropUrl('crop-123')).toBe('/api/v1/media/crops/crop-123');
    expect(api.media.getVideoUrl('vid-456')).toBe('/api/v1/media/videos/vid-456');
    expect(api.media.getJobVideoUrl('job-789')).toBe('/api/v1/media/jobs/job-789/video');
    expect(api.media.getEnrollmentImageUrl('w-1', 'img-2')).toBe(
      '/api/v1/media/workers/w-1/images/img-2'
    );
  });
});
