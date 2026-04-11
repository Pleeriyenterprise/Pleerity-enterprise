/**
 * Operations → Issue detail: triage result, reasoning, Create Work Order.
 * Route: /operations/issues/:issueId
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { AlertCircle, Loader2, Wrench, ArrowLeft, History } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { buildSafeQueryPath } from '../utils/clientPortalNavigation';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';

function ClientIssueDetailPageInner() {
  const { issueId } = useParams();
  const navigate = useNavigate();
  const [issue, setIssue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [closeNote, setCloseNote] = useState('');
  const [closing, setClosing] = useState(false);
  const [planJobGate, setPlanJobGate] = useState(null);

  useEffect(() => {
    if (!issueId) return;
    setLoading(true);
    setError(null);
    setIssue(null);
    setTimeline(null);
    clientAPI
      .getMaintenanceIssue(issueId)
      .then((res) => setIssue(res.data))
      .catch((err) => {
        if (err?.response?.status === 404) setError('Issue not found');
        else setError(err?.response?.data?.detail || 'Failed to load issue');
      })
      .finally(() => setLoading(false));
  }, [issueId]);

  useEffect(() => {
    if (!issueId || !issue || issue.issue_id !== issueId) return;
    setTimelineLoading(true);
    clientAPI
      .getMaintenanceIssueTimeline(issueId, { limit: 120 })
      .then((res) => setTimeline(res.data?.items || []))
      .catch(() => setTimeline([]))
      .finally(() => setTimelineLoading(false));
  }, [issueId, issue]);

  const handleCreateWorkOrder = () => {
    if (!issueId) return;
    setCreating(true);
    clientAPI
      .createWorkOrderFromIssue(issueId)
      .then((res) => {
        toast.success('Maintenance job created');
        const woId = res.data?.work_order_id;
        if (woId) navigate(buildSafeQueryPath('/operations/work-orders', { work_order_id: woId }));
        else navigate('/operations/issues');
      })
      .catch((err) => {
        if (openPlanRestrictedJobGate(err, setPlanJobGate, { propertyId: issue?.property_id })) return;
        toast.error(err?.response?.data?.detail || 'Failed to create maintenance job');
      })
      .finally(() => setCreating(false));
  };

  const handleCloseIssue = () => {
    if (!issueId) return;
    setClosing(true);
    clientAPI
      .updateMaintenanceIssue(issueId, {
        status: 'closed',
        resolution_note: closeNote.trim() || undefined,
      })
      .then((res) => {
        setIssue(res.data);
        setCloseNote('');
        toast.success('Maintenance issue closed');
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Could not close issue'))
      .finally(() => setClosing(false));
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try { return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' }); } catch { return s; }
  };

  const formatDateTime = (s) => {
    if (!s) return '—';
    try {
      return new Date(s).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return s;
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-2xl flex items-center gap-2 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin" />
        Loading…
      </div>
    );
  }
  if (error || !issue) {
    return (
      <div className="p-6 max-w-2xl">
        <Button variant="outline" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/operations/issues'))} className="mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Issues
        </Button>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6">
            <p className="font-medium text-amber-900">{error || 'Issue not found'}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const triage = issue.triage || {};
  const reasoning = triage.reasoning || [];

  return (
    <div className="p-6 max-w-2xl">
      <Button variant="outline" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/operations/issues'))} className="mb-4">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Issues
      </Button>
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <AlertCircle className="w-7 h-7" />
        Maintenance issue
      </h1>
      <p className="text-sm text-gray-500 mb-6">Created {formatDate(issue.created_at)} · {issue.status}</p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-700">{issue.description || '—'}</p>
          {issue.category && <p className="text-sm text-gray-500 mt-2">Category: {issue.category}</p>}
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <History className="w-4 h-4 text-teal-600" />
            Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          {timelineLoading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading activity…
            </div>
          ) : !timeline?.length ? (
            <p className="text-sm text-gray-500">No timeline events yet.</p>
          ) : (
            <ul className="space-y-4 border-l-2 border-gray-200 ml-2 pl-4">
              {timeline.map((row) => (
                <li key={row.id} className="relative">
                  <span className="absolute -left-[calc(0.5rem+5px)] top-1.5 w-2 h-2 rounded-full bg-teal-500 ring-4 ring-white" aria-hidden />
                  <p className="text-xs text-gray-500">{formatDateTime(row.timestamp)}</p>
                  <p className="font-medium text-gray-900">{row.title}</p>
                  <p className="text-sm text-gray-600 mt-0.5">{row.description}</p>
                  {row.metadata?.work_order_id && (
                    <button
                      type="button"
                      className="text-xs text-electric-teal hover:underline mt-1"
                      onClick={() => navigate(buildSafeQueryPath('/operations/work-orders', { work_order_id: row.metadata.work_order_id }))}
                    >
                      View job
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-gray-400 mt-4">Read-only history from this issue, linked jobs, and audits.</p>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Triage result</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p><span className="font-medium text-gray-700">Severity:</span> {triage.severity || issue.severity || '—'}</p>
          <p><span className="font-medium text-gray-700">Priority score:</span> {triage.priority_score ?? issue.priority_score ?? '—'}</p>
          <p><span className="font-medium text-gray-700">SLA:</span> {triage.sla_hours != null ? `${triage.sla_hours}h` : '—'}</p>
          <p><span className="font-medium text-gray-700">Recommended contractor type:</span> {triage.recommended_contractor_type || '—'}</p>
          {reasoning.length > 0 && (
            <div className="mt-4">
              <p className="font-medium text-gray-700 mb-2">Reasoning</p>
              <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                {reasoning.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {issue.status !== 'closed' && issue.status !== 'cancelled' && (
        <div className="space-y-4">
          <Button
            onClick={handleCreateWorkOrder}
            disabled={creating}
            className="bg-electric-teal hover:bg-electric-teal/90"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Wrench className="w-4 h-4 mr-2" />}
            Create maintenance job
          </Button>
          <Card className="border-gray-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Close maintenance issue</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-gray-600">
              <p>
                You can close this issue after the linked maintenance job is completed, or add a resolution note if it was handled another way.
              </p>
              <label className="block text-sm font-medium text-gray-700">Resolution note (required if no completed job)</label>
              <textarea
                value={closeNote}
                onChange={(e) => setCloseNote(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
                placeholder="e.g. Resolved by contractor visit on …"
              />
              <Button type="button" variant="outline" onClick={handleCloseIssue} disabled={closing}>
                {closing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Close issue
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      <PlanRestrictedJobModal gate={planJobGate} onDismiss={() => setPlanJobGate(null)} />
    </div>
  );
}

export default function ClientIssueDetailPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="maintenance_workflows">
      <ClientIssueDetailPageInner />
    </EntitlementProtectedRoute>
  );
}
