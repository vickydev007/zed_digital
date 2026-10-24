import {
  User,
  Tenant,
  TenantMembership,
  TokenResponse,
  DashboardStatsResponse,
  BenchmarkSummary,
} from '@/types/api';

export const TEST_FIXTURE_USER: User = {
  id: 'usr-test-001',
  email: 'admin@zeddigital.com',
  full_name: 'Test Administrator',
  is_active: true,
  is_superuser: true,
};

export const TEST_FIXTURE_TENANT_A: Tenant = {
  id: 'tnt-test-facility-a',
  name: 'Test Facility Alpha',
  slug: 'facility-alpha',
  is_active: true,
  created_at: '2026-10-24T00:00:00Z',
};

export const TEST_FIXTURE_TENANT_B: Tenant = {
  id: 'tnt-test-facility-b',
  name: 'Test Facility Bravo',
  slug: 'facility-bravo',
  is_active: true,
  created_at: '2026-10-24T00:00:00Z',
};

export const TEST_FIXTURE_MEMBERSHIPS: TenantMembership[] = [
  {
    id: 'mem-001',
    tenant_id: TEST_FIXTURE_TENANT_A.id,
    user_id: TEST_FIXTURE_USER.id,
    role: 'OWNER',
    tenant: TEST_FIXTURE_TENANT_A,
  },
  {
    id: 'mem-002',
    tenant_id: TEST_FIXTURE_TENANT_B.id,
    user_id: TEST_FIXTURE_USER.id,
    role: 'VIEWER',
    tenant: TEST_FIXTURE_TENANT_B,
  },
];

export const TEST_FIXTURE_TOKEN_RESPONSE: TokenResponse = {
  access_token: 'test.jwt.token.xyz',
  token_type: 'bearer',
  expires_in_seconds: 86400,
  user: TEST_FIXTURE_USER,
  tenants: TEST_FIXTURE_MEMBERSHIPS,
};

export const TEST_FIXTURE_DASHBOARD_STATS: DashboardStatsResponse = {
  active_workers_present: 12,
  qualifying_candidates_count: 5,
  repeat_passages_count: 24,
  unknown_observations_count: 8,
  total_passage_events: 49,
  active_cameras_count: 3,
  active_jobs_count: 1,
  category_counts: {
    OFFICIAL_WORKER: 12,
    NEW_PERSON: 5,
    PREVIOUSLY_ENROLLED: 24,
    UNKNOWN: 8,
  },
  recent_events: [
    {
      id: 'evt-001',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
      identity_status: 'OFFICIAL_WORKER',
      passage_status: 'REPEAT_PASSAGE',
      display_category: 'PREVIOUSLY_ENROLLED',
      confidence_score: 0.884,
      event_timestamp: '2026-10-24T10:15:00Z',
      is_reviewed: true,
      created_at: '2026-10-24T10:15:00Z',
    },
    {
      id: 'evt-002',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
      identity_status: 'OFFICIAL_WORKER',
      passage_status: 'FIRST_ENTRY',
      display_category: 'OFFICIAL_WORKER',
      confidence_score: 0.912,
      event_timestamp: '2026-10-24T10:12:00Z',
      is_reviewed: false,
      created_at: '2026-10-24T10:12:00Z',
    },
    {
      id: 'evt-003',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
      identity_status: 'NEW_CANDIDATE',
      passage_status: 'FIRST_ENTRY',
      display_category: 'NEW_PERSON',
      confidence_score: 0.582,
      event_timestamp: '2026-10-24T10:08:00Z',
      is_reviewed: false,
      created_at: '2026-10-24T10:08:00Z',
    },
    {
      id: 'evt-004',
      tenant_id: TEST_FIXTURE_TENANT_A.id,
      identity_status: 'UNKNOWN',
      passage_status: 'FIRST_ENTRY',
      display_category: 'UNKNOWN',
      confidence_score: 0.421,
      event_timestamp: '2026-10-24T10:02:00Z',
      is_reviewed: false,
      created_at: '2026-10-24T10:02:00Z',
    },
  ],
};

export const TEST_FIXTURE_BENCHMARK: BenchmarkSummary = {
  benchmark_id: 'bm-market1501-250id',
  title: 'Market-1501 Open-Set Verification Protocol',
  status: 'VERIFIED',
  empirical_operating_point: {
    score_threshold: 0.7124,
    contrast_margin: 0.05,
    genuine_recall_tar: 0.9448,
    false_accept_rate_far: 0.2023,
    impostor_rejection_rate: 0.7977,
  },
  metrics: {
    roc_auc: 0.9635,
    eer: 0.0882,
    rank1_accuracy: 0.9858,
    rank5_accuracy: 0.9964,
    map: 0.638,
    test_probes_count: 2500,
    enrolled_identities_count: 250,
  },
  latency: {
    mean_inference_ms: 4.82,
    p95_inference_ms: 5.6,
    fps: 207,
  },
  report_markdown: 'Verified benchmark report content.',
};
