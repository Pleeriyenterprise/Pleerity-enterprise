import React from 'react';
import { Badge } from '../ui/badge';

/** Shared urgency badge + due/overdue chip for dashboard priority actions, tasks, command centre. */
export function urgencyBadgeClassName(level) {
  const l = (level || '').toLowerCase();
  if (l === 'critical') return 'bg-red-100 text-red-800 border-red-200';
  if (l === 'high') return 'bg-amber-100 text-amber-900 border-amber-200';
  if (l === 'medium') return 'bg-gray-100 text-gray-800 border-gray-200';
  return 'bg-slate-50 text-slate-600 border-slate-100';
}

export function UrgencyBadge({ level, className = '' }) {
  const l = (level || 'medium').toString().toUpperCase();
  return (
    <Badge className={`text-xs font-medium border ${urgencyBadgeClassName(level)} ${className}`} variant="outline">
      {l}
    </Badge>
  );
}

export function DueTimingChip({ timingLabel, className = '' }) {
  if (!timingLabel) return null;
  return (
    <Badge variant="secondary" className={`text-xs font-normal ${className}`}>
      {timingLabel}
    </Badge>
  );
}

export function UrgencyRow({ urgencyLevel, timingLabel, className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <UrgencyBadge level={urgencyLevel} />
      <DueTimingChip timingLabel={timingLabel} />
    </div>
  );
}

/** Calendar-day diff in UTC; matches server-side task timing_label semantics. */
export function timingLabelFromDueAtIso(iso) {
  if (!iso) return null;
  try {
    const due = new Date(iso);
    if (Number.isNaN(due.getTime())) return null;
    const now = new Date();
    const dayMs = 86400000;
    const dueDay = Math.floor(Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate()) / dayMs);
    const nowDay = Math.floor(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()) / dayMs);
    const delta = nowDay - dueDay;
    if (delta > 0) return `Overdue by ${delta} day${delta === 1 ? '' : 's'}`;
    if (delta < 0) return `Due in ${-delta} day${-delta === 1 ? '' : 's'}`;
    return 'Due today';
  } catch {
    return null;
  }
}
