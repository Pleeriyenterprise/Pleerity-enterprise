import React from 'react';
import { cn } from '../../lib/utils';
import { Loader2 } from 'lucide-react';

/** Filters / toolbar: stack on narrow viewports, no horizontal squeeze. */
export function PortalFilterStack({ children, className }) {
  return (
    <div className={cn('flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end', className)}>
      {children}
    </div>
  );
}

/** Primary business-outcome actions (full-width on mobile when inside a card). */
export const portalPrimaryButtonClass =
  'min-h-11 h-11 px-4 font-semibold shadow-sm bg-midnight-blue hover:bg-midnight-blue/90 text-white';

/** Secondary navigation / context. */
export const portalSecondaryButtonClass = 'min-h-11 h-11 px-4 border-gray-200 text-midnight-blue';

/** Triage / inbox-only (snooze, dismiss, mark reviewed). */
export const portalTertiaryButtonClass = 'min-h-10 h-10 px-3 text-sm text-gray-600 border-dashed border-gray-200';

/** Drawer / modal inner panel: safe on small screens. */
export const portalDrawerPanelClass =
  'w-full max-w-lg max-h-[min(100dvh,100vh)] overflow-y-auto bg-white shadow-xl flex flex-col';

/** Root wrapper for pages inside ClientPortal (prevents horizontal bleed, flex shrink). */
export const portalPageRoot = 'w-full min-w-0';

export function PortalLoadingPanel({ message = 'Loading…' }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-16 px-4 text-gray-500 gap-3"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="w-8 h-8 animate-spin text-electric-teal" aria-hidden />
      <p className="text-sm text-center">{message}</p>
    </div>
  );
}
