import React from 'react';

/**
 * Shared governed copy for mark-not-applicable flows (portal).
 * Operational tone; no legal finality; async recalc honesty.
 */
export function NotApplicableGovernedNotice({ variant = 'full' }) {
  if (variant === 'compact') {
    return (
      <p className="text-xs text-gray-600 leading-relaxed">
        The requirement stays on record; it is not deleted. Use only when the obligation genuinely does not apply.
        Score and tracking views can update after recalculation finishes. Linked evidence and documents may remain on
        file. You can review or restore to active tracking later from Requirements.
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
