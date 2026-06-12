import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * In-card loading message — card chrome should render around this.
 */
export default function PortalCardLoading({
  label = 'Loading…',
  className,
  testId = 'portal-card-loading',
}) {
  return (
    <div
      className={cn('flex items-start gap-2 text-sm text-gray-600 py-1 min-h-[2rem]', className)}
      role="status"
      aria-live="polite"
      data-testid={testId}
    >
      <Loader2 className="w-4 h-4 animate-spin text-electric-teal shrink-0 mt-0.5" aria-hidden />
      <span className="leading-snug break-words">{label}</span>
    </div>
  );
}
