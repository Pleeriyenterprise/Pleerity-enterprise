import React, { useState } from 'react';
import { ChevronDown, Info } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import {
  MOBILE_VIEWPORT_MEDIA_QUERY,
  resolveNaGovernanceDisclosureDefaultOpen,
} from '../hooks/useMobileViewport';

export { resolveNaGovernanceDisclosureDefaultOpen };

/** Full governed copy body (compact paragraph). */
export function notApplicableGovernedCompactCopy() {
  return (
    'The requirement stays on record; it is not deleted. Use only when the obligation genuinely does not apply. ' +
    'Score and tracking views can update after recalculation finishes. Linked evidence and documents may remain on ' +
    'file. You can review or restore to active tracking later from Requirements.'
  );
}

/**
 * Shared governed copy for mark-not-applicable flows (portal).
 * Operational tone; no legal finality; async recalc honesty.
 */
export function NotApplicableGovernedNotice({ variant = 'full' }) {
  if (variant === 'compact') {
    return (
      <p className="text-xs text-gray-600 leading-relaxed" data-testid="governed-not-applicable-compact-copy">
        {notApplicableGovernedCompactCopy()}
      </p>
    );
  }
  return (
    <div className="text-sm text-gray-600 space-y-2" data-testid="governed-not-applicable-copy">
      <p className="font-medium text-gray-800">Before you confirm</p>
      <ul className="list-disc pl-4 space-y-1.5">
        <li>The requirement is not removed from your records.</li>
        <li>Use this only when the obligation genuinely does not apply to this property.</li>
        <li>It may stop affecting compliance tracking and score until recalculation completes.</li>
        <li>Linked evidence and documents can remain on file for audit and operational review.</li>
        <li>You can review or restore to active tracking later if circumstances change.</li>
      </ul>
      <p className="text-xs text-gray-500 pt-1">
        This is an operational record, not a legal determination. Updates may take a short time to appear across
        dashboards.
      </p>
    </div>
  );
}

function readInitialDisclosureOpen() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return resolveNaGovernanceDisclosureDefaultOpen(false);
  }
  return resolveNaGovernanceDisclosureDefaultOpen(window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY).matches);
}

/**
 * Collapsible NA governance notice — collapsed by default on mobile, expanded on desktop.
 * Preserves full compact compliance copy when expanded.
 */
export function NotApplicableGovernedDisclosure() {
  const [open, setOpen] = useState(readInitialDisclosureOpen);

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-md border border-gray-200 bg-white"
      data-testid="na-governed-disclosure"
    >
      <CollapsibleTrigger
        type="button"
        className="flex w-full items-start gap-2 px-3 py-2.5 text-left min-h-[44px] hover:bg-gray-50/80 rounded-md [&[data-state=open]]:rounded-b-none"
        aria-expanded={open}
        data-testid="na-governed-disclosure-trigger"
      >
        <Info className="w-4 h-4 shrink-0 mt-0.5 text-sky-600" aria-hidden />
        <span className="flex-1 min-w-0 text-xs font-medium text-gray-800">Important information</span>
        <span className="flex items-center gap-1 shrink-0 text-xs font-medium text-electric-teal">
          <span data-testid="na-governed-disclosure-toggle-label">{open ? 'Hide details' : 'Show details'}</span>
          <ChevronDown
            className={`w-4 h-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            aria-hidden
          />
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent
        className="border-t border-gray-100 px-3 pb-3 pt-2"
        data-testid="na-governed-disclosure-content"
      >
        <NotApplicableGovernedNotice variant="compact" />
      </CollapsibleContent>
    </Collapsible>
  );
}
