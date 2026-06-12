import React from 'react';
import { Inbox } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * Distinct empty-state notice — not used for loading or errors.
 */
export default function PortalEmptyNotice({
  title = 'No actions require attention right now.',
  description,
  className,
  testId = 'portal-empty-notice',
}) {
  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-4 text-sm text-gray-700',
        className,
      )}
      data-testid={testId}
      role="status"
    >
      <div className="flex items-start gap-3">
        <Inbox className="h-5 w-5 text-gray-400 shrink-0 mt-0.5" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium text-midnight-blue">{title}</p>
          {description ? <p className="text-gray-600 mt-1 leading-relaxed">{description}</p> : null}
        </div>
      </div>
    </div>
  );
}
