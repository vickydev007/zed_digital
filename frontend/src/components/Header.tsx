'use client';

import React from 'react';
import { Menu, RefreshCw, Radio } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  onToggleSidebar?: () => void;
}

export function Header({
  title,
  subtitle,
  onRefresh,
  isRefreshing = false,
  onToggleSidebar,
}: HeaderProps) {
  const { currentTenant } = useAuth();

  return (
    <header
      style={{
        height: '70px',
        borderBottom: '1px solid var(--border-card)',
        backgroundColor: 'rgba(14, 18, 29, 0.85)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 32px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button
          onClick={onToggleSidebar}
          style={{
            display: 'none',
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '6px',
          }}
          className="mobile-menu-btn"
          aria-label="Toggle navigation menu"
        >
          <Menu size={22} />
        </button>

        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.2px' }}>
            {title}
          </h2>
          {subtitle && (
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{subtitle}</p>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            borderRadius: '9999px',
            backgroundColor: 'var(--bg-card-subtle)',
            border: '1px solid var(--border-subtle)',
            fontSize: '12px',
          }}
        >
          <span className="live-indicator" aria-hidden="true" />
          <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Engine:</span>
          <span style={{ color: 'var(--color-official)', fontWeight: 600 }}>Active (v3.5)</span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 14px',
            borderRadius: '9999px',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            fontSize: '12px',
            color: 'var(--accent-primary)',
            fontWeight: 600,
          }}
        >
          <Radio size={14} />
          <span>{currentTenant?.name || 'Default Facility'}</span>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="btn btn-secondary"
            style={{ padding: '8px 12px', fontSize: '13px' }}
            title="Refresh telemetry and telemetry cache"
            aria-label="Refresh data"
          >
            <RefreshCw
              size={14}
              style={{
                animation: isRefreshing ? 'spin 1s linear infinite' : 'none',
              }}
            />
            <span style={{ display: 'none' }} className="refresh-text">Refresh</span>
          </button>
        )}
      </div>
    </header>
  );
}
