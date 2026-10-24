'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/AppShell';
import { CategoryBadge } from '@/components/CategoryBadge';
import { MediaImage } from '@/components/MediaImage';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { PassageEvent, PresenceSession, Camera } from '@/types/api';
import {
  Footprints,
  Users,
  CheckCircle,
  Eye,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export default function PassagePage() {
  const { currentTenant, userRole } = useAuth();
  const [events, setEvents] = useState<PassageEvent[]>([]);
  const [presence, setPresence] = useState<PresenceSession[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'events' | 'presence'>('events');

  const [categoryFilter, setCategoryFilter] = useState('');
  const [identityFilter, setIdentityFilter] = useState('');
  const [passageFilter, setPassageFilter] = useState('');
  const [cameraFilter, setCameraFilter] = useState('');

  const [page, setPage] = useState(0);
  const pageSize = 25;

  const [selectedEvent, setSelectedEvent] = useState<PassageEvent | null>(null);

  const isOperator = userRole === 'OWNER' || userRole === 'ADMIN' || userRole === 'OPERATOR';

  const fetchData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [eventsData, presenceData, camerasData] = await Promise.all([
        api.passage.getEvents({
          skip: page * pageSize,
          limit: pageSize,
          display_category: categoryFilter || undefined,
          identity_status: identityFilter || undefined,
          passage_status: passageFilter || undefined,
          camera_id: cameraFilter || undefined,
        }),
        api.passage.getPresence(),
        api.cameras.list(),
      ]);
      setEvents(eventsData);
      setPresence(presenceData);
      setCameras(camerasData);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to fetch passage telemetry';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, categoryFilter, identityFilter, passageFilter, cameraFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData, currentTenant?.id]);

  const handleReviewToggle = async (event: PassageEvent) => {
    if (!isOperator) return;
    try {
      const updated = await api.passage.reviewEvent(event.id, !event.is_reviewed);
      setEvents((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      if (selectedEvent?.id === updated.id) {
        setSelectedEvent(updated);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to update review status';
      setError(msg);
    }
  };

  const activeOccupants = presence.filter((p) => p.is_currently_present);

  return (
    <AppShell
      title="Passage Events & Presence Audits"
      subtitle="Complete chronological passage surveillance audit trail with decoupled identity and presence states."
      onRefresh={() => fetchData(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-card)', paddingBottom: '12px' }}>
          <button
            onClick={() => setActiveTab('events')}
            className={`btn ${activeTab === 'events' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px' }}
          >
            <Footprints size={16} /> Passage Event History ({events.length})
          </button>
          <button
            onClick={() => setActiveTab('presence')}
            className={`btn ${activeTab === 'presence' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px' }}
          >
            <Users size={16} /> Facility Presence ({activeOccupants.length} Active Inside)
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--color-unknown-bg)',
              border: '1px solid var(--color-unknown-border)',
              color: 'var(--color-unknown)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>{error}</span>
            <button onClick={() => setError(null)} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '11px' }}>
              Dismiss
            </button>
          </div>
        )}

        {activeTab === 'events' && (
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
                paddingBottom: '14px',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>Filters:</span>
                <select
                  value={categoryFilter}
                  onChange={(e) => {
                    setCategoryFilter(e.target.value);
                    setPage(0);
                  }}
                  className="form-control"
                  style={{ width: 'auto', fontSize: '12px' }}
                  aria-label="Filter by Display Category"
                >
                  <option value="">All Display Categories</option>
                  <option value="OFFICIAL_WORKER">Official Worker (Green)</option>
                  <option value="NEW_PERSON">New Person (Blue)</option>
                  <option value="PREVIOUSLY_ENROLLED">Repeat Passage (Yellow)</option>
                  <option value="UNKNOWN">Unknown / Ambiguous (Red)</option>
                </select>

                <select
                  value={identityFilter}
                  onChange={(e) => {
                    setIdentityFilter(e.target.value);
                    setPage(0);
                  }}
                  className="form-control"
                  style={{ width: 'auto', fontSize: '12px' }}
                  aria-label="Filter by Identity Status"
                >
                  <option value="">All Identity Statuses</option>
                  <option value="OFFICIAL_WORKER">OFFICIAL_WORKER</option>
                  <option value="NEW_CANDIDATE">NEW_CANDIDATE</option>
                  <option value="UNKNOWN">UNKNOWN</option>
                </select>

                <select
                  value={passageFilter}
                  onChange={(e) => {
                    setPassageFilter(e.target.value);
                    setPage(0);
                  }}
                  className="form-control"
                  style={{ width: 'auto', fontSize: '12px' }}
                  aria-label="Filter by Passage Status"
                >
                  <option value="">All Passage Statuses</option>
                  <option value="FIRST_ENTRY">FIRST_ENTRY</option>
                  <option value="PASSAGE_IN_PROGRESS">PASSAGE_IN_PROGRESS</option>
                  <option value="ALREADY_PASSED">ALREADY_PASSED</option>
                  <option value="REPEAT_PASSAGE">REPEAT_PASSAGE</option>
                </select>

                <select
                  value={cameraFilter}
                  onChange={(e) => {
                    setCameraFilter(e.target.value);
                    setPage(0);
                  }}
                  className="form-control"
                  style={{ width: 'auto', fontSize: '12px' }}
                  aria-label="Filter by Camera"
                >
                  <option value="">All Cameras</option>
                  {cameras.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '12px' }}
                >
                  <ChevronLeft size={14} /> Previous
                </button>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Page {page + 1}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={events.length < pageSize}
                  className="btn btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '12px' }}
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: '56px' }}>Crop</th>
                    <th scope="col">Event Timestamp</th>
                    <th scope="col">Category</th>
                    <th scope="col">Identity Status</th>
                    <th scope="col">Passage Status</th>
                    <th scope="col">Score</th>
                    <th scope="col">Track / Camera</th>
                    <th scope="col">Audit Status</th>
                    <th scope="col">Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', padding: '32px' }}>
                        Loading passage records...
                      </td>
                    </tr>
                  ) : events.length === 0 ? (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        No passage events matching current filter.
                      </td>
                    </tr>
                  ) : (
                    events.map((event) => (
                      <tr key={event.id}>
                        <td>
                          <div
                            onClick={() => setSelectedEvent(event)}
                            style={{ width: '40px', height: '40px', cursor: 'pointer' }}
                            title="Click to view full observation crop"
                          >
                            <MediaImage
                              src={event.crop_path ? api.media.getCropUrl(event.id) : null}
                              alt={`Passage crop ${event.id}`}
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
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div
                              style={{
                                width: '50px',
                                height: '5px',
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
                            <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                              {event.confidence_score.toFixed(3)}
                            </span>
                          </div>
                        </td>
                        <td style={{ fontSize: '11px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          {event.track_id ? `TRK-${event.track_id.slice(0, 8)}` : '—'}
                        </td>
                        <td>
                          {isOperator ? (
                            <button
                              onClick={() => handleReviewToggle(event)}
                              style={{
                                border: 'none',
                                background: 'none',
                                cursor: 'pointer',
                                padding: '3px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 600,
                                backgroundColor: event.is_reviewed ? 'var(--color-official-bg)' : 'rgba(255,255,255,0.05)',
                                color: event.is_reviewed ? 'var(--color-official)' : 'var(--text-dim)',
                              }}
                            >
                              {event.is_reviewed ? '✓ Audited' : 'Mark Audited'}
                            </button>
                          ) : (
                            <span style={{ fontSize: '11px', color: event.is_reviewed ? 'var(--color-official)' : 'var(--text-dim)' }}>
                              {event.is_reviewed ? 'Audited' : 'Pending'}
                            </span>
                          )}
                        </td>
                        <td>
                          <button
                            onClick={() => setSelectedEvent(event)}
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Inspect Observation Details"
                          >
                            <Eye size={12} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'presence' && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
                  Active Presence &amp; Building Occupancy ({activeOccupants.length})
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Tracks workers currently inside the perimeter with cumulative passage event counts
                </p>
              </div>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  backgroundColor: 'var(--color-official-bg)',
                  color: 'var(--color-official)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span className="live-indicator" /> Live Shift Tracking
              </span>
            </div>

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Worker / Identity ID</th>
                    <th scope="col">Identity Classification</th>
                    <th scope="col">Session Entry Time</th>
                    <th scope="col">Passage Count (Current Shift)</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {presence.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                        No presence sessions recorded.
                      </td>
                    </tr>
                  ) : (
                    presence.map((sess) => (
                      <tr key={sess.id}>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#fff' }}>
                          {sess.worker_id ? `STAFF-${sess.worker_id.slice(0, 8)}` : sess.candidate_identity_id ? `CAND-${sess.candidate_identity_id.slice(0, 8)}` : 'Unknown'}
                        </td>
                        <td>
                          <CategoryBadge identityStatus={sess.identity_status} size="sm" />
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {new Date(sess.session_start).toLocaleTimeString()}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                          {sess.passage_count} passage{sess.passage_count === 1 ? '' : 's'}
                        </td>
                        <td>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '4px',
                              backgroundColor: sess.is_currently_present ? 'var(--color-official-bg)' : 'rgba(255,255,255,0.05)',
                              color: sess.is_currently_present ? 'var(--color-official)' : 'var(--text-dim)',
                            }}
                          >
                            {sess.is_currently_present ? 'INSIDE FACILITY' : 'EXITED'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {selectedEvent && (
          <div className="modal-overlay" role="dialog" aria-modal="true" onClick={() => setSelectedEvent(null)}>
            <div
              className="modal-content"
              style={{ maxWidth: '520px', padding: '24px' }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>
                    Passage Observation Audit
                  </h3>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    ID: {selectedEvent.id}
                  </p>
                </div>
                <button onClick={() => setSelectedEvent(null)} className="btn btn-secondary" style={{ padding: '4px 8px' }}>
                  ✕
                </button>
              </div>

              <div style={{ textAlign: 'center', marginBottom: '16px' }}>
                <div
                  style={{
                    width: '180px',
                    height: '240px',
                    margin: '0 auto',
                    borderRadius: 'var(--radius-lg)',
                    overflow: 'hidden',
                    border: '2px solid var(--border-card)',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                  }}
                >
                  <MediaImage
                    src={selectedEvent.crop_path ? api.media.getCropUrl(selectedEvent.id) : null}
                    alt={`Observation crop ${selectedEvent.id}`}
                    width={180}
                    height={240}
                  />
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  marginBottom: '16px',
                }}
              >
                <CategoryBadge
                  category={selectedEvent.display_category}
                  identityStatus={selectedEvent.identity_status}
                  passageStatus={selectedEvent.passage_status}
                  size="lg"
                />
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  backgroundColor: 'var(--bg-deep)',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12px',
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Identity Status:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {selectedEvent.identity_status}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Passage Status:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {selectedEvent.passage_status}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Cosine Similarity:</span>
                  <div style={{ fontWeight: 700, color: 'var(--accent-primary)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {selectedEvent.confidence_score.toFixed(4)}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Timestamp:</span>
                  <div style={{ color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {new Date(selectedEvent.event_timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>

              {isOperator && (
                <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button
                    onClick={() => handleReviewToggle(selectedEvent)}
                    className="btn btn-primary"
                    style={{ width: '100%', fontSize: '13px' }}
                  >
                    <CheckCircle size={14} />
                    {selectedEvent.is_reviewed ? 'Mark as Unaudited' : 'Mark as Verified Audit Record'}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
