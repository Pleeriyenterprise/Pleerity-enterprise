import React from 'react';
import { isConditionStandardWorkflowHint } from '../../utils/workflowSemantics';

const SIGNAL_LABELS = {
  open_issues: 'Open maintenance issues',
  open_work_orders: 'Open work orders',
  open_risk_signals: 'Open risk signals',
  open_compliance_gaps: 'Open compliance gaps',
};

/**
 * Operational convergence inspect panel for FFHH / Repairing Standard rows.
 * @param {{ requirement: Record<string, unknown> | null | undefined }} props
 */
export default function ConditionStandardOperationalInspectPanel({ requirement }) {
  const row = requirement && typeof requirement === 'object' ? requirement : null;
  if (!row || !isConditionStandardWorkflowHint(row.workflow_class, row)) {
    return null;
  }

  const summary =
    row.active_standard_status_summary && typeof row.active_standard_status_summary === 'object'
      ? row.active_standard_status_summary
      : {};
  const counts =
    summary.signal_counts && typeof summary.signal_counts === 'object' ? summary.signal_counts : {};
  const disclosure = String(row.client_evidence_disclosure || '').trim();
  const stateLabel = String(summary.state_label || row.status_label || 'Awaiting operational review').trim();

  return (
    <section
      className="rounded-lg border border-slate-200 bg-slate-50/80 p-4 space-y-3"
      data-testid="condition-standard-operational-inspect-panel"
    >
      <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide">Operational condition summary</h3>
      <p className="text-sm font-medium text-gray-900" data-testid="condition-standard-state-label">
        {stateLabel}
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        {Object.entries(SIGNAL_LABELS).map(([key, label]) => (
          <div key={key}>
            <dt className="text-gray-500 text-xs">{label}</dt>
            <dd className="font-medium text-gray-900" data-testid={`condition-standard-signal-${key}`}>
              {String(counts[key] ?? 0)}
            </dd>
          </div>
        ))}
      </dl>
      {disclosure ? (
        <p className="text-sm text-gray-700 leading-relaxed" data-testid="condition-standard-disclosure">
          {disclosure}
        </p>
      ) : (
        <p className="text-sm text-gray-700 leading-relaxed" data-testid="condition-standard-disclosure">
          A single uploaded document does not prove this standard is met.
        </p>
      )}
      <p className="text-xs text-gray-600" data-testid="condition-standard-supporting-note">
        Supporting evidence may assist review but does not independently close this property standard.
      </p>
    </section>
  );
}
