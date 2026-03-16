/**
 * Admin Ops → Work order detail: full lifecycle, assign, status, recommended contractors panel.
 * Route: /admin/ops/maintenance/work-orders/:workOrderId
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { adminAPI } from '../../api/client';
import UnifiedAdminLayout from '../../components/admin/UnifiedAdminLayout';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Wrench, Loader2, ArrowLeft, UserPlus, Info, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';

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

  const loadWo = useCallback(() => {
    if (!workOrderId) return;
    setLoading(true);
    adminAPI.getWorkOrder(workOrderId)
      .then((res) => setWo(res.data))
      .catch(() => { setWo(null); toast.error('Work order not found'); })
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
            Back to Maintenance
          </Button>
          <p className="mt-4 text-gray-600">Work order not found.</p>
        </div>
      </UnifiedAdminLayout>
    );
  }

  return (
    <UnifiedAdminLayout>
      <div className="p-6 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <Button variant="outline" size="sm" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/admin/ops/maintenance'))}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Wrench className="w-7 h-7" />
              Work order
            </h1>
          </div>
        </div>
        <p className="text-sm text-gray-500 font-mono mb-6">{wo.work_order_id}</p>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base">Details</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p><span className="font-medium text-gray-700">Client:</span> {clientLabel(wo.client_id)}</p>
            <p><span className="font-medium text-gray-700">Property:</span> {wo.property_id}</p>
            <p><span className="font-medium text-gray-700">Description:</span> {wo.description || '—'}</p>
            <p><span className="font-medium text-gray-700">Category:</span> {wo.category || '—'}</p>
            <p><span className="font-medium text-gray-700">Severity:</span> {wo.severity || '—'}</p>
            <p><span className="font-medium text-gray-700">Created:</span> {formatDate(wo.created_at)}</p>
            <p><span className="font-medium text-gray-700">SLA respond by:</span> {formatDate(wo.sla_respond_by)}</p>
            <p><span className="font-medium text-gray-700">SLA complete by:</span> {formatDate(wo.sla_complete_by)}</p>
            {wo.sla_breach_risk_at && <p className="text-amber-700"><span className="font-medium">At risk:</span> {formatDate(wo.sla_breach_risk_at)}</p>}
            {wo.sla_breached_at && <p className="text-red-700"><span className="font-medium">Breached:</span> {formatDate(wo.sla_breached_at)}</p>}
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader><CardTitle className="text-base">Status & assignment</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-center gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
              <select value={wo.status} onChange={(e) => handleStatusChange(e.target.value)} disabled={updating} className="border border-gray-300 rounded px-3 py-2 text-sm">
                {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Contractor</label>
              {wo.contractor_id ? (
                <p className="text-sm text-gray-700">{contractors.find((c) => c.contractor_id === wo.contractor_id)?.name || wo.contractor_id}</p>
              ) : (
                <select className="border border-gray-300 rounded px-3 py-2 text-sm min-w-[160px]" value="" onChange={(e) => { const v = e.target.value; if (v) handleAssign(v); }} disabled={updating}>
                  <option value="">Assign…</option>
                  {contractors.map((c) => <option key={c.contractor_id} value={c.contractor_id}>{c.name}</option>)}
                </select>
              )}
            </div>
            {updating && <Loader2 className="w-5 h-5 animate-spin text-gray-400" />}
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><UserPlus className="w-4 h-4" /> Recommended contractors</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>

        {wo.triage_reasoning?.length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-base">Triage reasoning</CardTitle></CardHeader>
            <CardContent>
              <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                {wo.triage_reasoning.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </UnifiedAdminLayout>
  );
}
