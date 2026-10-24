'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { User, AlertCircle } from 'lucide-react';

interface MediaImageProps {
  src?: string | null;
  alt: string;
  width?: number | string;
  height?: number | string;
  className?: string;
  style?: React.CSSProperties;
}

export function MediaImage({
  src,
  alt,
  width = '100%',
  height = '100%',
  className = '',
  style = {},
}: MediaImageProps) {
  const { token, currentTenant } = useAuth();
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!src);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;

    if (!src) {
      setBlobUrl(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(false);

    api.media
      .fetchBlobUrl(src)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url);
          return;
        }
        createdUrl = url;
        setBlobUrl(url);
        setLoading(false);
      })
      .catch(() => {
        if (active) {
          setError(true);
          setLoading(false);
        }
      });

    return () => {
      active = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [src, token, currentTenant?.id]);

  if (!src || error) {
    return (
      <div
        className={className}
        style={{
          width,
          height,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg-card-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-dim)',
          fontSize: '11px',
          padding: '8px',
          ...style,
        }}
        role="img"
        aria-label={alt}
      >
        {error ? <AlertCircle size={20} /> : <User size={20} />}
        <span style={{ marginTop: '4px' }}>{error ? 'Unavailable' : 'No photo'}</span>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        className={className}
        style={{
          width,
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg-card-subtle)',
          borderRadius: 'var(--radius-md)',
          animation: 'pulse 1.5s infinite ease-in-out',
          ...style,
        }}
        aria-label="Loading image"
      />
    );
  }

  return (
    <img
      src={blobUrl!}
      alt={alt}
      className={className}
      style={{
        width,
        height,
        objectFit: 'cover',
        borderRadius: 'var(--radius-md)',
        ...style,
      }}
    />
  );
}
