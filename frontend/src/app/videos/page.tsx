'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AppShell } from '@/components/AppShell';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { VideoAsset, Job, Camera, VideoAnalyzeRequest } from '@/types/api';
import {
  UploadCloud,
  Film,
  Play,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
  Sliders,
} from 'lucide-react';

const MAX_FILE_SIZE_BYTES = 150 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv'];

export default function VideosPage() {
  const { currentTenant, userRole } = useAuth();
  const [videos, setVideos] = useState<VideoAsset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'upload' | 'jobs' | 'library'>('upload');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<VideoAsset | null>(null);

  const [analyzingVideo, setAnalyzingVideo] = useState<VideoAsset | null>(null);
  const [threshold, setThreshold] = useState<number>(0.7124);
  const [margin, setMargin] = useState<number>(0.05);
  const [saveAnnotatedVideo, setSaveAnnotatedVideo] = useState<boolean>(true);
  const [startingAnalysis, setStartingAnalysis] = useState(false);

  const [playingJobId, setPlayingJobId] = useState<string | null>(null);
  const [jobVideoBlobUrl, setJobVideoBlobUrl] = useState<string | null>(null);
  const [loadingVideoBlob, setLoadingVideoBlob] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isOperator = userRole === 'OWNER' || userRole === 'ADMIN' || userRole === 'OPERATOR';

  const fetchData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [vids, jbs, cams] = await Promise.all([
        api.videos.list(),
        api.jobs.list(),
        api.cameras.list(),
      ]);
      setVideos(vids);
      setJobs(jbs);
      setCameras(cams);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to fetch video assets';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, currentTenant?.id]);

  useEffect(() => {
    const hasActiveJobs = jobs.some((j) => j.status === 'RUNNING' || j.status === 'QUEUED');
    if (!hasActiveJobs) return;

    const interval = setInterval(async () => {
      try {
        const updatedJobs = await api.jobs.list();
        setJobs(updatedJobs);
      } catch {
        // silent polling failure
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [jobs]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    setUploadSuccess(null);
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(`Invalid video format. Supported formats: ${ALLOWED_EXTENSIONS.join(', ')}`);
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(`File size ${(file.size / (1024 * 1024)).toFixed(1)} MB exceeds the 150 MB limit.`);
      setSelectedFile(null);
      return;
    }

    if (file.size < 100) {
      setUploadError('Uploaded video file appears empty.');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError('Please select a valid video file.');
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const asset = await api.videos.upload(selectedFile, selectedCameraId || undefined);
      setUploadSuccess(asset);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchData(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Video upload failed';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleStartAnalysis = async () => {
    if (!analyzingVideo) return;
    setStartingAnalysis(true);
    try {
      const options: VideoAnalyzeRequest = {
        score_threshold: threshold,
        contrast_margin: margin,
        save_annotated_video: saveAnnotatedVideo,
      };
      await api.videos.analyze(analyzingVideo.id, options);
      setAnalyzingVideo(null);
      setActiveTab('jobs');
      fetchData(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to launch analysis job';
      setError(msg);
    } finally {
      setStartingAnalysis(false);
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      await api.jobs.cancel(jobId);
      fetchData(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to cancel job';
      setError(msg);
    }
  };

  const handlePlayJobVideo = async (jobId: string) => {
    setPlayingJobId(jobId);
    setLoadingVideoBlob(true);
    if (jobVideoBlobUrl) {
      URL.revokeObjectURL(jobVideoBlobUrl);
      setJobVideoBlobUrl(null);
    }

    try {
      const blobUrl = await api.media.fetchBlobUrl(api.media.getJobVideoUrl(jobId));
      setJobVideoBlobUrl(blobUrl);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load authorized job video';
      setError(msg);
    } finally {
      setLoadingVideoBlob(false);
    }
  };

  const handleCloseVideoModal = () => {
    setPlayingJobId(null);
    if (jobVideoBlobUrl) {
      URL.revokeObjectURL(jobVideoBlobUrl);
      setJobVideoBlobUrl(null);
    }
  };

  return (
    <AppShell
      title="Video Upload & Asynchronous Jobs"
      subtitle="Upload authorized surveillance footage, trigger background offline Re-ID inference, and inspect passage audits."
      onRefresh={() => fetchData(true)}
      isRefreshing={refreshing}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-card)', paddingBottom: '12px' }}>
          <button
            onClick={() => setActiveTab('upload')}
            className={`btn ${activeTab === 'upload' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px' }}
          >
            <UploadCloud size={16} /> Upload CCTV Video
          </button>
          <button
            onClick={() => setActiveTab('jobs')}
            className={`btn ${activeTab === 'jobs' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px' }}
          >
            <Clock size={16} /> Analysis Jobs ({jobs.length})
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={`btn ${activeTab === 'library' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ fontSize: '13px' }}
          >
            <Film size={16} /> Video Library ({videos.length})
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

        {activeTab === 'upload' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px' }}>
            <div className="card">
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff', marginBottom: '8px' }}>
                Upload Surveillance Video
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                Videos are probed for resolution, duration, and frame count before persisting to tenant storage.
              </p>

              {uploadError && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-unknown-bg)',
                    border: '1px solid var(--color-unknown-border)',
                    color: 'var(--color-unknown)',
                    fontSize: '13px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                  role="alert"
                >
                  <AlertCircle size={16} />
                  <span>{uploadError}</span>
                </div>
              )}

              {uploadSuccess && (
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--color-official-bg)',
                    border: '1px solid var(--color-official-border)',
                    color: 'var(--color-official)',
                    fontSize: '13px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, marginBottom: '6px' }}>
                    <CheckCircle2 size={18} />
                    <span>Upload &amp; Probing Complete!</span>
                  </div>
                  <div style={{ color: 'var(--text-main)', fontSize: '12px', lineHeight: '1.5' }}>
                    <strong>File:</strong> {uploadSuccess.original_filename} ({uploadSuccess.resolution_width}x
                    {uploadSuccess.resolution_height} @ {uploadSuccess.fps} FPS)
                    <br />
                    <strong>Duration:</strong> {uploadSuccess.duration_seconds.toFixed(1)}s ({uploadSuccess.frame_count} frames)
                  </div>
                  <button
                    onClick={() => setAnalyzingVideo(uploadSuccess)}
                    className="btn btn-primary"
                    style={{ marginTop: '12px', width: '100%', fontSize: '13px' }}
                  >
                    Configure &amp; Run Open-Set Re-ID
                  </button>
                </div>
              )}

              <form onSubmit={handleUploadSubmit}>
                <div className="form-group">
                  <label className="form-label" htmlFor="video-file-input">
                    Select CCTV Video File (.mp4, .avi, .mov, .mkv) *
                  </label>
                  <input
                    ref={fileInputRef}
                    id="video-file-input"
                    type="file"
                    accept=".mp4,.avi,.mov,.mkv"
                    onChange={handleFileChange}
                    className="form-control"
                    disabled={uploading}
                    required
                  />
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                    Maximum upload limit: 150 MB.
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="camera-select">
                    Associate with Camera Feed (Optional)
                  </label>
                  <select
                    id="camera-select"
                    value={selectedCameraId}
                    onChange={(e) => setSelectedCameraId(e.target.value)}
                    className="form-control"
                    disabled={uploading}
                  >
                    <option value="">No Camera Association (Direct Upload)</option>
                    {cameras.map((cam) => (
                      <option key={cam.id} value={cam.id}>
                        {cam.name} ({cam.location || 'Default'})
                      </option>
                    ))}
                  </select>
                </div>

                {isOperator && (
                  <button
                    type="submit"
                    disabled={uploading || !selectedFile}
                    className="btn btn-primary"
                    style={{ width: '100%', padding: '12px', marginTop: '10px' }}
                  >
                    {uploading ? (
                      <>
                        <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />
                        <span>Uploading &amp; Probing Media...</span>
                      </>
                    ) : (
                      <>
                        <UploadCloud size={16} />
                        <span>Upload Video to Facility Storage</span>
                      </>
                    )}
                  </button>
                )}
              </form>
            </div>

            <div className="card" style={{ backgroundColor: 'var(--bg-card-subtle)' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff', marginBottom: '12px' }}>
                Pipeline Processing Specifications
              </h3>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
                <li style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ color: 'var(--color-official)', flexShrink: 0 }}>✓</div>
                  <div>
                    <strong style={{ color: '#fff' }}>Pedestrian Detection:</strong> Faster R-CNN MobileNetV3 with bounding
                    box aspect ratio validation ($H/W \in [1.2, 4.5]$).
                  </div>
                </li>
                <li style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ color: 'var(--color-official)', flexShrink: 0 }}>✓</div>
                  <div>
                    <strong style={{ color: '#fff' }}>Feature Embedding:</strong> 512-dimensional L2-normalized deep feature
                    vectors extracted via ONNX Runtime ReID Engine.
                  </div>
                </li>
                <li style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ color: 'var(--color-official)', flexShrink: 0 }}>✓</div>
                  <div>
                    <strong style={{ color: '#fff' }}>Decoupled Decision Logic:</strong> Strict two-gate verification:
                    $s_1 \ge \tau$ and top margin $\Delta = s_1 - s_2 \ge \delta$.
                  </div>
                </li>
                <li style={{ display: 'flex', gap: '10px' }}>
                  <div style={{ color: 'var(--color-official)', flexShrink: 0 }}>✓</div>
                  <div>
                    <strong style={{ color: '#fff' }}>Repeat Passage Precedence:</strong> Returning staff workers display as
                    yellow while preserving official identity.
                  </div>
                </li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Background Analysis Jobs</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Asynchronous video inference queue with real-time polling
                </p>
              </div>
              <button onClick={() => fetchData(true)} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }}>
                <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} /> Refresh Jobs
              </button>
            </div>

            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Job ID</th>
                    <th scope="col">Status</th>
                    <th scope="col">Progress</th>
                    <th scope="col">Frames Processed</th>
                    <th scope="col">Submitted</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '32px' }}>
                        Loading job history...
                      </td>
                    </tr>
                  ) : jobs.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        No video processing jobs have been scheduled yet.
                      </td>
                    </tr>
                  ) : (
                    jobs.map((job) => {
                      let statusBadge = (
                        <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                          {job.status}
                        </span>
                      );
                      if (job.status === 'COMPLETED') {
                        statusBadge = (
                          <span className="badge-official" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                            COMPLETED
                          </span>
                        );
                      } else if (job.status === 'RUNNING') {
                        statusBadge = (
                          <span className="badge-repeat" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                            <span className="live-indicator" style={{ backgroundColor: 'var(--color-repeat)' }} />
                            RUNNING
                          </span>
                        );
                      } else if (job.status === 'FAILED') {
                        statusBadge = (
                          <span className="badge-unknown" style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
                            FAILED
                          </span>
                        );
                      } else if (job.status === 'QUEUED') {
                        statusBadge = (
                          <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, backgroundColor: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
                            QUEUED
                          </span>
                        );
                      }

                      return (
                        <tr key={job.id}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                            {job.id.slice(0, 10)}...
                          </td>
                          <td>{statusBadge}</td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div
                                style={{
                                  width: '90px',
                                  height: '6px',
                                  borderRadius: '3px',
                                  backgroundColor: 'var(--border-card)',
                                  overflow: 'hidden',
                                }}
                              >
                                <div
                                  style={{
                                    width: `${job.progress_percent}%`,
                                    height: '100%',
                                    backgroundColor:
                                      job.status === 'COMPLETED'
                                        ? 'var(--color-official)'
                                        : job.status === 'FAILED'
                                        ? 'var(--color-unknown)'
                                        : 'var(--accent-primary)',
                                    transition: 'width 0.3s ease',
                                  }}
                                />
                              </div>
                              <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                                {job.progress_percent}%
                              </span>
                            </div>
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>
                            {job.processed_frames} / {job.total_frames || '—'}
                          </td>
                          <td style={{ fontSize: '12px', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                            {new Date(job.created_at).toLocaleTimeString()}
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              {job.status === 'COMPLETED' && job.output_video_path && (
                                <button
                                  onClick={() => handlePlayJobVideo(job.id)}
                                  className="btn btn-primary"
                                  style={{ padding: '5px 10px', fontSize: '11px' }}
                                >
                                  <Play size={12} /> Play Output
                                </button>
                              )}
                              {(job.status === 'RUNNING' || job.status === 'QUEUED') && isOperator && (
                                <button
                                  onClick={() => handleCancelJob(job.id)}
                                  className="btn btn-danger"
                                  style={{ padding: '5px 10px', fontSize: '11px' }}
                                >
                                  <XCircle size={12} /> Cancel
                                </button>
                              )}
                              {job.status === 'FAILED' && job.error_details && (
                                <span style={{ fontSize: '11px', color: 'var(--color-unknown)', maxWidth: '200px', display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {job.error_details}
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'library' && (
          <div className="card">
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff', marginBottom: '16px' }}>
              Stored Video Assets
            </h3>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Filename</th>
                    <th scope="col">Resolution</th>
                    <th scope="col">FPS</th>
                    <th scope="col">Duration</th>
                    <th scope="col">File Size</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {videos.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                        No video assets in library.
                      </td>
                    </tr>
                  ) : (
                    videos.map((vid) => (
                      <tr key={vid.id}>
                        <td style={{ fontWeight: 600, color: '#fff' }}>{vid.original_filename}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {vid.resolution_width}x{vid.resolution_height}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{vid.fps}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{vid.duration_seconds.toFixed(1)}s</td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          {(vid.file_size_bytes / (1024 * 1024)).toFixed(1)} MB
                        </td>
                        <td>
                          {isOperator && (
                            <button
                              onClick={() => setAnalyzingVideo(vid)}
                              className="btn btn-primary"
                              style={{ padding: '5px 12px', fontSize: '12px' }}
                            >
                              <Play size={12} /> Run Analysis
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {analyzingVideo && (
          <div className="modal-overlay" role="dialog" aria-modal="true">
            <div className="modal-content" style={{ maxWidth: '500px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                <Sliders size={20} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#fff' }}>Configure Re-ID Parameters</h3>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
                Targeting video: <strong>{analyzingVideo.original_filename}</strong>
              </p>

              <div className="form-group">
                <label className="form-label" htmlFor="param-tau">
                  Verification Threshold ($\tau$) — Current: {threshold.toFixed(4)}
                </label>
                <input
                  id="param-tau"
                  type="range"
                  min="0.5"
                  max="0.9"
                  step="0.005"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                  <span>0.50 (Permissive)</span>
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 700 }}>
                    Calibrated: 0.7124 | Recommended Secure: 0.7520
                  </span>
                  <span>0.90 (Strict)</span>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="param-delta">
                  Contrast Ambiguity Margin ($\delta$) — Current: {margin.toFixed(3)}
                </label>
                <input
                  id="param-delta"
                  type="range"
                  min="0.01"
                  max="0.15"
                  step="0.005"
                  value={margin}
                  onChange={(e) => setMargin(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px', display: 'block' }}>
                  Requires Top-1 vs Top-2 similarity gap $\ge \delta$ to eliminate lookalike uniform confusion.
                </span>
              </div>

              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '16px' }}>
                <input
                  id="param-save-video"
                  type="checkbox"
                  checked={saveAnnotatedVideo}
                  onChange={(e) => setSaveAnnotatedVideo(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="param-save-video" style={{ fontSize: '13px', color: 'var(--text-main)', cursor: 'pointer' }}>
                  Save annotated bounding-box video output for in-browser playback
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                <button onClick={() => setAnalyzingVideo(null)} className="btn btn-secondary" disabled={startingAnalysis}>
                  Cancel
                </button>
                <button onClick={handleStartAnalysis} className="btn btn-primary" disabled={startingAnalysis}>
                  {startingAnalysis ? 'Submitting Job...' : 'Submit Background Job'}
                </button>
              </div>
            </div>
          </div>
        )}

        {playingJobId && (
          <div className="modal-overlay" role="dialog" aria-modal="true" onClick={handleCloseVideoModal}>
            <div
              className="modal-content"
              style={{ maxWidth: '880px', padding: '24px' }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
                  Annotated Re-ID Surveillance Output (Job {playingJobId.slice(0, 10)})
                </h3>
                <button onClick={handleCloseVideoModal} className="btn btn-secondary" style={{ padding: '4px 10px' }}>
                  ✕
                </button>
              </div>

              {loadingVideoBlob ? (
                <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginRight: '10px' }} />
                  <span>Streaming authorized video stream from facility storage...</span>
                </div>
              ) : jobVideoBlobUrl ? (
                <video
                  src={jobVideoBlobUrl}
                  controls
                  autoPlay
                  style={{ width: '100%', maxHeight: '520px', borderRadius: 'var(--radius-md)', backgroundColor: '#000' }}
                />
              ) : (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-unknown)' }}>
                  Failed to load video stream.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
