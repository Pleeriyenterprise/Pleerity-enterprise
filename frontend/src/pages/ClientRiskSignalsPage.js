/**
 * Operations → Risk Signals: portfolio-wide predictive maintenance and risk intelligence.
 * Uses GET /client/maintenance/risk-signals (filters, summary, highPriority), GET by signal_id for drawer.
 * Gated by predictive_maintenance.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { buildSafeQueryPath, normalizeRouteId, resolveIssueDetailPath, resolvePropertyPath } from '../utils/clientPortalNavigation';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '../components/ui/sheet';
import { Badge } from '../components/ui/badge';
import {
  TrendingUp,
  Loader2,
  AlertCircle,
  Search,
  Building2,
  Package,
  Eye,
  XCircle,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { useEntitlements } from '../contexts/EntitlementsContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  humanRiskType,
  humanSeverity,
  severityBadgeClass,
  humanAction,
  humanStatus,
  humanTrend,
  groupSignalsByProperty,
} from '../utils/riskPresentation';
import { assetIdParts } from '../utils/assetDisplay';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';
import { ContractorNetworkLockedModal } from '../components/client/ContractorNetworkLockedModal';
import { isIssueAssignContractorLocked } from '../utils/contractorNetworkEntitlement';
import { resolveRiskSignalPrimaryKey, normalizeOperationalPrimaryKey } from '../utils/primaryActionResolver';
import NextActionHero from '../components/operational/NextActionHero';
import ListCognitionChip from '../components/operational/ListCognitionChip';
import { getTrackedRequirementsForProperty } from '../utils/portalRequirementAttention';

/** Rent Operations / financial_operational signals do not affect compliance score. */
function isOperationalAdvisorySignal(signal) {
  return (
    signal?.source === 'rent_operations' || signal?.signal_category === 'financial_operational'
  );
}

const RISK_LEVELS = [
  { value: '', label: 'All levels' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];
const TRENDS = [
  { value: '', label: 'All trends' },
  { value: 'rising', label: 'Rising' },
  { value: 'stable', label: 'Stable' },
  { value: 'improving', label: 'Improving' },
];
const STATUSES = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
];

function riskLevelBadgeClass(level) {
  const cls = severityBadgeClass(level);
  return `${cls} border-transparent`;
}

function ClientRiskSignalsPageInner() {
  const { hasFeature } = useEntitlements();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerSignalId, setDrawerSignalId] = useState(null);
  const [drawerSignal, setDrawerSignal] = useState(null);
  const [drawerExplanation, setDrawerExplanation] = useState(null);
  const [drawerExplanationLoading, setDrawerExplanationLoading] = useState(false);
  const [drawerExplanationOpen, setDrawerExplanationOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  /** Read-only GET .../suggested-actions (primary + codes + alternatives); loaded with drawer */
  const [drawerSuggestedView, setDrawerSuggestedView] = useState(null);
  const [actionFromSignal, setActionFromSignal] = useState(null); // 'issue' | 'work_order' | 'schedule_inspection' | 'log_inspection_issue'
  const [drawerPrimaryBusy, setDrawerPrimaryBusy] = useState(false);
  const [dismissTargetId, setDismissTargetId] = useState(null);
  const [dismissReason, setDismissReason] = useState('no_action_required');
  const [dismissSaving, setDismissSaving] = useState(false);
  const [arrangeOpen, setArrangeOpen] = useState(false);
  /** When opening arrange from a list row, React state for drawer id may not flush before confirm — use ref. */
  const signalIdForArrangeRef = useRef(null);
  const [arrangePropertyId, setArrangePropertyId] = useState('');
  const [arrangeRequirements, setArrangeRequirements] = useState([]);
  const [arrangeReqPick, setArrangeReqPick] = useState('');
  const [arrangeLoading, setArrangeLoading] = useState(false);
  const [planJobGate, setPlanJobGate] = useState(null);
  const [contractorNetworkLockedOpen, setContractorNetworkLockedOpen] = useState(false);
  const [filters, setFilters] = useState({
    risk_level: '',
    risk_type: '',
    property_id: '',
    trend: '',
    status: '',
    q: '',
    from: '',
    to: '',
  });

  const buildParams = useCallback(() => {
    const params = { limit: 500 };
    if (filters.risk_level) params.risk_level = filters.risk_level;
    if (filters.risk_type) params.risk_type = filters.risk_type;
    if (filters.property_id) params.property_id = filters.property_id;
    if (filters.trend) params.trend = filters.trend;
    if (filters.status) params.status = filters.status;
    if (filters.q?.trim()) params.q = filters.q.trim();
    if (filters.from) params.from = filters.from;
    if (filters.to) params.to = filters.to;
    return params;
  }, [filters]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params = buildParams();
    Promise.all([
      clientAPI.getRiskSignals(params),
      clientAPI.getProperties().catch(() => ({ data: { properties: [] } })),
    ])
      .then(([signalsRes, propsRes]) => {
        setData(signalsRes.data || null);
        setProperties(propsRes.data?.properties || []);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Predictive maintenance is not enabled for your account.');
        } else {
          setError('Failed to load risk signals.');
          toast.error(err?.response?.data?.detail || 'Failed to load risk signals');
        }
        setData(null);
      })
      .finally(() => setLoading(false));
  }, [buildParams]);

  useEffect(() => {
    load();
  }, [load]);

  // Real-time refresh when actions emit compliance outcomes elsewhere in client portal.
  useEffect(() => {
    const onOutcome = () => {
      load();
      if (drawerSignalId) {
        setDrawerLoading(true);
        setDrawerSuggestedView(null);
        Promise.all([
          clientAPI.getRiskSignal(drawerSignalId).then((res) => res.data || null),
          clientAPI.getRiskSignalSuggestedActions(drawerSignalId).then((res) => res.data || null),
        ])
          .then(([sig, view]) => {
            setDrawerSignal(sig);
            setDrawerSuggestedView(sig ? view : null);
          })
          .catch(() => {
            setDrawerSignal(null);
            setDrawerSuggestedView(null);
          })
          .finally(() => setDrawerLoading(false));
      }
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [load, drawerSignalId]);

  useEffect(() => {
    const sid = searchParams.get('signal_id');
    if (sid) setDrawerSignalId(sid);
  }, [searchParams]);

  useEffect(() => {
    if (!drawerSignalId) {
      setDrawerExplanation(null);
      setDrawerExplanationOpen(false);
      setDrawerSignal(null);
      setDrawerSuggestedView(null);
      return;
    }
    setDrawerLoading(true);
    setDrawerSuggestedView(null);
    Promise.all([
      clientAPI.getRiskSignal(drawerSignalId).then((res) => res.data || null),
      clientAPI.getRiskSignalSuggestedActions(drawerSignalId).then((res) => res.data || null),
    ])
      .then(([sig, view]) => {
        setDrawerSignal(sig);
        setDrawerSuggestedView(sig ? view : null);
        if (!sig) toast.error('Failed to load risk signal details');
      })
      .catch(() => {
        setDrawerSignal(null);
        setDrawerSuggestedView(null);
        toast.error('Failed to load risk signal details');
      })
      .finally(() => setDrawerLoading(false));
  }, [drawerSignalId]);

  const propertyLabel = (propertyId) => {
    if (!properties?.length) return propertyId;
    const p = properties.find((x) => x.property_id === propertyId);
    return p?.nickname || p?.address_line_1 || propertyId;
  };

  const openCreateWorkOrder = (propertyId, description) => {
    const pid = normalizeRouteId(propertyId);
    navigate(
      buildSafeQueryPath('/operations/work-orders', {
        ...(pid ? { property_id: pid } : {}),
        ...(description ? { description: String(description) } : {}),
      })
    );
  };

  const applyFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const refreshAfterStatusChange = () => {
    load();
    setDrawerSignalId(null);
  };

  const handleAcknowledge = async (signalId) => {
    try {
      await clientAPI.updateRiskSignalStatus(signalId, 'acknowledged');
      toast.success('Risk signal acknowledged');
      refreshAfterStatusChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to acknowledge');
    }
  };

  const openDismissDialog = (signalId) => {
    setDismissTargetId(signalId);
    setDismissReason('no_action_required');
  };

  const confirmDismissSignal = async () => {
    if (!dismissTargetId) return;
    setDismissSaving(true);
    try {
      await clientAPI.dismissRiskSignal(dismissTargetId, dismissReason);
      toast.success('Risk signal dismissed');
      setDismissTargetId(null);
      refreshAfterStatusChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not dismiss risk signal');
    } finally {
      setDismissSaving(false);
    }
  };

  const openArrangeInspection = async (propertyId) => {
    if (!hasFeature('compliance_engine') || !hasFeature('maintenance_workflows')) {
      toast.error('Booking a compliance inspection requires compliance execution and maintenance workflows.');
      return;
    }
    setArrangePropertyId(propertyId);
    setArrangeReqPick('');
    setArrangeOpen(true);
    setArrangeLoading(true);
    try {
      const res = await clientAPI.getPropertyRequirements(propertyId);
      const rows = res.data?.requirements || [];
      const list = Array.isArray(rows) ? rows : [];
      setArrangeRequirements(getTrackedRequirementsForProperty(propertyId, list));
    } catch {
      setArrangeRequirements([]);
      toast.error('Could not load requirements for this property.');
    } finally {
      setArrangeLoading(false);
    }
  };

  const confirmArrangeInspection = async () => {
    const effectiveSignalId = signalIdForArrangeRef.current || drawerSignalId;
    if (!effectiveSignalId || !arrangeReqPick) {
      toast.error('Select a requirement to continue.');
      return;
    }
    const picked = arrangeRequirements.find((r) => (r.requirement_id || r.id) === arrangeReqPick);
    const reqCode = picked?.requirement_code || picked?.requirement_type || picked?.code;
    if (!reqCode) {
      toast.error('Selected row has no requirement code.');
      return;
    }
    setActionFromSignal('schedule_inspection');
    try {
      const res = await clientAPI.arrangeComplianceInspectionFromRiskSignal(effectiveSignalId, {
        requirement_code: String(reqCode),
        linked_property_requirement_id: arrangeReqPick,
        compliance_purpose: 'inspection',
      });
      const wid = res.data?.work_order?.work_order_id;
      toast.success('Compliance inspection job created. Open the job to request a contractor.');
      setArrangeOpen(false);
      signalIdForArrangeRef.current = null;
      setDrawerSignalId(null);
      load();
      if (wid) navigate(buildSafeQueryPath('/operations/work-orders', { work_order_id: wid }));
    } catch (e) {
      if (
        openPlanRestrictedJobGate(e, setPlanJobGate, {
          propertyId: arrangePropertyId || drawerSignal?.property_id,
        })
      ) {
        return;
      }
      toast.error(e?.response?.data?.detail || 'Could not arrange inspection');
    } finally {
      setActionFromSignal(null);
    }
  };

  const runRiskSignalPrimaryAction = async (s) => {
    if (!s?.signal_id) return;
    const hasMaint = hasFeature('maintenance_workflows');
    const hasComp = hasFeature('compliance_engine');
    const primary = resolveRiskSignalPrimaryKey(s, hasMaint, hasComp);
    const { key, url, continuation } = primary;
    const normalizedKey = normalizeOperationalPrimaryKey(key);

    if (isIssueAssignContractorLocked(primary, hasFeature('contractor_network'))) {
      setContractorNetworkLockedOpen(true);
      return;
    }

    if (
      url &&
      (normalizedKey === 'view_workflow' ||
        normalizedKey === 'assign_contractor' ||
        normalizedKey === 'next_action' ||
        continuation)
    ) {
      navigate(url.startsWith('/') ? url : `/${url}`);
      return;
    }
    if (normalizedKey === 'view_workflow' || continuation) {
      const woId =
        s?.operational_continuation?.existing_work_order_id ||
        s?.propagation?.work_order_id;
      if (woId) {
        navigate(`/operations/jobs/${woId}`);
        return;
      }
    }
    if (normalizedKey === 'compliance_inspection') {
      signalIdForArrangeRef.current = s.signal_id;
      setDrawerSignalId(s.signal_id);
      await openArrangeInspection(s.property_id);
      return;
    }
    if (normalizedKey === 'log_inspection_issue') {
      try {
        await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {});
        toast.success('Logged for follow-up');
        refreshAfterStatusChange();
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Failed');
      }
      return;
    }
    if (normalizedKey === 'maintenance_job') {
      if (hasMaint) {
        try {
          const res = await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
          const replay = Boolean(res.data?.idempotent_replay || res.data?.operational_continuation?.has_active_lineage);
          const woId = res.data?.work_order_id || res.data?.existing_work_order_id;
          if (replay && woId) {
            toast.success(res.data?.operational_continuation?.user_safe_reason || 'Active workflow already exists — opening it.');
            navigate(`/operations/jobs/${woId}`);
          } else {
            toast.success('Job started');
          }
          setDrawerSignalId(null);
          load();
        } catch (e) {
          if (openPlanRestrictedJobGate(e, setPlanJobGate, { propertyId: s.property_id })) return;
          toast.error(e?.response?.data?.detail || 'Failed');
        }
      } else {
        setDrawerSignalId(null);
        openCreateWorkOrder(s.property_id, s.recommended_action);
      }
      return;
    }
    if (normalizedKey === 'maintenance_issue') {
      try {
        const res = await clientAPI.createIssueFromRiskSignal(s.signal_id, {});
        toast.success('Logged for follow-up');
        setDrawerSignalId(null);
        if (res?.data?.issue_id) navigate(resolveIssueDetailPath(res.data.issue_id));
        load();
      } catch (e) {
        toast.error(e?.response?.data?.detail || 'Failed');
      }
      return;
    }
    setDrawerSignalId(s.signal_id);
  };

  const riskTypesFromSignals = (signals) => {
    const set = new Set();
    (signals || []).forEach((s) => s.risk_type && set.add(s.risk_type));
    return Array.from(set).sort();
  };

  if (error && !loading) {
    return (
      <div className="p-4 sm:p-6 max-w-2xl mx-auto w-full min-w-0 client-portal-prose">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <TrendingUp className="w-7 h-7 shrink-0" />
          Risk signals
        </h1>
        <Card className="border border-slate-200 bg-slate-50/90 border-l-4 border-l-brand-info">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-brand-info shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-midnight-blue">Predictive maintenance not enabled</p>
              <p className="text-sm text-slate-700 mt-2 leading-relaxed">{error}</p>
              <p className="text-sm text-slate-600 mt-3 leading-relaxed">
                Contact your account administrator or support to enable predictive maintenance for your account.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const summary = data?.summary || {};
  const signals = data?.signals || [];
  const highPriority = data?.highPriority || [];
  const hasFilters =
    filters.risk_level ||
    filters.risk_type ||
    filters.property_id ||
    filters.trend ||
    filters.status ||
    (filters.q || '').trim() ||
    filters.from ||
    filters.to;

  return (
    <div className="p-4 sm:p-6 max-w-[1400px] mx-auto w-full min-w-0 client-portal-prose">
      <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <TrendingUp className="w-7 h-7 shrink-0" />
        Risk signals
      </h1>
      <p className="text-slate-600 mb-6 text-sm sm:text-base leading-relaxed break-words">
        Predictive risk signals from your property data — each item suggests a next operational step when you are ready. Acknowledging,
        resolving, or dismissing a signal is <span className="font-medium text-gray-800">risk-layer housekeeping only</span> and does
        not by itself restore compliance; follow obligations, evidence, and verification where they apply.
      </p>

      {(() => {
        const grouped = groupSignalsByProperty(signals);
        const urgent = signals.filter((s) => ['critical', 'high'].includes((s.risk_level || '').toLowerCase())).length;
        const medium = signals.filter((s) => (s.risk_level || '').toLowerCase() === 'medium').length;
        const top = grouped.slice(0, 3).map((g) => g.propertyName).join(', ');
        return (
          <Card className="mb-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">At-a-glance summary</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-700 space-y-1">
              <p>{signals.length} active risk signals across {grouped.length} properties.</p>
              <p>{urgent} urgent, {medium} needs attention, and {Math.max(signals.length - urgent - medium, 0)} monitor.</p>
              <p>Most affected properties: {top || 'None with active signals in this view'}.</p>
            </CardContent>
          </Card>
        );
      })()}

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3 mb-6">
        {[
          { key: 'total', label: 'Total', value: summary.total ?? 0, filter: null },
          { key: 'high', label: 'Urgent', value: summary.high ?? 0, filter: { risk_level: 'high' } },
          { key: 'medium', label: 'Needs attention', value: summary.medium ?? 0, filter: { risk_level: 'medium' } },
          { key: 'low', label: 'Monitor', value: summary.low ?? 0, filter: { risk_level: 'low' } },
          { key: 'properties', label: 'Properties affected', value: summary.propertiesAffected ?? 0, filter: null },
          { key: 'preventive', label: 'Preventive actions', value: summary.preventiveActions ?? 0, filter: null },
        ].map(({ key, label, value, filter }) => (
          <Card
            key={key}
            className={`cursor-pointer transition-colors hover:shadow-md ${filter && value > 0 ? 'hover:border-electric-teal' : ''}`}
            onClick={() => filter && value > 0 && setFilters((f) => ({ ...f, ...filter }))}
          >
            <CardContent className="p-3 sm:p-4 min-w-0">
              <p className="text-xs text-muted-foreground uppercase tracking-wide truncate">{label}</p>
              <p className="text-lg sm:text-xl font-semibold text-midnight-blue mt-1">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filter bar */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3 [&_button]:min-h-11">
          <div className="w-full sm:w-48">
            <label className="text-xs text-muted-foreground block mb-1">Priority</label>
            <Select value={filters.risk_level || ' '} onValueChange={(v) => applyFilter('risk_level', v === ' ' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="All levels" /></SelectTrigger>
              <SelectContent>
                {RISK_LEVELS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || ' '}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48">
            <label className="text-xs text-muted-foreground block mb-1">Risk type</label>
            <Select value={filters.risk_type || ' '} onValueChange={(v) => applyFilter('risk_type', v === ' ' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="All types" /></SelectTrigger>
              <SelectContent>
                <SelectItem value=" ">All types</SelectItem>
                    {riskTypesFromSignals(signals).map((rt) => (
                  <SelectItem key={rt} value={rt}>{humanRiskType(rt)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48">
            <label className="text-xs text-muted-foreground block mb-1">Property</label>
            <Select value={filters.property_id || ' '} onValueChange={(v) => applyFilter('property_id', v === ' ' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="All properties" /></SelectTrigger>
              <SelectContent>
                <SelectItem value=" ">All properties</SelectItem>
                {properties.map((p) => (
                  <SelectItem key={p.property_id} value={p.property_id}>
                    {p.nickname || p.address_line_1 || p.property_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-36">
            <label className="text-xs text-muted-foreground block mb-1">Trend</label>
            <Select value={filters.trend || ' '} onValueChange={(v) => applyFilter('trend', v === ' ' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                {TRENDS.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || ' '}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-36">
            <label className="text-xs text-muted-foreground block mb-1">Status</label>
            <Select value={filters.status || ' '} onValueChange={(v) => applyFilter('status', v === ' ' ? '' : v)}>
              <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
              <SelectContent>
                {STATUSES.map((o) => (
                  <SelectItem key={o.value || 'all'} value={o.value || ' '}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-48 flex-1 min-w-[120px]">
            <label className="text-xs text-muted-foreground block mb-1">Search</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Risk type, action, reasons…"
                value={filters.q}
                onChange={(e) => applyFilter('q', e.target.value)}
                className="pl-8 min-h-11 w-full"
              />
            </div>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <div className="flex-1 min-w-0">
              <label className="text-xs text-muted-foreground block mb-1">From</label>
              <Input
                type="date"
                value={filters.from}
                onChange={(e) => applyFilter('from', e.target.value)}
                className="w-full sm:w-36 min-h-11"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-xs text-muted-foreground block mb-1">To</label>
              <Input
                type="date"
                value={filters.to}
                onChange={(e) => applyFilter('to', e.target.value)}
                className="w-full sm:w-36 min-h-11"
              />
            </div>
          </div>
          <Button onClick={load} variant="secondary" className="w-full sm:w-auto min-h-11">Apply</Button>
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setFilters({
                  risk_level: '',
                  risk_type: '',
                  property_id: '',
                  trend: '',
                  status: '',
                  q: '',
                  from: '',
                  to: '',
                })
              }
            >
              Clear
            </Button>
          )}
        </CardContent>
      </Card>

      {/* High Priority panel */}
      {highPriority.length > 0 && (
        <Card className="mb-6 border border-slate-200 bg-slate-50/90 border-l-4 border-l-brand-danger">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-midnight-blue">
              <AlertCircle className="w-4 h-4 text-brand-danger shrink-0" />
              Urgent risk signals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {highPriority.slice(0, 15).map((s) => (
                <li
                  key={s.signal_id}
                  className="flex flex-col gap-3 p-4 rounded-lg bg-white border border-slate-200 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-900 break-words">{humanRiskType(s)}</p>
                    <p className="text-sm text-gray-700 break-words">{propertyLabel(s.property_id)}</p>
                    <p className="text-sm text-gray-600 mt-0.5 break-words line-clamp-3">{humanAction(s.recommended_action, s)}</p>
                    {Array.isArray(s.reasons) && s.reasons[0] && (
                      <p className="text-xs text-gray-500 mt-1 break-words">{s.reasons[0]}</p>
                    )}
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2 shrink-0 w-full sm:w-auto">
                    <Button
                      className="w-full sm:w-auto min-h-11 justify-center"
                      onClick={() => runRiskSignalPrimaryAction(s)}
                    >
                      {
                        resolveRiskSignalPrimaryKey(s, hasFeature('maintenance_workflows'), hasFeature('compliance_engine'))
                          .label
                      }
                    </Button>
                    <Button className="w-full sm:w-auto min-h-11 justify-center" variant="outline" onClick={() => setDrawerSignalId(s.signal_id)}>
                      <Eye className="w-4 h-4 mr-1 shrink-0" /> View details
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between md:space-y-0 pb-2">
          <CardTitle>Active risk signals</CardTitle>
          {summary.lastRecalculatedAt && (
            <span className="text-xs text-muted-foreground break-words">
              Last recalculated: {new Date(summary.lastRecalculatedAt).toLocaleString()}
            </span>
          )}
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : signals.length === 0 ? (
            <div className="py-12 text-center">
              {hasFilters ? (
                <>
                  <p className="text-gray-600 font-medium">No risk signals match your current filters.</p>
                  <p className="text-sm text-gray-500 mt-1">Try clearing filters or adjusting the date range.</p>
                  <Button variant="outline" size="sm" className="mt-4" onClick={() => setFilters({ risk_level: '', risk_type: '', property_id: '', trend: '', status: '', q: '', from: '', to: '' })}>
                    Clear filters
                  </Button>
                </>
              ) : (
                <>
                  <Package className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                  <p className="text-gray-600 font-medium">No active risk signals</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Risk signals are generated from property data (assets, jobs, compliance context). They refresh when data changes or on the scheduled update.
                  </p>
                  <div className="flex gap-2 justify-center mt-4">
                    <Button variant="outline" size="sm" onClick={() => navigate('/properties')}>
                      <Building2 className="w-4 h-4 mr-1" /> View properties
                    </Button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <>
              <div className="md:hidden space-y-3">
                {signals.map((s) => (
                  <div
                    key={s.signal_id}
                    className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className={riskLevelBadgeClass(s.risk_level)}>
                        {humanSeverity(s.risk_level)}
                      </Badge>
                      <Badge variant="secondary" className="text-xs font-normal">
                        {humanStatus(s.status)}
                      </Badge>
                      {isOperationalAdvisorySignal(s) && (
                        <Badge variant="outline" className="text-xs border-amber-200 bg-amber-50 text-amber-900">
                          Operational advisory only
                        </Badge>
                      )}
                      <span className="text-xs text-muted-foreground ml-auto">{humanTrend(s.trend)}</span>
                    </div>
                    <div>
                      <p className="font-semibold text-midnight-blue break-words">{humanRiskType(s)}</p>
                      <ListCognitionChip entity={s} className="mt-2" />
                      <p className="text-sm text-gray-600 mt-1 break-words">{propertyLabel(s.property_id)}</p>
                      {s.asset_id &&
                        (() => {
                          const asset = assetIdParts(s.asset_id);
                          if (!asset.isTruncated) {
                            return (
                              <p className="text-xs text-muted-foreground mt-1">
                                Linked asset · <span className="font-mono text-gray-800">{asset.full}</span>
                              </p>
                            );
                          }
                          return (
                            <details className="rounded-lg border border-gray-100 bg-gray-50/90 mt-2">
                              <summary className="cursor-pointer px-3 py-2.5 text-sm text-electric-teal font-medium min-h-[44px] flex items-center gap-2">
                                <span>
                                  Linked asset · <span className="font-mono text-gray-800">{asset.short}</span>
                                </span>
                              </summary>
                              <div className="px-3 pb-3 pt-0 border-t border-gray-100">
                                <p className="text-xs text-gray-500 mt-2 mb-1">Full reference (support or property records)</p>
                                <code className="text-xs font-mono text-gray-900 break-all block bg-white border border-gray-200 rounded-md px-2 py-2">
                                  {asset.full}
                                </code>
                              </div>
                            </details>
                          );
                        })()}
                    </div>
                    {Array.isArray(s.reasons) && s.reasons[0] && (
                      <p className="text-sm text-gray-700 break-words">
                        <span className="font-medium text-gray-800">Context:</span> {s.reasons[0]}
                      </p>
                    )}
                    <p className="text-sm text-gray-700 break-words line-clamp-4">{humanAction(s.recommended_action, s)}</p>
                    <p className="text-xs text-muted-foreground">
                      Updated {s.updated_at ? new Date(s.updated_at).toLocaleString() : '—'}
                    </p>
                    <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
                      <Button className="w-full min-h-11 justify-center" variant="default" onClick={() => runRiskSignalPrimaryAction(s)}>
                        {
                          resolveRiskSignalPrimaryKey(s, hasFeature('maintenance_workflows'), hasFeature('compliance_engine'))
                            .label
                        }
                      </Button>
                      <Button className="w-full min-h-11 justify-center" variant="outline" onClick={() => setDrawerSignalId(s.signal_id)}>
                        <Eye className="w-4 h-4 mr-2 shrink-0" /> View details
                      </Button>
                      {s.status === 'active' && (
                        <div className="flex flex-col gap-2">
                          <button
                            type="button"
                            className="text-xs text-gray-500 hover:text-midnight-blue text-left underline"
                            onClick={() => handleAcknowledge(s.signal_id)}
                          >
                            Acknowledge
                          </button>
                          <Button variant="outline" className="min-h-11 text-xs w-full" onClick={() => openDismissDialog(s.signal_id)}>
                            <XCircle className="w-4 h-4 mr-1 shrink-0" /> Dismiss
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Risk signal</TableHead>
                      <TableHead>Property</TableHead>
                      <TableHead>Asset</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Trend</TableHead>
                      <TableHead>Context</TableHead>
                      <TableHead>Recommended action</TableHead>
                      <TableHead>Last updated</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {signals.map((s) => {
                      const rowAsset = s.asset_id ? assetIdParts(s.asset_id) : null;
                      return (
                      <TableRow key={s.signal_id}>
                        <TableCell className="font-medium max-w-[14rem] break-words">
                          <div className="space-y-1">
                            <span>{humanRiskType(s)}</span>
                            <ListCognitionChip entity={s} />
                            {isOperationalAdvisorySignal(s) && (
                              <Badge variant="outline" className="text-xs border-amber-200 bg-amber-50 text-amber-900 block w-fit">
                                Operational advisory only
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[10rem] break-words">{propertyLabel(s.property_id)}</TableCell>
                        <TableCell className="text-muted-foreground max-w-[6rem]">
                          {rowAsset ? (
                            <span className="font-mono text-xs" title={rowAsset.full}>
                              {rowAsset.short}
                            </span>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={riskLevelBadgeClass(s.risk_level)}>
                            {humanSeverity(s.risk_level)}
                          </Badge>
                        </TableCell>
                        <TableCell>{humanTrend(s.trend)}</TableCell>
                        <TableCell className="max-w-[180px] truncate" title={Array.isArray(s.reasons) ? s.reasons.join('; ') : ''}>
                          {Array.isArray(s.reasons) && s.reasons[0] ? s.reasons[0] : '—'}
                        </TableCell>
                        <TableCell className="max-w-[180px] truncate" title={s.recommended_action}>
                          {humanAction(s.recommended_action, s)}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                          {s.updated_at ? new Date(s.updated_at).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex flex-col items-end gap-1">
                            <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90 text-white" onClick={() => runRiskSignalPrimaryAction(s)}>
                              {resolveRiskSignalPrimaryKey(s, hasFeature('maintenance_workflows'), hasFeature('compliance_engine')).label}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setDrawerSignalId(s.signal_id)}>
                              <Eye className="w-4 h-4 mr-1" /> View details
                            </Button>
                            {s.status === 'active' && (
                              <>
                                <button
                                  type="button"
                                  className="text-xs text-gray-500 hover:text-midnight-blue underline"
                                  onClick={() => handleAcknowledge(s.signal_id)}
                                >
                                  Acknowledge
                                </button>
                                <Button size="sm" variant="ghost" className="text-gray-600" onClick={() => openDismissDialog(s.signal_id)}>
                                  <XCircle className="w-4 h-4 mr-1" /> Dismiss
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                    })}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Detail drawer */}
      <Sheet open={!!drawerSignalId} onOpenChange={(open) => !open && setDrawerSignalId(null)}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Risk signal details</SheetTitle>
          </SheetHeader>
          {drawerLoading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : drawerSignal ? (
            <div className="space-y-4 py-4">
              <NextActionHero
                entity={drawerSignal}
                onPrimaryClick={async () => {
                  setDrawerPrimaryBusy(true);
                  try {
                    await runRiskSignalPrimaryAction(drawerSignal);
                  } finally {
                    setDrawerPrimaryBusy(false);
                  }
                }}
                primaryBusy={drawerPrimaryBusy}
              />
              <div>
                <p className="text-xs text-muted-foreground uppercase">Risk type</p>
                <p className="font-medium">{humanRiskType(drawerSignal)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground uppercase">Property</p>
                <p className="font-medium">{propertyLabel(drawerSignal.property_id)}</p>
              </div>
              {drawerSignal.asset_id && (() => {
                const asset = assetIdParts(drawerSignal.asset_id);
                return (
                  <div>
                    <p className="text-xs text-muted-foreground uppercase">Linked asset</p>
                    <p className="font-medium font-mono text-sm">{asset.short}</p>
                    {asset.isTruncated && (
                      <details className="mt-2 rounded-md border border-gray-100 bg-gray-50/80">
                        <summary className="cursor-pointer px-3 py-2 text-sm text-electric-teal font-medium min-h-[44px] flex items-center">
                          Show full reference
                        </summary>
                        <div className="px-3 pb-3">
                          <code className="text-xs font-mono text-gray-900 break-all block bg-white border rounded px-2 py-2">{asset.full}</code>
                        </div>
                      </details>
                    )}
                  </div>
                );
              })()}
              <div className="flex gap-2">
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Level</p>
                  <Badge variant="outline" className={riskLevelBadgeClass(drawerSignal.risk_level)}>
                    {humanSeverity(drawerSignal.risk_level)}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Trend</p>
                  <p className="font-medium">{humanTrend(drawerSignal.trend)}</p>
                </div>
              </div>
              {drawerSignal.generated_at && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Generated</p>
                  <p className="text-sm">{new Date(drawerSignal.generated_at).toLocaleString()}</p>
                </div>
              )}
              {drawerSignal.updated_at && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Last updated</p>
                  <p className="text-sm">{new Date(drawerSignal.updated_at).toLocaleString()}</p>
                </div>
              )}
              {drawerSignal.status && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Status</p>
                  <p className="font-medium">{humanStatus(drawerSignal.status)}</p>
                </div>
              )}
              {Array.isArray(drawerSignal.reasons) && drawerSignal.reasons.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase mb-1">Signal context</p>
                  <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                    {drawerSignal.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {drawerSuggestedView?.recommended_action && (
                <div className="rounded-md border border-gray-200 bg-gray-50/80 p-3 space-y-1">
                  <p className="text-xs text-muted-foreground uppercase">Primary suggestion</p>
                  <p className="text-sm font-medium text-midnight-blue">{drawerSuggestedView.recommended_action.title}</p>
                  {drawerSuggestedView.recommended_action.recommended_trade && (
                    <p className="text-xs text-gray-600">Trade: {drawerSuggestedView.recommended_action.recommended_trade}</p>
                  )}
                  {drawerSuggestedView.recommended_action.description && (
                    <p className="text-sm text-gray-700">{drawerSuggestedView.recommended_action.description}</p>
                  )}
                </div>
              )}
              {!drawerSuggestedView?.recommended_action && drawerSignal.recommended_action && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Recommended action</p>
                  <p className="text-sm">{humanAction(drawerSignal.recommended_action, drawerSignal)}</p>
                </div>
              )}
              {Array.isArray(drawerSuggestedView?.alternatives) && drawerSuggestedView.alternatives.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase mb-2">Other options</p>
                  <ul className="space-y-2 text-sm rounded-md border border-gray-200 bg-white p-3">
                    {drawerSuggestedView.alternatives.map((alt, i) => (
                      <li
                        key={alt.type || `alt-${i}`}
                        className="border-b border-gray-100 pb-2 last:border-0 last:pb-0"
                      >
                        <p className="font-medium text-midnight-blue">{alt.title || alt.type}</p>
                        {alt.recommended_trade && (
                          <p className="text-xs text-gray-600">Trade: {alt.recommended_trade}</p>
                        )}
                        {alt.description && <p className="text-gray-700">{alt.description}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Expandable "Why this matters" from explanation engine */}
              <div className="border rounded-lg overflow-hidden bg-gray-50/80">
                <button
                  type="button"
                  className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-medium text-gray-900 hover:bg-gray-100"
                  onClick={async () => {
                    const next = !drawerExplanationOpen;
                    setDrawerExplanationOpen(next);
                    if (next && !drawerExplanation && !drawerExplanationLoading) {
                      setDrawerExplanationLoading(true);
                      try {
                        const res = await clientAPI.getRiskSignalExplanation(drawerSignalId);
                        setDrawerExplanation(res.data);
                      } catch {
                        setDrawerExplanation(null);
                      } finally {
                        setDrawerExplanationLoading(false);
                      }
                    }
                  }}
                >
                  <span className="flex items-center gap-2">
                    <Info className="w-4 h-4 text-electric-teal" />
                    Why this matters
                  </span>
                  {drawerExplanationOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {drawerExplanationOpen && (
                  <div className="px-3 pb-3 pt-0 border-t border-gray-200 space-y-2">
                    {drawerExplanationLoading ? (
                      <p className="text-sm text-gray-500 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</p>
                    ) : drawerExplanation ? (
                      <>
                        <p className="text-sm text-gray-700">{drawerExplanation.why_it_matters}</p>
                        <p className="text-xs text-muted-foreground uppercase pt-1">Recommended action</p>
                        <p className="text-sm font-medium text-midnight-blue">{drawerExplanation.recommended_action_text}</p>
                      </>
                    ) : (
                      <p className="text-sm text-gray-500">Could not load explanation.</p>
                    )}
                  </div>
                )}
              </div>
              {drawerSignal?.operational_continuation?.has_active_lineage && (
                <div className="mb-4 rounded-md border border-teal-200 bg-teal-50/80 p-3 text-sm text-slate-800">
                  <p className="font-medium text-midnight-blue">Active workflow in progress</p>
                  <p className="mt-1">
                    {drawerSignal.operational_continuation.user_safe_reason ||
                      'A maintenance workflow is already linked to this signal.'}
                  </p>
                  {drawerSignal.operational_continuation.existing_work_order_id && (
                    <Button
                      type="button"
                      variant="link"
                      className="h-auto p-0 mt-2 text-electric-teal"
                      onClick={() =>
                        navigate(`/operations/jobs/${drawerSignal.operational_continuation.existing_work_order_id}`)
                      }
                    >
                      View active job
                    </Button>
                  )}
                </div>
              )}
              <div className="pt-4 border-t space-y-2">
                <p className="text-xs text-muted-foreground uppercase">Next step</p>
                <div className="flex flex-wrap gap-2">
                  {(() => {
                    const hasMaint = hasFeature('maintenance_workflows');
                    const hasComp = hasFeature('compliance_engine');
                    const { key: drawerPrimaryKey, label: drawerPrimaryLabel } = resolveRiskSignalPrimaryKey(drawerSignal, hasMaint, hasComp);
                    if (drawerPrimaryKey === 'review') {
                      return (
                        <p className="text-sm text-gray-600">
                          Review the details above. Dismiss when no action is needed, or use related links below.
                        </p>
                      );
                    }
                    return (
                      <Button
                        size="sm"
                        variant="default"
                        disabled={!!actionFromSignal || drawerPrimaryBusy}
                        onClick={async () => {
                          setDrawerPrimaryBusy(true);
                          try {
                            await runRiskSignalPrimaryAction(drawerSignal);
                          } finally {
                            setDrawerPrimaryBusy(false);
                          }
                        }}
                      >
                        {drawerPrimaryBusy ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                        {drawerPrimaryLabel}
                      </Button>
                    );
                  })()}
                </div>
                <p className="text-xs text-muted-foreground mt-2">Related</p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => navigate(resolvePropertyPath(drawerSignal.property_id))}>
                    <Building2 className="w-4 h-4 mr-1" /> View property
                  </Button>
                  {drawerSignal.asset_id && drawerSignal.property_id && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(resolvePropertyPath(drawerSignal.property_id, '?tab=assets'))}
                    >
                      <Package className="w-4 h-4 mr-1" /> View assets
                    </Button>
                  )}
                </div>
              </div>
              {drawerSignal?.status === 'active' && (
                <p className="text-xs text-muted-foreground pt-3 border-t">
                  Acknowledge or dismiss updates this risk signal only — it does not restore compliance or close statutory obligations
                  by itself.
                </p>
              )}
            </div>
          ) : (
            <p className="text-gray-500 py-4">Could not load risk signal details.</p>
          )}
          <SheetFooter className="pt-4 border-t flex flex-row flex-wrap items-center justify-between gap-3">
            {drawerSignal?.status === 'active' && (
              <>
                <Button variant="default" onClick={() => openDismissDialog(drawerSignalId)}>
                  <XCircle className="w-4 h-4 mr-2" /> Dismiss
                </Button>
                <button
                  type="button"
                  className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                  onClick={() => handleAcknowledge(drawerSignalId)}
                >
                  Acknowledge
                </button>
              </>
            )}
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Dialog open={Boolean(dismissTargetId)} onOpenChange={(o) => !o && setDismissTargetId(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Dismiss risk signal</DialogTitle>
            <DialogDescription>
              Dismiss only after you have handled the situation or decided no action is needed. Dismissing does not close compliance
              gaps or obligations by itself. If linked maintenance or compliance work is already complete in the platform, you can
              dismiss without choosing a reason.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label className="text-sm font-medium text-gray-700">Reason (if no completed work in the platform)</label>
            <select
              value={dismissReason}
              onChange={(e) => setDismissReason(e.target.value)}
              className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
            >
              <option value="no_action_required">No action required</option>
              <option value="handled_externally">Handled outside the platform</option>
              <option value="duplicate">Duplicate / not applicable</option>
            </select>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setDismissTargetId(null)} disabled={dismissSaving}>
              Cancel
            </Button>
            <Button type="button" onClick={confirmDismissSignal} disabled={dismissSaving}>
              {dismissSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Confirm dismiss'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={arrangeOpen} onOpenChange={(o) => !o && setArrangeOpen(false)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Schedule compliance inspection job</DialogTitle>
            <DialogDescription>
              Choose the requirement this inspection addresses. You will open the job next to assign a contractor and complete
              booking, visit, and proof. Completing the job does not automatically restore compliance—evidence and verification still
              follow their own paths when they apply.
            </DialogDescription>
          </DialogHeader>
          {arrangeLoading ? (
            <p className="text-sm text-gray-500 flex items-center gap-2 py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading requirements…
            </p>
          ) : (
            <div className="space-y-2 py-2">
              <label className="text-sm font-medium text-gray-700">Requirement on this property</label>
              <select
                value={arrangeReqPick}
                onChange={(e) => setArrangeReqPick(e.target.value)}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm"
              >
                <option value="">— Select —</option>
                {arrangeRequirements.map((r) => {
                  const rid = r.requirement_id || r.id;
                  const label = r.title || r.requirement_code || r.requirement_type || rid;
                  return (
                    <option key={rid} value={rid}>
                      {label}
                    </option>
                  );
                })}
              </select>
            </div>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setArrangeOpen(false)} disabled={!!actionFromSignal}>
              Cancel
            </Button>
            <Button type="button" onClick={confirmArrangeInspection} disabled={!!actionFromSignal || arrangeLoading}>
              {actionFromSignal === 'schedule_inspection' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Continue'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PlanRestrictedJobModal gate={planJobGate} onDismiss={() => setPlanJobGate(null)} />
      <ContractorNetworkLockedModal open={contractorNetworkLockedOpen} onOpenChange={setContractorNetworkLockedOpen} />
    </div>
  );
}

export default function ClientRiskSignalsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="predictive_maintenance">
      <ClientRiskSignalsPageInner />
    </EntitlementProtectedRoute>
  );
}
