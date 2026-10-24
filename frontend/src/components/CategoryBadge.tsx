import React from 'react';
import { DisplayCategory, IdentityStatus, PassageStatus } from '@/types/api';
import { ShieldCheck, UserPlus, RefreshCw, AlertTriangle } from 'lucide-react';

interface CategoryBadgeProps {
  category?: DisplayCategory | string;
  identityStatus?: IdentityStatus | string;
  passageStatus?: PassageStatus | string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

export function CategoryBadge({
  category,
  identityStatus,
  passageStatus,
  size = 'md',
  showIcon = true,
}: CategoryBadgeProps) {
  let effectiveCategory = category;

  if (!effectiveCategory) {
    if (passageStatus === 'REPEAT_PASSAGE') {
      effectiveCategory = 'PREVIOUSLY_ENROLLED';
    } else if (identityStatus === 'OFFICIAL_WORKER') {
      effectiveCategory = 'OFFICIAL_WORKER';
    } else if (identityStatus === 'NEW_CANDIDATE') {
      effectiveCategory = 'NEW_PERSON';
    } else {
      effectiveCategory = 'UNKNOWN';
    }
  }

  let badgeClass = 'badge-unknown';
  let label = 'Unknown Observation';
  let icon = <AlertTriangle size={14} aria-hidden="true" />;
  let colorDot = '#ef4444';

  switch (effectiveCategory) {
    case 'OFFICIAL_WORKER':
      badgeClass = 'badge-official';
      label = 'Official Worker';
      icon = <ShieldCheck size={14} aria-hidden="true" />;
      colorDot = '#10b981';
      break;
    case 'NEW_PERSON':
    case 'NEW_CANDIDATE':
      badgeClass = 'badge-newperson';
      label = 'New Person (First Seen)';
      icon = <UserPlus size={14} aria-hidden="true" />;
      colorDot = '#06b6d4';
      break;
    case 'PREVIOUSLY_ENROLLED':
    case 'REPEAT_PASSAGE':
      badgeClass = 'badge-repeat';
      label = 'Repeat Passage';
      icon = <RefreshCw size={14} aria-hidden="true" />;
      colorDot = '#f59e0b';
      break;
    case 'UNKNOWN':
    default:
      badgeClass = 'badge-unknown';
      label = 'Unknown / Ambiguous';
      icon = <AlertTriangle size={14} aria-hidden="true" />;
      colorDot = '#ef4444';
      break;
  }

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3.5 py-1.5 gap-2',
  }[size];

  return (
    <span
      className={`${badgeClass} ${sizeClasses}`}
      role="status"
      aria-label={`Category: ${label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        borderRadius: '9999px',
        fontWeight: 600,
        letterSpacing: '0.2px',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: colorDot,
        }}
        aria-hidden="true"
      />
      {showIcon && icon}
      <span>{label}</span>
    </span>
  );
}
