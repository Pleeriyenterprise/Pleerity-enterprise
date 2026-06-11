import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { adminAPI } from '../../api/client';
import { runGovernedAdminMutation } from '../../utils/adminGovernedMutation';
import { getGovernanceWarning } from '../../utils/adminActionGovernance';
import { AlertTriangle, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

const SCOPE_LABELS = {
  CLIENT: 'Single client',
  PROPERTY: 'Single property',
  CLIENT_GROUP: 'Selected clients',
  PLAN: 'Plan cohort',
  JURISDICTION: 'Jurisdiction cohort',
  FILTERED_COHORT: 'Filtered cohort',
  PORTFOLIO_WIDE: 'Full portfolio',
};

const STEPS = ['scope', 'targets', 'impact', 'confirm'];

function buildPreviewBody(jobId, state) {
  const body = {
    job: jobId,
    scope_type: state.scopeType,
    portfolio_wide: state.scopeType === 'PORTFOLIO_WIDE',
    portfolio_wide_confirmed: state.portfolioConfirmed,
  };
  if (state.scopeType === 'CLIENT') body.client_id = state.clientId;
  if (state.scopeType === 'CLIENT_GROUP') body.client_ids = state.clientIds;
  if (state.scopeType === 'PROPERTY') body.property_id = state.propertyId;
  if (state.scopeType === 'PLAN') body.plan_code = state.planCode;
  if (state.scopeType === 'JURISDICTION') body.jurisdiction = state.jurisdiction;
  if (state.scopeType === 'FILTERED_COHORT') body.cohort_filter = state.cohortFilter;
  if (state.propertyIds?.length) body.property_ids = state.propertyIds;
  return body;
}

function buildRunBody(jobId, state, reason) {
  return { ...buildPreviewBody(jobId, state), reason: reason.trim() };
}

export function ManualJobExecutionModal({ jobId, onClose, onSuccess }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [governance, setGovernance] = useState(null);
  const [loadingGov, setLoadingGov] = useState(true);
  const [clients, setClients] = useState([]);
  const [scopeType, setScopeType] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientIds, setClientIds] = useState([]);
  const [propertyId, setPropertyId] = useState('');
  const [propertyIds, setPropertyIds] = useState([]);
  const [planCode, setPlanCode] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [cohortFilter, setCohortFilter] = useState('');
  const [portfolioConfirmed, setPortfolioConfirmed] = useState(false);
  const [reason, setReason] = useState('');
  const [impact, setImpact] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executeConfirmed, setExecuteConfirmed] = useState(false);

  const state = useMemo(
    () => ({
      scopeType,
      clientId,
      clientIds,
      propertyId,
      propertyIds,
      planCode,
      jurisdiction,
      cohortFilter,
      portfolioConfirmed,
    }),
    [scopeType, clientId, clientIds, propertyId, propertyIds, planCode, jurisdiction, cohortFilter, portfolioConfirmed],
  );

  useEffect(() => {
    if (!jobId) return;
    setLoadingGov(true);
    Promise.all([
      adminAPI.getJobExecutionGovernance(jobId).then((r) => r.data),
      adminAPI.getClients(0, 200).then((r) => r.data?.clients || r.data || []),
    ])
      .then(([gov, clientRows]) => {
        setGovernance(gov);
        setClients(clientRows);
        const first = (gov?.allowed_scopes || [])[0] || '';
        setScopeType(first);
      })
      .catch(() => toast.error('Failed to load job execution governance'))
      .finally(() => setLoadingGov(false));
  }, [jobId]);

  const allowedScopes = governance?.allowed_scopes || [];

  const targetsValid = useCallback(() => {
    if (!scopeType) return false;
    if (scopeType === 'CLIENT') return Boolean(clientId.trim());
    if (scopeType === 'CLIENT_GROUP') return clientIds.length > 0;
    if (scopeType === 'PROPERTY') return Boolean(propertyId.trim());
    if (scopeType === 'PLAN') return Boolean(planCode);
    if (scopeType === 'JURISDICTION') return Boolean(jurisdiction.trim());
    if (scopeType === 'FILTERED_COHORT') return Boolean(cohortFilter);
    if (scopeType === 'PORTFOLIO_WIDE') return portfolioConfirmed;
    return false;
  }, [scopeType, clientId, clientIds, propertyId, planCode, jurisdiction, cohortFilter, portfolioConfirmed]);

  const loadImpact = useCallback(async () => {
    setImpactLoading(true);
    try {
      const res = await adminAPI.previewJobExecution(buildPreviewBody(jobId, state));
      setImpact(res.data);
      if (!res.data?.ok) {
        toast.error(res.data?.error || 'Could not estimate impact');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Impact preview failed');
      setImpact(null);
    } finally {
      setImpactLoading(false);
    }
  }, [jobId, state]);

  useEffect(() => {
    if (STEPS[stepIndex] === 'impact' && targetsValid()) {
      loadImpact();
    }
  }, [stepIndex, loadImpact, targetsValid]);

  const goNext = () => {
    const step = STEPS[stepIndex];
    if (step === 'scope' && !scopeType) {
      toast.error('Select an execution scope');
      return;
    }
    if (step === 'targets' && !targetsValid()) {
      toast.error('Complete required targets for this scope');
      return;
    }
    if (step === 'confirm') return;
    setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  };

  const goBack = () => setStepIndex((i) => Math.max(i - 1, 0));

  const handleExecute = async () => {
    if (!executeConfirmed) {
      toast.error('Confirm execution before running');
      return;
    }
    if (reason.trim().length < 10) {
      toast.error('Support reason of at least 10 characters is required');
      return;
    }
    const actionId = scopeType === 'PORTFOLIO_WIDE' ? 'run_portfolio_wide_job' : 'run_scoped_automation_job';
    setExecuting(true);
    try {
      const body = buildRunBody(jobId, state, reason);
      const res = await runGovernedAdminMutation({
        actionId,
        reason: reason.trim(),
        resourceKey: `${jobId}:${clientId || scopeType}`,
        mutate: (headers) => adminAPI.runJobNow(body, { headers }),
      });
      toast.success(res.data?.message || `Job ${jobId} completed`);
      onSuccess?.(res.data);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || `Failed to run ${jobId}`);
    } finally {
      setExecuting(false);
    }
  };

  const toggleClientInGroup = (id) => {
    setClientIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  if (!jobId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
      <div className="bg-white rounded-lg shadow-xl max-w-xl w-full m-4 p-4 space-y-4 max-h-[90vh] overflow-y-auto" data-testid="manual-job-execution-modal">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Run job</h2>
            <p className="text-sm text-gray-500 font-mono">{jobId}</p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-800">Close</button>
        </div>

        <div className="flex gap-1 text-xs">
          {STEPS.map((s, i) => (
            <span
              key={s}
              className={`px-2 py-0.5 rounded ${i === stepIndex ? 'bg-electric-teal text-white' : i < stepIndex ? 'bg-teal-50 text-teal-800' : 'bg-gray-100 text-gray-500'}`}
            >
              {i + 1}. {s}
            </span>
          ))}
        </div>

        {loadingGov ? (
          <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
        ) : (
          <>
            {STEPS[stepIndex] === 'scope' && (
              <div className="space-y-2" data-testid="job-exec-step-scope">
                <p className="text-sm text-gray-600">Choose execution scope. Unsupported scopes are not shown.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {allowedScopes.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setScopeType(s)}
                      className={`text-left px-3 py-2 rounded border text-sm ${scopeType === s ? 'border-electric-teal bg-teal-50' : 'border-gray-200 hover:bg-gray-50'}`}
                      data-testid={`scope-${s}`}
                    >
                      <span className="font-medium">{SCOPE_LABELS[s] || s}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {STEPS[stepIndex] === 'targets' && (
              <div className="space-y-3" data-testid="job-exec-step-targets">
                {scopeType === 'CLIENT' && (
                  <>
                    <label className="block text-sm font-medium">Client</label>
                    <select className="w-full border rounded px-3 py-2 text-sm" value={clientId} onChange={(e) => setClientId(e.target.value)} data-testid="job-exec-client-select">
                      <option value="">Select client</option>
                      {clients.map((c) => (
                        <option key={c.client_id} value={c.client_id}>{c.company_name || c.full_name || c.email || c.client_id}</option>
                      ))}
                    </select>
                    {governance?.accepts_property_ids_filter && clientId && (
                      <div>
                        <label className="block text-sm font-medium mt-2">Property subset (optional, comma-separated IDs)</label>
                        <input
                          className="w-full border rounded px-3 py-2 text-sm font-mono"
                          placeholder="property-uuid-1, property-uuid-2"
                          value={propertyIds.join(', ')}
                          onChange={(e) =>
                            setPropertyIds(
                              e.target.value
                                .split(',')
                                .map((s) => s.trim())
                                .filter(Boolean),
                            )
                          }
                        />
                      </div>
                    )}
                  </>
                )}
                {scopeType === 'CLIENT_GROUP' && (
                  <div className="max-h-48 overflow-y-auto border rounded p-2 space-y-1">
                    {clients.map((c) => (
                      <label key={c.client_id} className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={clientIds.includes(c.client_id)} onChange={() => toggleClientInGroup(c.client_id)} />
                        {c.company_name || c.email || c.client_id}
                      </label>
                    ))}
                  </div>
                )}
                {scopeType === 'PROPERTY' && (
                  <input className="w-full border rounded px-3 py-2 text-sm font-mono" placeholder="Property ID" value={propertyId} onChange={(e) => setPropertyId(e.target.value)} data-testid="job-exec-property-id" />
                )}
                {scopeType === 'PLAN' && (
                  <select className="w-full border rounded px-3 py-2 text-sm" value={planCode} onChange={(e) => setPlanCode(e.target.value)}>
                    <option value="">Select plan</option>
                    {(governance?.plan_options || []).map((p) => (
                      <option key={p.code} value={p.code}>{p.label}</option>
                    ))}
                  </select>
                )}
                {scopeType === 'JURISDICTION' && (
                  <input className="w-full border rounded px-3 py-2 text-sm uppercase" placeholder="e.g. EW, SCT, WLS" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} />
                )}
                {scopeType === 'FILTERED_COHORT' && (
                  <select className="w-full border rounded px-3 py-2 text-sm" value={cohortFilter} onChange={(e) => setCohortFilter(e.target.value)}>
                    <option value="">Select filter</option>
                    {(governance?.cohort_filter_options || []).map((o) => (
                      <option key={o.key} value={o.key}>{o.label}</option>
                    ))}
                  </select>
                )}
                {scopeType === 'PORTFOLIO_WIDE' && (
                  <div className="space-y-2">
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 flex gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>{getGovernanceWarning('run_portfolio_wide_job')}</span>
                    </div>
                    <label className="flex items-start gap-2 text-sm">
                      <input type="checkbox" checked={portfolioConfirmed} onChange={(e) => setPortfolioConfirmed(e.target.checked)} data-testid="job-exec-portfolio-confirmed" />
                      I confirm portfolio-wide execution for all eligible customers
                    </label>
                  </div>
                )}
              </div>
            )}

            {STEPS[stepIndex] === 'impact' && (
              <div className="space-y-2" data-testid="job-exec-step-impact">
                {impactLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /> Estimating impact…</div>
                ) : impact?.ok ? (
                  <ul className="text-sm text-gray-700 space-y-1 list-disc pl-5">
                    {(impact.estimates?.summary_lines || []).map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-red-600">{impact?.error || 'Impact preview unavailable'}</p>
                )}
              </div>
            )}

            {STEPS[stepIndex] === 'confirm' && (
              <div className="space-y-3" data-testid="job-exec-step-confirm">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div><strong>Scope:</strong> {SCOPE_LABELS[scopeType] || scopeType}</div>
                  {impact?.estimates?.summary_lines?.[0] && <div className="mt-1 text-gray-600">{impact.estimates.summary_lines[0]}</div>}
                </div>
                <textarea
                  className="w-full border rounded px-3 py-2 text-sm min-h-[72px]"
                  placeholder="Support reason (min 10 characters)"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  data-testid="job-exec-reason"
                />
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" checked={executeConfirmed} onChange={(e) => setExecuteConfirmed(e.target.checked)} data-testid="job-exec-final-confirm" />
                  I have reviewed scope and impact and want to execute this job
                </label>
              </div>
            )}
          </>
        )}

        <div className="flex justify-between gap-2 pt-2 border-t">
          <button type="button" onClick={stepIndex === 0 ? onClose : goBack} className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
            {stepIndex === 0 ? 'Cancel' : <><ChevronLeft className="w-4 h-4" /> Back</>}
          </button>
          {STEPS[stepIndex] !== 'confirm' ? (
            <button type="button" onClick={goNext} className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-electric-teal text-white rounded hover:opacity-90" data-testid="job-exec-next">
              Next <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleExecute}
              disabled={executing || !executeConfirmed || reason.trim().length < 10}
              className="px-3 py-1.5 text-sm bg-electric-teal text-white rounded hover:opacity-90 disabled:opacity-50"
              data-testid="job-exec-run"
            >
              {executing ? 'Running…' : scopeType === 'PORTFOLIO_WIDE' ? 'Run portfolio-wide' : 'Execute'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ManualJobExecutionModal;
