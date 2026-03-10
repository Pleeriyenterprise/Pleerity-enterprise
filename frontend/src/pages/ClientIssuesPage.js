/**
 * Operations → Issues: work orders in open state + triaged issues (create issue → triage → create WO).
 * Filters: property, status, category, severity. Gated by maintenance_workflows.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { AlertCircle, Plus, Loader2, Wrench, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

const OPEN_STATUSES = ['OPEN', 'ASSIGNED'];

function ClientIssuesPageInner() {
  const navigate = useNavigate();
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [properties, setProperties] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [createIssueOpen, setCreateIssueOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ property_id: '', description: '', category: 'general', severity: 'medium' });
  const [createSaving, setCreateSaving] = useState(false);
  const [createIssueSaving, setCreateIssueSaving] = useState(false);
  const [error, setError] = useState(null);
  const [filterProperty, setFilterProperty] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');

  const loadWorkOrders = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = { skip: 0, limit: 200 };
    if (filterProperty) params.property_id = filterProperty;
    if (filterStatus) params.status = filterStatus;
    clientAPI
      .getMaintenanceWorkOrders(params)
      .then((res) => {
        const all = res.data?.work_orders || [];
        const open = filterStatus ? all : all.filter((wo) => OPEN_STATUSES.includes(wo.status));
        setWorkOrders(open);
        setTotal(open.length);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          setError('Failed to load issues.');
          toast.error(err?.response?.data?.detail || 'Failed to load issues');
        }
        setWorkOrders([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [filterProperty, filterStatus]);

  const loadIssues = useCallback(() => {
    setIssuesLoading(true);
    const params = { skip: 0, limit: 100 };
    if (filterProperty) params.property_id = filterProperty;
    if (filterCategory) params.category = filterCategory;
    if (filterSeverity) params.severity = filterSeverity;
    if (filterStatus) params.status = filterStatus;
    clientAPI
      .getMaintenanceIssues(params)
      .then((res) => {
        setIssues(res.data?.issues || []);
        setIssuesTotal(res.data?.total ?? 0);
      })
      .catch(() => {
        setIssues([]);
        setIssuesTotal(0);
      })
      .finally(() => setIssuesLoading(false));
  }, [filterProperty, filterCategory, filterSeverity, filterStatus]);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);

  useEffect(() => {
    loadWorkOrders();
    loadProperties();
  }, [loadWorkOrders, loadProperties]);
  useEffect(() => { loadIssues(); }, [loadIssues]);

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!createForm.property_id || !createForm.description?.trim()) {
      toast.error('Select a property and enter a description');
      return;
    }
    setCreateSaving(true);
    clientAPI
      .createMaintenanceWorkOrder({
        property_id: createForm.property_id,
        description: createForm.description.trim(),
        category: createForm.category || undefined,
        severity: createForm.severity || undefined,
      })
      .then(() => {
        toast.success('Issue reported. A work order has been created.');
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to report issue'))
      .finally(() => setCreateSaving(false));
  };

  const handleCreateIssueSubmit = (e) => {
    e.preventDefault();
    if (!createForm.property_id || !createForm.description?.trim()) {
      toast.error('Select a property and enter a description');
      return;
    }
    setCreateIssueSaving(true);
    clientAPI
      .createMaintenanceIssue({
        property_id: createForm.property_id,
        description: createForm.description.trim(),
        category: createForm.category || undefined,
      })
      .then((res) => {
        toast.success('Issue created and triaged.');
        setCreateIssueOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        const issueId = res.data?.issue_id;
        loadIssues();
        loadWorkOrders();
        if (issueId) navigate(`/operations/issues/${issueId}`);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to create issue'))
      .finally(() => setCreateIssueSaving(false));
  };

  const propertyLabel = (id) => {
    const p = properties.find((x) => x.property_id === id);
    return p ? (p.nickname || p.address_line_1 || p.postcode || id) : id;
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try {
      return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
    } catch {
      return s;
    }
  };

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <AlertCircle className="w-7 h-7" />
          Issues
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6">
            <p className="font-medium text-amber-900">{error}</p>
            <p className="text-sm text-amber-800 mt-2">Contact your administrator to enable maintenance workflows.</p>
            <Button variant="outline" className="mt-4" onClick={() => navigate('/operations/work-orders')}>
              View Work Orders
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <AlertCircle className="w-7 h-7" />
          Issues
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/operations/work-orders')}>
            View all work orders
          </Button>
          <Button variant="outline" onClick={() => setCreateIssueOpen(true)}>
            <FileText className="w-4 h-4 mr-2" />
            Create issue (triaged)
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
            <Plus className="w-4 h-4 mr-2" />
            Report issue
          </Button>
        </div>
      </div>
      <p className="text-gray-600 mb-4">
        Open and assigned issues. Report an issue to create a work order; or create an issue first to get triage and reasoning, then create a work order from it.
      </p>
      <div className="flex flex-wrap gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
          <select value={filterProperty} onChange={(e) => setFilterProperty(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[160px]">
            <option value="">All</option>
            {properties.map((p) => (
              <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status (work orders)</label>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[120px]">
            <option value="">Open only</option>
            <option value="OPEN">Open</option>
            <option value="ASSIGNED">Assigned</option>
            <option value="IN_PROGRESS">In progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Category (issues)</label>
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[120px]">
            <option value="">All</option>
            <option value="general">General</option>
            <option value="plumbing">Plumbing</option>
            <option value="electrical">Electrical</option>
            <option value="heating">Heating</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Severity (issues)</label>
          <select value={filterSeverity} onChange={(e) => setFilterSeverity(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[100px]">
            <option value="">All</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Open issues</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : workOrders.length === 0 ? (
            <p className="text-gray-500 py-6">No open issues. Use &quot;Report issue&quot; to create one, or view all work orders for full history.</p>
          ) : (
            <ul className="space-y-3">
              {workOrders.map((wo) => (
                <li
                  key={wo.work_order_id}
                  className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div>
                    <p className="font-medium text-gray-900">{propertyLabel(wo.property_id)}</p>
                    <p className="text-sm text-gray-600 truncate max-w-md">{wo.description || '—'}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Created {formatDate(wo.created_at)} · {wo.source === 'tenant_request' ? 'Tenant' : wo.source || 'You'}
                    </p>
                  </div>
                  <span className="px-2 py-1 rounded text-xs font-medium bg-amber-100 text-amber-800">{wo.status}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><FileText className="w-5 h-5" /> Triaged issues</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-4">Issues created with triage (severity, reasoning). Create a work order from an issue to link it.</p>
          {issuesLoading ? (
            <div className="flex gap-2 text-gray-500 py-4"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : issues.length === 0 ? (
            <p className="text-gray-500 py-4">No triaged issues. Use &quot;Create issue (triaged)&quot; to add one.</p>
          ) : (
            <ul className="space-y-3">
              {issues.map((iss) => (
                <li key={iss.issue_id} className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div>
                    <p className="font-medium text-gray-900">{propertyLabel(iss.property_id)}</p>
                    <p className="text-sm text-gray-600 truncate max-w-md">{iss.description || '—'}</p>
                    <p className="text-xs text-gray-500 mt-1">Created {formatDate(iss.created_at)} · {iss.severity} · {iss.status}</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => navigate(`/operations/issues/${iss.issue_id}`)}>
                    View
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {issuesTotal > 0 && <p className="text-sm text-gray-500 mt-2">Total: {issuesTotal}</p>}
        </CardContent>
      </Card>

      {createOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Report an issue</h2>
            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property *</label>
                <select
                  value={createForm.property_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                >
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={3}
                  placeholder="Describe the issue..."
                  required
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {createSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
      {createIssueOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Create issue (triaged)</h2>
            <form onSubmit={handleCreateIssueSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property *</label>
                <select
                  value={createForm.property_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  required
                >
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={3}
                  placeholder="Describe the issue..."
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select
                  value={createForm.category}
                  onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                >
                  <option value="general">General</option>
                  <option value="plumbing">Plumbing</option>
                  <option value="electrical">Electrical</option>
                  <option value="heating">Heating</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createIssueSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {createIssueSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setCreateIssueOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ClientIssuesPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="maintenance_workflows">
      <ClientIssuesPageInner />
    </EntitlementProtectedRoute>
  );
}
