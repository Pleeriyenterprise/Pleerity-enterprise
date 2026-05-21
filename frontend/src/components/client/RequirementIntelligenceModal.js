import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, ExternalLink } from 'lucide-react';
import { clientAPI } from '../../api/client';
import RequirementSubmissionInspectPanel from './RequirementSubmissionInspectPanel';
import {
  isViewExistingSubmissionCta,
  pickLatestComplianceEvidenceRecord,
} from '../../utils/complianceEvidenceSubmissionView';
import { requirementHasPersistedClientSubmission } from '../../utils/clientPersistedSubmissionPresentation';
import { Button } from '../ui/button';
import { requirementLabel } from '../../domain/presentDomain';
import { mergeRequirementSupportingLinks, resolveRequirementAction } from '../../utils/requirementTakeActionResolver';
import { mergeRequirementIntelPayload, pickWhyItMattersForDisplay } from '../../utils/requirementIntelligenceMerge';
import {
  requirementStatusSummaryForModal,
  humanApplicabilityClientLabel,
  formatAcceptedEvidenceModesForClient,
  activeComplianceJobClientSummary,
} from '../../utils/requirementIntelligenceLabels';
import { formatRiskLabel } from '../../utils/riskLabel';
import { resolveDocumentsPath } from '../../utils/clientPortalNavigation';
import { useGuidedEvidenceModal } from '../../context/GuidedEvidenceModalContext';
import { projectResolvedRequirementSemantics } from '../../utils/resolvedRequirementViewModel';
import { NotApplicableGovernedNotice } from '../../utils/notApplicableGovernedCopy';
import {
  guidedMixedEvidenceInitialMode,
  shouldPreferGuidedEvidenceOverIntelView,
} from '../../utils/rightToRentTrustPresentation';

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

function tenantSafeTriggerExplanation(merged) {
  const te = merged?.trigger_explanation;
  if (typeof te === 'string' && te.trim()) return te.trim();
  return '';
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
 *   initialFocusSubmission?: boolean,
 * }} props
 */
export default function RequirementIntelligenceModal({
  open,
  requirementId,
  seedRequirement = null,
  propertyLabel = null,
  onClose,
  onNavigate,
  onEvidenceSubmitted,
  showEditDatesAndApplicability = false,
  onEditDates,
  onMarkNotApplicable,
  addressForMailto = null,
  initialFocusSubmission = false,
}) {
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const submissionPanelRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [cerLoading, setCerLoading] = useState(false);
  const [hasSubmission, setHasSubmission] = useState(false);

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

  const pid = useMemo(() => {
    const fromPayload = payload?.requirement?.property_id;
    const fromSeed = seedRequirement?.property_id;
    return String(fromPayload || fromSeed || '').trim();
  }, [payload, seedRequirement]);

  const rid = useMemo(() => {
    const fromPayload = payload?.requirement?.requirement_id;
    const fromSeed = seedRequirement?.requirement_id;
    return String(requirementId || fromPayload || fromSeed || '').trim();
  }, [payload, seedRequirement, requirementId]);

  const loadSubmissionPresence = useCallback(() => {
    if (!open || !pid || !rid) {
      setHasSubmission(false);
      return undefined;
    }
    const seedRow = seedRequirement || payload?.requirement;
    if (requirementHasPersistedClientSubmission(seedRow)) {
      setHasSubmission(true);
    }
    let cancelled = false;
    setCerLoading(true);
    clientAPI
      .listComplianceEvidence(pid, rid)
      .then((res) => {
        if (cancelled) return;
        const latest = pickLatestComplianceEvidenceRecord(res?.data?.evidence_records);
        setHasSubmission(Boolean(latest));
      })
      .catch(() => {
        if (!cancelled) setHasSubmission(false);
      })
      .finally(() => {
        if (!cancelled) setCerLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, pid, rid, seedRequirement, payload?.requirement]);

  useEffect(() => loadSubmissionPresence(), [loadSubmissionPresence]);

  const scrollToSubmissionPanel = useCallback(() => {
    const el = submissionPanelRef.current;
    if (!el || typeof el.scrollIntoView !== 'function') return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  useEffect(() => {
    if (!open || !initialFocusSubmission || !hasSubmission || cerLoading) return undefined;
    const t = window.setTimeout(() => scrollToSubmissionPanel(), 120);
    return () => window.clearTimeout(t);
  }, [open, initialFocusSubmission, hasSubmission, cerLoading, scrollToSubmissionPanel]);

  const merged = useMemo(
    () => mergeRequirementIntelPayload(seedRequirement, payload?.requirement),
    [seedRequirement, payload],
  );

  const why = useMemo(() => (merged ? pickWhyItMattersForDisplay(merged) : null), [merged]);
  const statusSummary = useMemo(() => requirementStatusSummaryForModal(merged), [merged]);
  const acceptedEvidenceModes = useMemo(() => formatAcceptedEvidenceModesForClient(merged), [merged]);
  const activeJobSummary = useMemo(
    () => activeComplianceJobClientSummary(payload?.active_compliance_job),
    [payload],
  );
  const supportingLinks = useMemo(() => (merged ? mergeRequirementSupportingLinks(merged) : []), [merged]);
  const resolvedSemantics = useMemo(() => {
    if (!merged || typeof merged.take_action !== 'object') return null;
    return projectResolvedRequirementSemantics(merged, { pagePropertyId: merged?.property_id || null });
  }, [merged]);
  const resolved = useMemo(
    () => (merged ? resolvedSemantics?.cta || resolveRequirementAction(merged, {}) : null),
    [merged, resolvedSemantics],
  );
  const statusEvidenceLine = useMemo(() => {
    if (!merged) return statusSummary.evidenceLine;
    const fromSemantics = resolvedSemantics?.evidenceStatusForStatus(merged.status || merged.compliance_state || 'PENDING')?.subline;
    return fromSemantics || statusSummary.evidenceLine;
  }, [merged, resolvedSemantics, statusSummary.evidenceLine]);

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


  const primaryHandler = () => {
    if (!resolved) return;
    if (isViewExistingSubmissionCta(resolved) && hasSubmission) {
      if (shouldPreferGuidedEvidenceOverIntelView(merged, resolved) && pid && rid) {
        onClose();
        openGuidedEvidence({
          propertyId: pid,
          requirement: merged || { requirement_id: rid },
          initialEvidenceMode:
            resolved.guided_initial_evidence_mode || guidedMixedEvidenceInitialMode() || undefined,
          onSubmitted: () => {
            loadSubmissionPresence();
            onEvidenceSubmitted?.();
          },
        });
        return;
      }
      scrollToSubmissionPanel();
      return;
    }
    if (resolved.primary_action_handler === 'external' && resolved.primary_route) {
      window.open(resolved.primary_route, '_blank', 'noopener,noreferrer');
      return;
    }
    if (resolved.primary_action_handler === 'guided_evidence' && pid && rid) {
      onClose();
      openGuidedEvidence({
        propertyId: pid,
        requirement: merged || { requirement_id: rid },
        initialEvidenceMode: resolved.guided_initial_evidence_mode || undefined,
        onSubmitted: () => {
          loadSubmissionPresence();
          onEvidenceSubmitted?.();
        },
      });
      return;
    }
    if (resolved.primary_route) onNavigate(resolved.primary_route);
  };
  const docsView = pid && rid ? resolveDocumentsPath(pid, { requirement_id: rid }) : pid ? resolveDocumentsPath(pid) : '/documents';
  const docsUpload =
    pid && rid ? resolveDocumentsPath(pid, { requirement_id: rid, focus: 'upload' }) : docsView;
  const primaryLabel = String(resolved?.primary_action_label || '').trim() || 'Take action';

  const showUploadSecondary =
    Boolean(pid && rid) &&
    resolved.primary_route &&
    String(resolved.primary_route).split('?')[0] !== '/documents';

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="view-requirement-modal">
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[min(92dvh,92vh)] flex flex-col overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="requirement-intel-title"
        data-testid="requirement-intel-dialog"
        data-cer-loading={cerLoading ? 'true' : 'false'}
        data-cer-ready={!cerLoading && hasSubmission ? 'true' : 'false'}
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
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Status summary</h3>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <div>
                    <dt className="text-gray-500 text-xs">Action status</dt>
                    <dd className="font-medium text-gray-900" data-testid="requirement-intel-workflow-label">
                      {statusSummary.workflow}
                    </dd>
                  </div>
                  {statusSummary.compliance ? (
                    <div>
                      <dt className="text-gray-500 text-xs">Compliance</dt>
                      <dd className="font-medium text-gray-900" data-testid="requirement-intel-compliance-label">
                        {statusSummary.compliance}
                      </dd>
                    </div>
                  ) : null}
                  {statusEvidenceLine ? (
                    <div>
                      <dt className="text-gray-500 text-xs">Evidence</dt>
                      <dd className="font-medium text-gray-900" data-testid="requirement-intel-evidence-label">
                        {statusEvidenceLine}
                      </dd>
                    </div>
                  ) : null}
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
                  {pickDueOrRenewal(merged) ? (
                    <div className="sm:col-span-2">
                      <dt className="text-gray-500 text-xs">Due / renewal</dt>
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
                      Based on your compliance rule set
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
                  Use the primary action below. It matches the current obligation for this property.
                </p>
              </section>

              {acceptedEvidenceModes && acceptedEvidenceModes.length > 0 ? (
                <section data-testid="requirement-intel-section-accepted-evidence">
                  <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Accepted evidence</h3>
                  <ul className="list-disc list-inside text-gray-800 space-y-1">
                    {acceptedEvidenceModes.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {supportingLinks.length > 0 ? (
                <section data-testid="requirement-intel-section-links">
                  <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Guidance links</h3>
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
                <h3 className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mb-2">Why this applies</h3>
                <p className="text-gray-800" data-testid="requirement-intel-applicability-human">
                  {humanApplicabilityClientLabel(merged.applicability)}
                </p>
                {tenantSafeTriggerExplanation(merged) ? (
                  <p className="text-gray-700 mt-2 text-sm leading-relaxed">{tenantSafeTriggerExplanation(merged)}</p>
                ) : null}
              </section>

              {pid && rid && hasSubmission ? (
                <RequirementSubmissionInspectPanel
                  ref={submissionPanelRef}
                  propertyId={pid}
                  requirementId={rid}
                />
              ) : null}

              {activeJobSummary.navigateJobId ? (
                <section
                  className="rounded-lg border border-amber-200 bg-amber-50/40 p-3"
                  data-testid="requirement-intel-active-job"
                >
                  <p className="text-xs font-semibold text-midnight-blue uppercase tracking-wide">{activeJobSummary.title}</p>
                  {activeJobSummary.lines.length > 0 ? (
                    <ul className="mt-2 text-sm text-gray-800 list-disc list-inside space-y-1">
                      {activeJobSummary.lines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  ) : null}
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    className="mt-2 w-full sm:w-auto min-h-10"
                    data-testid="requirement-intel-open-job"
                    onClick={() => {
                      onClose();
                      onNavigate(`/operations/jobs/${encodeURIComponent(activeJobSummary.navigateJobId)}`);
                    }}
                  >
                    View compliance job
                  </Button>
                </section>
              ) : null}
            </>
          ) : null}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/80 shrink-0 space-y-3">
          {!loading && !error && merged ? (
            <>
              {onMarkNotApplicable ? (
                <div
                  className="rounded-md border border-gray-200 bg-white p-3 mb-1"
                  data-testid="requirement-intel-na-governance"
                >
                  <NotApplicableGovernedNotice variant="compact" />
                </div>
              ) : null}
              <div className="flex flex-col sm:flex-row gap-2 sm:justify-end sm:items-center">
                <Button
                  type="button"
                  className="w-full sm:w-auto min-h-11 bg-midnight-blue hover:bg-midnight-blue/90 text-white"
                  onClick={primaryHandler}
                  disabled={
                    !resolved ||
                    resolved.primary_action_handler === 'guided_evidence_error' ||
                    (!resolved.primary_route &&
                      resolved.primary_action_handler !== 'external' &&
                      resolved.primary_action_handler !== 'guided_evidence')
                  }
                  title={
                    resolved.primary_action_handler === 'guided_evidence_error'
                      ? 'Guided resolution is unavailable: property or requirement context is missing. Use other actions below or contact support.'
                      : undefined
                  }
                  data-testid="requirement-intel-primary-cta"
                >
                  {primaryLabel}
                </Button>
                <Button type="button" variant="outline" className="w-full sm:w-auto min-h-11" onClick={onClose}>
                  Close
                </Button>
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-2 text-xs text-gray-600 justify-end" data-testid="requirement-intel-secondary-actions">
                {hasSubmission ? (
                  <button
                    type="button"
                    className="text-electric-teal hover:underline font-medium"
                    onClick={scrollToSubmissionPanel}
                    data-testid="requirement-intel-view-submission"
                  >
                    View submission
                  </button>
                ) : null}
                {showUploadSecondary ? (
                  <button
                    type="button"
                    className="text-electric-teal hover:underline font-medium"
                    onClick={() => onNavigate(docsUpload)}
                  >
                    Upload document
                  </button>
                ) : null}
                {onMarkNotApplicable ? (
                  <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => onMarkNotApplicable(merged)}>
                    Record as not applicable
                  </button>
                ) : null}
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
