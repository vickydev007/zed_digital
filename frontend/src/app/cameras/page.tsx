'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AppShell } from '@/components/AppShell';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import {
  Camera,
  CameraCreateRequest,
  CameraUpdateRequest,
  CameraRuntimeStatus,
  CameraTestConnectionResponse,
} from '@/types/api';
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
  Eye,
  CheckCircle2,
  XCircle,
  Activity,
  X,
  Radio,
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

  const [monitoringCamera, setMonitoringCamera] = useState<Camera | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<CameraRuntimeStatus | null>(null);
  const [previewToken, setPreviewToken] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [streamActionLoading, setStreamActionLoading] = useState(false);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);
  const activeTokenRef = useRef<{ camId: string; token: string } | null>(null);

  const [formName, setFormName] = useState('');
  const [formLocation, setFormLocation] = useState('');
  const [formRtspUrl, setFormRtspUrl] = useState('');
  const [formFps, setFormFps] = useState(25);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<CameraTestConnectionResponse | null>(null);

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

  const pollCameraStatus = useCallback(async (camId: string) => {
    try {
      const status = await api.cameras.getStatus(camId);
      setRuntimeStatus(status);
      setStreamError(null);
      setCameras((prev) =>
        prev.map((c) => (c.id === camId ? { ...c, status: status.status } : c))
      );
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to fetch status';
      setStreamError(msg);
    }
  }, []);

  useEffect(() => {
    if (monitoringCamera) {
      pollCameraStatus(monitoringCamera.id);
      api.cameras.getPreviewToken(monitoringCamera.id)
        .then((res) => {
          setPreviewToken(res.preview_token);
          activeTokenRef.current = { camId: monitoringCamera.id, token: res.preview_token };
        })
        .catch(() => setPreviewToken(null));

      statusPollRef.current = setInterval(() => {
        pollCameraStatus(monitoringCamera.id);
      }, 2500);
    } else {
      if (statusPollRef.current) {
        clearInterval(statusPollRef.current);
        statusPollRef.current = null;
      }
      if (activeTokenRef.current) {
        api.cameras.revokePreviewToken(activeTokenRef.current.camId, activeTokenRef.current.token).catch(() => {});
        activeTokenRef.current = null;
      }
      setRuntimeStatus(null);
      setPreviewToken(null);
      setStreamError(null);
    }

    return () => {
      if (statusPollRef.current) {
        clearInterval(statusPollRef.current);
      }
      if (activeTokenRef.current) {
        api.cameras.revokePreviewToken(activeTokenRef.current.camId, activeTokenRef.current.token).catch(() => {});
        activeTokenRef.current = null;
      }
    };
  }, [monitoringCamera, pollCameraStatus]);


  const handleOpenAdd = () => {
    setFormName('');
    setFormLocation('');
    setFormRtspUrl('');
    setFormFps(25);
    setFormError(null);
    setTestResult(null);
    setIsAddOpen(true);
  };

  const handleOpenEdit = (cam: Camera) => {
    setEditingCamera(cam);
    setFormName(cam.name);
    setFormLocation(cam.location || '');
    setFormRtspUrl('');
    setFormFps(cam.stream_fps);
    setFormError(null);
    setTestResult(null);
  };

  const handleTestConnection = async () => {
    if (!formRtspUrl.trim()) {
      setFormError('Please enter an RTSP Stream URL to test.');
      return;
    }

    setTestingConnection(true);
    setTestResult(null);
    setFormError(null);

    try {
      const res = await api.cameras.testConnection({
        rtsp_url: formRtspUrl.trim(),
      });
      setTestResult(res);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Connection probe failed';
      setFormError(msg);
    } finally {
      setTestingConnection(false);
    }
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
      if (cam.status === 'ONLINE' || cam.status === 'CONNECTING') {
        await api.cameras.stop(cam.id);
      } else {
        await api.cameras.start(cam.id);
      }
      fetchCameras(true);
      if (monitoringCamera && monitoringCamera.id === cam.id) {
        pollCameraStatus(cam.id);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to toggle camera status';
      setError(msg);
    }
  };

  const handleToggleFromModal = async () => {
    if (!monitoringCamera) return;
    setStreamActionLoading(true);
    try {
      const currentActive =
        runtimeStatus?.status === 'ONLINE' ||
        runtimeStatus?.status === 'CONNECTING' ||
        monitoringCamera.status === 'ONLINE' ||
        monitoringCamera.status === 'CONNECTING';

      if (currentActive) {
        await api.cameras.stop(monitoringCamera.id);
      } else {
        await api.cameras.start(monitoringCamera.id);
      }
      await pollCameraStatus(monitoringCamera.id);
      fetchCameras(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Action failed';
      setStreamError(msg);
    } finally {
      setStreamActionLoading(false);
    }
  };

  const handleDeleteCamera = async (id: string) => {
    try {
      await api.cameras.delete(id);
      setDeletingCameraId(null);
      if (monitoringCamera?.id === id) {
        setMonitoringCamera(null);
      }
      fetchCameras(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to delete camera';
      setError(msg);
    }
  };

  const getStatusDisplay = (status: string) => {
    switch (status) {
      case 'ONLINE':
        return {
          label: 'LIVE',
          bg: 'var(--color-official-bg)',
          border: '1px solid var(--color-official-border)',
          color: 'var(--color-official)',
          indicator: 'live-indicator',
          helpText: 'Camera feed is streaming and processing real-time detections.',
        };
      case 'CONNECTING':
        return {
          label: 'CONNECTING',
          bg: 'var(--color-repeat-bg)',
          border: '1px solid var(--color-repeat-border)',
          color: 'var(--color-repeat)',
          indicator: 'live-indicator',
          helpText: 'Negotiating RTSP connection and initial frame acquisition...',
        };
      case 'AUTH_EXPIRED':
        return {
          label: 'AUTH EXPIRED',
          bg: 'rgba(245, 158, 11, 0.15)',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          color: '#fbbf24',
          indicator: 'offline-indicator',
          helpText: 'RTSP token expired / authentication rejected (401). Please edit camera to refresh credentials.',
        };
      case 'DEGRADED':
        return {
          label: 'RECONNECTING',
          bg: 'var(--color-repeat-bg)',
          border: '1px solid var(--color-repeat-border)',
          color: 'var(--color-repeat)',
          indicator: 'live-indicator',
          helpText: 'Stream interrupted. Reconnecting with exponential backoff...',
        };
      case 'ERROR':
        return {
          label: 'FAILED',
          bg: 'var(--color-unknown-bg)',
          border: '1px solid var(--color-unknown-border)',
          color: 'var(--color-unknown)',
          indicator: 'offline-indicator',
          helpText: 'Connection failed. Verify host reachability, port availability, and network routing.',
        };
      case 'STOPPING':
      case 'OFFLINE':
      default:
        return {
          label: 'STOPPED',
          bg: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-dim)',
          indicator: 'offline-indicator',
          helpText: 'Stream worker is inactive. Click Start to begin live ingestion.',
        };
    }
  };

  const getStatusBadgeStyle = getStatusDisplay;

  const isModalStreamActive =
    runtimeStatus?.status === 'ONLINE' ||
    runtimeStatus?.status === 'CONNECTING' ||
    monitoringCamera?.status === 'ONLINE';

  return (
    <AppShell
      title="CCTV Camera Management"
      subtitle="Register, monitor, and configure RTSP video inputs with real-time AI inference and stream encryption."
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
              Phase 5.2 Live CCTV Ingestion &amp; Real-Time Open-Set Person Re-ID
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px', lineHeight: '1.5' }}>
              Configured RTSP/RTSPS video streams are ingested in isolated worker threads with bounded 1-frame buffers
              (zero latency buildup). Detections, tracks, embeddings, and open-set matching run continuously with live
              Passage Event and Presence Session persistence. Click <strong>Live View</strong> on any camera to stream
              annotated real-time AI frames directly to the browser.
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
              gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
              gap: '20px',
            }}
          >
            {cameras.map((cam) => {
              const badge = getStatusDisplay(cam.status);
              const isRunning = cam.status === 'ONLINE' || cam.status === 'CONNECTING';

              return (
                <div key={cam.id} className="card card-hover" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div
                        style={{
                          width: '42px',
                          height: '42px',
                          borderRadius: '10px',
                          backgroundColor: cam.status === 'ONLINE' ? 'var(--color-official-bg)' : 'var(--bg-card-subtle)',
                          color: cam.status === 'ONLINE' ? 'var(--color-official)' : 'var(--text-dim)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          border: cam.status === 'ONLINE' ? '1px solid var(--color-official-border)' : '1px solid var(--border-card)',
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
                        backgroundColor: badge.bg,
                        border: badge.border,
                        color: badge.color,
                      }}
                    >
                      <span className={badge.indicator} />
                      <span>{badge.label}</span>
                    </span>
                  </div>

                  {cam.status === 'AUTH_EXPIRED' && (
                    <div
                      style={{
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'rgba(245, 158, 11, 0.12)',
                        border: '1px solid rgba(245, 158, 11, 0.35)',
                        color: '#fbbf24',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>RTSP credentials or token expired (401). Click Edit to update stream URL.</span>
                    </div>
                  )}

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
                      <span style={{ color: 'var(--text-dim)' }}>Configured Rate:</span>
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

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 'auto', paddingTop: '8px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => setMonitoringCamera(cam)}
                      className="btn btn-secondary"
                      style={{ flex: 1, padding: '7px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      title="Open Live Monitor & Annotations"
                    >
                      <Eye size={14} style={{ color: 'var(--accent-primary)' }} />
                      <span>Live View</span>
                    </button>

                    {isOperator && (
                      <button
                        onClick={() => handleToggleFeed(cam)}
                        className={`btn ${isRunning ? 'btn-secondary' : 'btn-primary'}`}
                        style={{ flex: 1, padding: '7px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      >
                        {isRunning ? (
                          <>
                            <Square size={14} /> Stop
                          </>
                        ) : (
                          <>
                            <Play size={14} /> Start
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

        {monitoringCamera && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="live-monitor-title">
            <div
              className="modal-content"
              style={{
                maxWidth: '920px',
                width: '95%',
                padding: '24px',
                backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-card)',
              }}
            >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(59, 130, 246, 0.12)',
                      color: 'var(--accent-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Radio size={20} />
                  </div>
                  <div>
                    <h3 id="live-monitor-title" style={{ fontSize: '17px', fontWeight: 700, color: '#fff' }}>
                      {monitoringCamera.name} — Live Stream &amp; Inference
                    </h3>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {monitoringCamera.location || 'Perimeter CCTV Zone'} &bull; ID: {monitoringCamera.id.slice(0, 12)}
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {(() => {
                    const mBadge = getStatusDisplay(runtimeStatus?.status || monitoringCamera.status);
                    return (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '4px 10px',
                          borderRadius: '9999px',
                          backgroundColor: mBadge.bg,
                          border: mBadge.border,
                          color: mBadge.color,
                        }}
                      >
                        <span className={mBadge.indicator} />
                        <span>{mBadge.label}</span>
                      </span>
                    );
                  })()}

                  <button
                    onClick={() => setMonitoringCamera(null)}
                    className="btn btn-secondary"
                    style={{ padding: '6px', borderRadius: '8px' }}
                    title="Close Monitor"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

                  <div
                style={{
                  position: 'relative',
                  width: '100%',
                  aspectRatio: '16 / 9',
                  backgroundColor: '#07090e',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  border: '1px solid var(--border-card)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {runtimeStatus?.status === 'ONLINE' || monitoringCamera.status === 'ONLINE' ? (
                  <img
                    src={api.cameras.getPreviewUrl(monitoringCamera.id, previewToken || undefined)}
                    alt={`${monitoringCamera.name} Live Feed`}

                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                      display: 'block',
                    }}
                    onError={() => {
                      setStreamError('Stream connection interrupted or awaiting next keyframe.');
                    }}
                  />
                ) : (
                  (() => {
                    const modalBadge = getStatusDisplay(runtimeStatus?.status || monitoringCamera.status);
                    return (
                      <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
                        <Video size={48} style={{ margin: '0 auto 12px', color: modalBadge.color, opacity: 0.8 }} />
                        <h4 style={{ fontSize: '15px', fontWeight: 600, color: '#fff' }}>
                          Stream is Currently {modalBadge.label}
                        </h4>
                        <p style={{ fontSize: '12px', maxWidth: '420px', margin: '6px auto 16px', lineHeight: '1.4', color: modalBadge.color }}>
                          {runtimeStatus?.last_error || modalBadge.helpText}
                        </p>
                        {isOperator && (
                          <div style={{ display: 'flex', justifyContent: 'center', gap: '10px' }}>
                            <button
                              onClick={handleToggleFromModal}
                              className="btn btn-primary"
                              disabled={streamActionLoading}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                            >
                              <Play size={14} />
                              <span>{streamActionLoading ? 'Starting Stream...' : 'Start Camera Stream'}</span>
                            </button>
                            {(runtimeStatus?.status === 'AUTH_EXPIRED' || (runtimeStatus?.last_error && runtimeStatus.last_error.includes('401'))) && isAdmin && (
                              <button
                                onClick={() => {
                                  const camToEdit = monitoringCamera;
                                  setMonitoringCamera(null);
                                  handleOpenEdit(camToEdit);
                                }}
                                className="btn btn-secondary"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', backgroundColor: 'rgba(245, 158, 11, 0.2)', border: '1px solid rgba(245, 158, 11, 0.4)', color: '#fbbf24' }}
                              >
                                <Edit size={14} />
                                <span>Update RTSP Token</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()
                )}

                    {(streamError || runtimeStatus?.last_error) && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '12px',
                      left: '12px',
                      right: '12px',
                      padding: '10px 14px',
                      backgroundColor:
                        runtimeStatus?.status === 'AUTH_EXPIRED' || (runtimeStatus?.last_error && runtimeStatus.last_error.includes('401'))
                          ? 'rgba(245, 158, 11, 0.95)'
                          : 'rgba(239, 68, 68, 0.9)',
                      color: '#fff',
                      fontSize: '12px',
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '8px',
                      backdropFilter: 'blur(4px)',
                      zIndex: 10,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                      <span>{runtimeStatus?.last_error || streamError}</span>
                    </div>
                    {(runtimeStatus?.status === 'AUTH_EXPIRED' || (runtimeStatus?.last_error && runtimeStatus.last_error.includes('401'))) && isAdmin && (
                      <button
                        onClick={() => {
                          const camToEdit = monitoringCamera;
                          setMonitoringCamera(null);
                          handleOpenEdit(camToEdit);
                        }}
                        className="btn btn-secondary"
                        style={{ padding: '3px 8px', fontSize: '11px', backgroundColor: '#fff', color: '#000', border: 'none', flexShrink: 0 }}
                      >
                        Edit URL
                      </button>
                    )}
                  </div>
                )}
              </div>

                  <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '10px',
                  marginTop: '16px',
                }}
              >
                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Received Rate</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.received_fps?.toFixed(1) || '0.0'} <span style={{ fontSize: '11px', fontWeight: 400 }}>FPS</span>
                  </div>
                </div>

                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Inference Rate</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.processed_fps?.toFixed(1) || '0.0'} <span style={{ fontSize: '11px', fontWeight: 400 }}>FPS</span>
                  </div>
                </div>

                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Active Tracks</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-official)', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.active_tracks ?? 0}
                  </div>
                </div>

                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Received Frames</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.received_frames ?? 0}
                  </div>
                </div>

                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Reconnect Count</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: runtimeStatus?.reconnect_count ? 'var(--color-repeat)' : 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.reconnect_count ?? 0}
                  </div>
                </div>

                <div style={{ padding: '10px 14px', borderRadius: '8px', backgroundColor: 'var(--bg-deep)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Worker Uptime</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.uptime_seconds ? `${Math.floor(runtimeStatus.uptime_seconds)}s` : '0s'}
                  </div>
                </div>
              </div>

                  <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '10px',
                  marginTop: '10px',
                }}
              >
                <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Capture Frame Age</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.latency_summary?.frame_age_ms ? `${runtimeStatus.latency_summary.frame_age_ms.toFixed(1)} ms` : '--'}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Inference Time</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.latency_summary?.inference_duration_ms ? `${runtimeStatus.latency_summary.inference_duration_ms.toFixed(1)} ms` : '--'}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Event DB Latency</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#a78bfa', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.latency_summary?.persistence_duration_ms ? `${runtimeStatus.latency_summary.persistence_duration_ms.toFixed(1)} ms` : '--'}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>JPEG Compression</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#fb923c', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.latency_summary?.jpeg_encode_ms ? `${runtimeStatus.latency_summary.jpeg_encode_ms.toFixed(1)} ms` : '--'}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Server Pipeline Total</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#4ade80', fontFamily: 'var(--font-mono)' }}>
                    {runtimeStatus?.latency_summary?.server_pipeline_latency_ms ? `${runtimeStatus.latency_summary.server_pipeline_latency_ms.toFixed(1)} ms` : '--'}
                  </div>
                </div>
              </div>

                  <div
                style={{
                  marginTop: '16px',
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-deep)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                  fontSize: '12px',
                }}
              >
                <span style={{ fontWeight: 600, color: 'var(--text-dim)' }}>Real-Time Inference Legend:</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#22c55e' }} />
                    <span style={{ color: '#22c55e', fontWeight: 600 }}>Confirmed Worker</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#eab308' }} />
                    <span style={{ color: '#eab308', fontWeight: 600 }}>Repeat Passage</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#3b82f6' }} />
                    <span style={{ color: '#3b82f6', fontWeight: 600 }}>Candidate (In Review)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: '#ef4444' }} />
                    <span style={{ color: '#ef4444', fontWeight: 600 }}>Unknown / Ambiguous</span>
                  </div>
                </div>
              </div>

                  <div
                style={{
                  marginTop: '10px',
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(56, 189, 248, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '10px',
                  fontSize: '11px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-dim)' }}>Active Re-ID Policy:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#38bdf8' }}>
                    {runtimeStatus?.policy_id || 'POL-ALERTING-V1'}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>
                    (&tau; &ge; {runtimeStatus?.operating_tau !== undefined ? runtimeStatus.operating_tau.toFixed(2) : '0.85'}, &delta; &ge; {runtimeStatus?.operating_margin !== undefined ? runtimeStatus.operating_margin.toFixed(2) : '0.10'}, min_obs: 3)
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-dim)' }}>Sensor Profile:</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: runtimeStatus?.camera_profile === 'C5_PHOTOMETRIC' ? '#f59e0b' : '#10b981' }}>
                    {runtimeStatus?.camera_profile || 'DEFAULT'}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>&bull; Human Verification Required</span>
                </div>
              </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                  Transport: Multipart Motion-JPEG (Bounded 1-Frame Buffer &bull; Zero Latency Buildup)
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                  {isOperator && (
                    <button
                      onClick={handleToggleFromModal}
                      className={`btn ${isModalStreamActive ? 'btn-secondary' : 'btn-primary'}`}
                      disabled={streamActionLoading}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
                    >
                      {isModalStreamActive ? (
                        <>
                          <Square size={14} />
                          <span>{streamActionLoading ? 'Stopping...' : 'Stop Stream'}</span>
                        </>
                      ) : (
                        <>
                          <Play size={14} />
                          <span>{streamActionLoading ? 'Starting...' : 'Start Stream'}</span>
                        </>
                      )}
                    </button>
                  )}

                  <button
                    onClick={() => setMonitoringCamera(null)}
                    className="btn btn-secondary"
                    style={{ fontSize: '12px' }}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
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

              {testResult && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: testResult.success ? 'var(--color-official-bg)' : 'var(--color-unknown-bg)',
                    border: testResult.success ? '1px solid var(--color-official-border)' : '1px solid var(--color-unknown-border)',
                    color: testResult.success ? 'var(--color-official)' : 'var(--color-unknown)',
                    fontSize: '13px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                  }}
                >
                  {testResult.success ? <CheckCircle2 size={18} style={{ flexShrink: 0, marginTop: '2px' }} /> : <XCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />}
                  <div>
                    <div style={{ fontWeight: 600 }}>
                      {testResult.success ? 'Connection Successful' : 'Connection Failed'}
                    </div>
                    <div style={{ fontSize: '12px', marginTop: '2px', opacity: 0.9 }}>
                      {testResult.message || testResult.error || 'Camera stream responded to RTSP handshake.'}
                    </div>
                  </div>
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label className="form-label" htmlFor="cam-rtsp" style={{ marginBottom: 0 }}>
                      RTSP Stream URL {editingCamera ? '(Leave blank to retain stored stream)' : '*'}
                    </label>
                    {formRtspUrl.trim() && (
                      <button
                        type="button"
                        onClick={handleTestConnection}
                        disabled={testingConnection}
                        className="btn btn-secondary"
                        style={{ padding: '3px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                      >
                        {testingConnection ? <RefreshCw size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Activity size={12} />}
                        <span>{testingConnection ? 'Probing...' : 'Test Connection'}</span>
                      </button>
                    )}
                  </div>
                  <input
                    id="cam-rtsp"
                    type="text"
                    value={formRtspUrl}
                    onChange={(e) => {
                      setFormRtspUrl(e.target.value);
                      setTestResult(null);
                    }}
                    placeholder="rtsp://operator:secret@192.168.1.50:554/live"
                    required={!editingCamera}
                    className="form-control"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}
                  />
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                    SSRF protection active: DNS pre-resolved; loopback (127.0.0.1) and cloud metadata (169.254.169.254) are rejected.
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
                      setTestResult(null);
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
                Are you sure you want to delete this camera? This action will terminate any active live ingestion worker
                and disable surveillance on this channel. Historical passage events already recorded will be preserved.
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
