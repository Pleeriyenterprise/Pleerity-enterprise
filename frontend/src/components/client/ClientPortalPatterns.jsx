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

/** Disclosure when cached operational data is shown while a refresh is in flight. */
export function PortalStaleRefreshBanner({ refreshing, className }) {
  if (!refreshing) return null;
  return (
    <p
      className={cn(
        'text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-md px-3 py-2 mb-4',
        'flex items-center gap-2',
        className,
      )}
      role="status"
      data-testid="portal-stale-refresh-banner"
    >
      <Loader2 className="w-3.5 h-3.5 animate-spin text-electric-teal shrink-0" aria-hidden />
      Showing last loaded data while refreshing…
    </p>
  );
}

/** Page chrome visible during progressive hydration (header stays, body skeletons). */
export function PortalPageShell({ title, subtitle, children, actions, refreshing = false, testId }) {
  return (
    <div className={portalPageRoot} data-testid={testId}>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {title ? <h1 className="text-2xl font-bold text-midnight-blue">{title}</h1> : null}
          {subtitle ? <p className="text-sm text-gray-500 mt-1">{subtitle}</p> : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      <PortalStaleRefreshBanner refreshing={refreshing} />
      {children}
    </div>
  );
}

export function PortalSectionSkeleton({ rows = 3, className }) {
  return (
    <div className={cn('space-y-3', className)} data-testid="portal-section-skeleton" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 rounded-lg bg-gray-100 animate-pulse" />
      ))}
    </div>
  );
}

export function PortalWidgetLoading({ label = 'Loading…', className }) {
  return (
    <div
      className={cn('flex items-center gap-2 text-sm text-gray-500 py-6', className)}
      role="status"
      data-testid="portal-widget-loading"
    >
      <Loader2 className="w-4 h-4 animate-spin text-electric-teal" aria-hidden />
      {label}
    </div>
  );
}
