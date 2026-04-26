import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, ExternalLink } from 'lucide-react';
import { clientAPI } from '../../api/client';
import { Button } from '../ui/button';
import { requirementLabel } from '../../domain/presentDomain';
import { mergeRequirementSupportingLinks, resolveRequirementAction } from '../../utils/requirementTakeActionResolver';
import { mergeRequirementIntelPayload, pickWhyItMattersForDisplay } from '../../utils/requirementIntelligenceMerge';
import { requirementWorkflowDisplayPair, humanEvidenceStateLabel } from '../../utils/requirementIntelligenceLabels';
import { formatRiskLabel } from '../../utils/riskLabel';
import { resolveDocumentsPath } from '../../utils/clientPortalNavigation';
import { SUPPORT_EMAIL } from '../../config';

function formatIntelDate(value) {
  if (value == null || value === '') return null;
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

function pickDueOrRenewal(merged) {
  const raw =
    merged.confirmed_expiry_date ||
    merged.extracted_expiry_date ||
    merged.due_date ||
    merged.renewal_date ||
    merged.next_review_date ||
    null;
  const label = merged.confirmed_expiry_date ? 'Renewal / confirmed date' : 'Due / renewal date';
  const formatted = formatIntelDate(raw);
  return formatted ? `${label}: ${formatted}` : null;
}

function triggerExplanationLines(merged) {
  const te = merged.trigger_explanation;
  if (!te) return [];
  if (typeof te === 'string' && te.trim()) return [te.trim()];
  if (typeof te !== 'object') return [];
  const lines = [];
  if (te.property_jurisdiction) lines.push(`Property jurisdiction: ${te.property_jurisdiction}`);
  if (te.jurisdiction_basis) lines.push(`Jurisdiction basis: ${String(te.jurisdiction_basis).replace(/_/g, ' ')}`);
  if (te.requirement_type) lines.push(`Requirement type: ${te.requirement_type}`);
  return lines;
}

/**
 * @param {{
 *   open: boolean,
 *   requirementId: string | null,
 *   seedRequirement?: Record<string, unknown> | null,
 *   propertyLabel?: string | null,
 *   onClose: () => void,
 *   onNavigate: (path: string) => void,
 *   showEditDatesAndApplicability?: boolean,
 *   onEditDates?: (merged: Record<string, unknown>) => void,
 *   onMarkNotApplicable?: (merged: Record<string, unknown>) => void,
 *   addressForMailto?: string | null,
 * }} props
 */
export default function RequirementIntelligenceModal({
  open,
  requirementId,
  seedRequirement = null,
  propertyLabel = null,
  onClose,
  onNavigate,
  showEditDatesAndApplicability = false,
  onEditDates,
  onMarkNotApplicable,
  addressForMailto = null,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);

  const load = useCallback(() => {
    if (!open || !requirementId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError('');
    setPayload(null);
    clientAPI
      .getRequirementWorkflow(requirementId)
      .then((r) => {
        if (!cancelled) setPayload(r.data || null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message || 'Could not load requirement');
          setPayload(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, requirementId]);

  useEffect(() => {
    return load();
  }, [load]);

  const merged = useMemo(
    () => mergeRequirementIntelPayload(seedRequirement, payload?.requirement),
    [seedRequirement, payload],
  );

  const why = useMemo(() => (merged ? pickWhyItMattersForDisplay(merged) : null), [merged]);
  const statusPair = useMemo(() => requirementWorkflowDisplayPair(merged), [merged]);
  const supportingLinks = useMemo(() => (merged ? mergeRequirementSupportingLinks(merged) : []), [merged]);
  const resolved = useMemo(() => resolveRequirementAction(merged, {}), [merged]);

  const displayTitle = useMemo(() => {
    if (!merged) return 'Requirement';
    const dl = String(merged.display_label || merged.display_name || '').trim();
    if (dl) return dl;
    return requirementLabel(merged.requirement_type || merged.requirement_code || '') || 'Requirement';
  }, [merged]);

  const propertyLine = useMemo(() => {
    const fromMerged = String(merged?.property_label || '').trim();
    if (fromMerged) return fromMerged;
    if (propertyLabel && String(propertyLabel).trim()) return String(propertyLabel).trim();
    return null;
  }, [merged, propertyLabel]);

  const riskLine = useMemo(() => {
    if (!merged) return null;
    const r = merged.criticality || merged.risk_level || merged.risk;
    if (!r) return null;
    return formatRiskLabel(String(r));
  }, [merged]);

  const evidenceLine = useMemo(() => {
    if (!merged?.evidence_state) return null;
    return humanEvidenceStateLabel(merged.evidence_state);
  }, [merged]);

  const primaryHandler = () => {
    if (resolved.primary_action_handler === 'external' && resolved.primary_route) {
      window.open(resolved.primary_route, '_blank', 'noopener,noreferrer');
      return;
    }
    if (resolved.primary_route) onNavigate(resolved.primary_route);
  };

  const pid = merged?.property_id ? String(merged.property_id) : '';
  const rid = merged?.requirement_id ? String(merged.requirement_id) : '';
  const docsView = pid && rid ? resolveDocumentsPath(pid, { requirement_id: rid }) : pid ? resolveDocumentsPath(pid) : '/documents';
  const docsUpload =
    pid && rid ? resolveDocumentsPath(pid, { requirement_id: rid, focus: 'upload' }) : docsView;
  const propertyCompliance = pid ? `/properties/${encodeURIComponent(pid)}#compliance` : null;
  const mailQuery = addressForMailto
    ? `?subject=${encodeURIComponent(`Support request: ${addressForMailto}`)}`
    : `?subject=${encodeURIComponent('Support request: requirement')}`;

  const primaryLabel = String(resolved.primary_action_label || '').trim() || 'Take action';

  const showUploadSecondary =
    Boolean(pid && rid) &&
    resolved.primary_route &&
    String(resolved.primary_route).split('?')[0] !== '/documents';

  const showBookSecondary =
    Boolean(propertyCompliance) &&
    (String(merged?.compliance_requirement_class || '').toUpperCase() === 'JOB' ||
      String(merged?.engine_fulfillment_mode || merged?.fulfillment_mode || '').toLowerCase() === 'job');

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="view-requirement-modal">
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[min(92dvh,92vh)] flex flex-col overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="requirement-intel-title"
      >
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 shrink-0">
          <h2 id="requirement-intel-title" className="text-lg font-semibold text-midnight-blue">
            Requirement details
          </h2>
          <p className="text-sm font-medium text-gray-900 mt-1">{displayTitle}</p>
          {propertyLine ? <p className="text-sm text-gray-600 mt-0.5">{propertyLine}</p> : null}
        </div>

        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-5 text-sm">
          {loading ? (
            <div className="flex items-center gap-2 text-gray-500 py-10" data-testid="requirement-intel-loading">
              <Loader2 className="w-5 h-5 animate-spin shrink-0" aria-hidden />
              Loading…
            </div>
          ) : null}
          {error ? (
            <p className="text-sm text-red-700" data-testid="requirement-intel-error">
              {typeof error === 'string' ? error : 'Could not load requirement'}
            </p>
          ) : null}

          {!loading && !error && merged ? (
            <>
              <section data-testid="requirement-intel-section-status">
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Current status</h3>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <div>
                    <dt className="text-gray-500 text-xs">Workflow</dt>
                    <dd className="font-medium text-gray-900" data-testid="requirement-intel-workflow-label">
                      {statusPair.workflow}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 text-xs">Compliance</dt>
                    <dd className="font-medium text-gray-900" data-testid="requirement-intel-compliance-label">
                      {statusPair.compliance}
                    </dd>
                  </div>
                  {merged.property_jurisdiction ? (
                    <div className="sm:col-span-2">
                      <dt className="text-gray-500 text-xs">Jurisdiction</dt>
                      <dd className="font-medium text-gray-900">{String(merged.property_jurisdiction)}</dd>
                    </div>
                  ) : null}
                  {riskLine ? (
                    <div>
                      <dt className="text-gray-500 text-xs">Risk / criticality</dt>
                      <dd className="font-medium text-gray-900">{riskLine}</dd>
                    </div>
                  ) : null}
                  {evidenceLine ? (
                    <div>
                      <dt className="text-gray-500 text-xs">Evidence</dt>
                      <dd className="font-medium text-gray-900">{evidenceLine}</dd>
                    </div>
                  ) : null}
                  {pickDueOrRenewal(merged) ? (
                    <div className="sm:col-span-2">
                      <dt className="text-gray-500 text-xs">Timing</dt>
                      <dd className="font-medium text-gray-900">{pickDueOrRenewal(merged)}</dd>
                    </div>
                  ) : null}
                </dl>
              </section>

              {why && (why.short || why.long) ? (
                <section data-testid="requirement-intel-section-why">
                  <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Why this matters</h3>
                  {why.source === 'published_jurisdiction' && why.jurisdictionRulesLabel ? (
                    <p className="text-xs text-teal-800 font-medium mb-1" data-testid="requirement-intel-jurisdiction-why-badge">
                      Based on {why.jurisdictionRulesLabel} rules
                    </p>
                  ) : null}
                  {why.source === 'published' ? (
                    <p className="text-xs text-teal-800 font-medium mb-1" data-testid="requirement-intel-published-why-badge">
                      From published registry
                    </p>
                  ) : null}
                  {why.short ? (
                    <p className="text-gray-800 leading-relaxed" data-testid="requirement-intel-why-short">
                      {why.short}
                    </p>
                  ) : null}
                  {why.long && why.long !== why.short ? (
                    <p className="text-gray-700 leading-relaxed mt-2 text-sm" data-testid="requirement-intel-why-long">
                      {why.long}
                    </p>
                  ) : null}
                </section>
              ) : null}

              <section data-testid="requirement-intel-section-what">
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">What you need to do</h3>
                <p className="text-gray-800">
                  Follow the primary action below. It reflects the current obligation for this property.
                </p>
                {merged.take_action?.provenance?.primary_label ? (
                  <p className="text-xs text-gray-500 mt-2">
                    Source: {String(merged.take_action.provenance.primary_label)}
                  </p>
                ) : null}
              </section>

              {supportingLinks.length > 0 ? (
                <section data-testid="requirement-intel-section-links">
                  <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Supporting action links</h3>
                  <ul className="space-y-2" data-testid="requirement-intel-action-links">
                    {supportingLinks.map((link, idx) => {
                      const url = String(link.url || '').trim();
                      const label = String(link.label || link.key || 'Link').trim();
                      if (!url) return null;
                      return (
                        <li key={`${url}-${idx}`}>
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-electric-teal hover:underline inline-flex items-center gap-1 break-all"
                          >
                            {label}
                            <ExternalLink className="w-3.5 h-3.5 shrink-0" aria-hidden />
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}

              <section data-testid="requirement-intel-section-applicability">
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">
                  Applicability / why this applies
                </h3>
                {merged.applicability ? (
                  <p className="text-gray-800">
                    <span className="text-gray-500">Applicability: </span>
                    {String(merged.applicability).replace(/_/g, ' ')}
                  </p>
                ) : null}
                {triggerExplanationLines(merged).length > 0 ? (
                  <ul className="list-disc list-inside text-gray-700 mt-2 space-y-1">
                    {triggerExplanationLines(merged).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-600 text-sm">This requirement is included for this property based on your plan and jurisdiction rules.</p>
                )}
              </section>

              <section data-testid="requirement-intel-section-audit">
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Audit / source details</h3>
                <dl className="space-y-1 text-sm text-gray-700">
                  {merged.source ? (
                    <div>
                      <dt className="text-gray-500 text-xs inline mr-1">Source</dt>
                      <dd className="inline">{String(merged.source)}</dd>
                    </div>
                  ) : null}
                  {merged.registry_metadata?.primary_action_mode ? (
                    <div data-testid="requirement-intel-published-cta-mode">
                      <dt className="text-gray-500 text-xs inline mr-1">Published primary action mode</dt>
                      <dd className="inline">{String(merged.registry_metadata.primary_action_mode)}</dd>
                    </div>
                  ) : null}
                  {merged.cta_action_mode ? (
                    <div>
                      <dt className="text-gray-500 text-xs inline mr-1">Resolved CTA mode</dt>
                      <dd className="inline">{String(merged.cta_action_mode)}</dd>
                    </div>
                  ) : null}
                </dl>
              </section>

              {payload?.active_compliance_job?.job_id ? (
                <section className="rounded-lg border border-amber-200 bg-amber-50/40 p-3">
                  <p className="text-xs font-semibold text-midnight-blue uppercase tracking-wide">Active compliance job</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    className="mt-2 w-full sm:w-auto min-h-10"
                    onClick={() => {
                      const jid = payload.active_compliance_job.job_id;
                      onClose();
                      onNavigate(`/operations/jobs/${jid}`);
                    }}
                  >
                    Open job {String(payload.active_compliance_job.job_id).slice(0, 8)}…
                  </Button>
                </section>
              ) : null}
            </>
          ) : null}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/80 shrink-0 space-y-3">
          {!loading && !error && merged ? (
            <>
              <div className="flex flex-col sm:flex-row gap-2 sm:justify-end sm:items-center">
                <Button
                  type="button"
                  className="w-full sm:w-auto min-h-11 bg-midnight-blue hover:bg-midnight-blue/90 text-white"
                  onClick={primaryHandler}
                  disabled={!resolved.primary_route && resolved.primary_action_handler !== 'external'}
                  data-testid="requirement-intel-primary-cta"
                >
                  {primaryLabel}
                </Button>
                <Button type="button" variant="outline" className="w-full sm:w-auto min-h-11" onClick={onClose}>
                  Close
                </Button>
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-2 text-xs text-gray-600 justify-end" data-testid="requirement-intel-secondary-actions">
                {showUploadSecondary ? (
                  <button
                    type="button"
                    className="text-electric-teal hover:underline font-medium"
                    onClick={() => onNavigate(docsUpload)}
                  >
                    Upload document
                  </button>
                ) : null}
                {showBookSecondary && propertyCompliance ? (
                  <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => onNavigate(propertyCompliance)}>
                    Book inspection / job
                  </button>
                ) : null}
                {onMarkNotApplicable ? (
                  <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => onMarkNotApplicable(merged)}>
                    Mark as not applicable
                  </button>
                ) : null}
                <a href={`mailto:${SUPPORT_EMAIL}${mailQuery}`} className="text-electric-teal hover:underline font-medium">
                  Request help
                </a>
                {pid ? (
                  <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => onNavigate(docsView)}>
                    View documents
                  </button>
                ) : null}
                {showEditDatesAndApplicability && onEditDates ? (
                  <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => onEditDates(merged)}>
                    Edit dates and applicability
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={onClose}>
                Close
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
