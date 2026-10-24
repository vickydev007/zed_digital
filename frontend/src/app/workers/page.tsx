'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AppShell } from '@/components/AppShell';
import { MediaImage } from '@/components/MediaImage';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Worker, WorkerCreateRequest, WorkerEnrollResponse } from '@/types/api';
import {
  UserPlus,
  Search,
  Camera,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react';

export default function WorkersPage() {
  const { currentTenant, userRole } = useAuth();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  const [isAddWorkerOpen, setIsAddWorkerOpen] = useState(false);
  const [deactivatingWorkerId, setDeactivatingWorkerId] = useState<string | null>(null);

  const [newStaffCode, setNewStaffCode] = useState('');
  const [newFullName, setNewFullName] = useState('');
  const [newDepartment, setNewDepartment] = useState('');
  const [newBatch, setNewBatch] = useState('');
  const [newUniform, setNewUniform] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [enrollingPhoto, setEnrollingPhoto] = useState(false);
  const [enrollFeedback, setEnrollFeedback] = useState<WorkerEnrollResponse | null>(null);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);

  const isAdmin = userRole === 'OWNER' || userRole === 'ADMIN';
  const isOperator = isAdmin || userRole === 'OPERATOR';

  const fetchWorkers = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = await api.workers.list({
        search: search.trim() || undefined,
        department: departmentFilter || undefined,
        is_active: activeFilter === 'all' ? undefined : activeFilter === 'active',
      });
      setWorkers(data);
      if (selectedWorker) {
        const updated = data.find((w) => w.id === selectedWorker.id);
        if (updated) setSelectedWorker(updated);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to fetch workers';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [search, departmentFilter, activeFilter, selectedWorker?.id]);

  useEffect(() => {
    fetchWorkers();
  }, [fetchWorkers, currentTenant?.id]);

  const handleCreateWorker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStaffCode.trim() || !newFullName.trim()) {
      setCreateError('Staff Code and Full Name are required.');
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    try {
      const payload: WorkerCreateRequest = {
        staff_code: newStaffCode.trim().toUpperCase(),
        full_name: newFullName.trim(),
        department: newDepartment.trim() || undefined,
        batch: newBatch.trim() || undefined,
        uniform_category: newUniform.trim() || undefined,
      };
      const created = await api.workers.create(payload);
      setIsAddWorkerOpen(false);
      setNewStaffCode('');
      setNewFullName('');
      setNewDepartment('');
      setNewBatch('');
      setNewUniform('');
      setSelectedWorker(created);
      fetchWorkers(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to create worker profile';
      setCreateError(msg);
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handlePhotoEnroll = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedWorker) return;

    setEnrollingPhoto(true);
    setEnrollError(null);
    setEnrollFeedback(null);

    try {
      const res = await api.workers.enrollPhoto(selectedWorker.id, file, true);
      setEnrollFeedback(res);
      fetchWorkers(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Photo enrollment failed';
      setEnrollError(msg);
    } finally {
      setEnrollingPhoto(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  };

  const handleDeactivate = async (workerId: string) => {
    try {
      await api.workers.deactivate(workerId);
      setDeactivatingWorkerId(null);
      fetchWorkers(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to deactivate worker';
      setError(msg);
    }
  };

  const departments = Array.from(new Set(workers.map((w) => w.department).filter(Boolean))) as string[];

  return (
    <AppShell
      title="Worker Enrollment Directory"
      subtitle="Manage enrolled facility personnel, upload reference portraits, and audit facial and body quality scores."
      onRefresh={() => fetchWorkers(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', flex: 1 }}>
            <div style={{ position: 'relative', minWidth: '240px' }}>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search staff code or name..."
                className="form-control"
                style={{ paddingLeft: '36px', fontSize: '13px' }}
              />
              <Search
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-dim)',
                }}
              />
            </div>

            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="form-control"
              style={{ width: 'auto', fontSize: '13px' }}
              aria-label="Filter by department"
            >
              <option value="">All Departments</option>
              {departments.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>

            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="form-control"
              style={{ width: 'auto', fontSize: '13px' }}
              aria-label="Filter by status"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
            </select>
          </div>

          {isOperator && (
            <button
              onClick={() => {
                setCreateError(null);
                setIsAddWorkerOpen(true);
              }}
              className="btn btn-primary"
            >
              <UserPlus size={16} /> Enroll New Worker
            </button>
          )}
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

        <div style={{ display: 'grid', gridTemplateColumns: selectedWorker ? '1.4fr 1fr' : '1fr', gap: '24px' }}>
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Personnel Roster ({workers.length})</h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {workers.filter((w) => w.enrollment_status === 'ENROLLED').length} with active embeddings
              </span>
            </div>

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: '50px' }}>Photo</th>
                    <th scope="col">Staff Code</th>
                    <th scope="col">Full Name</th>
                    <th scope="col">Department</th>
                    <th scope="col">Uniform</th>
                    <th scope="col">Enrollment</th>
                    <th scope="col">Active</th>
                    <th scope="col">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '32px' }}>
                        Loading worker profiles...
                      </td>
                    </tr>
                  ) : workers.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        No worker records found matching filter criteria.
                      </td>
                    </tr>
                  ) : (
                    workers.map((worker) => {
                      const isSelected = selectedWorker?.id === worker.id;
                      const primaryImg = worker.images.find((img) => img.is_primary) || worker.images[0];

                      return (
                        <tr
                          key={worker.id}
                          onClick={() => setSelectedWorker(worker)}
                          style={{
                            cursor: 'pointer',
                            backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                          }}
                        >
                          <td>
                            <div style={{ width: '36px', height: '36px' }}>
                              <MediaImage
                                src={
                                  primaryImg
                                    ? api.media.getEnrollmentImageUrl(worker.id, primaryImg.id)
                                    : null
                                }
                                alt={worker.full_name}
                                width={36}
                                height={36}
                              />
                            </div>
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--color-official)' }}>
                            {worker.staff_code}
                          </td>
                          <td style={{ fontWeight: 600, color: '#fff' }}>{worker.full_name}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{worker.department || '—'}</td>
                          <td style={{ color: 'var(--text-dim)', fontSize: '12px' }}>{worker.uniform_category || 'Standard'}</td>
                          <td>
                            <span
                              style={{
                                fontSize: '11px',
                                fontWeight: 700,
                                padding: '3px 8px',
                                borderRadius: '4px',
                                backgroundColor:
                                  worker.enrollment_status === 'ENROLLED'
                                    ? 'var(--color-official-bg)'
                                    : 'rgba(255, 255, 255, 0.06)',
                                color:
                                  worker.enrollment_status === 'ENROLLED'
                                    ? 'var(--color-official)'
                                    : 'var(--text-muted)',
                              }}
                            >
                              {worker.enrollment_status}
                            </span>
                          </td>
                          <td>
                            <span
                              style={{
                                display: 'inline-block',
                                width: '8px',
                                height: '8px',
                                borderRadius: '50%',
                                backgroundColor: worker.is_active ? 'var(--color-official)' : 'var(--text-dim)',
                              }}
                            />
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

          {selectedWorker && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>{selectedWorker.full_name}</h3>
                  <p style={{ fontSize: '13px', color: 'var(--color-official)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                    Staff Code: {selectedWorker.staff_code}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedWorker(null)}
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
                  <span style={{ color: 'var(--text-dim)' }}>Department:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>
                    {selectedWorker.department || 'Not Assigned'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Shift Batch:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>
                    {selectedWorker.batch || 'General'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Uniform Category:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>
                    {selectedWorker.uniform_category || 'Standard Staff'}
                  </div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)' }}>Enrolled Images:</span>
                  <div style={{ fontWeight: 600, color: '#fff', marginTop: '2px' }}>
                    {selectedWorker.images.length} Photos
                  </div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, color: '#fff' }}>Reference Portrait Gallery</h4>
                  {isOperator && (
                    <label
                      htmlFor="photo-upload-input"
                      className="btn btn-secondary"
                      style={{ padding: '6px 12px', fontSize: '12px', cursor: enrollingPhoto ? 'not-allowed' : 'pointer' }}
                    >
                      <Camera size={14} />
                      <span>{enrollingPhoto ? 'Assessing...' : 'Add Photo'}</span>
                      <input
                        ref={photoInputRef}
                        id="photo-upload-input"
                        type="file"
                        accept="image/*"
                        onChange={handlePhotoEnroll}
                        disabled={enrollingPhoto}
                        style={{ display: 'none' }}
                      />
                    </label>
                  )}
                </div>

                {enrollFeedback && (
                  <div
                    style={{
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: enrollFeedback.is_accepted ? 'var(--color-official-bg)' : 'var(--color-unknown-bg)',
                      border: `1px solid ${enrollFeedback.is_accepted ? 'var(--color-official-border)' : 'var(--color-unknown-border)'}`,
                      color: enrollFeedback.is_accepted ? 'var(--color-official)' : 'var(--color-unknown)',
                      fontSize: '12px',
                      marginBottom: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
                      {enrollFeedback.is_accepted ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                      <span>{enrollFeedback.is_accepted ? 'Photo Quality Accepted & Embedded' : 'Photo Rejected: Low Quality'}</span>
                    </div>
                    <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--text-main)' }}>
                      Quality Score: {(enrollFeedback.quality_score * 100).toFixed(1)}% | Blur Metric: {enrollFeedback.blur_score.toFixed(1)}
                    </div>
                  </div>
                )}

                {enrollError && (
                  <div
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--color-unknown-bg)',
                      border: '1px solid var(--color-unknown-border)',
                      color: 'var(--color-unknown)',
                      fontSize: '12px',
                      marginBottom: '14px',
                    }}
                  >
                    {enrollError}
                  </div>
                )}

                {selectedWorker.images.length === 0 ? (
                  <div
                    style={{
                      textAlign: 'center',
                      padding: '30px',
                      border: '1px dashed var(--border-card)',
                      borderRadius: 'var(--radius-md)',
                      color: 'var(--text-muted)',
                      fontSize: '13px',
                    }}
                  >
                    <Camera size={32} style={{ color: 'var(--text-dim)', margin: '0 auto 8px' }} />
                    <p>No reference enrollment photos yet.</p>
                    <p style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                      Upload a front-facing image to generate deep feature embeddings for gallery matching.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '10px' }}>
                    {selectedWorker.images.map((img) => (
                      <div
                        key={img.id}
                        style={{
                          borderRadius: 'var(--radius-md)',
                          overflow: 'hidden',
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--bg-deep)',
                          position: 'relative',
                        }}
                      >
                        <div style={{ width: '100%', height: '120px' }}>
                          <MediaImage
                            src={api.media.getEnrollmentImageUrl(selectedWorker.id, img.id)}
                            alt={`Enrollment photo for ${selectedWorker.full_name}`}
                            width="100%"
                            height={120}
                          />
                        </div>
                        <div style={{ padding: '6px 8px', fontSize: '10px', color: 'var(--text-muted)' }}>
                          <div>Q: {(img.quality_score * 100).toFixed(0)}%</div>
                          {img.is_primary && (
                            <span style={{ color: 'var(--color-official)', fontWeight: 700 }}>Primary</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {isAdmin && selectedWorker.is_active && (
                <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
                  <button
                    onClick={() => setDeactivatingWorkerId(selectedWorker.id)}
                    className="btn btn-danger"
                    style={{ width: '100%', fontSize: '13px' }}
                  >
                    Deactivate Worker Profile
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {isAddWorkerOpen && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="add-worker-title">
            <div className="modal-content">
              <h3 id="add-worker-title" style={{ fontSize: '18px', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
                Enroll New Worker Profile
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                Create official worker record. You can upload reference portraits after saving profile details.
              </p>

              {createError && (
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
                  {createError}
                </div>
              )}

              <form onSubmit={handleCreateWorker}>
                <div className="form-group">
                  <label className="form-label" htmlFor="new-staff-code">
                    Staff Code (Unique ID) *
                  </label>
                  <input
                    id="new-staff-code"
                    type="text"
                    value={newStaffCode}
                    onChange={(e) => setNewStaffCode(e.target.value)}
                    placeholder="EMP-0142"
                    required
                    className="form-control"
                    style={{ fontFamily: 'var(--font-mono)' }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-full-name">
                    Full Legal Name *
                  </label>
                  <input
                    id="new-full-name"
                    type="text"
                    value={newFullName}
                    onChange={(e) => setNewFullName(e.target.value)}
                    placeholder="Sarah Jenkins"
                    required
                    className="form-control"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-department">
                    Department
                  </label>
                  <input
                    id="new-department"
                    type="text"
                    value={newDepartment}
                    onChange={(e) => setNewDepartment(e.target.value)}
                    placeholder="Operations & Security"
                    className="form-control"
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label" htmlFor="new-batch">
                      Shift Batch
                    </label>
                    <input
                      id="new-batch"
                      type="text"
                      value={newBatch}
                      onChange={(e) => setNewBatch(e.target.value)}
                      placeholder="Shift Alpha"
                      className="form-control"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="new-uniform">
                      Uniform Category
                    </label>
                    <input
                      id="new-uniform"
                      type="text"
                      value={newUniform}
                      onChange={(e) => setNewUniform(e.target.value)}
                      placeholder="Navy Uniform"
                      className="form-control"
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                  <button
                    type="button"
                    onClick={() => setIsAddWorkerOpen(false)}
                    className="btn btn-secondary"
                    disabled={createSubmitting}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={createSubmitting}>
                    {createSubmitting ? 'Creating Profile...' : 'Save & Continue to Photos'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {deactivatingWorkerId && (
          <div className="modal-overlay" role="dialog" aria-modal="true">
            <div className="modal-content" style={{ maxWidth: '420px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--color-unknown)', marginBottom: '12px' }}>
                <AlertTriangle size={24} />
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Deactivate Worker Profile</h3>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '20px' }}>
                Are you sure you want to deactivate this worker? Their feature embeddings will no longer be matched
                against CCTV query probes.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button onClick={() => setDeactivatingWorkerId(null)} className="btn btn-secondary">
                  Cancel
                </button>
                <button onClick={() => handleDeactivate(deactivatingWorkerId)} className="btn btn-danger">
                  Deactivate Worker
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
