/**
 * Operations → Risk Signals: portfolio-wide predictive maintenance and risk intelligence.
 * Uses GET /client/maintenance/risk-signals (filters, summary, highPriority), GET by signal_id for drawer.
 * Gated by predictive_maintenance.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { buildSafeQueryPath, normalizeRouteId, resolvePropertyPath } from '../utils/clientPortalNavigation';
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
  ClipboardCheck,
  Wrench,
  Search,
  Building2,
  Package,
  Eye,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
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
  const [actionFromSignal, setActionFromSignal] = useState(null); // 'issue' | 'work_order'
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
        if (!sig) toast.error('Failed to load signal details');
      })
      .catch(() => {
        setDrawerSignal(null);
        setDrawerSuggestedView(null);
        toast.error('Failed to load signal details');
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
      toast.success('Signal acknowledged');
      refreshAfterStatusChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to acknowledge');
    }
  };

  const handleResolve = async (signalId) => {
    try {
      await clientAPI.updateRiskSignalStatus(signalId, 'resolved');
      toast.success('Signal resolved');
      refreshAfterStatusChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to resolve');
    }
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
          Risk Signals
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Predictive maintenance not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{error}</p>
              <p className="text-sm text-amber-700 mt-2">
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
        Property health insights
      </h1>
      <p className="text-gray-600 mb-6 text-sm sm:text-base break-words">
        Clear, practical issue summaries with recommended next steps and deadlines.
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
              <p>{signals.length} active issues across {grouped.length} properties.</p>
              <p>{urgent} urgent, {medium} needs attention, and {Math.max(signals.length - urgent - medium, 0)} monitor.</p>
              <p>Most affected properties: {top || 'None currently flagged'}.</p>
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
        <Card className="mb-6 border-amber-200 bg-amber-50/50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600" />
              Urgent issues
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {highPriority.slice(0, 15).map((s) => (
                <li
                  key={s.signal_id}
                  className="flex flex-col gap-3 p-3 rounded-lg bg-white border border-amber-100 sm:flex-row sm:items-start sm:justify-between"
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
                    <Button className="w-full sm:w-auto min-h-11 justify-center" variant="outline" onClick={() => setDrawerSignalId(s.signal_id)}>
                      <Eye className="w-4 h-4 mr-1 shrink-0" /> View
                    </Button>
                    <Button
                      className="w-full sm:w-auto min-h-11 justify-center"
                      variant="outline"
                      onClick={() => openCreateWorkOrder(s.property_id, s.recommended_action)}
                    >
                      <Wrench className="w-4 h-4 mr-1 shrink-0" /> Work order
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
          <CardTitle>Active issues</CardTitle>
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
                    Signals are generated from property data (assets, work orders, compliance). Run Recalculate from a property’s Risk Signals tab or wait for the nightly job.
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
                      <span className="text-xs text-muted-foreground ml-auto">{humanTrend(s.trend)}</span>
                    </div>
                    <div>
                      <p className="font-semibold text-midnight-blue break-words">{humanRiskType(s)}</p>
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
                        <span className="font-medium text-gray-800">Why flagged:</span> {s.reasons[0]}
                      </p>
                    )}
                    <p className="text-sm text-gray-700 break-words line-clamp-4">
                      <span className="font-medium text-gray-800">Next step:</span> {humanAction(s.recommended_action, s)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Updated {s.updated_at ? new Date(s.updated_at).toLocaleString() : '—'}
                    </p>
                    <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
                      <Button className="w-full min-h-11 justify-center" variant="default" onClick={() => setDrawerSignalId(s.signal_id)}>
                        <Eye className="w-4 h-4 mr-2 shrink-0" /> View details
                      </Button>
                      <Button
                        className="w-full min-h-11 justify-center"
                        variant="outline"
                        onClick={() => openCreateWorkOrder(s.property_id, s.recommended_action)}
                      >
                        <Wrench className="w-4 h-4 mr-2 shrink-0" /> Create work order
                      </Button>
                      {s.status === 'active' && (
                        <div className="grid grid-cols-2 gap-2">
                          <Button variant="outline" className="min-h-11 text-xs" onClick={() => handleAcknowledge(s.signal_id)}>
                            <CheckCircle className="w-4 h-4 mr-1 shrink-0" /> Acknowledge
                          </Button>
                          <Button variant="outline" className="min-h-11 text-xs" onClick={() => handleResolve(s.signal_id)}>
                            <XCircle className="w-4 h-4 mr-1 shrink-0" /> Resolve
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
                      <TableHead>Issue</TableHead>
                      <TableHead>Property</TableHead>
                      <TableHead>Asset</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Trend</TableHead>
                      <TableHead>Why flagged</TableHead>
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
                        <TableCell className="font-medium max-w-[14rem] break-words">{humanRiskType(s)}</TableCell>
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
                          <div className="flex flex-wrap gap-1 justify-end">
                            <Button size="sm" variant="ghost" onClick={() => setDrawerSignalId(s.signal_id)}>
                              <Eye className="w-4 h-4 mr-1" /> View
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openCreateWorkOrder(s.property_id, s.recommended_action)}
                            >
                              <Wrench className="w-4 h-4 mr-1" /> Work order
                            </Button>
                            {s.status === 'active' && (
                              <>
                                <Button size="sm" variant="ghost" className="text-gray-600" onClick={() => handleAcknowledge(s.signal_id)}>
                                  <CheckCircle className="w-4 h-4 mr-1" /> Acknowledge
                                </Button>
                                <Button size="sm" variant="ghost" className="text-gray-600" onClick={() => handleResolve(s.signal_id)}>
                                  <XCircle className="w-4 h-4 mr-1" /> Resolve
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
                  <p className="text-xs text-muted-foreground uppercase mb-1">Why flagged</p>
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
              <div className="pt-4 border-t space-y-2">
                <p className="text-xs text-muted-foreground uppercase">Suggested actions</p>
                <div className="flex flex-wrap gap-2">
                  {(() => {
                    const actions =
                      Array.isArray(drawerSuggestedView?.suggested_action_codes) && drawerSuggestedView.suggested_action_codes.length > 0
                        ? drawerSuggestedView.suggested_action_codes
                        : Array.isArray(drawerSignal.suggested_actions)
                          ? drawerSignal.suggested_actions
                          : ['create_issue', 'create_work_order'];
                    return (
                      <>
                        {actions.includes('create_issue') && (
                          <Button
                            size="sm"
                            variant="default"
                            disabled={!!actionFromSignal}
                            onClick={async () => {
                              setActionFromSignal('issue');
                              try {
                                const res = await clientAPI.createIssueFromRiskSignal(drawerSignalId, {});
                                toast.success('Issue created. You can view it in Operations → Issues.');
                                if (res?.data?.issue_id) navigate(buildSafeQueryPath('/operations/issues', { highlight: res.data.issue_id }));
                                setDrawerSignalId(null);
                                load();
                              } catch (e) {
                                toast.error(e?.response?.data?.detail || 'Failed to create issue');
                              } finally {
                                setActionFromSignal(null);
                              }
                            }}
                          >
                            {actionFromSignal === 'issue' ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ClipboardCheck className="w-4 h-4 mr-1" />}
                            Create issue
                          </Button>
                        )}
                        {actions.includes('create_work_order') && (
                          <Button
                            size="sm"
                            variant="default"
                            disabled={!!actionFromSignal}
                            onClick={async () => {
                              setActionFromSignal('work_order');
                              try {
                                const res = await clientAPI.createWorkOrderFromRiskSignal(drawerSignalId, {});
                                toast.success('Work order created. You can view it in Operations → Work orders.');
                                if (res?.data?.work_order_id) navigate(buildSafeQueryPath('/operations/work-orders', { highlight: res.data.work_order_id }));
                                setDrawerSignalId(null);
                                load();
                              } catch (e) {
                                toast.error(e?.response?.data?.detail || 'Failed to create work order');
                              } finally {
                                setActionFromSignal(null);
                              }
                            }}
                          >
                            {actionFromSignal === 'work_order' ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Wrench className="w-4 h-4 mr-1" />}
                            Create work order
                          </Button>
                        )}
                        {actions.includes('schedule_inspection') && (
                          <Button
                            size="sm"
                            variant="default"
                            disabled={!!actionFromSignal}
                            onClick={async () => {
                              setActionFromSignal('schedule_inspection');
                              try {
                                const res = await clientAPI.scheduleInspectionFromRiskSignal(drawerSignalId, {});
                                toast.success('Inspection issue created.');
                                if (res?.data?.issue_id) navigate(buildSafeQueryPath('/operations/issues', { highlight: res.data.issue_id }));
                                setDrawerSignalId(null);
                                load();
                              } catch (e) {
                                toast.error(e?.response?.data?.detail || 'Failed to create inspection');
                              } finally {
                                setActionFromSignal(null);
                              }
                            }}
                          >
                            {actionFromSignal === 'schedule_inspection' ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ClipboardCheck className="w-4 h-4 mr-1" />}
                            Schedule inspection
                          </Button>
                        )}
                      </>
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
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openCreateWorkOrder(drawerSignal.property_id, drawerSignal.recommended_action)}
                  >
                    <Wrench className="w-4 h-4 mr-1" /> Create work order (manual)
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 py-4">Could not load signal details.</p>
          )}
          <SheetFooter className="pt-4 border-t">
            {drawerSignal?.status === 'active' && (
              <>
                <Button variant="outline" onClick={() => handleAcknowledge(drawerSignalId)}>
                  <CheckCircle className="w-4 h-4 mr-2" /> Acknowledge
                </Button>
                <Button variant="default" onClick={() => handleResolve(drawerSignalId)}>
                  <XCircle className="w-4 h-4 mr-2" /> Mark resolved
                </Button>
              </>
            )}
          </SheetFooter>
        </SheetContent>
      </Sheet>
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
