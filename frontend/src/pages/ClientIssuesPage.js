/**
 * Operations → Issues: portfolio-wide issue intake and triage workspace.
 * Primary content: Issues queue. Work orders accessible via link. Gated by maintenance_workflows.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { AlertCircle, Plus, Loader2, FileText, X, Wrench, Building2 } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

function ClientIssuesPageInner() {
  const navigate = useNavigate();
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [issuesLoading, setIssuesLoading] = useState(true);
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
  const [filterSource, setFilterSource] = useState('');
  const [filterFromDate, setFilterFromDate] = useState('');
  const [filterToDate, setFilterToDate] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [issueDetailDrawer, setIssueDetailDrawer] = useState(null);
  const [issueDetailData, setIssueDetailData] = useState(null);
  const [issueDetailLoading, setIssueDetailLoading] = useState(false);
  const [creatingWoFromIssue, setCreatingWoFromIssue] = useState(null);

  const loadIssues = useCallback(() => {
    setIssuesLoading(true);
    setError(null);
    const params = { skip: 0, limit: 200 };
    if (filterProperty) params.property_id = filterProperty;
    if (filterCategory) params.category = filterCategory;
    if (filterSeverity) params.severity = filterSeverity;
    if (filterStatus) params.status = filterStatus;
    if (filterSource) params.source = filterSource;
    if (filterFromDate) params.from_date = filterFromDate;
    if (filterToDate) params.to_date = filterToDate;
    clientAPI
      .getMaintenanceIssues(params)
      .then((res) => {
        setIssues(res.data?.issues || []);
        setIssuesTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          toast.error(err?.response?.data?.detail || 'Failed to load issues');
        }
        setIssues([]);
        setIssuesTotal(0);
      })
      .finally(() => setIssuesLoading(false));
  }, [filterProperty, filterCategory, filterSeverity, filterStatus, filterSource, filterFromDate, filterToDate]);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);

  useEffect(() => {
    loadProperties();
  }, [loadProperties]);
  useEffect(() => { loadIssues(); }, [loadIssues]);

  useEffect(() => {
    if (!issueDetailDrawer) { setIssueDetailData(null); return; }
    setIssueDetailLoading(true);
    clientAPI.getMaintenanceIssue(issueDetailDrawer)
      .then((res) => setIssueDetailData(res.data || null))
      .catch(() => setIssueDetailData(null))
      .finally(() => setIssueDetailLoading(false));
  }, [issueDetailDrawer]);

  const propertyLabel = (id) => {
    const p = properties.find((x) => x.property_id === id);
    return p ? (p.nickname || p.address_line_1 || p.postcode || id) : id;
  };

  const formatDate = (s) => {
    if (!s) return '—';
    try { return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' }); } catch { return s; }
  };

  const summary = useMemo(() => {
    const open = issues.filter((i) => (i.status || '').toLowerCase() !== 'closed');
    const newCount = issues.filter((i) => (i.status || '').toLowerCase() === 'new').length;
    const highSeverity = issues.filter((i) => ['high', 'urgent', 'critical'].includes((i.severity || '').toLowerCase()) && (i.status || '').toLowerCase() !== 'closed').length;
    const readyForWo = issues.filter((i) => (i.status || '').toLowerCase() === 'ready_for_work_order').length;
    const monitoring = issues.filter((i) => (i.status || '').toLowerCase() === 'monitoring').length;
    const recurring = issues.filter((i) => i.recurrence_flag === true).length;
    return {
      totalOpen: open.length,
      new: newCount,
      highSeverity,
      readyForWorkOrder: readyForWo,
      monitoring,
      recurring,
    };
  }, [issues]);

  const filteredBySearch = useMemo(() => {
    if (!searchQuery.trim()) return issues;
    const q = searchQuery.trim().toLowerCase();
    return issues.filter((i) => {
      const desc = (i.description || '').toLowerCase();
      const id = (i.issue_id || '').toLowerCase();
      const p = properties.find((x) => x.property_id === i.property_id);
      const propLabel = (p ? (p.nickname || p.address_line_1 || p.postcode || i.property_id) : i.property_id).toLowerCase();
      return desc.includes(q) || id.includes(q) || propLabel.includes(q);
    });
  }, [issues, searchQuery, properties]);

  const recurringIssues = useMemo(() => issues.filter((i) => i.recurrence_flag === true), [issues]);

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
        toast.success('Work order created.');
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadIssues();
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
        const outcomeMsg = res.data?.outcome?.message;
        toast.success(outcomeMsg || 'Issue created and triaged.');
        if (res.data?.outcome && typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: res.data.outcome }));
        }
        setCreateIssueOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        const issueId = res.data?.issue_id;
        loadIssues();
        if (issueId) setIssueDetailDrawer(issueId);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to create issue'))
      .finally(() => setCreateIssueSaving(false));
  };

  const handleCreateWoFromIssue = (issueId) => {
    setCreatingWoFromIssue(issueId);
    clientAPI.createWorkOrderFromIssue(issueId)
      .then(() => {
        toast.success('Work order created from issue.');
        loadIssues();
        setIssueDetailDrawer(null);
        setIssueDetailData(null);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to create work order'))
      .finally(() => setCreatingWoFromIssue(null));
  };

  const applyFilter = (key, value) => {
    if (key === 'status') setFilterStatus(value);
    if (key === 'severity') setFilterSeverity(value);
  };

  if (error && !issuesLoading) {
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
    <div className="p-6 max-w-6xl">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <AlertCircle className="w-7 h-7" />
          Issues
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/operations/work-orders')}>
            View work orders
          </Button>
          <Button variant="outline" onClick={() => setCreateIssueOpen(true)}>
            <FileText className="w-4 h-4 mr-2" />
            Add issue
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
            <Plus className="w-4 h-4 mr-2" />
            Report issue (create work order)
          </Button>
        </div>
      </div>
      <p className="text-gray-600 mb-6">
        Portfolio-wide issue intake and triage. Add an issue for triage and reasoning, or report an issue to create a work order directly.
      </p>

      {/* Summary KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <button type="button" onClick={() => applyFilter('status', '')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Open issues</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.totalOpen}</p>
        </button>
        <button type="button" onClick={() => applyFilter('status', 'new')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">New</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.new}</p>
        </button>
        <button type="button" onClick={() => applyFilter('severity', 'high')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">High severity</p>
          <p className="text-lg font-semibold text-amber-600">{summary.highSeverity}</p>
        </button>
        <button type="button" onClick={() => applyFilter('status', 'ready_for_work_order')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Ready for WO</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.readyForWorkOrder}</p>
        </button>
        <button type="button" onClick={() => applyFilter('status', 'monitoring')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Monitoring</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.monitoring}</p>
        </button>
        <div className="p-3 rounded-lg border border-gray-200 bg-white">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Recurring</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.recurring}</p>
        </div>
      </div>

      {/* Filters + search */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
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
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[140px]">
                <option value="">All</option>
                <option value="new">New</option>
                <option value="triaged">Triaged</option>
                <option value="monitoring">Monitoring</option>
                <option value="ready_for_work_order">Ready for work order</option>
                <option value="closed">Closed</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[120px]">
                <option value="">All</option>
                <option value="general">General</option>
                <option value="plumbing">Plumbing</option>
                <option value="electrical">Electrical</option>
                <option value="heating">Heating</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
              <select value={filterSeverity} onChange={(e) => setFilterSeverity(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[100px]">
                <option value="">All</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent / Critical</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
              <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[120px]">
                <option value="">All</option>
                <option value="tenant">Tenant</option>
                <option value="client">Landlord / Client</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From date</label>
              <input type="date" value={filterFromDate} onChange={(e) => setFilterFromDate(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">To date</label>
              <input type="date" value={filterToDate} onChange={(e) => setFilterToDate(e.target.value)} className="border border-gray-300 rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
              <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Description, ref, property…" className="border border-gray-300 rounded-md px-3 py-2 text-sm min-w-[180px]" />
            </div>
            <Button variant="outline" size="sm" onClick={() => { setFilterProperty(''); setFilterStatus(''); setFilterCategory(''); setFilterSeverity(''); setFilterSource(''); setFilterFromDate(''); setFilterToDate(''); setSearchQuery(''); }}>Clear filters</Button>
            <Button variant="ghost" size="sm" onClick={loadIssues}>Refresh</Button>
          </div>
        </CardContent>
      </Card>

      {/* Issues queue table */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Issues</CardTitle>
        </CardHeader>
        <CardContent>
          {issuesLoading ? (
            <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : !issues.length ? (
            <div className="py-8 text-center text-gray-500">
              <p className="font-medium">No maintenance issues have been recorded across your portfolio.</p>
              <div className="flex flex-wrap gap-2 justify-center mt-3">
                <Button size="sm" variant="outline" onClick={() => setCreateIssueOpen(true)}>Add issue</Button>
                <Button size="sm" variant="outline" onClick={() => navigate('/properties')}>View properties</Button>
              </div>
            </div>
          ) : !filteredBySearch.length ? (
            <div className="py-8 text-center text-gray-500">
              <p className="font-medium">No issues match your current filters.</p>
              <Button size="sm" variant="outline" className="mt-2" onClick={() => { setFilterProperty(''); setFilterStatus(''); setFilterCategory(''); setFilterSeverity(''); setFilterSource(''); setFilterFromDate(''); setFilterToDate(''); setSearchQuery(''); }}>Clear filters</Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="p-2">Ref / Title</th>
                    <th className="p-2">Property</th>
                    <th className="p-2">Category</th>
                    <th className="p-2">Severity</th>
                    <th className="p-2">Priority</th>
                    <th className="p-2">Asset</th>
                    <th className="p-2">Source</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Created</th>
                    <th className="p-2">SLA</th>
                    <th className="p-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBySearch.map((iss) => (
                    <tr key={iss.issue_id} className="border-b hover:bg-gray-50">
                      <td className="p-2 max-w-[200px]">
                        <span className="text-xs text-gray-500 block truncate">{iss.issue_id?.slice(0, 8)}</span>
                        <span className="font-medium truncate block" title={iss.description}>{iss.description || '—'}</span>
                      </td>
                      <td className="p-2 text-gray-600">{propertyLabel(iss.property_id)}</td>
                      <td className="p-2 text-gray-600">{(iss.category || '—').replace(/_/g, ' ')}</td>
                      <td className="p-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${(iss.severity || '').toLowerCase() === 'urgent' ? 'bg-red-100 text-red-800' : (iss.severity || '').toLowerCase() === 'high' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'}`}>
                          {(iss.severity || '—').toLowerCase()}
                        </span>
                      </td>
                      <td className="p-2">{iss.priority_score != null ? iss.priority_score : '—'}</td>
                      <td className="p-2 text-gray-600">{iss.asset_id ? (iss.asset_id.slice(0, 8) + '…') : 'Unlinked'}</td>
                      <td className="p-2 text-gray-600">{(iss.source || '—').toLowerCase()}</td>
                      <td className="p-2">{(iss.status || '—').replace(/_/g, ' ')}</td>
                      <td className="p-2 text-gray-600">{formatDate(iss.created_at)}</td>
                      <td className="p-2 text-gray-600">{iss.triage?.sla_hours != null ? `${iss.triage.sla_hours}h` : '—'}</td>
                      <td className="p-2 text-right">
                        <Button size="sm" variant="ghost" onClick={() => setIssueDetailDrawer(iss.issue_id)}>View</Button>
                        {iss.status !== 'ready_for_work_order' && iss.status !== 'closed' && (
                          <Button size="sm" variant="outline" className="ml-1" onClick={() => handleCreateWoFromIssue(iss.issue_id)} disabled={creatingWoFromIssue === iss.issue_id}>
                            {creatingWoFromIssue === iss.issue_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3 mr-1" />}
                            Create WO
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {issuesTotal > 0 && <p className="text-sm text-gray-500 mt-2">Total: {issuesTotal}</p>}
        </CardContent>
      </Card>

      {/* Recurring / Flagged issues panel */}
      {recurringIssues.length > 0 && (
        <Card className="mb-6 border-amber-200 bg-amber-50/30">
          <CardHeader>
            <CardTitle className="text-base">Recurring / Flagged issues</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {recurringIssues.slice(0, 10).map((iss) => (
                <li key={iss.issue_id} className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-white border border-amber-100">
                  <span className="font-medium truncate max-w-[240px]">{(iss.category || '').replace(/_/g, ' ')} at {propertyLabel(iss.property_id)}</span>
                  <span className="text-xs text-gray-600">{iss.asset_id ? 'Asset linked' : 'No asset'}</span>
                  <span className="text-xs text-amber-700">Recurring · Investigate root cause / Create inspection</span>
                  <Button size="sm" variant="outline" onClick={() => setIssueDetailDrawer(iss.issue_id)}>View</Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Issue detail drawer */}
      {issueDetailDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setIssueDetailDrawer(null)}>
          <div className="w-full max-w-lg bg-white shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-midnight-blue">Issue details</h3>
              <button type="button" onClick={() => setIssueDetailDrawer(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4">
              {issueDetailLoading ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : issueDetailData ? (
                <>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap mb-4">{issueDetailData.description || '—'}</p>
                  <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
                    <dt className="text-gray-500">Property</dt>
                    <dd>{propertyLabel(issueDetailData.property_id)}</dd>
                    <dt className="text-gray-500">Category</dt>
                    <dd>{(issueDetailData.category || '—').replace(/_/g, ' ')}</dd>
                    <dt className="text-gray-500">Severity</dt>
                    <dd>{issueDetailData.severity || '—'}</dd>
                    <dt className="text-gray-500">Priority score</dt>
                    <dd>{issueDetailData.priority_score != null ? issueDetailData.priority_score : '—'}</dd>
                    <dt className="text-gray-500">Source</dt>
                    <dd>{(issueDetailData.source || '—').toLowerCase()}</dd>
                    <dt className="text-gray-500">Status</dt>
                    <dd>{(issueDetailData.status || '—').replace(/_/g, ' ')}</dd>
                    <dt className="text-gray-500">Asset</dt>
                    <dd>{issueDetailData.asset_id ? issueDetailData.asset_id.slice(0, 12) + '…' : 'Unlinked'}</dd>
                    <dt className="text-gray-500">Created</dt>
                    <dd>{formatDate(issueDetailData.created_at)}</dd>
                    <dt className="text-gray-500">SLA</dt>
                    <dd>{issueDetailData.triage?.sla_hours != null ? `${issueDetailData.triage.sla_hours}h` : '—'}</dd>
                  </dl>
                  {issueDetailData.triage?.reasoning?.length > 0 && (
                    <div className="mb-4">
                      <h4 className="font-medium text-gray-700 mb-1">Triage reasoning</h4>
                      <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">{issueDetailData.triage.reasoning.map((r, i) => <li key={i}>{r}</li>)}</ul>
                    </div>
                  )}
                  {issueDetailData.triage?.recommended_contractor_type && (
                    <p className="text-sm text-gray-600 mb-4">Recommended contractor: {(issueDetailData.triage.recommended_contractor_type || '').replace(/_/g, ' ')}</p>
                  )}
                  <div className="flex flex-wrap gap-2 pt-2">
                    {issueDetailData.status !== 'ready_for_work_order' && issueDetailData.status !== 'closed' && (
                      <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => handleCreateWoFromIssue(issueDetailData.issue_id)} disabled={creatingWoFromIssue === issueDetailData.issue_id}>
                        {creatingWoFromIssue === issueDetailData.issue_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wrench className="w-4 h-4 mr-1" />}
                        Create work order
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => { navigate(`/properties/${issueDetailData.property_id}`); setIssueDetailDrawer(null); }}>
                      <Building2 className="w-4 h-4 mr-1" />
                      View property
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => { setIssueDetailDrawer(null); navigate(`/operations/issues/${issueDetailData.issue_id}`); }}>Open full page</Button>
                    <Button size="sm" variant="outline" onClick={() => setIssueDetailDrawer(null)}>Close</Button>
                  </div>
                </>
              ) : <p className="text-gray-500 py-4">Could not load issue.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      {createOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCreateOpen(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Report issue (create work order)</h2>
            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property *</label>
                <select value={createForm.property_id} onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" required>
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea value={createForm.description} onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={3} placeholder="Describe the issue..." required />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createSaving} className="bg-electric-teal hover:bg-electric-teal/90">{createSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create work order'}</Button>
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
      {createIssueOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCreateIssueOpen(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Add issue (triaged)</h2>
            <form onSubmit={handleCreateIssueSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property *</label>
                <select value={createForm.property_id} onChange={(e) => setCreateForm((f) => ({ ...f, property_id: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" required>
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                <textarea value={createForm.description} onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={3} placeholder="Describe the issue..." required />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select value={createForm.category} onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full">
                  <option value="general">General</option>
                  <option value="plumbing">Plumbing</option>
                  <option value="electrical">Electrical</option>
                  <option value="heating">Heating</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={createIssueSaving} className="bg-electric-teal hover:bg-electric-teal/90">{createIssueSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create issue'}</Button>
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
