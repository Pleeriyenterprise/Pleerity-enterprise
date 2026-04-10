/**
 * Admin Ops → Job detail: full lifecycle, assign, status, recommended contractors panel.
 * Route: /admin/ops/maintenance/jobs/:workOrderId (legacy /work-orders/… redirects here).
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  adminAPI,
  openBlobApiResponse,
  contractorEvidenceFilenameFromKey,
  isContractorFileEvidenceKey,
} from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Wrench, Loader2, ArrowLeft, UserPlus, Info, ChevronDown, ChevronUp, ListChecks, Calendar, FileSearch, Receipt } from 'lucide-react';
import { toast } from 'sonner';
import {
  adminInterventionRequired,
  adminSimplifiedProgressFromWorkOrder,
  deriveCanonicalJobStatus,
} from '../../utils/jobWorkflowUi';
import { jurisdictionSourceLabel } from '../../utils/jurisdictionComplianceCopy';

const STATUS_OPTIONS = [
  { value: 'OPEN', label: 'Open' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'AWAITING_PARTS', label: 'Awaiting parts' },
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'CLOSED', label: 'Closed' },
];

export default function AdminWorkOrderDetailPage() {
  const { workOrderId } = useParams();
  const navigate = useNavigate();
  const [wo, setWo] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [noStrongMatch, setNoStrongMatch] = useState(false);
  const [loading, setLoading] = useState(true);
  const [recLoading, setRecLoading] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [contractors, setContractors] = useState([]);
  const [clients, setClients] = useState([]);
  const [contractorExplainId, setContractorExplainId] = useState(null);
  const [contractorExplainData, setContractorExplainData] = useState(null);
  const [contractorExplainLoading, setContractorExplainLoading] = useState(false);
  const [contractorEvidenceLoadingKey, setContractorEvidenceLoadingKey] = useState(null);

  const loadWo = useCallback(() => {
    if (!workOrderId) return;
    setLoading(true);
    adminAPI.getWorkOrder(workOrderId)
      .then((res) => setWo(res.data))
      .catch(() => { setWo(null); toast.error('Job not found'); })
      .finally(() => setLoading(false));
  }, [workOrderId]);

  const loadRecommendations = useCallback(() => {
    if (!workOrderId) return;
    setRecLoading(true);
    adminAPI.getRecommendContractors(workOrderId, { limit: 10 })
      .then((res) => {
        setRecommendations(res.data?.contractors || []);
        setNoStrongMatch(!!res.data?.no_strong_match);
      })
      .catch(() => { setRecommendations([]); setNoStrongMatch(false); })
      .finally(() => setRecLoading(false));
  }, [workOrderId]);

  useEffect(() => { loadWo(); }, [loadWo]);
  useEffect(() => { if (wo) loadRecommendations(); }, [wo, loadRecommendations]);
  useEffect(() => {
    adminAPI.getContractors({ skip: 0, limit: 500 }).then((res) => setContractors(res.data?.contractors || [])).catch(() => setContractors([]));
    adminAPI.getClients(0, 500).then((res) => setClients(res.data?.clients || res.data?.items || [])).catch(() => setClients([]));
  }, []);

  const handleStatusChange = (status) => {
    if (!workOrderId) return;
    setUpdating(true);
    adminAPI.updateWorkOrder(workOrderId, { status })
      .then(() => { toast.success('Status updated'); loadWo(); })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
      .finally(() => setUpdating(false));
  };

  const handleAssign = (contractorId) => {
    if (!workOrderId || !contractorId) return;
    setUpdating(true);
    adminAPI.updateWorkOrder(workOrderId, { contractor_id: contractorId })
      .then(() => { toast.success('Contractor assigned'); loadWo(); })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Assign failed'))
      .finally(() => setUpdating(false));
  };

  const clientLabel = (id) => {
    if (!id) return '—';
    const c = clients.find((x) => x.client_id === id);
    return c ? (c.company_name || c.full_name || c.email || id) : id;
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try { return new Date(s).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }); } catch { return s; }
  };

  const openContractorEvidence = async (storageKey, download) => {
    if (!workOrderId || !storageKey) return;
    setContractorEvidenceLoadingKey(storageKey);
    try {
      const res = await adminAPI.getWorkOrderContractorEvidenceFile(workOrderId, storageKey, download);
      openBlobApiResponse(res, {
        download,
        fallbackFilename: contractorEvidenceFilenameFromKey(storageKey),
      });
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Could not open evidence file');
    } finally {
      setContractorEvidenceLoadingKey(null);
    }
  };

  if (loading && !wo) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6 flex items-center gap-2 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          Loading…
        </div>
      </UnifiedAdminLayout>
    );
  }
  if (!wo) {
    return (
      <UnifiedAdminLayout>
        <div className="p-6">
          <Button variant="outline" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/admin/ops/maintenance'))}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to jobs
          </Button>
          <p className="mt-4 text-gray-600">Job not found.</p>
        </div>
      </UnifiedAdminLayout>
    );
  }

  const canonicalJobStatus = deriveCanonicalJobStatus(wo);
  const intervention = adminInterventionRequired(canonicalJobStatus, wo.operational_exception);
  const adminProgress = adminSimplifiedProgressFromWorkOrder(wo);
  const kindUpper = String(wo.work_order_kind || 'MAINTENANCE').toUpperCase();

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-4xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <Button variant="outline" size="sm" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/admin/ops/maintenance'))}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Wrench className="w-7 h-7" />
              Job
            </h1>
          </div>
        </div>
        <p className="text-sm text-gray-500 font-mono mb-1">{wo.work_order_id}</p>
        <p className="text-base font-medium text-gray-900 mb-4">{wo.description || '—'}</p>

        <Card className="mb-6 border-gray-200">
          <CardHeader className="pb-2"><CardTitle className="text-base">Risk & context</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p><span className="font-medium text-gray-700">Client:</span> {clientLabel(wo.client_id)}</p>
            <p><span className="font-medium text-gray-700">Property:</span> {wo.property_id}</p>
            {(wo.property_effective_jurisdiction_label || wo.property_jurisdiction_source) ? (
              <p className="text-gray-600">
                <span className="font-medium text-gray-700">Jurisdiction:</span>{' '}
                {wo.property_effective_jurisdiction_label || '—'}
                {wo.property_jurisdiction_source
                  ? ` · Source: ${jurisdictionSourceLabel(wo.property_jurisdiction_source)}`
                  : ''}
              </p>
            ) : null}
            <p><span className="font-medium text-gray-700">Category:</span> {wo.category || '—'}</p>
            <p><span className="font-medium text-gray-700">Severity:</span> {wo.severity || '—'}</p>
            <p><span className="font-medium text-gray-700">Created:</span> {formatDate(wo.created_at)}</p>
            <p><span className="font-medium text-gray-700">SLA respond by:</span> {formatDate(wo.sla_respond_by)}</p>
            <p><span className="font-medium text-gray-700">SLA complete by:</span> {formatDate(wo.sla_complete_by)}</p>
            {wo.sla_breach_risk_at && <p className="text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1.5"><span className="font-medium">At risk:</span> {formatDate(wo.sla_breach_risk_at)}</p>}
            {wo.sla_breached_at && <p className="text-red-800 bg-red-50 border border-red-100 rounded px-2 py-1.5"><span className="font-medium">Breached:</span> {formatDate(wo.sla_breached_at)}</p>}
          </CardContent>
        </Card>

        {intervention ? (
          <Alert className="mb-6 border-amber-300 bg-amber-50 text-amber-950">
            <AlertDescription className="text-sm font-medium">
              Intervention required — an operational hold is active on this job. Validate proof and assignment after coordination;
              use override only when policy allows.
            </AlertDescription>
          </Alert>
        ) : null}

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><ListChecks className="w-4 h-4" /> Unified progress & raw states</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div><dt className="text-gray-500">Job kind</dt><dd className="font-mono">{kindUpper}</dd></div>
              <div><dt className="text-gray-500">Persisted status</dt><dd className="font-mono">{wo.status || '—'}</dd></div>
              <div><dt className="text-gray-500">Canonical job status</dt><dd className="font-mono">{canonicalJobStatus}</dd></div>
              <div><dt className="text-gray-500">Operational exception</dt><dd className="font-mono">{wo.operational_exception || '—'}</dd></div>
              <div><dt className="text-gray-500">Schedule status</dt><dd className="font-mono">{wo.schedule_status || '—'}</dd></div>
              {kindUpper === 'COMPLIANCE' && wo.linked_property_requirement_id ? (
                <div className="sm:col-span-2">
                  <dt className="text-gray-500">Linked requirement</dt>
                  <dd className="font-mono break-all">{wo.linked_property_requirement_id}</dd>
                </div>
              ) : null}
              {wo.requirement_code ? (
                <div><dt className="text-gray-500">Requirement code</dt><dd className="font-mono">{wo.requirement_code}</dd></div>
              ) : null}
              {wo.compliance_proof_status != null && String(wo.compliance_proof_status).trim() !== '' ? (
                <div><dt className="text-gray-500">Compliance proof status</dt><dd className="font-mono">{String(wo.compliance_proof_status)}</dd></div>
              ) : null}
            </dl>
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">Simplified lifecycle (ops view)</p>
              <div className="flex flex-wrap items-center gap-1 text-[10px] sm:text-xs">
                {adminProgress.steps.map((label, idx) => {
                  const cancelled = adminProgress.currentIndex < 0;
                  const active = !cancelled && adminProgress.currentIndex === idx;
                  const done = !cancelled && adminProgress.currentIndex > idx;
                  return (
                    <span key={label} className="flex items-center gap-1">
                      {idx > 0 ? <span className="text-gray-300">→</span> : null}
                      <span
                        className={`px-2 py-1 rounded font-medium ${
                          cancelled
                            ? 'bg-gray-100 text-gray-400'
                            : active
                              ? 'bg-midnight-blue text-white'
                              : done
                                ? 'bg-emerald-100 text-emerald-900'
                                : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {label}
                      </span>
                    </span>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><UserPlus className="w-4 h-4" /> Assignment & contractor governance</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Contractor</label>
                {wo.contractor_id ? (
                  <p className="text-sm text-gray-700">{contractors.find((c) => c.contractor_id === wo.contractor_id)?.name || wo.contractor_id}</p>
                ) : (
                  <select className="border border-gray-300 rounded px-3 py-2 text-sm min-w-[160px]" value="" onChange={(e) => { const v = e.target.value; if (v) handleAssign(v); }} disabled={updating}>
                    <option value="">Approve / assign…</option>
                    {contractors.map((c) => <option key={c.contractor_id} value={c.contractor_id}>{c.name}</option>)}
                  </select>
                )}
              </div>
              {updating && <Loader2 className="w-5 h-5 animate-spin text-gray-400 self-end" />}
            </div>
            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-500 mb-2">Recommended contractors</p>
              {recLoading ? (
                <div className="flex items-center gap-2 text-gray-500 py-4"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
              ) : recommendations.length === 0 ? (
                <p className="text-sm text-gray-500 py-2">
                  {noStrongMatch
                    ? 'No strong contractor match found. Review manually.'
                    : 'No recommendations. Add contractors with matching trade types in '}
                  {!noStrongMatch && <Link to="/admin/ops/contractors" className="text-electric-teal hover:underline">Contractors</Link>}
                  {!noStrongMatch && '.'}
                </p>
              ) : (
                <ul className="space-y-3">
                  {recommendations.map((c) => {
                    const showExplain = contractorExplainId === c.contractor_id;
                    return (
                      <li key={c.contractor_id} className="p-3 bg-gray-50 rounded border border-gray-100 overflow-hidden">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-gray-900">{c.name || c.company_name}</span>
                              {c.recommendation_label && (
                                <span className="text-xs font-medium text-electric-teal bg-electric-teal/10 px-1.5 py-0.5 rounded">{c.recommendation_label}</span>
                              )}
                              {c.score != null && <span className="text-xs text-gray-500">Score: {c.score}</span>}
                            </div>
                            {c.trade_types?.length > 0 && <p className="text-xs text-gray-600 mt-0.5">{c.trade_types.join(', ')}</p>}
                            {c.reasons?.length > 0 && (
                              <ul className="text-xs text-gray-500 mt-1 space-y-0.5 list-disc list-inside">
                                {c.reasons.map((r, i) => <li key={i}>{r}</li>)}
                              </ul>
                            )}
                            <div className="flex gap-3 mt-2 text-xs text-gray-600 flex-wrap">
                              {c.performance_score != null && <span>Score: {Math.round(c.performance_score)}</span>}
                              {c.reliability_score != null && <span>Reliability: {Math.round((c.reliability_score || 0) * 100)}%</span>}
                              {(c.completed_jobs != null || c.assigned_jobs != null) && <span>Jobs completed: {c.completed_jobs ?? 0}</span>}
                              {c.rating_average != null && <span>Rating: {Number(c.rating_average).toFixed(1)}/5</span>}
                              {c.sla_compliance_rate != null && <span>SLA: {Math.round(Number(c.sla_compliance_rate) * 100)}%</span>}
                              {c.benchmark_fit && <span>Price: {c.benchmark_fit}</span>}
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              className="text-xs text-electric-teal hover:underline flex items-center gap-0.5"
                              onClick={async () => {
                                if (showExplain) {
                                  setContractorExplainId(null);
                                  setContractorExplainData(null);
                                  return;
                                }
                                setContractorExplainId(c.contractor_id);
                                if (contractorExplainData && contractorExplainId === c.contractor_id) return;
                                setContractorExplainData(null);
                                setContractorExplainLoading(true);
                                try {
                                  const res = await adminAPI.getContractorExplanation(c.contractor_id);
                                  setContractorExplainData(res.data);
                                } catch {
                                  setContractorExplainData(null);
                                } finally {
                                  setContractorExplainLoading(false);
                                }
                              }}
                            >
                              <Info className="w-3 h-3" /> Why this matters {showExplain ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            </button>
                            {wo.contractor_id !== c.contractor_id && (
                              <Button size="sm" variant="outline" onClick={() => handleAssign(c.contractor_id)} disabled={updating}>Assign</Button>
                            )}
                          </div>
                        </div>
                        {showExplain && (
                          <div className="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-700">
                            {contractorExplainLoading ? (
                              <p className="flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Loading…</p>
                            ) : contractorExplainData ? (
                              <>
                                <p>{contractorExplainData.why_it_matters}</p>
                                <p className="font-medium text-midnight-blue mt-1">{contractorExplainData.recommended_action_text}</p>
                              </>
                            ) : (
                              <p>Could not load explanation.</p>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Calendar className="w-4 h-4" /> Scheduling</CardTitle></CardHeader>
          <CardContent className="text-sm space-y-1">
            <p><span className="font-medium text-gray-700">Schedule status:</span> {wo.schedule_status || '—'}</p>
            <p><span className="font-medium text-gray-700">Scheduled at:</span> {formatDate(wo.scheduled_at)}</p>
            <p><span className="font-medium text-gray-700">Timezone:</span> {wo.scheduled_timezone || '—'}</p>
            <p><span className="font-medium text-gray-700">Scheduled by:</span> {wo.scheduled_by || '—'}</p>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><FileSearch className="w-4 h-4" /> Documents / validation</CardTitle></CardHeader>
          <CardContent>
            {!(wo.evidence_keys || []).length ? (
              <p className="text-sm text-gray-500">No linked document keys on this job.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {(wo.evidence_keys || []).map((key) => {
                  const ks = String(key);
                  if (isContractorFileEvidenceKey(ks)) {
                    return (
                      <li key={ks} className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-gray-700 break-all text-xs">{contractorEvidenceFilenameFromKey(ks)}</span>
                        <span className="flex gap-1 shrink-0">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={contractorEvidenceLoadingKey === ks}
                            onClick={() => openContractorEvidence(ks, false)}
                          >
                            View
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={contractorEvidenceLoadingKey === ks}
                            onClick={() => openContractorEvidence(ks, true)}
                          >
                            Download
                          </Button>
                        </span>
                      </li>
                    );
                  }
                  return (
                    <li key={ks} className="text-xs text-gray-700 break-all">
                      <span className="font-medium text-gray-600">Linked ref:</span> {ks}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Receipt className="w-4 h-4" /> Billing / approval</CardTitle></CardHeader>
          <CardContent className="text-sm text-gray-700 space-y-2">
            <p>
              Client invoice approval happens in the client Approvals workspace; admin-created invoices use Ops → Invoices. This
              screen does not load invoice rows — cross-check the client account if a job is stuck in billing.
            </p>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base">Audit timeline</CardTitle></CardHeader>
          <CardContent>
            <ul className="text-xs text-gray-700 space-y-1">
              <li><span className="font-medium text-gray-600">Created:</span> {formatDate(wo.created_at)}</li>
              <li><span className="font-medium text-gray-600">Updated:</span> {formatDate(wo.updated_at)}</li>
              {wo.assigned_at ? <li><span className="font-medium text-gray-600">Assigned:</span> {formatDate(wo.assigned_at)}</li> : null}
              {wo.accepted_at ? <li><span className="font-medium text-gray-600">Accepted:</span> {formatDate(wo.accepted_at)}</li> : null}
              {wo.completed_at ? <li><span className="font-medium text-gray-600">Completed:</span> {formatDate(wo.completed_at)}</li> : null}
            </ul>
          </CardContent>
        </Card>

        <Card className="mb-6 border-gray-300">
          <CardHeader><CardTitle className="text-base">Override — persisted status</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-center gap-4">
            <p className="text-xs text-gray-600 w-full">
              Use only when you understand client workflow impact. Prefer lifecycle APIs and client actions where possible.
            </p>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Status override</label>
              <select value={wo.status} onChange={(e) => handleStatusChange(e.target.value)} disabled={updating} className="border border-gray-300 rounded px-3 py-2 text-sm">
                {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            {updating && <Loader2 className="w-5 h-5 animate-spin text-gray-400" />}
          </CardContent>
        </Card>

        {wo.triage_reasoning?.length > 0 ? (
          <Card>
            <CardHeader><CardTitle className="text-base">Triage reasoning</CardTitle></CardHeader>
            <CardContent>
              <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                {wo.triage_reasoning.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </UnifiedAdminLayout>
  );
}
