'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/AppShell';
import { MediaImage } from '@/components/MediaImage';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { CandidateIdentity, Worker, PassageEvent, CandidateReviewRequest } from '@/types/api';
import {
  UserX,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';

export default function CandidatesPage() {
  const { currentTenant, userRole } = useAuth();
  const [candidates, setCandidates] = useState<CandidateIdentity[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateIdentity | null>(null);
  const [candidateEvents, setCandidateEvents] = useState<PassageEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [reviewAction, setReviewAction] = useState<'PROMOTED' | 'REJECTED'>('PROMOTED');
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const isOperator = userRole === 'OWNER' || userRole === 'ADMIN' || userRole === 'OPERATOR';

  const fetchData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [cands, wrks] = await Promise.all([
        api.candidates.list({
          review_status: statusFilter === 'all' ? undefined : statusFilter,
        }),
        api.workers.list({ is_active: true }),
      ]);
      setCandidates(cands);
      setWorkers(wrks);

      if (selectedCandidate) {
        const updated = cands.find((c) => c.id === selectedCandidate.id);
        if (updated) setSelectedCandidate(updated);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load provisional candidates';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, selectedCandidate?.id]);

  useEffect(() => {
    fetchData();
  }, [fetchData, currentTenant?.id]);

  const handleSelectCandidate = async (cand: CandidateIdentity) => {
    setSelectedCandidate(cand);
    setLoadingEvents(true);
    try {
      const events = await api.passage.getEvents({
        limit: 20,
      });
      const filtered = events.filter((e) => e.candidate_identity_id === cand.id);
      setCandidateEvents(filtered);
    } catch {
      setCandidateEvents([]);
    } finally {
      setLoadingEvents(false);
    }
  };

  const handleOpenReview = (action: 'PROMOTED' | 'REJECTED') => {
    setReviewAction(action);
    setReviewNotes('');
    setSelectedWorkerId(workers[0]?.id || '');
    setReviewError(null);
    setIsReviewModalOpen(true);
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCandidate) return;

    setReviewSubmitting(true);
    setReviewError(null);

    try {
      const payload: CandidateReviewRequest = {
        review_status: reviewAction,
        notes: reviewNotes.trim() || undefined,
        approved_worker_id: reviewAction === 'PROMOTED' && selectedWorkerId ? selectedWorkerId : undefined,
      };

      const updated = await api.candidates.review(selectedCandidate.id, payload);
      setSelectedCandidate(updated);
      setIsReviewModalOpen(false);
      fetchData(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to submit review decision';
      setReviewError(msg);
    } finally {
      setReviewSubmitting(false);
    }
  };

  return (
    <AppShell
      title="Candidate Identity Review"
      subtitle="Audit first-seen provisional identities, inspect representative crops, and promote verified personnel to official staff."
      onRefresh={() => fetchData(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Audit Filter:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="form-control"
              style={{ width: 'auto', fontSize: '13px' }}
              aria-label="Filter candidates by review status"
            >
              <option value="all">All Candidate Records</option>
              <option value="PENDING_REVIEW">Pending Review (Action Required)</option>
              <option value="PROMOTED">Promoted to Official Staff</option>
              <option value="REJECTED">Rejected / Visitor</option>
            </select>
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
            Provisional candidates are created when an unknown probe creates a stable track
          </div>
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

        <div style={{ display: 'grid', gridTemplateColumns: selectedCandidate ? '1.3fr 1fr' : '1fr', gap: '24px' }}>
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
                Provisional Candidate Gallery ({candidates.length})
              </h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {candidates.filter((c) => c.review_status === 'PENDING_REVIEW').length} Pending Operator Review
              </span>
            </div>

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Candidate Code</th>
                    <th scope="col">First Seen</th>
                    <th scope="col">Last Seen</th>
                    <th scope="col">Review Status</th>
                    <th scope="col">Linked Worker</th>
                    <th scope="col">Inspect</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '32px' }}>
                        Loading candidate records...
                      </td>
                    </tr>
                  ) : candidates.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        No candidate identities found in current filter.
                      </td>
                    </tr>
                  ) : (
                    candidates.map((cand) => {
                      const isSelected = selectedCandidate?.id === cand.id;
                      let badge = (
                        <span className="badge-newperson" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                          PENDING REVIEW
                        </span>
                      );
                      if (cand.review_status === 'PROMOTED') {
                        badge = (
                          <span className="badge-official" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                            PROMOTED (STAFF)
                          </span>
                        );
                      } else if (cand.review_status === 'REJECTED') {
                        badge = (
                          <span className="badge-unknown" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                            REJECTED
                          </span>
                        );
                      }

                      return (
                        <tr
                          key={cand.id}
                          onClick={() => handleSelectCandidate(cand)}
                          style={{
                            cursor: 'pointer',
                            backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                          }}
                        >
                          <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--color-newperson)' }}>
                            {cand.candidate_code}
                          </td>
                          <td style={{ fontSize: '12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                            {new Date(cand.first_seen_at).toLocaleTimeString()}
                          </td>
                          <td style={{ fontSize: '12px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                            {new Date(cand.last_seen_at).toLocaleTimeString()}
                          </td>
                          <td>{badge}</td>
                          <td style={{ fontSize: '12px', color: cand.approved_worker_id ? 'var(--color-official)' : 'var(--text-dim)' }}>
                            {cand.approved_worker_id ? `Linked (ID: ${cand.approved_worker_id.slice(0, 8)})` : 'None'}
                          </td>
                          <td>
                            <ChevronRight size={16} style={{ color: isSelected ? 'var(--accent-primary)' : 'var(--text-dim)' }} />
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {selectedCandidate && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                    Candidate {selectedCandidate.candidate_code}
                  </h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    ID: {selectedCandidate.id}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedCandidate(null)}
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '12px' }}
                >
                  ✕
                </button>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  backgroundColor: 'var(--bg-card-subtle)',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12px',
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>First Sighted:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {new Date(selectedCandidate.first_seen_at).toLocaleString()}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Last Sighted:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                    {new Date(selectedCandidate.last_seen_at).toLocaleString()}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Review Status:</span>
                  <div style={{ fontWeight: 700, marginTop: '2px', color: selectedCandidate.review_status === 'PROMOTED' ? 'var(--color-official)' : selectedCandidate.review_status === 'REJECTED' ? 'var(--color-unknown)' : 'var(--color-newperson)' }}>
                    {selectedCandidate.review_status}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Review Notes:</span>
                  <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                    {selectedCandidate.notes || 'No review notes'}
                  </div>
                </div>
              </div>

              <div>
                <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#fff', marginBottom: '12px' }}>
                  Associated Passage Observation Crops ({candidateEvents.length})
                </h4>

                {loadingEvents ? (
                  <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                    <RefreshCw size={18} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 8px' }} />
                    <p style={{ fontSize: '12px' }}>Retrieving passage crops...</p>
                  </div>
                ) : candidateEvents.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-dim)', fontStyle: 'italic' }}>
                    No direct passage crops linked in current buffer.
                  </p>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))', gap: '10px' }}>
                    {candidateEvents.map((evt) => (
                      <div
                        key={evt.id}
                        style={{
                          borderRadius: 'var(--radius-md)',
                          overflow: 'hidden',
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--bg-deep)',
                        }}
                      >
                        <div style={{ width: '100%', height: '80px' }}>
                          <MediaImage
                            src={evt.crop_path ? api.media.getCropUrl(evt.id) : null}
                            alt={`Candidate observation crop ${evt.id}`}
                            width="100%"
                            height={80}
                          />
                        </div>
                        <div style={{ padding: '4px', fontSize: '9px', textAlign: 'center', color: 'var(--text-dim)' }}>
                          {evt.confidence_score.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {isOperator && selectedCandidate.review_status === 'PENDING_REVIEW' && (
                <div style={{ display: 'flex', gap: '10px', marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
                  <button
                    onClick={() => handleOpenReview('PROMOTED')}
                    className="btn btn-primary"
                    style={{ flex: 1, fontSize: '13px' }}
                  >
                    <CheckCircle2 size={16} /> Approve &amp; Promote
                  </button>
                  <button
                    onClick={() => handleOpenReview('REJECTED')}
                    className="btn btn-danger"
                    style={{ flex: 1, fontSize: '13px' }}
                  >
                    <UserX size={16} /> Reject Candidate
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {isReviewModalOpen && selectedCandidate && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="review-modal-title">
            <div className="modal-content" style={{ maxWidth: '480px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                {reviewAction === 'PROMOTED' ? (
                  <CheckCircle2 size={24} style={{ color: 'var(--color-official)' }} />
                ) : (
                  <AlertTriangle size={24} style={{ color: 'var(--color-unknown)' }} />
                )}
                <h3 id="review-modal-title" style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>
                  {reviewAction === 'PROMOTED' ? 'Promote Candidate to Official Staff' : 'Reject Provisional Candidate'}
                </h3>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                Candidate code: <strong>{selectedCandidate.candidate_code}</strong>. Decisions are written to the tenant
                audit trail.
              </p>

              {reviewError && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-unknown-bg)',
                    border: '1px solid var(--color-unknown-border)',
                    color: 'var(--color-unknown)',
                    fontSize: '13px',
                    marginBottom: '16px',
                  }}
                  role="alert"
                >
                  {reviewError}
                </div>
              )}

              <form onSubmit={handleSubmitReview}>
                {reviewAction === 'PROMOTED' && (
                  <div className="form-group">
                    <label className="form-label" htmlFor="link-worker-select">
                      Link to Registered Staff Member (Optional)
                    </label>
                    <select
                      id="link-worker-select"
                      value={selectedWorkerId}
                      onChange={(e) => setSelectedWorkerId(e.target.value)}
                      className="form-control"
                    >
                      <option value="">Create as Standalone Approved Identity</option>
                      {workers.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.staff_code} — {w.full_name} ({w.department || 'General'})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label" htmlFor="review-notes-input">
                    Review Decision Notes
                  </label>
                  <textarea
                    id="review-notes-input"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Enter audit rationale (e.g., Verified shift supervisor visual confirmation)"
                    rows={3}
                    className="form-control"
                    style={{ resize: 'vertical' }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                  <button
                    type="button"
                    onClick={() => setIsReviewModalOpen(false)}
                    className="btn btn-secondary"
                    disabled={reviewSubmitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className={`btn ${reviewAction === 'PROMOTED' ? 'btn-primary' : 'btn-danger'}`}
                    disabled={reviewSubmitting}
                  >
                    {reviewSubmitting ? 'Recording Audit...' : `Confirm ${reviewAction}`}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
