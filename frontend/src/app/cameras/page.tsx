'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/AppShell';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Camera, CameraCreateRequest, CameraUpdateRequest } from '@/types/api';
import {
  Video,
  Plus,
  Play,
  Square,
  Trash2,
  Edit,
  AlertTriangle,
  Info,
  RefreshCw,
  Lock,
} from 'lucide-react';

export default function CamerasPage() {
  const { currentTenant, userRole } = useAuth();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [deletingCameraId, setDeletingCameraId] = useState<string | null>(null);

  const [formName, setFormName] = useState('');
  const [formLocation, setFormLocation] = useState('');
  const [formRtspUrl, setFormRtspUrl] = useState('');
  const [formFps, setFormFps] = useState(25);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  const isAdmin = userRole === 'OWNER' || userRole === 'ADMIN';
  const isOperator = isAdmin || userRole === 'OPERATOR';

  const fetchCameras = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = await api.cameras.list();
      setCameras(data);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load cameras';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras, currentTenant?.id]);

  const handleOpenAdd = () => {
    setFormName('');
    setFormLocation('');
    setFormRtspUrl('');
    setFormFps(25);
    setFormError(null);
    setIsAddOpen(true);
  };

  const handleOpenEdit = (cam: Camera) => {
    setEditingCamera(cam);
    setFormName(cam.name);
    setFormLocation(cam.location || '');
    setFormRtspUrl('');
    setFormFps(cam.stream_fps);
    setFormError(null);
  };

  const handleSaveCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setFormError('Camera name is required.');
      return;
    }
    if (!editingCamera && !formRtspUrl.trim()) {
      setFormError('RTSP Stream URL is required.');
      return;
    }

    setFormSubmitting(true);
    setFormError(null);

    try {
      if (editingCamera) {
        const updateData: CameraUpdateRequest = {
          name: formName.trim(),
          location: formLocation.trim() || undefined,
          stream_fps: formFps,
        };
        if (formRtspUrl.trim()) {
          updateData.rtsp_url = formRtspUrl.trim();
        }
        await api.cameras.update(editingCamera.id, updateData);
        setEditingCamera(null);
      } else {
        const createData: CameraCreateRequest = {
          name: formName.trim(),
          location: formLocation.trim() || undefined,
          rtsp_url: formRtspUrl.trim(),
          stream_fps: formFps,
        };
        await api.cameras.create(createData);
        setIsAddOpen(false);
      }
      fetchCameras(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Operation failed';
      setFormError(msg);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggleFeed = async (cam: Camera) => {
    try {
      if (cam.status === 'ONLINE') {
        await api.cameras.stop(cam.id);
      } else {
        await api.cameras.start(cam.id);
      }
      fetchCameras(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to toggle camera status';
      setError(msg);
    }
  };

  const handleDeleteCamera = async (id: string) => {
    try {
      await api.cameras.delete(id);
      setDeletingCameraId(null);
      fetchCameras(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to delete camera';
      setError(msg);
    }
  };

  return (
    <AppShell
      title="CCTV Camera Management"
      subtitle="Register, monitor, and configure RTSP video inputs with server-side credential encryption."
      onRefresh={() => fetchCameras(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div
          style={{
            padding: '20px 24px',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '16px',
          }}
        >
          <Info size={24} style={{ color: 'var(--accent-primary)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#fff' }}>
              Live RTSP Playback &amp; Streaming Architecture Note
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px', lineHeight: '1.5' }}>
              Raw RTSP/RTSPS video streams cannot be played natively in web browsers without transcoding to WebRTC or HLS.
              The backend stores encrypted camera configurations, applies SSRF URL filtering, and executes inference on
              ingested video feeds. Direct in-browser video playback is supported for completed offline analysis jobs
              under <strong>Video Upload &amp; Jobs</strong>.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>Registered Cameras</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              {cameras.length} camera feed{cameras.length === 1 ? '' : 's'} assigned to {currentTenant?.name}
            </p>
          </div>

          {isAdmin && (
            <button
              onClick={handleOpenAdd}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Plus size={16} />
              <span>Register New Camera</span>
            </button>
          )}
        </div>

        {error && (
          <div
            style={{
              padding: '14px 18px',
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

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
            <p>Loading CCTV camera endpoints...</p>
          </div>
        ) : cameras.length === 0 ? (
          <div
            className="card"
            style={{
              textAlign: 'center',
              padding: '60px 20px',
              backgroundColor: 'var(--bg-card-subtle)',
            }}
          >
            <Video size={48} style={{ color: 'var(--text-dim)', margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>No Cameras Configured</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '440px', margin: '8px auto 20px' }}>
              Add an authorized RTSP surveillance stream to begin perimeter and turnstile person re-identification.
            </p>
            {isAdmin && (
              <button onClick={handleOpenAdd} className="btn btn-primary">
                <Plus size={16} /> Register First Camera
              </button>
            )}
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
              gap: '20px',
            }}
          >
            {cameras.map((cam) => {
              const isOnline = cam.status === 'ONLINE';
              return (
                <div key={cam.id} className="card card-hover" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div
                        style={{
                          width: '42px',
                          height: '42px',
                          borderRadius: '10px',
                          backgroundColor: isOnline ? 'var(--color-official-bg)' : 'var(--bg-card-subtle)',
                          color: isOnline ? 'var(--color-official)' : 'var(--text-dim)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          border: isOnline ? '1px solid var(--color-official-border)' : '1px solid var(--border-card)',
                        }}
                      >
                        <Video size={20} />
                      </div>
                      <div>
                        <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#fff' }}>{cam.name}</h4>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{cam.location || 'Facility Zone'}</p>
                      </div>
                    </div>

                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '4px 10px',
                        borderRadius: '9999px',
                        backgroundColor: isOnline ? 'var(--color-official-bg)' : 'rgba(255, 255, 255, 0.05)',
                        border: isOnline ? '1px solid var(--color-official-border)' : '1px solid var(--border-subtle)',
                        color: isOnline ? 'var(--color-official)' : 'var(--text-dim)',
                      }}
                    >
                      <span className={isOnline ? 'live-indicator' : 'offline-indicator'} />
                      <span>{cam.status}</span>
                    </span>
                  </div>

                  <div
                    style={{
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--bg-deep)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-dim)' }}>Stream Security:</span>
                      <span
                        style={{
                          color: cam.has_encrypted_stream ? 'var(--color-official)' : 'var(--text-dim)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontWeight: 600,
                        }}
                      >
                        <Lock size={12} />
                        {cam.has_encrypted_stream ? 'AES-GCM Encrypted' : 'Unencrypted'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-dim)' }}>Frame Rate:</span>
                      <span style={{ color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                        {cam.stream_fps} FPS
                      </span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-dim)' }}>Camera ID:</span>
                      <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        {cam.id.slice(0, 12)}...
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 'auto', paddingTop: '8px' }}>
                    {isOperator && (
                      <button
                        onClick={() => handleToggleFeed(cam)}
                        className={`btn ${isOnline ? 'btn-secondary' : 'btn-primary'}`}
                        style={{ flex: 1, padding: '7px 12px', fontSize: '12px' }}
                      >
                        {isOnline ? (
                          <>
                            <Square size={14} /> Stop Stream
                          </>
                        ) : (
                          <>
                            <Play size={14} /> Start Stream
                          </>
                        )}
                      </button>
                    )}

                    {isAdmin && (
                      <>
                        <button
                          onClick={() => handleOpenEdit(cam)}
                          className="btn btn-secondary"
                          style={{ padding: '7px 12px', fontSize: '12px' }}
                          title="Edit Camera Details"
                        >
                          <Edit size={14} />
                        </button>
                        <button
                          onClick={() => setDeletingCameraId(cam.id)}
                          className="btn btn-danger"
                          style={{ padding: '7px 12px', fontSize: '12px' }}
                          title="Delete Camera"
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {(isAddOpen || editingCamera) && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="camera-modal-title">
            <div className="modal-content">
              <h3 id="camera-modal-title" style={{ fontSize: '18px', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
                {editingCamera ? 'Edit Camera Parameters' : 'Register CCTV Camera Stream'}
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                Camera credentials will be encrypted at rest using AES-GCM and never returned in API payloads.
              </p>

              {formError && (
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
                  {formError}
                </div>
              )}

              <form onSubmit={handleSaveCamera}>
                <div className="form-group">
                  <label className="form-label" htmlFor="cam-name">
                    Camera Display Name *
                  </label>
                  <input
                    id="cam-name"
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="Gate A Turnstile North"
                    required
                    className="form-control"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="cam-location">
                    Physical Location
                  </label>
                  <input
                    id="cam-location"
                    type="text"
                    value={formLocation}
                    onChange={(e) => setFormLocation(e.target.value)}
                    placeholder="Building 3 — Level 1 Entrance"
                    className="form-control"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="cam-rtsp">
                    RTSP Stream URL {editingCamera ? '(Leave blank to retain stored stream)' : '*'}
                  </label>
                  <input
                    id="cam-rtsp"
                    type="text"
                    value={formRtspUrl}
                    onChange={(e) => setFormRtspUrl(e.target.value)}
                    placeholder="rtsp://operator:secret@192.168.1.50:554/live"
                    required={!editingCamera}
                    className="form-control"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}
                  />
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                    SSRF protection active: Localhost (127.0.0.1) and cloud metadata IPs (169.254.169.254) are rejected.
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="cam-fps">
                    Capture Sampling FPS
                  </label>
                  <select
                    id="cam-fps"
                    value={formFps}
                    onChange={(e) => setFormFps(Number(e.target.value))}
                    className="form-control"
                  >
                    <option value={10}>10 FPS (Low Bandwidth)</option>
                    <option value={15}>15 FPS (Balanced Re-ID)</option>
                    <option value={25}>25 FPS (Standard CCTV)</option>
                    <option value={30}>30 FPS (High Density)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddOpen(false);
                      setEditingCamera(null);
                    }}
                    className="btn btn-secondary"
                    disabled={formSubmitting}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={formSubmitting}>
                    {formSubmitting ? 'Saving...' : editingCamera ? 'Save Changes' : 'Register Camera'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {deletingCameraId && (
          <div className="modal-overlay" role="dialog" aria-modal="true">
            <div className="modal-content" style={{ maxWidth: '420px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--color-unknown)', marginBottom: '12px' }}>
                <AlertTriangle size={24} />
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Confirm Camera Deletion</h3>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', marginBottom: '20px' }}>
                Are you sure you want to delete this camera? This action will disable surveillance on this channel.
                Historical passage events already recorded will be preserved.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button onClick={() => setDeletingCameraId(null)} className="btn btn-secondary">
                  Cancel
                </button>
                <button onClick={() => handleDeleteCamera(deletingCameraId)} className="btn btn-danger">
                  Delete Camera
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
