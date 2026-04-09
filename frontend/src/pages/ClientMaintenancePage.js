/**
 * Operations → Jobs (/operations/work-orders): portfolio execution list (maintenance + compliance).
 * Summary KPIs, filters, table, SLA risk panel. Row actions open the canonical job page.
 * Gated by maintenance_workflows (EntitlementProtectedRoute; upgrade prompt when not entitled).
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI, parseApiError } from '../api/client';
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
  AlertTriangle,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';
import { issueSeverityLabel, workOrderStatusLabel } from '../domain/presentDomain';
import { assetIdParts } from '../utils/assetDisplay';
import { normalizeRouteId, resolveIssueDetailPath, resolvePropertyPath } from '../utils/clientPortalNavigation';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import { workOrderKindBadgeClassName, workOrderKindClientLabel } from '../utils/jobWorkflowUi';
import { cn } from '../lib/utils';

const WO_STATUS_OPTIONS = [
  { value: 'DRAFT', label: 'Draft' },
  { value: 'OPEN', label: 'Open' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'AWAITING_PARTS', label: 'Awaiting parts' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'VERIFIED', label: 'Verified' },
  { value: 'CLOSED', label: 'Closed job' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

/** True when client must use contractor routing (request → confirm), not direct PATCH assign. */
function workOrderNeedsContractorRouting(wo, hasComplianceEngine) {
  if (!wo) return false;
  const kind = (wo.work_order_kind || '').toUpperCase();
  if (kind === 'COMPLIANCE') return !!hasComplianceEngine;
  return !!wo.requires_client_assignment_confirmation;
}

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
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ property_id: '', description: '', category: 'general', severity: 'medium' });
  const [createSaving, setCreateSaving] = useState(false);
  const [invoiceModalOpen, setInvoiceModalOpen] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
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
        const detail = parseApiError(err, `Failed to load ${PORTAL_COPY.jobs.toLowerCase()}`);
        if (err?.response?.status === 403) {
          setMaintenanceError(detail || 'Maintenance workflows are not enabled for your account.');
        } else {
          setMaintenanceError(`Failed to load ${PORTAL_COPY.jobs.toLowerCase()}.`);
          toast.error(detail);
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

  useEffect(() => {
    const woid = searchParams.get('work_order_id');
    if (woid) {
      navigate(`/operations/jobs/${encodeURIComponent(woid)}`, { replace: true });
    }
  }, [searchParams, navigate]);

  useEffect(() => {
    const sla = searchParams.get('sla_state');
    if (sla) setFilterSlaState(sla);
  }, [searchParams]);
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

  const openRecordInvoice = (wo) => {
    if (!wo?.property_id || !wo?.contractor_id) return;
    setInvoiceForm({
      reference: '',
      description: (wo.description || '').slice(0, 200),
      submitted_amount: '',
    });
    setInvoiceModalOpen({
      work_order_id: wo.work_order_id,
      property_id: wo.property_id,
      contractor_id: wo.contractor_id,
    });
  };

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
        toast.success(`${PORTAL_COPY.job} created`);
        setCreateOpen(false);
        setCreateForm({ property_id: '', description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(parseApiError(err, 'Create failed')))
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
      <div className="p-4 sm:p-6 max-w-2xl mx-auto w-full min-w-0 client-portal-prose">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <Wrench className="w-7 h-7 shrink-0" />
          {PORTAL_COPY.jobs}
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
    <div className="p-4 sm:p-6 max-w-6xl mx-auto w-full min-w-0 client-portal-prose">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between mb-4">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2 min-w-0">
          <Wrench className="w-7 h-7 shrink-0" />
          {PORTAL_COPY.jobs}
        </h1>
        <div className="flex flex-col sm:flex-row gap-2 w-full lg:w-auto lg:shrink-0">
          <Button variant="outline" className="w-full sm:w-auto min-h-11 justify-center" onClick={() => navigate('/operations/issues')}>
            View maintenance issues
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="w-full sm:w-auto min-h-11 justify-center bg-electric-teal hover:bg-electric-teal/90">
            <Plus className="w-4 h-4 mr-2 shrink-0" />
            Report issue
          </Button>
        </div>
      </div>
      <p className="text-gray-600 mb-6 text-sm sm:text-base break-words">
        {PORTAL_COPY.jobsListDescription} Track status, request contractors where confirmation is required, and monitor SLA deadlines.
      </p>

      {/* Summary KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-2 sm:gap-3 mb-6">
        <button
          type="button"
          onClick={() => applySummaryFilter('status', '')}
          className="p-3 rounded-lg border border-gray-200 bg-white text-left hover:bg-gray-50 transition-colors min-w-0"
        >
          <p className="text-xs text-gray-500 uppercase tracking-wide truncate">Active</p>
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
                      <span className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${i.risk === 'high' || i.risk === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{issueSeverityLabel(i.risk)}</span>
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
            <div className="w-full sm:w-auto min-w-0 flex-1 sm:flex-initial">
              <label className="block text-xs text-gray-500 mb-1">Status</label>
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full sm:w-auto min-h-11 max-w-full">
                <option value="">All</option>
                {WO_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="w-full sm:w-auto min-w-0 flex-1 sm:flex-initial">
              <label className="block text-xs text-gray-500 mb-1">Property</label>
              <select value={filterProperty} onChange={(e) => setFilterProperty(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full min-h-11 max-w-full sm:min-w-[160px]">
                <option value="">All</option>
                {properties.map((p) => <option key={p.property_id} value={p.property_id}>{propertyLabel(p.property_id)}</option>)}
              </select>
            </div>
            {hasFeature('contractor_network') && (
              <div className="w-full sm:w-auto min-w-0 flex-1 sm:flex-initial">
                <label className="block text-xs text-gray-500 mb-1">Contractor</label>
                <select value={filterContractor} onChange={(e) => setFilterContractor(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full min-h-11 max-w-full sm:min-w-[160px]">
                  <option value="">All</option>
                  {contractors.map((c) => <option key={c.contractor_id || c.id} value={c.contractor_id || c.id}>{c.name || c.contractor_name || c.contractor_id}</option>)}
                </select>
              </div>
            )}
            <div className="w-full sm:w-auto min-w-0 flex-1 sm:flex-initial">
              <label className="block text-xs text-gray-500 mb-1">SLA state</label>
              <select value={filterSlaState} onChange={(e) => setFilterSlaState(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full sm:w-auto min-h-11">
                <option value="">All</option>
                <option value="on_track">On track</option>
                <option value="near_breach">Near breach</option>
                <option value="breached">Breached</option>
              </select>
            </div>
            <div className="w-full sm:w-auto">
              <label className="block text-xs text-gray-500 mb-1">From date</label>
              <input type="date" value={filterFromDate} onChange={(e) => setFilterFromDate(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full sm:w-auto min-h-11" />
            </div>
            <div className="w-full sm:w-auto">
              <label className="block text-xs text-gray-500 mb-1">To date</label>
              <input type="date" value={filterToDate} onChange={(e) => setFilterToDate(e.target.value)} className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full sm:w-auto min-h-11" />
            </div>
            <div className="w-full min-w-0 sm:flex-1 sm:min-w-[12rem]">
              <label className="block text-xs text-gray-500 mb-1">Search</label>
              <input
                type="text"
                placeholder="Ref, title, property, contractor…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="border border-gray-200 rounded-md px-3 py-2.5 text-sm w-full min-h-11 max-w-full"
              />
            </div>
            <Button variant="outline" className="w-full sm:w-auto min-h-11" onClick={clearFilters}>Clear filters</Button>
            <Button variant="ghost" className="w-full sm:w-auto min-h-11" onClick={loadWorkOrders}>Refresh</Button>
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
            <div className="md:hidden space-y-3">
              {slaRiskList.slice(0, 10).map((wo) => {
                const hr = hoursRemainingOrOverdue(wo.sla_complete_by);
                return (
                  <div key={wo.work_order_id} className="rounded-lg border border-amber-200 bg-white p-4 space-y-2">
                    <p className="text-xs font-mono text-gray-500">{wo.work_order_id}</p>
                    <p className="font-medium text-gray-900 break-words">{wo.description || '—'}</p>
                    <p className="text-sm text-gray-600 break-words">{propertyLabel(wo.property_id)}</p>
                    <p className="text-sm">
                      SLA due {formatDate(wo.sla_complete_by)}
                      {hr && <span className={`ml-1 ${hr.overdue ? 'text-red-600 font-medium' : 'text-amber-600'}`}>{hr.text}</span>}
                    </p>
                    <span className={`inline-flex px-2 py-1 rounded text-xs ${statusBadgeClass(wo.status)}`}>{workOrderStatusLabel(wo.status)}</span>
                    <Button className="w-full min-h-11 mt-2" variant="outline" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>View job</Button>
                  </div>
                );
              })}
            </div>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-600">
                    <th className="p-2">Job</th>
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
                        <td className="p-2 max-w-[10rem] break-words">{propertyLabel(wo.property_id)}</td>
                        <td className="p-2">{formatDate(wo.sla_complete_by)} {hr && <span className={hr.overdue ? 'text-red-600' : 'text-amber-600'}>{hr.text}</span>}</td>
                        <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${statusBadgeClass(wo.status)}`}>{workOrderStatusLabel(wo.status)}</span></td>
                        <td className="p-2 text-right">
                          <Button size="sm" variant="outline" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>View</Button>
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

      {/* Jobs table (API: maintenance work orders) */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">{PORTAL_COPY.jobs}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : workOrders.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 mb-4">No {PORTAL_COPY.jobs.toLowerCase()} have been created across your portfolio yet.</p>
              <div className="flex gap-2 justify-center flex-wrap">
                <Button variant="outline" onClick={() => navigate('/operations/issues')}>View maintenance issues</Button>
                <Button onClick={() => setCreateOpen(true)} className="bg-electric-teal hover:bg-electric-teal/90">Report issue</Button>
              </div>
            </div>
          ) : !filteredBySearch.length ? (
            <div className="py-8 text-center">
              <p className="text-gray-500 mb-4">No {PORTAL_COPY.jobs.toLowerCase()} match your current filters.</p>
              <Button variant="outline" onClick={clearFilters}>Clear filters</Button>
            </div>
          ) : (
            <>
              <div className="md:hidden space-y-3">
                {filteredBySearch.map((wo) => {
                  const sla = slaStateLabel(wo);
                  return (
                    <div key={wo.work_order_id} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
                      <div className="flex flex-wrap gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${statusBadgeClass(wo.status)}`}>{workOrderStatusLabel(wo.status)}</span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${sla.class}`}>{sla.label}</span>
                        <span className={cn('px-2 py-1 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                        <span className="text-xs text-gray-500 ml-auto">{issueSeverityLabel(wo.severity)}</span>
                      </div>
                      <div>
                        <p className="text-xs font-mono text-gray-500 break-all">{wo.work_order_id}</p>
                        <p className="font-semibold text-midnight-blue mt-1 break-words">{wo.description || 'Job'}</p>
                        <button
                          type="button"
                          onClick={() => {
                            const pid = normalizeRouteId(wo.property_id);
                            if (pid) navigate(resolvePropertyPath(pid));
                          }}
                          className="text-sm text-electric-teal hover:underline mt-2 text-left break-words w-full"
                        >
                          {propertyLabel(wo.property_id)}
                        </button>
                      </div>
                      <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs text-gray-600">
                        <dt>SLA due</dt>
                        <dd>{formatDate(wo.sla_complete_by)}</dd>
                        <dt>Contractor</dt>
                        <dd className="break-words">{wo.contractor_id ? contractorLabel(wo.contractor_id) : 'Unassigned'}</dd>
                        <dt>Updated</dt>
                        <dd>{formatRelativeTime(wo.updated_at)}</dd>
                      </dl>
                      {wo.asset_id && (() => {
                        const asset = assetIdParts(wo.asset_id);
                        if (!asset.isTruncated) {
                          return (
                            <p className="text-xs text-gray-600 pt-1">
                              Linked asset · <span className="font-mono text-gray-900">{asset.full}</span>
                            </p>
                          );
                        }
                        return (
                          <details className="rounded-md border border-gray-100 bg-gray-50/80">
                            <summary className="cursor-pointer px-3 py-2.5 text-xs text-electric-teal font-medium min-h-[44px] flex items-center gap-1">
                              Linked asset · <span className="font-mono text-gray-800">{asset.short}</span>
                            </summary>
                            <div className="px-3 pb-3 border-t border-gray-100">
                              <p className="text-xs text-gray-500 mt-2 mb-1">Full reference</p>
                              <code className="text-xs font-mono text-gray-900 break-all block bg-white border rounded px-2 py-2">{asset.full}</code>
                            </div>
                          </details>
                        );
                      })()}
                      <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
                        <Button className="w-full min-h-11" variant="default" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>View details</Button>
                        {hasFeature('invoicing') && wo.contractor_id && wo.property_id && (
                          <Button className="w-full min-h-11" variant="outline" onClick={() => openRecordInvoice(wo)}>
                            Record invoice
                          </Button>
                        )}
                        {hasFeature('contractor_network') && !wo.contractor_id && (
                          <Button className="w-full min-h-11" variant="outline" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>
                            {workOrderNeedsContractorRouting(wo, hasFeature('compliance_engine')) ? 'Request contractor' : 'Assign contractor'}
                          </Button>
                        )}
                        {wo.issue_id && (
                          <Button
                            className="w-full min-h-11"
                            variant="outline"
                            onClick={() => navigate(resolveIssueDetailPath(wo.issue_id))}
                          >
                            View linked issue
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="p-2">Ref / Title</th>
                      <th className="p-2">Job type</th>
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
                      const rowAsset = wo.asset_id ? assetIdParts(wo.asset_id) : null;
                      return (
                        <tr key={wo.work_order_id} className="border-b hover:bg-gray-50">
                          <td className="p-2 max-w-[200px]">
                            <span className="font-mono text-xs text-gray-500 block truncate">{wo.work_order_id?.slice(0, 8)}…</span>
                            <span className="font-medium truncate block" title={wo.description}>{wo.description || '—'}</span>
                          </td>
                          <td className="p-2 whitespace-nowrap">
                            <span className={cn('inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                          </td>
                          <td className="p-2">
                            <button type="button" onClick={() => {
                            const pid = normalizeRouteId(wo.property_id);
                            if (pid) navigate(resolvePropertyPath(pid));
                          }} className="text-electric-teal hover:underline truncate max-w-[120px] block text-left">
                              {propertyLabel(wo.property_id)}
                            </button>
                          </td>
                          <td className="p-2">
                            {wo.issue_id ? (
                              <button
                                type="button"
                                onClick={() => navigate(resolveIssueDetailPath(wo.issue_id))}
                                className="text-electric-teal hover:underline text-xs truncate max-w-[80px] block"
                              >
                                View
                              </button>
                            ) : '—'}
                          </td>
                          <td className="p-2 text-gray-600 max-w-[6rem]">
                            {rowAsset ? (
                              <span className="font-mono text-xs" title={rowAsset.full}>
                                {rowAsset.short}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="p-2">{issueSeverityLabel(wo.severity)}</td>
                          <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${statusBadgeClass(wo.status)}`}>{workOrderStatusLabel(wo.status)}</span></td>
                          <td className="p-2 max-w-[8rem] break-words">{wo.contractor_id ? contractorLabel(wo.contractor_id) : <span className="text-gray-400">Unassigned</span>}</td>
                          <td className="p-2 whitespace-nowrap">{formatDate(wo.sla_complete_by)}</td>
                          <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${sla.class}`}>{sla.label}</span></td>
                          <td className="p-2 text-gray-500 whitespace-nowrap">{formatRelativeTime(wo.updated_at)}</td>
                          <td className="p-2 text-right whitespace-nowrap">
                            <Button size="sm" variant="ghost" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>View</Button>
                            {hasFeature('invoicing') && wo.contractor_id && wo.property_id && (
                              <Button size="sm" variant="outline" className="ml-1" onClick={() => openRecordInvoice(wo)}>
                                Invoice
                              </Button>
                            )}
                            {hasFeature('contractor_network') && !wo.contractor_id && (
                              <Button size="sm" variant="outline" className="ml-1" onClick={() => navigate(`/operations/jobs/${encodeURIComponent(wo.work_order_id)}`)}>
                                {workOrderNeedsContractorRouting(wo, hasFeature('compliance_engine')) ? 'Request' : 'Assign'}
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
        </CardContent>
      </Card>

      {/* Record invoice modal (from jobs list) */}
      {invoiceModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModalOpen(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-electric-teal" />
              Record invoice
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Create an invoice linked to this {PORTAL_COPY.job.toLowerCase()}. It will appear in Approvals for review.
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
                  toast.error(parseApiError(err, 'Failed to create invoice'));
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

      {/* Create job (report issue) modal */}
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
