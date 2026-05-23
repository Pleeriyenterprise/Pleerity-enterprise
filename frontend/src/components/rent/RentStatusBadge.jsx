import React from 'react';
import { Badge } from '../ui/badge';
import { cn } from '@/lib/utils';

const STATUS_STYLES = {
  UPCOMING: 'bg-slate-100 text-slate-700',
  DUE_TODAY: 'bg-amber-100 text-amber-800',
  PAID: 'bg-emerald-100 text-emerald-800',
  PARTIALLY_PAID: 'bg-sky-100 text-sky-800',
  OVERDUE: 'bg-orange-100 text-orange-800',
  SEVERELY_OVERDUE: 'bg-red-100 text-red-800',
  WAIVED: 'bg-gray-100 text-gray-600',
  DISPUTED: 'bg-purple-100 text-purple-800',
};

const STATUS_LABELS = {
  UPCOMING: 'Upcoming',
  DUE_TODAY: 'Due today',
  PAID: 'Paid',
  PARTIALLY_PAID: 'Partial',
  OVERDUE: 'Overdue',
  SEVERELY_OVERDUE: 'Severely overdue',
  WAIVED: 'Waived',
  DISPUTED: 'Disputed',
};

export function RentStatusBadge({ status, className }) {
  const key = (status || '').toUpperCase();
  return (
    <Badge className={cn(STATUS_STYLES[key] || 'bg-gray-100', className)} data-testid={`rent-status-${key}`}>
      {STATUS_LABELS[key] || status || '—'}
    </Badge>
  );
}
