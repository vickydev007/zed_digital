'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/AppShell';
import { CategoryBadge } from '@/components/CategoryBadge';
import { MediaImage } from '@/components/MediaImage';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { DashboardStatsResponse } from '@/types/api';
import {
  Users,
  UserPlus,
  RefreshCw,
  AlertTriangle,
  Video,
  Activity,
  Layers,
  Info,
  Calendar,
  AlertCircle,
} from 'lucide-react';

export default function DashboardPage() {
  const { currentTenant } = useAuth();
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<string>('all');

  const fetchStats = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = await api.dashboard.getStats();
      setStats(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch operations telemetry';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats, currentTenant?.id]);

  return (
    <AppShell
      title="Operations Dashboard"
      subtitle="Real-time CCTV telemetry, presence tracking, and decoupled open-set re-identification."
      onRefresh={() => fetchStats(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Calendar size={18} style={{ color: 'var(--text-dim)' }} />
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>
              Telemetry Window:
            </span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="form-control"
              style={{ width: 'auto', padding: '6px 12px', fontSize: '13px' }}
              aria-label="Filter telemetry by time range"
            >
              <option value="all">Facility Inception to Present</option>
              <option value="24h">Past 24 Hours</option>
              <option value="today">Today (Shift 1 & 2)</option>
              <option value="1h">Last 60 Minutes (Live)</option>
            </select>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--text-dim)',
            }}
          >
            <Info size={14} />
            <span>Identity status is decoupled from passage status</span>
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: '16px 20px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--color-unknown-bg)',
              border: '1px solid var(--color-unknown-border)',
              color: 'var(--color-unknown)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
            role="alert"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <AlertCircle size={20} />
              <div>
                <strong style={{ display: 'block', fontSize: '14px' }}>Telemetry Error</strong>
                <span style={{ fontSize: '13px' }}>{error}</span>
              </div>
            </div>
            <button
              onClick={() => fetchStats(true)}
              className="btn btn-danger"
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              Retry Connection
            </button>
          </div>
        )}

        <section aria-label="Key Re-Identification Metrics">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '20px',
            }}
          >
            <div
              className="card card-hover"
              style={{
                borderTop: '3px solid var(--color-official)',
                background: 'linear-gradient(180deg, rgba(16, 185, 129, 0.05) 0%, var(--bg-card) 60%)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.8px',
                      color: 'var(--color-official)',
                    }}
                  >
                    Active Official Workers
                  </span>
                  <div style={{ fontSize: '36px', fontWeight: 800, margin: '8px 0 4px', color: '#fff' }}>
                    {loading ? '—' : stats?.active_workers_present ?? 0}
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Unique enrolled staff currently inside facility
                  </p>
                </div>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    backgroundColor: 'var(--color-official-bg)',
                    color: 'var(--color-official)',
                  }}
                >
                  <Users size={24} />
                </div>
              </div>
            </div>

            <div
              className="card card-hover"
              style={{
                borderTop: '3px solid var(--color-newperson)',
                background: 'linear-gradient(180deg, rgba(6, 182, 212, 0.05) 0%, var(--bg-card) 60%)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.8px',
                      color: 'var(--color-newperson)',
                    }}
                  >
                    New Candidate Identities
                  </span>
                  <div style={{ fontSize: '36px', fontWeight: 800, margin: '8px 0 4px', color: '#fff' }}>
                    {loading ? '—' : stats?.qualifying_candidates_count ?? 0}
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    First-seen unknown persons pending review
                  </p>
                </div>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    backgroundColor: 'var(--color-newperson-bg)',
                    color: 'var(--color-newperson)',
                  }}
                >
                  <UserPlus size={24} />
                </div>
              </div>
            </div>

            <div
              className="card card-hover"
              style={{
                borderTop: '3px solid var(--color-repeat)',
                background: 'linear-gradient(180deg, rgba(245, 158, 11, 0.05) 0%, var(--bg-card) 60%)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.8px',
                      color: 'var(--color-repeat)',
                    }}
                  >
                    Repeat Passage Events
                  </span>
                  <div style={{ fontSize: '36px', fontWeight: 800, margin: '8px 0 4px', color: '#fff' }}>
                    {loading ? '—' : stats?.repeat_passages_count ?? 0}
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Consecutive passes by already-enrolled persons
                  </p>
                </div>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    backgroundColor: 'var(--color-repeat-bg)',
                    color: 'var(--color-repeat)',
                  }}
                >
                  <RefreshCw size={24} />
                </div>
              </div>
            </div>

            <div
              className="card card-hover"
              style={{
                borderTop: '3px solid var(--color-unknown)',
                background: 'linear-gradient(180deg, rgba(239, 68, 68, 0.05) 0%, var(--bg-card) 60%)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.8px',
                      color: 'var(--color-unknown)',
                    }}
                  >
                    Unknown Observations
                  </span>
                  <div style={{ fontSize: '36px', fontWeight: 800, margin: '8px 0 4px', color: '#fff' }}>
                    {loading ? '—' : stats?.unknown_observations_count ?? 0}
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Ambiguous probes (&lt; τ or margin &lt; δ)
                  </p>
                </div>
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    backgroundColor: 'var(--color-unknown-bg)',
                    color: 'var(--color-unknown)',
                  }}
                >
                  <AlertTriangle size={24} />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '20px',
          }}
          aria-label="Infrastructure Connectivity Status"
        >
          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                padding: '14px',
                borderRadius: '12px',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                color: 'var(--accent-primary)',
              }}
            >
              <Video size={24} />
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
                Active CCTV Cameras
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                {loading ? '—' : stats?.active_cameras_count ?? 0} Online
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Protected RTSP destinations configured
              </div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                padding: '14px',
                borderRadius: '12px',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                color: 'var(--color-repeat)',
              }}
            >
              <Activity size={24} />
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
                Active Video Jobs
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                {loading ? '—' : stats?.active_jobs_count ?? 0} In Progress
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                In-process asynchronous inference worker
              </div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                padding: '14px',
                borderRadius: '12px',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                color: 'var(--color-official)',
              }}
            >
              <Layers size={24} />
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
                Total Recorded Passages
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                {loading ? '—' : stats?.total_passage_events ?? 0} Events
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Persisted in facility audit log
              </div>
            </div>
          </div>
        </section>

        <section
          className="card"
          style={{ backgroundColor: 'var(--bg-card-subtle)' }}
          aria-label="Four-Category Visual Legend"
        >
          <div style={{ marginBottom: '14px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#fff', letterSpacing: '0.2px' }}>
              Four-Category Visual Precedence Architecture
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Identity classification is strictly decoupled from turnstile passage states. Colors indicate verified
              detection category.
            </p>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
            }}
          >
            <div
              style={{
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
              }}
            >
              <div style={{ marginBottom: '6px' }}>
                <CategoryBadge category="OFFICIAL_WORKER" size="sm" />
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Green</strong>: Enrolled staff member actively verified on entry ($s \ge \tau$ and $\Delta \ge \delta$).
              </p>
            </div>

            <div
              style={{
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
              }}
            >
              <div style={{ marginBottom: '6px' }}>
                <CategoryBadge category="NEW_PERSON" size="sm" />
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Blue</strong>: First-seen unknown person creating a provisional candidate record.
              </p>
            </div>

            <div
              style={{
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
              }}
            >
              <div style={{ marginBottom: '6px' }}>
                <CategoryBadge category="PREVIOUSLY_ENROLLED" size="sm" />
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Yellow</strong>: Repeat passage precedence. Staff worker passing again displays yellow while retaining official status.
              </p>
            </div>

            <div
              style={{
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
              }}
            >
              <div style={{ marginBottom: '6px' }}>
                <CategoryBadge category="UNKNOWN" size="sm" />
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                <strong>Red</strong>: Ambient pedestrian or ambiguous match rejected by threshold or contrast margin.
              </p>
            </div>
          </div>
        </section>

        <section className="card" aria-label="Recent Passage Events Feed">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '20px',
            }}
          >
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Recent Passage Events</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Chronological surveillance audit log from CCTV stream inference
              </p>
            </div>
            <span
              style={{
                fontSize: '11px',
                color: 'var(--text-dim)',
                backgroundColor: 'var(--bg-card-subtle)',
                padding: '4px 10px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {stats?.recent_events.length ?? 0} Recent Events
            </span>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col" style={{ width: '60px' }}>Crop</th>
                  <th scope="col">Event Timestamp</th>
                  <th scope="col">Display Category</th>
                  <th scope="col">Identity Status</th>
                  <th scope="col">Passage Status</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Track / Camera</th>
                  <th scope="col">Audit Status</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '32px' }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
                        <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
                        <span>Loading CCTV passage records...</span>
                      </div>
                    </td>
                  </tr>
                ) : !stats?.recent_events || stats.recent_events.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      No passage events registered yet for this facility. Upload a CCTV video or initiate camera stream to
                      begin inference.
                    </td>
                  </tr>
                ) : (
                  stats.recent_events.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <div style={{ width: '40px', height: '40px' }}>
                          <MediaImage
                            src={event.crop_path ? api.media.getCropUrl(event.id) : null}
                            alt={`Representative crop for event ${event.id}`}
                            width={40}
                            height={40}
                          />
                        </div>
                      </td>
                      <td style={{ whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                        {new Date(event.event_timestamp).toLocaleString()}
                      </td>
                      <td>
                        <CategoryBadge
                          category={event.display_category}
                          identityStatus={event.identity_status}
                          passageStatus={event.passage_status}
                          size="sm"
                        />
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 600 }}>
                        {event.identity_status}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                        {event.passage_status}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div
                            style={{
                              width: '60px',
                              height: '6px',
                              borderRadius: '3px',
                              backgroundColor: 'var(--border-card)',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(0, event.confidence_score * 100))}%`,
                                height: '100%',
                                backgroundColor:
                                  event.confidence_score >= 0.7124
                                    ? 'var(--color-official)'
                                    : event.confidence_score >= 0.6
                                    ? 'var(--color-repeat)'
                                    : 'var(--color-unknown)',
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                            {event.confidence_score.toFixed(3)}
                          </span>
                        </div>
                      </td>
                      <td style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        {event.track_id ? `TRK-${event.track_id.slice(0, 8)}` : '—'}
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            backgroundColor: event.is_reviewed ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                            color: event.is_reviewed ? 'var(--color-official)' : 'var(--text-dim)',
                            fontWeight: 600,
                          }}
                        >
                          {event.is_reviewed ? 'Audited' : 'Unreviewed'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
