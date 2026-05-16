import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { buildTechnicalDetailsRows } from '../../utils/adminOperationalPresentation';

/**
 * Expandable audit/debug panel — raw canonical values and IDs only here.
 * @param {{ doc: Record<string, unknown>, expanded: boolean, onToggle: () => void, testId?: string }} props
 */
export default function OperationalTechnicalDetailsPanel({ doc, expanded, onToggle, testId }) {
  const rows = buildTechnicalDetailsRows(doc);

  return (
    <div className="mt-2" data-testid={testId}>
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-midnight-blue"
        aria-expanded={expanded}
        data-testid={testId ? `${testId}-toggle` : undefined}
      >
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        Technical details
      </button>
      {expanded && (
        <div
          className="mt-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs font-mono text-gray-800 space-y-1.5 max-w-2xl"
          data-testid={testId ? `${testId}-panel` : undefined}
        >
          {rows.length === 0 ? (
            <p className="text-gray-500 font-sans">No technical metadata recorded yet.</p>
          ) : (
            rows.map((row) => (
              <div key={row.key} className="flex flex-wrap gap-x-2 gap-y-0.5">
                <span className="text-gray-500 shrink-0">{row.label}:</span>
                <span className="break-all">{String(row.value)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
