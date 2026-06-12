import React, { useId, useMemo } from 'react';
import { Check, Circle, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PORTAL_LOADING_FOOTER_NOTE } from './portalLoadingStageModels';
import { usePortalLoadingStages } from './usePortalLoadingStages';

function StageIcon({ status }) {
  if (status === 'complete') {
    return <Check className="w-4 h-4 text-teal-700 shrink-0" aria-hidden />;
  }
  if (status === 'active') {
    return <Loader2 className="w-4 h-4 animate-spin text-electric-teal shrink-0" aria-hidden />;
  }
  return <Circle className="w-4 h-4 text-gray-300 shrink-0" aria-hidden />;
}

function stagePrefix(status) {
  if (status === 'complete') return 'Completed';
  if (status === 'active') return 'In progress';
  return 'Pending';
}

/**
 * Shared portal loading experience with staged progress copy.
 */
export default function PortalLoadingState({
  title = 'Building your workspace…',
  subtitle,
  stages: stageDefs = [],
  footerNote = PORTAL_LOADING_FOOTER_NOTE,
  isActive = true,
  variant = 'section',
  showSkeleton = true,
  skeletonRows = 3,
  className,
  testId = 'portal-loading-state',
}) {
  const labelId = useId();
  const stages = usePortalLoadingStages(stageDefs, isActive);
  const liveMessage = useMemo(() => {
    const active = stages.find((s) => s.status === 'active');
    if (active) return `${active.label}…`;
    const lastDone = [...stages].reverse().find((s) => s.status === 'complete');
    return lastDone ? `${lastDone.label} complete` : title;
  }, [stages, title]);

  return (
    <div
      className={cn(
        'rounded-xl border border-gray-200 bg-white shadow-sm',
        variant === 'page' ? 'p-4 sm:p-5' : 'p-3 sm:p-4',
        className,
      )}
      data-testid={testId}
      role="status"
      aria-live="polite"
      aria-labelledby={labelId}
    >
      <p id={labelId} className="text-base sm:text-lg font-semibold text-midnight-blue leading-snug">
        {title}
      </p>
      {subtitle ? <p className="text-sm text-gray-600 mt-1 leading-relaxed">{subtitle}</p> : null}

      {stages.length > 0 ? (
        <ul className="mt-4 space-y-2.5" aria-label="Loading progress">
          {stages.map((stage) => (
            <li key={stage.id} className="flex items-start gap-2.5 text-sm min-w-0">
              <StageIcon status={stage.status} />
              <span
                className={cn(
                  'leading-snug break-words',
                  stage.status === 'complete' ? 'text-gray-600' : 'text-gray-800',
                )}
              >
                <span className="sr-only">{stagePrefix(stage.status)}: </span>
                {stage.label}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {footerNote ? (
        <p className="text-xs text-gray-500 mt-4 leading-relaxed">{footerNote}</p>
      ) : null}

      <span className="sr-only" aria-live="polite">
        {liveMessage}
      </span>

      {showSkeleton ? (
        <div className="mt-4 space-y-2" aria-hidden>
          {Array.from({ length: skeletonRows }).map((_, i) => (
            <div key={i} className="h-12 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      ) : null}
    </div>
  );
}
