import React from 'react';
import { X } from 'lucide-react';
import { ScaleAutomationCallout } from './PlanGatingDiscoverability';
import { propagationNoticeForUi } from '../../utils/propagationNoticePresentation';
import { cn } from '../../lib/utils';

/**
 * Dismissible, async-honest callout when API returns optional `propagation_notice` (L-009).
 * Presentation only — no entitlement or authority changes.
 */
export default function PropagationNoticeCallout({ notice, onDismiss, className = '' }) {
  const ui = propagationNoticeForUi(notice);
  if (!ui) return null;

  return (
    <div
      className={cn('flex gap-2 rounded-lg border border-slate-200 bg-slate-50/90 p-3 text-sm text-slate-700 shadow-sm', className)}
      data-testid="propagation-notice-callout"
      data-propagation-code={ui.code || ''}
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium text-midnight-blue">{ui.headline}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600">{ui.body}</p>
      </div>
      {typeof onDismiss === 'function' ? (
        <button
          type="button"
          className="h-8 w-8 shrink-0 rounded text-slate-500 hover:bg-white hover:text-midnight-blue"
          onClick={onDismiss}
          aria-label="Dismiss notice"
        >
          <X className="mx-auto h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}
