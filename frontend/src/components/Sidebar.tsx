'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
  LayoutDashboard,
  Footprints,
  Video,
  Film,
  Users,
  UserCheck,
  BarChart3,
  ShieldAlert,
  Building2,
  LogOut,
  ChevronDown,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { currentTenant, userTenants, switchTenant, userRole, logout, user } = useAuth();

  const navItems = [
    { href: '/', label: 'Operations Dashboard', icon: LayoutDashboard },
    { href: '/passage', label: 'Passage Events & Presence', icon: Footprints },
    { href: '/cameras', label: 'CCTV Camera Streams', icon: Video },
    { href: '/videos', label: 'Video Upload & Jobs', icon: Film },
    { href: '/workers', label: 'Worker Directory', icon: Users },
    { href: '/candidates', label: 'Candidate Review', icon: UserCheck },
    { href: '/evaluation', label: 'Empirical Evaluation', icon: BarChart3 },
  ];

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            zIndex: 40,
            backdropFilter: 'blur(4px)',
          }}
          aria-hidden="true"
        />
      )}

      <aside
        style={{
          width: 'var(--sidebar-width)',
          backgroundColor: 'var(--bg-card)',
          borderRight: '1px solid var(--border-card)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 50,
          transition: 'transform 0.3s ease',
          transform: isOpen ? 'translateX(0)' : 'none',
        }}
        className="sidebar-container"
      >
        <div
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(59, 130, 246, 0.4)',
              color: '#fff',
            }}
          >
            <ShieldAlert size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '0.4px' }}>Zed Digital</h1>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Open-Set Re-ID v3.5</p>
          </div>
        </div>

        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <label
            htmlFor="tenant-select"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              color: 'var(--text-dim)',
              marginBottom: '6px',
            }}
          >
            <Building2 size={12} /> Active Facility
          </label>
          <div style={{ position: 'relative' }}>
            <select
              id="tenant-select"
              value={currentTenant?.id || ''}
              onChange={(e) => switchTenant(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 30px 8px 12px',
                backgroundColor: 'var(--bg-deep)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-main)',
                fontSize: '13px',
                fontWeight: 500,
                appearance: 'none',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              {userTenants.map((m) => (
                <option key={m.tenant_id} value={m.tenant_id}>
                  {m.tenant?.name || m.tenant_id} ({m.role})
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
                pointerEvents: 'none',
              }}
            />
          </div>
        </div>

        <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }} aria-label="Main Navigation">
          <ul style={{ listStyle: 'none' }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <li key={item.href} style={{ marginBottom: '4px' }}>
                  <Link
                    href={item.href}
                    onClick={onClose}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '13px',
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? '#fff' : 'var(--text-muted)',
                      backgroundColor: isActive ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                      border: isActive ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Icon size={18} style={{ color: isActive ? 'var(--accent-primary)' : 'inherit' }} />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div
          style={{
            padding: '16px 20px',
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-card-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                {user?.full_name || user?.email}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    color: 'var(--accent-primary)',
                  }}
                >
                  {userRole || 'VIEWER'}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                  {user?.is_superuser ? 'Superuser' : ''}
                </span>
              </div>
            </div>
            <button
              onClick={logout}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
