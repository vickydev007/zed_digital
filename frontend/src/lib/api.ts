import {
  TokenResponse,
  User,
  TenantMembership,
  Tenant,
  DashboardStatsResponse,
  PassageEvent,
  PresenceSession,
  Camera,
  CameraCreateRequest,
  CameraUpdateRequest,
  CameraRuntimeStatus,
  CameraTestConnectionRequest,
  CameraTestConnectionResponse,
  CameraPreviewTokenResponse,
  CameraLatencyMetricsResponse,
  ClientLatencyReportRequest,
  VideoAsset,
  VideoAnalyzeRequest,
  Job,
  JobProgress,
  Worker,
  WorkerCreateRequest,
  WorkerUpdateRequest,
  WorkerEnrollResponse,
  CandidateIdentity,
  CandidateReviewRequest,
  BenchmarkSummary,
  ExperimentRun,
} from '@/types/api';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

let activeToken: string | null = null;
let activeTenantId: string | null = null;

export function setApiAuth(token: string | null, tenantId: string | null) {
  activeToken = token;
  activeTenantId = tenantId;
}

export function getApiAuth() {
  return { token: activeToken, tenantId: activeTenantId };
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  customHeaders: Record<string, string> = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    ...customHeaders,
  };

  if (activeToken) {
    headers['Authorization'] = `Bearer ${activeToken}`;
  }
  if (activeTenantId) {
    headers['X-Tenant-ID'] = activeTenantId;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...(options.headers as Record<string, string>),
    },
  });

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    let data: unknown = null;
    try {
      data = await response.json();
      if (data && typeof data === 'object' && 'detail' in data) {
        errorDetail = String((data as { detail: unknown }).detail);
      }
    } catch {
    }
    throw new ApiError(errorDetail || `HTTP error ${response.status}`, response.status, data);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  auth: {
    login: async (username: string, password: string): Promise<TokenResponse> => {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!res.ok) {
        let errMessage = 'Invalid credentials';
        try {
          const errData = await res.json();
          if (errData?.detail) errMessage = errData.detail;
        } catch {
        }
        throw new ApiError(errMessage, res.status);
      }

      return res.json();
    },

    getMe: (): Promise<User> => {
      return request<User>('/api/v1/auth/me');
    },

    getTenants: (): Promise<TenantMembership[]> => {
      return request<TenantMembership[]>('/api/v1/auth/tenants');
    },

    createTenant: (name: string, slug: string): Promise<Tenant> => {
      return request<Tenant>('/api/v1/auth/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, slug }),
      });
    },
  },

  dashboard: {
    getStats: (): Promise<DashboardStatsResponse> => {
      return request<DashboardStatsResponse>('/api/v1/dashboard/stats');
    },
  },

  passage: {
    getEvents: (params?: {
      skip?: number;
      limit?: number;
      identity_status?: string;
      passage_status?: string;
      display_category?: string;
      worker_id?: string;
      camera_id?: string;
      video_job_id?: string;
    }): Promise<PassageEvent[]> => {
      const query = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== '') {
            query.append(k, String(v));
          }
        });
      }
      return request<PassageEvent[]>(`/api/v1/passage/events?${query.toString()}`);
    },

    getEvent: (eventId: string): Promise<PassageEvent> => {
      return request<PassageEvent>(`/api/v1/passage/events/${eventId}`);
    },

    reviewEvent: (eventId: string, isReviewed = true): Promise<PassageEvent> => {
      return request<PassageEvent>(`/api/v1/passage/events/${eventId}/review?is_reviewed=${isReviewed}`, {
        method: 'POST',
      });
    },

    getPresence: (isPresent?: boolean): Promise<PresenceSession[]> => {
      const query = isPresent !== undefined ? `?is_present=${isPresent}` : '';
      return request<PresenceSession[]>(`/api/v1/passage/presence${query}`);
    },
  },

  cameras: {
    list: (params?: { skip?: number; limit?: number; is_active?: boolean }): Promise<Camera[]> => {
      const query = new URLSearchParams();
      if (params) {
        if (params.skip !== undefined) query.append('skip', String(params.skip));
        if (params.limit !== undefined) query.append('limit', String(params.limit));
        if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      }
      return request<Camera[]>(`/api/v1/cameras?${query.toString()}`);
    },

    get: (cameraId: string): Promise<Camera> => {
      return request<Camera>(`/api/v1/cameras/${cameraId}`);
    },

    create: (data: CameraCreateRequest): Promise<Camera> => {
      return request<Camera>('/api/v1/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },

    update: (cameraId: string, data: CameraUpdateRequest): Promise<Camera> => {
      return request<Camera>(`/api/v1/cameras/${cameraId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },

    delete: (cameraId: string): Promise<void> => {
      return request<void>(`/api/v1/cameras/${cameraId}`, {
        method: 'DELETE',
      });
    },

    start: (cameraId: string): Promise<{ id: string; name: string; status: string; action_performed: string }> => {
      return request(`/api/v1/cameras/${cameraId}/start`, { method: 'POST' });
    },

    stop: (cameraId: string): Promise<{ id: string; name: string; status: string; action_performed: string }> => {
      return request(`/api/v1/cameras/${cameraId}/stop`, { method: 'POST' });
    },

    getStatus: (cameraId: string): Promise<CameraRuntimeStatus> => {
      return request<CameraRuntimeStatus>(`/api/v1/cameras/${cameraId}/status`);
    },

    testConnection: (data: CameraTestConnectionRequest): Promise<CameraTestConnectionResponse> => {
      return request<CameraTestConnectionResponse>('/api/v1/cameras/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },

    getPreviewToken: (cameraId: string): Promise<CameraPreviewTokenResponse> => {
      return request<CameraPreviewTokenResponse>(`/api/v1/cameras/${cameraId}/preview-token`, {
        method: 'POST',
      });
    },

    revokePreviewToken: (cameraId: string, token: string): Promise<{ status: string; camera_id: string }> => {
      return request<{ status: string; camera_id: string }>(`/api/v1/cameras/${cameraId}/revoke-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
    },

    getPreviewUrl: (cameraId: string, scopedToken?: string): string => {
      const auth = getApiAuth();
      const params = new URLSearchParams();
      const tokenToUse = scopedToken || auth.token;
      if (tokenToUse) params.append('token', tokenToUse);
      if (auth.tenantId) params.append('tenant_id', auth.tenantId);
      const q = params.toString() ? `?${params.toString()}` : '';
      return `${API_BASE_URL}/api/v1/cameras/${cameraId}/preview${q}`;
    },

    getLatencyMetrics: (cameraId: string): Promise<CameraLatencyMetricsResponse> => {
      return request<CameraLatencyMetricsResponse>(`/api/v1/cameras/${cameraId}/latency`);
    },

    reportClientLatency: (cameraId: string, data: ClientLatencyReportRequest): Promise<{ success: boolean; camera_id: string }> => {
      return request<{ success: boolean; camera_id: string }>(`/api/v1/cameras/${cameraId}/client-latency`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },
  },


  videos: {
    upload: async (file: File, cameraId?: string): Promise<VideoAsset> => {
      const formData = new FormData();
      formData.append('file', file);
      const query = cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : '';

      return request<VideoAsset>(`/api/v1/videos/upload${query}`, {
        method: 'POST',
        body: formData,
      });
    },

    list: (skip = 0, limit = 50): Promise<VideoAsset[]> => {
      return request<VideoAsset[]>(`/api/v1/videos?skip=${skip}&limit=${limit}`);
    },

    get: (videoId: string): Promise<VideoAsset> => {
      return request<VideoAsset>(`/api/v1/videos/${videoId}`);
    },

    analyze: (videoId: string, options?: VideoAnalyzeRequest): Promise<Job> => {
      return request<Job>(`/api/v1/videos/${videoId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options || {}),
      });
    },
  },

  jobs: {
    list: (params?: { skip?: number; limit?: number; status?: string }): Promise<Job[]> => {
      const query = new URLSearchParams();
      if (params?.skip !== undefined) query.append('skip', String(params.skip));
      if (params?.limit !== undefined) query.append('limit', String(params.limit));
      if (params?.status) query.append('status', params.status);
      return request<Job[]>(`/api/v1/jobs?${query.toString()}`);
    },

    get: (jobId: string): Promise<Job> => {
      return request<Job>(`/api/v1/jobs/${jobId}`);
    },

    getProgress: (jobId: string): Promise<JobProgress> => {
      return request<JobProgress>(`/api/v1/jobs/${jobId}/progress`);
    },

    cancel: (jobId: string): Promise<Job> => {
      return request<Job>(`/api/v1/jobs/${jobId}/cancel`, { method: 'POST' });
    },
  },

  workers: {
    list: (params?: {
      skip?: number;
      limit?: number;
      search?: string;
      department?: string;
      is_active?: boolean;
    }): Promise<Worker[]> => {
      const query = new URLSearchParams();
      if (params) {
        if (params.skip !== undefined) query.append('skip', String(params.skip));
        if (params.limit !== undefined) query.append('limit', String(params.limit));
        if (params.search) query.append('search', params.search);
        if (params.department) query.append('department', params.department);
        if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      }
      return request<Worker[]>(`/api/v1/workers?${query.toString()}`);
    },

    get: (workerId: string): Promise<Worker> => {
      return request<Worker>(`/api/v1/workers/${workerId}`);
    },

    create: (data: WorkerCreateRequest): Promise<Worker> => {
      return request<Worker>('/api/v1/workers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },

    update: (workerId: string, data: WorkerUpdateRequest): Promise<Worker> => {
      return request<Worker>(`/api/v1/workers/${workerId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },

    deactivate: (workerId: string): Promise<Worker> => {
      return request<Worker>(`/api/v1/workers/${workerId}/deactivate`, { method: 'POST' });
    },

    enrollPhoto: async (workerId: string, file: File, isPrimary = true): Promise<WorkerEnrollResponse> => {
      const formData = new FormData();
      formData.append('file', file);
      return request<WorkerEnrollResponse>(`/api/v1/workers/${workerId}/enroll?is_primary=${isPrimary}`, {
        method: 'POST',
        body: formData,
      });
    },
  },

  candidates: {
    list: (params?: { skip?: number; limit?: number; review_status?: string }): Promise<CandidateIdentity[]> => {
      const query = new URLSearchParams();
      if (params?.skip !== undefined) query.append('skip', String(params.skip));
      if (params?.limit !== undefined) query.append('limit', String(params.limit));
      if (params?.review_status) query.append('review_status', params.review_status);
      return request<CandidateIdentity[]>(`/api/v1/candidates?${query.toString()}`);
    },

    get: (candidateId: string): Promise<CandidateIdentity> => {
      return request<CandidateIdentity>(`/api/v1/candidates/${candidateId}`);
    },

    review: (candidateId: string, data: CandidateReviewRequest): Promise<CandidateIdentity> => {
      return request<CandidateIdentity>(`/api/v1/candidates/${candidateId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    },
  },

  evaluation: {
    getBenchmarks: (): Promise<BenchmarkSummary> => {
      return request<BenchmarkSummary>('/api/v1/evaluation/benchmarks');
    },

    getExperiments: (): Promise<ExperimentRun[]> => {
      return request<ExperimentRun[]>('/api/v1/evaluation/experiments');
    },

    seedExperiment: (): Promise<ExperimentRun> => {
      return request<ExperimentRun>('/api/v1/evaluation/experiments/seed', { method: 'POST' });
    },
  },

  media: {
    fetchBlobUrl: async (endpoint: string): Promise<string> => {
      const headers: Record<string, string> = {};
      if (activeToken) headers['Authorization'] = `Bearer ${activeToken}`;
      if (activeTenantId) headers['X-Tenant-ID'] = activeTenantId;

      const res = await fetch(`${API_BASE_URL}${endpoint}`, { headers });
      if (!res.ok) {
        throw new ApiError(`Failed to fetch media: ${res.statusText}`, res.status);
      }
      const blob = await res.blob();
      return URL.createObjectURL(blob);
    },

    getCropUrl: (cropId: string) => `/api/v1/media/crops/${cropId}`,
    getVideoUrl: (videoId: string) => `/api/v1/media/videos/${videoId}`,
    getJobVideoUrl: (jobId: string) => `/api/v1/media/jobs/${jobId}/video`,
    getEnrollmentImageUrl: (workerId: string, imageId: string) =>
      `/api/v1/media/workers/${workerId}/images/${imageId}`,
  },
};
