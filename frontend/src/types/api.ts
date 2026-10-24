export type Role = 'OWNER' | 'ADMIN' | 'OPERATOR' | 'VIEWER';

export type DisplayCategory = 'OFFICIAL_WORKER' | 'NEW_PERSON' | 'PREVIOUSLY_ENROLLED' | 'UNKNOWN';

export type IdentityStatus = 'OFFICIAL_WORKER' | 'NEW_CANDIDATE' | 'UNKNOWN';

export type PassageStatus = 'FIRST_ENTRY' | 'PASSAGE_IN_PROGRESS' | 'ALREADY_PASSED' | 'REPEAT_PASSAGE';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface TenantMembership {
  id: string;
  tenant_id: string;
  user_id: string;
  role: Role;
  tenant?: Tenant;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: User;
  tenants: TenantMembership[];
}

export interface DashboardStatsResponse {
  active_workers_present: number;
  qualifying_candidates_count: number;
  repeat_passages_count: number;
  unknown_observations_count: number;
  total_passage_events: number;
  active_cameras_count: number;
  active_jobs_count: number;
  category_counts: Record<string, number>;
  recent_events: PassageEvent[];
}

export interface PassageEvent {
  id: string;
  tenant_id: string;
  camera_id?: string | null;
  video_job_id?: string | null;
  track_id?: string | null;
  worker_id?: string | null;
  candidate_identity_id?: string | null;
  identity_status: IdentityStatus;
  passage_status: PassageStatus;
  display_category: DisplayCategory;
  confidence_score: number;
  crop_path?: string | null;
  event_timestamp: string;
  is_reviewed: boolean;
  created_at: string;
}

export interface PresenceSession {
  id: string;
  tenant_id: string;
  worker_id?: string | null;
  candidate_identity_id?: string | null;
  identity_status: IdentityStatus;
  session_start: string;
  session_end?: string | null;
  is_currently_present: boolean;
  last_seen_camera_id?: string | null;
  passage_count: number;
  created_at: string;
  updated_at: string;
}

export interface Camera {
  id: string;
  tenant_id: string;
  name: string;
  location?: string | null;
  is_active: boolean;
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  stream_fps: number;
  last_heartbeat?: string | null;
  has_encrypted_stream: boolean;
  created_at: string;
  updated_at: string;
}

export interface CameraCreateRequest {
  name: string;
  location?: string;
  rtsp_url: string;
  stream_fps?: number;
}

export interface CameraUpdateRequest {
  name?: string;
  location?: string;
  rtsp_url?: string;
  is_active?: boolean;
  stream_fps?: number;
}

export interface VideoAsset {
  id: string;
  tenant_id: string;
  camera_id?: string | null;
  original_filename: string;
  file_path: string;
  file_size_bytes: number;
  duration_seconds: number;
  fps: number;
  frame_count: number;
  resolution_width: number;
  resolution_height: number;
  uploaded_by?: string | null;
  created_at: string;
}

export interface VideoAnalyzeRequest {
  score_threshold?: number;
  contrast_margin?: number;
  downsample_fps?: number;
  detector_confidence?: number;
  save_annotated_video?: boolean;
}

export interface Job {
  id: string;
  tenant_id: string;
  video_asset_id?: string | null;
  camera_id?: string | null;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_percent: number;
  processed_frames: number;
  total_frames: number;
  output_video_path?: string | null;
  report_json_path?: string | null;
  error_details?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface JobProgress {
  id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_percent: number;
  completed_at?: string | null;
  error_details?: string | null;
}

export interface EnrollmentImage {
  id: string;
  worker_id: string;
  image_path: string;
  blur_score: number;
  quality_score: number;
  is_primary: boolean;
  created_at: string;
}

export interface Worker {
  id: string;
  tenant_id: string;
  staff_code: string;
  full_name: string;
  batch?: string | null;
  department?: string | null;
  uniform_category?: string | null;
  enrollment_status: 'ENROLLED' | 'PENDING' | 'REVOKED';
  is_active: boolean;
  created_at: string;
  updated_at: string;
  images: EnrollmentImage[];
}

export interface WorkerCreateRequest {
  staff_code: string;
  full_name: string;
  batch?: string;
  department?: string;
  uniform_category?: string;
}

export interface WorkerUpdateRequest {
  full_name?: string;
  batch?: string;
  department?: string;
  uniform_category?: string;
  enrollment_status?: string;
  is_active?: boolean;
}

export interface WorkerEnrollResponse {
  worker_id: string;
  image_id: string;
  embedding_id: string;
  blur_score: number;
  quality_score: number;
  is_accepted: boolean;
  quality_passed: boolean;
}

export interface CandidateIdentity {
  id: string;
  tenant_id: string;
  candidate_code: string;
  first_seen_at: string;
  last_seen_at: string;
  review_status: 'PENDING_REVIEW' | 'PROMOTED' | 'REJECTED';
  approved_worker_id?: string | null;
  notes?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateReviewRequest {
  review_status: 'PROMOTED' | 'REJECTED' | 'PENDING_REVIEW';
  notes?: string;
  approved_worker_id?: string;
}

export interface EvaluationResultItem {
  metric_name: string;
  metric_value: number;
  confidence_interval_low?: number | null;
  confidence_interval_high?: number | null;
  details_json?: Record<string, unknown> | null;
}

export interface ExperimentRun {
  id: string;
  tenant_id?: string | null;
  experiment_name: string;
  model_name: string;
  model_version: string;
  dataset_split: string;
  score_threshold: number;
  contrast_margin: number;
  evaluation_protocol: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  results: EvaluationResultItem[];
}

export interface BenchmarkSummary {
  benchmark_id: string;
  title: string;
  status: string;
  empirical_operating_point: {
    score_threshold: number;
    contrast_margin: number;
    genuine_recall_tar: number;
    false_accept_rate_far: number;
    impostor_rejection_rate: number;
  };
  metrics: {
    roc_auc: number;
    eer: number;
    rank1_accuracy: number;
    rank5_accuracy: number;
    map: number;
    test_probes_count: number;
    enrolled_identities_count: number;
  };
  latency: {
    mean_inference_ms: number;
    p95_inference_ms: number;
    fps: number;
  };
  report_markdown: string;
}
