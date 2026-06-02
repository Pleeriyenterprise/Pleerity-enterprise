import React from 'react';
import { resolveAssuranceTier, assuranceTierSummary } from '../../utils/assurancePresentation';

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(value);
  }
}

/**
 * Read-only assurance context inside the requirement intelligence modal.
 */
export default function RequirementModalAssuranceSection({ merged, latestCer }) {
  const tier = resolveAssuranceTier(merged);
  const summary = assuranceTierSummary(tier);
  const submittedAt = latestCer?.created_at || merged?.evidence_last_submitted_at;
  const submittedBy = latestCer?.created_by_user_id || null;

  return (
    <section
      className="rounded-lg border border-slate-200 bg-slate-50/80 p-4 space-y-3"
      data-testid="requirement-modal-assurance-section"
      data-assurance-tier={tier}
    >
      <div>
        <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-1">Assurance</h3>
        <p className="text-sm font-medium text-gray-900" data-testid="assurance-tier-title">
          {summary.title}
        </p>
        <p className="text-sm text-gray-700 mt-1" data-testid="assurance-tier-guidance">
          {summary.guidance}
        </p>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-2 text-sm">
        <div>
          <dt className="text-xs text-gray-500">Recorded</dt>
          <dd className="font-medium text-gray-900">{formatDate(submittedAt)}</dd>
        </div>
        {submittedBy ? (
          <div>
            <dt className="text-xs text-gray-500">Submitter (user id)</dt>
            <dd className="font-medium text-gray-900 break-all">{submittedBy}</dd>
          </div>
        ) : null}
        {merged?.truth_presentation_label ? (
          <div className="sm:col-span-2">
            <dt className="text-xs text-gray-500">Status</dt>
            <dd className="font-medium text-gray-900">{merged.truth_presentation_label}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
