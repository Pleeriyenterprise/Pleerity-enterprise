/**
 * Operations → Work Orders: portfolio-wide execution and job control workspace.
 * Summary KPIs, filters, table, SLA risk panel, work order detail drawer.
 * Gated by maintenance_workflows (EntitlementProtectedRoute; upgrade prompt when not entitled).
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Wrench,
  Plus,
  Loader2,
  AlertCircle,
  TrendingUp,
  X,
  AlertTriangle,
  Building2,
  FileText,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';

const WO_STATUS_OPTIONS = [
  { value: 'DRAFT', label: 'Draft' },
  { value: 'OPEN', label: 'Open' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'AWAITING_PARTS', label: 'Awaiting parts' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'CLOSED', label: 'Closed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

function formatDate(s) {
  if (!s) return '—';
  try {
    const d = typeof s === 'string' ? new Date(s) : s;
    return d.toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return s;
  }
}

function formatRelativeTime(s) {
  if (!s) return '—';
  try {
    const d = typeof s === 'string' ? new Date(s) : s;
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(s);
  } catch {
    return s;
  }
}

function hoursRemainingOrOverdue(slaCompleteBy) {
  if (!slaCompleteBy) return null;
  try {
    const due = new Date(slaCompleteBy);
    const now = new Date();
    const hours = (due - now) / 3600000;
    if (hours < 0) return { overdue: true, text: `${Math.round(-hours)}h overdue` };
    return { overdue: false, text: `${Math.round(hours)}h left` };
  } catch {
    return null;
  }
}

export default function ClientMaintenancePage() {
  return (
    <EntitlementProtectedRoute requiredFeature="maintenance_workflows">
      <ClientMaintenancePageInner />
    </EntitlementProtectedRoute>
  );
}

function ClientMaintenancePageInner() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { hasFeature } = useEntitlements();
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [maintenanceError, setMaintenanceError] = useState(null);
  const [properties, setProperties] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterProperty, setFilterProperty] = useState('');
  const [filterContractor, setFilterContractor] = useState('');
  const [filterSlaState, setFilterSlaState] = useState('');
  const [filterFromDate, setFilterFromDate] = useState('');
  const [filterToDate, setFilterToDate] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [woDetailDrawer, setWoDetailDrawer] = useState(null);
  const [woDetailData, setWoDetailData] = useState(null);
  const [woDetailLoading, setWoDetailLoading] = useState(false);
  const [woRecommendList, setWoRecommendList] = useState(null);
  const [woRecommendLoading, setWoRecommendLoading] = useState(false);
  const [woUpdateSaving, setWoUpdateSaving] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ property_id: '', description: '', category: 'general', severity: 'medium' });
  const [createSaving, setCreateSaving] = useState(false);
  const [invoiceModalOpen, setInvoiceModalOpen] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
  const [contractorExplainId, setContractorExplainId] = useState(null);
  const [contractorExplainData, setContractorExplainData] = useState(null);
  const [contractorExplainLoading, setContractorExplainLoading] = useState(false);
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const loadWorkOrders = useCallback(() => {
    setLoading(true);
    setMaintenanceError(null);
    const params = { skip: 0, limit: 200 };
    if (filterStatus) params.status = filterStatus;
    if (filterProperty) params.property_id = filterProperty;
    if (filterContractor) params.contractor_id = filterContractor;
    if (filterSlaState) params.sla_state = filterSlaState;
    if (filterFromDate) params.from_date = filterFromDate;
    if (filterToDate) params.to_date = filterToDate;
    clientAPI.getMaintenanceWorkOrders(params)
      .then((res) => {
        setWorkOrders(res.data?.work_orders || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        if (err?.response?.status === 403) {
          setMaintenanceError(detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          setMaintenanceError('Failed to load work orders.');
          toast.error(detail || 'Failed to load work orders');
        }
        setWorkOrders([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [filterStatus, filterProperty, filterContractor, filterSlaState, filterFromDate, filterToDate]);

  const loadProperties = useCallback(() => {
    clientAPI.getProperties().then((res) => {
      setProperties(res.data?.properties || res.data || []);
    }).catch(() => setProperties([]));
  }, []);

  const loadContractors = useCallback(() => {
    if (!hasFeature('contractor_network')) return;
    clientAPI.getContractors({ limit: 200 }).then((res) => {
      setContractors(res.data?.contractors || res.data || []);
    }).catch(() => setContractors([]));
  }, [hasFeature]);

  const loadInsights = useCallback(() => {
    clientAPI.getPredictiveInsights({ limit: 20 })
      .then((res) => setInsights(res.data))
      .catch(() => setInsights(null))
      .finally(() => setInsightsLoading(false));
  }, []);

  useEffect(() => { loadWorkOrders(); }, [loadWorkOrders]);
  useEffect(() => { loadProperties(); loadContractors(); }, [loadProperties, loadContractors]);
  useEffect(() => { setInsightsLoading(true); loadInsights(); }, [loadInsights]);

  useEffect(() => {
    const propertyId = searchParams.get('property_id');
    const description = searchParams.get('description');
    if (propertyId || description) {
      setCreateForm((f) => ({
        ...f,
        ...(propertyId && { property_id: propertyId }),
        ...(description && { description: description }),
      }));
      setCreateOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!woDetailDrawer) { setWoDetailData(null); setWoRecommendList(null); setContractorExplainId(null); setContractorExplainData(null); return; }
    setWoDetailLoading(true);
    setWoRecommendList(null);
    clientAPI.getMaintenanceWorkOrder(woDetailDrawer)
      .then((res) => {
        setWoDetailData(res.data || null);
        if (hasFeature('contractor_network')) {
          setWoRecommendLoading(true);
          clientAPI.getRecommendContractors(woDetailDrawer, { limit: 10 })
            .then((r) => setWoRecommendList(r.data?.contractors || []))
            .catch(() => setWoRecommendList([]))
            .finally(() => setWoRecommendLoading(false));
        }
      })
      .catch(() => setWoDetailData(null))
      .finally(() => setWoDetailLoading(false));
  }, [woDetailDrawer, hasFeature]);

  const propertyLabel = useCallback((id) => {
    const p = properties.find((x) => x.property_id === id);
    return p ? (p.nickname || p.address_line_1 || p.postcode || id) : id;
  }, [properties]);

  const contractorLabel = useCallback((id) => {
    if (!id) return '—';
    const c = contractors.find((x) => (x.contractor_id || x.id) === id);
    return c ? (c.name || c.contractor_name || c.contractor_id || id) : id;
  }, [contractors]);

  const summary = useMemo(() => {
    const activeStatuses = ['DRAFT', 'OPEN', 'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'AWAITING_PARTS'];
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    let totalActive = 0;
    let draft = 0;
    let assigned = 0;
    let inProgress = 0;
    let awaitingParts = 0;
    let completedToday = 0;
    let slaBreaches = 0;
    workOrders.forEach((wo) => {
      const s = (wo.status || '').toUpperCase();
      if (activeStatuses.includes(s)) totalActive++;
      if (s === 'DRAFT') draft++;
      if (s === 'ASSIGNED') assigned++;
      if (s === 'IN_PROGRESS') inProgress++;
      if (s === 'AWAITING_PARTS') awaitingParts++;
      if (wo.completed_at && new Date(wo.completed_at) >= todayStart) completedToday++;
      if (wo.sla_breached_at) slaBreaches++;
    });
    return { totalActive, draft, assigned, inProgress, awaitingParts, completedToday, slaBreaches };
  }, [workOrders]);

  const slaRiskList = useMemo(() => {
    return workOrders.filter((wo) => wo.sla_breached_at || wo.sla_breach_risk_at);
  }, [workOrders]);

  const filteredBySearch = useMemo(() => {
    if (!searchQuery.trim()) return workOrders;
    const q = searchQuery.trim().toLowerCase();
    return workOrders.filter((wo) => {
      const propLabel = propertyLabel(wo.property_id);
      const contractorName = contractorLabel(wo.contractor_id);
      return (
        (wo.description || '').toLowerCase().includes(q) ||
        (wo.work_order_id || '').toLowerCase().includes(q) ||
        (wo.issue_id || '').toLowerCase().includes(q) ||
        (propLabel || '').toLowerCase().includes(q) ||
        (contractorName || '').toLowerCase().includes(q)
      );
    });
  }, [workOrders, searchQuery, propertyLabel, contractorLabel]);

  const statusBadgeClass = (status) => {
    const s = (status || '').toUpperCase();
    if (s === 'COMPLETED' || s === 'VERIFIED' || s === 'CLOSED') return 'bg-green-100 text-green-800';
    if (s === 'CANCELLED') return 'bg-gray-100 text-gray-600';
    if (s === 'IN_PROGRESS' || s === 'ASSIGNED' || s === 'SCHEDULED') return 'bg-blue-100 text-blue-800';
    if (s === 'DRAFT' || s === 'OPEN') return 'bg-amber-100 text-amber-800';
    if (s === 'AWAITING_PARTS') return 'bg-orange-100 text-orange-800';
    return 'bg-gray-100 text-gray-700';
  };

  const slaStateLabel = (wo) => {
    if (wo.sla_breached_at) return { label: 'Breached', class: 'bg-red-100 text-red-800' };
    if (wo.sla_breach_risk_at) return { label: 'Near breach', class: 'bg-amber-100 text-amber-800' };
    return { label: 'On track', class: 'bg-gray-100 text-gray-600' };
  };

  const handleUpdateStatus = (workOrderId, newStatus) => {
    setWoUpdateSaving(true);
    clientAPI.updateMaintenanceWorkOrder(workOrderId, { status: newStatus })
      .then(() => {
        toast.success('Status updated');
        if (woDetailDrawer === workOrderId) setWoDetailData((d) => (d ? { ...d, status: newStatus } : null));
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
      .finally(() => setWoUpdateSaving(false));
  };

  const handleAssignContractor = (workOrderId, contractorId) => {
    setWoUpdateSaving(true);
    clientAPI.updateMaintenanceWorkOrder(workOrderId, { contractor_id: contractorId })
      .then(() => {
        toast.success('Contractor assigned');
        if (woDetailDrawer === workOrderId) {
          setWoDetailData((d) => (d ? { ...d, contractor_id: contractorId } : null));
          setWoRecommendList(null);
        }
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Assign failed'))
      .finally(() => setWoUpdateSaving(false));
  };

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!createForm.property_id || !createForm.description?.trim()) {
      toast.error('Select a property and enter a description');
      return;
    }
    setCreateSaving(true);
    clientAPI.createMaintenanceWorkOrder({
      property_id: createForm.property_id,
      description: createForm.description.trim(),
      category: createForm.category || undefined,
      severity: createForm.severity || undefined,
    })
      .then(() => {
        toast.success('Work order created');
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setCreateSaving(false));
  };

  const clearFilters = () => {
    setFilterStatus('');
    setFilterProperty('');
    setFilterContractor('');
    setFilterSlaState('');
    setFilterFromDate('');
    setFilterToDate('');
    setSearchQuery('');
  };

  const applySummaryFilter = (key, value) => {
    if (key === 'status') setFilterStatus(value);
    if (key === 'sla') setFilterSlaState(value);
  };

  const hasActiveFilters = filterStatus || filterProperty || filterContractor || filterSlaState || filterFromDate || filterToDate || searchQuery.trim();

  if (maintenanceError && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <Wrench className="w-7 h-7" />
          Work Orders
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Maintenance not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{maintenanceError}</p>
              <p className="text-sm text-amber-700 mt-2">Contact your account administrator or support to enable maintenance workflows for your account.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Wrench className="w-7 h-7" />
          Work Orders
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/operations/issues')}>
            View Issues
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">
            <Plus className="w-4 h-4 mr-2" />
            Report issue
          </Button>
        </div>
      </div>
      <p className="text-gray-600 mb-6">
        Portfolio-wide work order execution. Track status, assign contractors, and monitor SLA deadlines.
      </p>

      {/* Summary KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mb-6">
        <button
          type="button"
          onClick={() => applySummaryFilter('status', '')}
          className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors"
        >
          <p className="text-xs text-gray-500 uppercase tracking-wide">Active</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.totalActive}</p>
        </button>
        <button type="button" onClick={() => applySummaryFilter('status', 'DRAFT')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Draft</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.draft}</p>
        </button>
        <button type="button" onClick={() => applySummaryFilter('status', 'ASSIGNED')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Assigned</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.assigned}</p>
        </button>
        <button type="button" onClick={() => applySummaryFilter('status', 'IN_PROGRESS')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">In progress</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.inProgress}</p>
        </button>
        <button type="button" onClick={() => applySummaryFilter('status', 'AWAITING_PARTS')} className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Awaiting parts</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.awaitingParts}</p>
        </button>
        <button type="button" className="p-3 rounded-lg border border-gray-200 bg-white text-left">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Completed today</p>
          <p className="text-lg font-semibold text-midnight-blue">{summary.completedToday}</p>
        </button>
        <button type="button" onClick={() => applySummaryFilter('sla', 'breached')} className="p-3 rounded-lg border border-red-200 bg-red-50/50 text-left hover:bg-red-50 transition-colors">
          <p className="text-xs text-red-700 uppercase tracking-wide">SLA breaches</p>
          <p className="text-lg font-semibold text-red-800">{summary.slaBreaches}</p>
        </button>
      </div>

      {/* Predictive insights */}
      {(insights !== null || insightsLoading) && (
        <Card className="mb-6 border-teal-200 bg-teal-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-electric-teal" />
              Predictive insights
              {insightsLoading && <Loader2 className="w-4 h-4 animate-spin text-teal-600" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {insightsLoading && <p className="text-sm text-gray-500 py-2">Loading insights…</p>}
            {!insightsLoading && insights?.properties?.length > 0 && insights.properties.some((p) => p.insights?.length > 0) && (
              insights.properties.filter((p) => p.insights?.length > 0).map((prop) => (
                <div key={prop.property_id} className="text-sm p-3 bg-white rounded-lg border border-teal-100">
                  <p className="font-medium text-gray-900">{prop.nickname || prop.address_line_1 || prop.property_id}</p>
                  {prop.insights.slice(0, 5).map((i, idx) => (
                    <div key={idx} className="mt-2 pl-2 border-l-2 border-teal-200">
                      <p className="text-gray-700">{i.recommendation}</p>
                      {i.detail && <p className="text-xs text-gray-500 mt-0.5">{i.detail}</p>}
                      <span className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${i.risk === 'high' || i.risk === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{i.risk}</span>
                    </div>
                  ))}
                </div>
              ))
            )}
            {!insightsLoading && insights !== null && (!insights?.properties?.length || !insights.properties.some((p) => p.insights?.length > 0)) && (
              <p className="text-sm text-gray-600 py-2">No insights yet. Add property assets or ensure building age is set where relevant.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Status</label>
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm">
                <option value="">All</option>
                {WO_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Property</label>
              <select value={filterProperty} onChange={(e) => setFilterProperty(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm min-w-[160px]">
                <option value="">All</option>
                {properties.map((p) => <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>)}
              </select>
            </div>
            {hasFeature('contractor_network') && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Contractor</label>
                <select value={filterContractor} onChange={(e) => setFilterContractor(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm min-w-[160px]">
                  <option value="">All</option>
                  {contractors.map((c) => <option key={c.contractor_id || c.id} value={c.contractor_id || c.id}>{c.name || c.contractor_name || c.contractor_id}</option>)}
                </select>
              </div>
            )}
            <div>
              <label className="block text-xs text-gray-500 mb-1">SLA state</label>
              <select value={filterSlaState} onChange={(e) => setFilterSlaState(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm">
                <option value="">All</option>
                <option value="on_track">On track</option>
                <option value="near_breach">Near breach</option>
                <option value="breached">Breached</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">From date</label>
              <input type="date" value={filterFromDate} onChange={(e) => setFilterFromDate(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">To date</label>
              <input type="date" value={filterToDate} onChange={(e) => setFilterToDate(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Search</label>
              <input
                type="text"
                placeholder="Ref, title, property, contractor…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="border border-gray-200 rounded-md px-3 py-2 text-sm w-48"
              />
            </div>
            <Button variant="outline" size="sm" onClick={clearFilters}>Clear filters</Button>
            <Button variant="ghost" size="sm" onClick={loadWorkOrders}>Refresh</Button>
          </div>
        </CardContent>
      </Card>

      {/* SLA Risk panel */}
      {slaRiskList.length > 0 && (
        <Card className="mb-6 border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              SLA risk
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="p-2">Work order</th>
                    <th className="p-2">Property</th>
                    <th className="p-2">SLA due</th>
                    <th className="p-2">Status</th>
                    <th className="p-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {slaRiskList.slice(0, 10).map((wo) => {
                    const hr = hoursRemainingOrOverdue(wo.sla_complete_by);
                    return (
                      <tr key={wo.work_order_id} className="border-b hover:bg-amber-50/50">
                        <td className="p-2">
                          <span className="font-mono text-xs text-gray-500 block">{wo.work_order_id?.slice(0, 8)}…</span>
                          <span className="truncate max-w-[180px] block" title={wo.description}>{wo.description || '—'}</span>
                        </td>
                        <td className="p-2">{propertyLabel(wo.property_id)}</td>
                        <td className="p-2">{formatDate(wo.sla_complete_by)} {hr && <span className={hr.overdue ? 'text-red-600' : 'text-amber-600'}>{hr.text}</span>}</td>
                        <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${statusBadgeClass(wo.status)}`}>{wo.status}</span></td>
                        <td className="p-2 text-right">
                          <Button size="sm" variant="outline" onClick={() => setWoDetailDrawer(wo.work_order_id)}>View</Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Work orders table */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Work orders</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : workOrders.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 mb-4">No work orders have been created across your portfolio yet.</p>
              <div className="flex gap-2 justify-center flex-wrap">
                <Button variant="outline" onClick={() => navigate('/operations/issues')}>View Issues</Button>
                <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">Report issue</Button>
              </div>
            </div>
          ) : !filteredBySearch.length ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 mb-4">No work orders match your current filters.</p>
              <Button variant="outline" onClick={clearFilters}>Clear filters</Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="p-2">Ref / Title</th>
                    <th className="p-2">Property</th>
                    <th className="p-2">Issue</th>
                    <th className="p-2">Asset</th>
                    <th className="p-2">Severity</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Contractor</th>
                    <th className="p-2">SLA due</th>
                    <th className="p-2">SLA state</th>
                    <th className="p-2">Updated</th>
                    <th className="p-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBySearch.map((wo) => {
                    const sla = slaStateLabel(wo);
                    return (
                      <tr key={wo.work_order_id} className="border-b hover:bg-gray-50">
                        <td className="p-2 max-w-[200px]">
                          <span className="font-mono text-xs text-gray-500 block truncate">{wo.work_order_id?.slice(0, 8)}…</span>
                          <span className="font-medium truncate block" title={wo.description}>{wo.description || '—'}</span>
                        </td>
                        <td className="p-2">
                          <button type="button" onClick={() => wo.property_id && navigate(`/properties/${wo.property_id}`)} className="text-electric-teal hover:underline truncate max-w-[120px] block text-left">
                            {propertyLabel(wo.property_id)}
                          </button>
                        </td>
                        <td className="p-2">
                          {wo.issue_id ? (
                            <button type="button" onClick={() => navigate('/operations/issues')} className="text-electric-teal hover:underline text-xs truncate max-w-[80px] block">View</button>
                          ) : '—'}
                        </td>
                        <td className="p-2 text-gray-600">{wo.asset_id ? wo.asset_id.slice(0, 8) + '…' : '—'}</td>
                        <td className="p-2 capitalize">{(wo.severity || '—').toLowerCase()}</td>
                        <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${statusBadgeClass(wo.status)}`}>{wo.status}</span></td>
                        <td className="p-2">{wo.contractor_id ? contractorLabel(wo.contractor_id) : <span className="text-gray-400">Unassigned</span>}</td>
                        <td className="p-2">{formatDate(wo.sla_complete_by)}</td>
                        <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${sla.class}`}>{sla.label}</span></td>
                        <td className="p-2 text-gray-500">{formatRelativeTime(wo.updated_at)}</td>
                        <td className="p-2 text-right">
                          <Button size="sm" variant="ghost" onClick={() => setWoDetailDrawer(wo.work_order_id)}>View</Button>
                          {hasFeature('contractor_network') && !wo.contractor_id && (
                            <Button size="sm" variant="outline" className="ml-1" onClick={() => { setWoDetailDrawer(wo.work_order_id); }}>Assign</Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
        </CardContent>
      </Card>

      {/* Work order detail drawer */}
      {woDetailDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setWoDetailDrawer(null)}>
          <div className="w-full max-w-lg bg-white shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-midnight-blue">Work order details</h3>
              <button type="button" onClick={() => setWoDetailDrawer(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4">
              {woDetailLoading ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : woDetailData ? (
                <>
                  <p className="font-medium text-gray-900 mb-2">{woDetailData.description || '—'}</p>
                  <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
                    <dt className="text-gray-500">Status</dt>
                    <dd><span className={`px-1.5 py-0.5 rounded text-xs ${statusBadgeClass(woDetailData.status)}`}>{woDetailData.status || '—'}</span></dd>
                    <dt className="text-gray-500">Severity</dt><dd className="capitalize">{(woDetailData.severity || '—').toLowerCase()}</dd>
                    <dt className="text-gray-500">SLA complete by</dt><dd>{formatDate(woDetailData.sla_complete_by)}</dd>
                    <dt className="text-gray-500">Contractor</dt><dd>{woDetailData.contractor_id ? contractorLabel(woDetailData.contractor_id) : <span className="text-gray-400">Unassigned</span>}</dd>
                    <dt className="text-gray-500">Asset</dt><dd>{woDetailData.asset_id ? woDetailData.asset_id.slice(0, 8) + '…' : '—'}</dd>
                    <dt className="text-gray-500">Linked issue</dt>
                    <dd>
                      {woDetailData.issue_id ? (
                        <button type="button" className="text-electric-teal hover:underline" onClick={() => { navigate('/operations/issues'); setWoDetailDrawer(null); }}>View issue</button>
                      ) : '—'}
                    </dd>
                    <dt className="text-gray-500">Property</dt>
                    <dd>
                      {woDetailData.property_id ? (
                        <button type="button" className="text-electric-teal hover:underline" onClick={() => { navigate(`/properties/${woDetailData.property_id}`); setWoDetailDrawer(null); }}>{propertyLabel(woDetailData.property_id)}</button>
                      ) : '—'}
                    </dd>
                    <dt className="text-gray-500">Updated</dt><dd>{formatRelativeTime(woDetailData.updated_at)}</dd>
                  </dl>
                  {woDetailData.resolution_outcome && <p className="text-sm text-gray-600 mb-2">Outcome: {woDetailData.resolution_outcome}</p>}
                  {(woDetailData.cost_estimate_min != null || woDetailData.cost_estimate_max != null) && (
                    <p className="text-sm text-gray-600 mb-4">Cost estimate: £{woDetailData.cost_estimate_min ?? '—'} – £{woDetailData.cost_estimate_max ?? '—'}</p>
                  )}
                  <div className="rounded-lg border border-sky-200 bg-sky-50/80 p-3 text-sm text-sky-900 mb-4">
                    <p className="font-medium mb-1">Payment responsibility</p>
                    <p>Contractors are independent service providers engaged by you. You are responsible for paying the contractor. Pleerity does not process contractor payments.</p>
                  </div>
                  <div className="space-y-2 mb-4">
                    <label className="block text-sm font-medium text-gray-700">Update status</label>
                    <select
                      value={woDetailData.status || ''}
                      onChange={(e) => handleUpdateStatus(woDetailData.work_order_id, e.target.value)}
                      disabled={woUpdateSaving}
                      className="border border-gray-200 rounded-md px-3 py-2 text-sm w-full"
                    >
                      {WO_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </div>
                  {hasFeature('contractor_network') && (
                    <div className="mt-4">
                      <h4 className="font-medium text-gray-700 mb-2">Recommended contractors</h4>
                      {woRecommendLoading ? <p className="text-sm text-gray-500">Loading…</p> : woRecommendList?.length > 0 ? (
                        <ul className="space-y-2">
                          {woRecommendList.slice(0, 5).map((c) => {
                            const cid = c.contractor_id || c.id;
                            const showExplain = contractorExplainId === cid;
                            return (
                              <li key={cid} className="border border-gray-100 rounded overflow-hidden bg-gray-50/80">
                                <div className="flex items-center justify-between gap-2 text-sm p-2">
                                  <div>
                                    <span className="font-medium text-gray-900">{c.name || c.contractor_name || cid}</span>
                                    <div className="flex flex-wrap gap-x-3 gap-y-0 mt-0.5 text-xs text-gray-600">
                                      {c.performance_score != null && <span>Score: {Math.round(c.performance_score)}</span>}
                                      {c.reliability_score != null && <span>Reliability: {Math.round((c.reliability_score || 0) * 100)}%</span>}
                                      {(c.completed_jobs != null || c.assigned_jobs != null) && <span>Jobs completed: {c.completed_jobs ?? 0}</span>}
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
                                        setContractorExplainId(cid);
                                        if (contractorExplainData && contractorExplainId === cid) return;
                                        setContractorExplainData(null);
                                        setContractorExplainLoading(true);
                                        try {
                                          const res = await clientAPI.getContractorExplanation(cid);
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
                                    <Button size="sm" variant="outline" onClick={() => handleAssignContractor(woDetailData.work_order_id, cid)} disabled={woUpdateSaving}>Assign</Button>
                                  </div>
                                </div>
                                {showExplain && (
                                  <div className="px-2 pb-2 pt-0 border-t border-gray-100 text-xs text-gray-700">
                                    {contractorExplainLoading ? <p className="flex items-center gap-1"><Loader2 className="w-3 h-3 animate-spin" /> Loading…</p> : contractorExplainData ? (
                                      <>
                                        <p className="mt-1">{contractorExplainData.why_it_matters}</p>
                                        <p className="font-medium text-midnight-blue mt-1">{contractorExplainData.recommended_action_text}</p>
                                      </>
                                    ) : <p>Could not load explanation.</p>}
                                  </div>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      ) : <p className="text-sm text-gray-500">No recommendations.</p>}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 mt-4">
                    {woDetailData.property_id && (
                      <Button size="sm" variant="outline" onClick={() => { navigate(`/properties/${woDetailData.property_id}`); setWoDetailDrawer(null); }}>
                        <Building2 className="w-3 h-3 mr-1" /> View property
                      </Button>
                    )}
                    {hasFeature('invoicing') && woDetailData.contractor_id && woDetailData.property_id && (
                      <Button
                        size="sm"
                        variant="default"
                        className="bg-electric-teal hover:bg-electric-teal/90"
                        onClick={() => {
                          setInvoiceForm({
                            reference: '',
                            description: woDetailData.description?.slice(0, 200) || '',
                            submitted_amount: '',
                          });
                          setInvoiceModalOpen(woDetailData);
                        }}
                      >
                        <FileText className="w-3 h-3 mr-1" /> Record invoice
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => setWoDetailDrawer(null)}>Close</Button>
                  </div>
                </>
              ) : <p className="text-gray-500 py-4">Could not load work order.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Record invoice modal (from work order) */}
      {invoiceModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModalOpen(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-electric-teal" />
              Record invoice
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Create an invoice linked to this work order. It will appear in Approvals for review.
            </p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setInvoiceSaving(true);
                try {
                  await clientAPI.createInvoice({
                    property_id: invoiceModalOpen.property_id,
                    contractor_id: invoiceModalOpen.contractor_id,
                    work_order_id: invoiceModalOpen.work_order_id,
                    reference: invoiceForm.reference?.trim() || undefined,
                    description: invoiceForm.description?.trim() || undefined,
                    submitted_amount: invoiceForm.submitted_amount ? parseFloat(invoiceForm.submitted_amount) : undefined,
                  });
                  toast.success('Invoice created. You can review it in Operations → Approvals.');
                  setInvoiceModalOpen(null);
                  setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
                  navigate('/operations/approvals');
                } catch (err) {
                  toast.error(err?.response?.data?.detail || 'Failed to create invoice');
                } finally {
                  setInvoiceSaving(false);
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reference (optional)</label>
                <input
                  type="text"
                  value={invoiceForm.reference}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="e.g. INV-001"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <textarea
                  value={invoiceForm.description}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  rows={2}
                  placeholder="Work description"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount £ (optional)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={invoiceForm.submitted_amount}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full"
                  placeholder="0.00"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={invoiceSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {invoiceSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create invoice'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setInvoiceModalOpen(null)}>Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create work order modal */}
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
    </div>
  );
}
