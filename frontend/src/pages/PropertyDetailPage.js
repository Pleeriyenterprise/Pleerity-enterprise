import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import apiClient, { clientAPI } from '../api/client';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import ErrorBanner from '../components/ErrorBanner';
import {
  ArrowLeft,
  Building2,
  FileText,
  Upload,
  RefreshCw,
  Mail,
  TrendingUp,
  TrendingDown,
  History,
  X,
  MinusCircle,
  Wrench,
  ClipboardCheck,
  Users,
  Calendar,
  AlertCircle,
  Loader2,
  Plus,
  Lock,
  Package,
  BarChart3,
  Eye,
  Download,
  Link2,
  Zap,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import UpgradePrompt, { getFeatureDisplayInfo } from '../components/UpgradePrompt';
import { SUPPORT_EMAIL } from '../config';
import { getEvidenceStatus } from '../utils/evidenceStatus';
import { formatRiskLabel } from '../utils/riskLabel';
import { humanRiskType, humanSeverity, humanAction } from '../utils/riskPresentation';
import {
  requirementLabel,
  complianceRequirementStatusLabel,
  documentTypeLabel,
  issueStatusLabel,
} from '../domain/presentDomain';
import { toast } from 'sonner';
import { buildSafeQueryPath, resolveClientPortalPath, resolveDocumentsPath } from '../utils/clientPortalNavigation';

const NOT_REQUIRED_REASONS = [
  { value: 'no_gas_supply', label: 'No gas supply' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'not_applicable', label: 'Not applicable' },
  { value: 'other', label: 'Other' },
];

const TAB_OVERVIEW = 'overview';
const TAB_COMPLIANCE = 'compliance';
const TAB_MAINTENANCE = 'maintenance';
const TAB_EVIDENCE = 'evidence';
const TAB_CONTRACTORS = 'contractors';
const TAB_TIMELINE = 'timeline';
const TAB_RISK_SIGNALS = 'risk_signals';
const TAB_ASSETS = 'assets';

export default function PropertyDetailPage() {
  const { propertyId } = useParams();
  const navigate = useNavigate();
  const { hasFeature } = useEntitlements();
  const [activeTab, setActiveTab] = useState(TAB_OVERVIEW);
  const [property, setProperty] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [complianceDetail, setComplianceDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scoreHistoryModal, setScoreHistoryModal] = useState(false);
  const [scoreHistoryEntries, setScoreHistoryEntries] = useState([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [notApplicableModal, setNotApplicableModal] = useState(null);
  const [notApplicableReason, setNotApplicableReason] = useState('');
  const [notApplicableSubmitting, setNotApplicableSubmitting] = useState(false);
  // Tab-specific data
  const [workOrders, setWorkOrders] = useState([]);
  const [workOrdersLoading, setWorkOrdersLoading] = useState(false);
  const [predictiveInsights, setPredictiveInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [riskSignalsData, setRiskSignalsData] = useState(null);
  const [riskSignalsLoading, setRiskSignalsLoading] = useState(false);
  const [riskSignalsRecalculating, setRiskSignalsRecalculating] = useState(false);
  const [createWoOpen, setCreateWoOpen] = useState(false);
  const [createWoForm, setCreateWoForm] = useState({ description: '', category: 'general', severity: 'medium' });
  const [createWoSaving, setCreateWoSaving] = useState(false);
  const [maintenanceIssues, setMaintenanceIssues] = useState([]);
  const [maintenanceIssuesLoading, setMaintenanceIssuesLoading] = useState(false);
  const [maintenanceIssueFilter, setMaintenanceIssueFilter] = useState({ status: '', severity: '', category: '' });
  const [maintenanceWoFilter, setMaintenanceWoFilter] = useState({ status: '' });
  const [issueDetailDrawer, setIssueDetailDrawer] = useState(null);
  const [issueDetailData, setIssueDetailData] = useState(null);
  const [issueDetailLoading, setIssueDetailLoading] = useState(false);
  const [woDetailDrawer, setWoDetailDrawer] = useState(null);
  const [woDetailData, setWoDetailData] = useState(null);
  const [woDetailLoading, setWoDetailLoading] = useState(false);
  const [createIssueOpen, setCreateIssueOpen] = useState(false);
  const [createIssueForm, setCreateIssueForm] = useState({ description: '', category: 'general' });
  const [createIssueSaving, setCreateIssueSaving] = useState(false);
  const [woRecommendList, setWoRecommendList] = useState(null);
  const [woRecommendLoading, setWoRecommendLoading] = useState(false);
  const [woUpdateSaving, setWoUpdateSaving] = useState(false);
  const [assets, setAssets] = useState([]);
  const [assetsSummary, setAssetsSummary] = useState(null);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsInitialising, setAssetsInitialising] = useState(false);
  const [assetDetailDrawer, setAssetDetailDrawer] = useState(null);
  const [assetDetailData, setAssetDetailData] = useState(null);
  const [assetDetailLoading, setAssetDetailLoading] = useState(false);
  const [editAssetModal, setEditAssetModal] = useState(null);
  const [editAssetForm, setEditAssetForm] = useState({});
  const [editAssetSaving, setEditAssetSaving] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [evidenceData, setEvidenceData] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const [timelineItems, setTimelineItems] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState(null);
  const [timelineFilters, setTimelineFilters] = useState({ category: '', dateRange: '30', actor_type: '' });
  const [timelineNextCursor, setTimelineNextCursor] = useState(null);
  const [complianceStatusFilter, setComplianceStatusFilter] = useState('');
  const [complianceSearchQuery, setComplianceSearchQuery] = useState('');
  const [complianceExpandedReqId, setComplianceExpandedReqId] = useState(null);
  const [complianceExplainability, setComplianceExplainability] = useState(null);
  const [complianceExplainabilityLoading, setComplianceExplainabilityLoading] = useState(false);
  const [priorityActions, setPriorityActions] = useState({ actions: [], total: 0 });
  const [urgentExplainKey, setUrgentExplainKey] = useState(null);
  const [urgentExplainData, setUrgentExplainData] = useState(null);
  const [urgentExplainLoading, setUrgentExplainLoading] = useState(false);

  const [bookInspectionOpen, setBookInspectionOpen] = useState(false);
  const [bookInspectionSignalId, setBookInspectionSignalId] = useState(null);
  const [bookInspectionReqPick, setBookInspectionReqPick] = useState('');
  const [bookInspectionSaving, setBookInspectionSaving] = useState(false);

  useEffect(() => {
    const hash = window.location.hash;
    const match = hash && hash.startsWith('#req=') && decodeURIComponent(hash.slice(5)).trim();
    if (match && requirements.length > 0) {
      const el = document.querySelector(`[data-req-code="${match}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [requirements]);

  const fetchData = React.useCallback(async () => {
    try {
      setError(null);
      if (!propertyId || propertyId === 'undefined' || propertyId === 'null') {
        setProperty(null);
        setComplianceDetail(null);
        setRequirements([]);
        setError('Invalid property link. Open a property from your portfolio.');
        return;
      }
      const propsRes = await clientAPI.getProperties();
      const prop = (propsRes.data.properties || []).find((p) => p.property_id === propertyId);
      setProperty(prop || null);
      try {
        const detailRes = await clientAPI.getComplianceDetail(propertyId);
        if (detailRes?.data) {
          setComplianceDetail(detailRes.data);
          setRequirements(detailRes.data.matrix || []);
          return;
        }
      } catch (_) {
        /* fallback to requirements list */
      }
      const reqsRes = await clientAPI.getPropertyRequirements(propertyId);
      setRequirements(reqsRes.data?.requirements || []);
      setComplianceDetail(null);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load property');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [propertyId]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchData().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [fetchData]);

  const loadWorkOrders = useCallback(() => {
    if (!propertyId || !hasFeature('maintenance_workflows')) return;
    setWorkOrdersLoading(true);
    clientAPI.getMaintenanceWorkOrders({ property_id: propertyId, limit: 100 })
      .then((res) => setWorkOrders(res.data?.work_orders || []))
      .catch(() => setWorkOrders([]))
      .finally(() => setWorkOrdersLoading(false));
  }, [propertyId, hasFeature]);

  const loadMaintenanceIssues = useCallback(() => {
    if (!propertyId || !hasFeature('maintenance_workflows')) return;
    setMaintenanceIssuesLoading(true);
    const params = { property_id: propertyId, limit: 100 };
    if (maintenanceIssueFilter.status) params.status = maintenanceIssueFilter.status;
    if (maintenanceIssueFilter.severity) params.severity = maintenanceIssueFilter.severity;
    if (maintenanceIssueFilter.category) params.category = maintenanceIssueFilter.category;
    clientAPI.getMaintenanceIssues(params)
      .then((res) => setMaintenanceIssues(res.data?.issues || []))
      .catch(() => setMaintenanceIssues([]))
      .finally(() => setMaintenanceIssuesLoading(false));
  }, [propertyId, hasFeature, maintenanceIssueFilter.status, maintenanceIssueFilter.severity, maintenanceIssueFilter.category]);

  const loadInsights = useCallback(() => {
    if (!propertyId || !hasFeature('predictive_maintenance')) return;
    setInsightsLoading(true);
    clientAPI.getPredictiveInsights({ limit: 100 })
      .then((res) => {
        const props = res.data?.properties || [];
        const forProp = props.find((p) => p.property_id === propertyId);
        setPredictiveInsights(forProp || null);
      })
      .catch(() => setPredictiveInsights(null))
      .finally(() => setInsightsLoading(false));
  }, [propertyId, hasFeature]);

  const loadRiskSignals = useCallback(() => {
    if (!propertyId || !hasFeature('predictive_maintenance')) return;
    setRiskSignalsLoading(true);
    clientAPI.getPropertyRiskSignals(propertyId)
      .then((res) => setRiskSignalsData(res.data || null))
      .catch(() => setRiskSignalsData(null))
      .finally(() => setRiskSignalsLoading(false));
  }, [propertyId, hasFeature]);

  const openBookInspectionFromRisk = useCallback(
    (signalId) => {
      if (!hasFeature('compliance_engine') || !hasFeature('maintenance_workflows')) return;
      setBookInspectionSignalId(signalId);
      setBookInspectionReqPick('');
      setBookInspectionOpen(true);
    },
    [hasFeature],
  );

  const confirmBookInspectionFromRisk = useCallback(async () => {
    if (!bookInspectionSignalId || !bookInspectionReqPick) {
      toast.error('Select a requirement to continue.');
      return;
    }
    const picked = requirements.find((r) => (r.requirement_id || r.id) === bookInspectionReqPick);
    const reqCode = picked?.requirement_code || picked?.requirement_type || picked?.code;
    if (!reqCode) {
      toast.error('Selected requirement has no code.');
      return;
    }
    setBookInspectionSaving(true);
    try {
      const res = await clientAPI.arrangeComplianceInspectionFromRiskSignal(bookInspectionSignalId, {
        requirement_code: String(reqCode),
        linked_property_requirement_id: bookInspectionReqPick,
        compliance_purpose: 'inspection',
      });
      const wid = res.data?.work_order?.work_order_id;
      toast.success('Compliance inspection job created. Open Operations → Jobs to request a contractor.');
      setBookInspectionOpen(false);
      setBookInspectionSignalId(null);
      loadRiskSignals();
      if (wid) navigate(buildSafeQueryPath('/operations/work-orders', { work_order_id: wid }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not book inspection');
    } finally {
      setBookInspectionSaving(false);
    }
  }, [bookInspectionSignalId, bookInspectionReqPick, requirements, navigate, loadRiskSignals]);

  useEffect(() => {
    if (!propertyId) return;
    clientAPI.getPriorityActions({ property_id: propertyId, limit: 10 })
      .then((res) => setPriorityActions({ actions: res.data?.actions || [], total: res.data?.total ?? 0 }))
      .catch(() => setPriorityActions({ actions: [], total: 0 }));
  }, [propertyId]);

  const loadAssets = useCallback(() => {
    if (!propertyId || (!hasFeature('maintenance_workflows') && !hasFeature('predictive_maintenance'))) return;
    setAssetsLoading(true);
    clientAPI.getPropertyAssets(propertyId)
      .then((res) => {
        setAssets(res.data?.assets || []);
        setAssetsSummary(res.data?.summary || null);
      })
      .catch(() => { setAssets([]); setAssetsSummary(null); })
      .finally(() => setAssetsLoading(false));
  }, [propertyId, hasFeature]);

  const loadDocuments = useCallback(() => {
    if (!propertyId) return;
    setDocumentsLoading(true);
    clientAPI.getDocuments({ property_id: propertyId })
      .then((res) => setDocuments(res.data?.documents || []))
      .catch(() => setDocuments([]))
      .finally(() => setDocumentsLoading(false));
  }, [propertyId]);

  const loadEvidence = useCallback(() => {
    if (!propertyId) return;
    setEvidenceLoading(true);
    clientAPI.getPropertyEvidence(propertyId)
      .then((res) => setEvidenceData(res.data || null))
      .catch(() => setEvidenceData(null))
      .finally(() => setEvidenceLoading(false));
  }, [propertyId]);

  const loadComplianceExplainability = useCallback(() => {
    if (!propertyId) return;
    setComplianceExplainabilityLoading(true);
    clientAPI.getPropertyComplianceScoreExplanation(propertyId)
      .then((res) => setComplianceExplainability(res.data || null))
      .catch(() => setComplianceExplainability(null))
      .finally(() => setComplianceExplainabilityLoading(false));
  }, [propertyId]);

  // Keep property-level compliance/risk views in sync with Action -> Outcome events from other screens.
  useEffect(() => {
    if (!propertyId) return undefined;
    const onOutcome = (evt) => {
      const outcomePropertyId = evt?.detail?.property_id;
      if (outcomePropertyId && outcomePropertyId !== propertyId) return;
      fetchData();
      loadComplianceExplainability();
      if (hasFeature('maintenance_workflows')) {
        loadWorkOrders();
        loadMaintenanceIssues();
      }
      if (hasFeature('predictive_maintenance')) {
        loadInsights();
        loadRiskSignals();
      }
      if (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance')) {
        loadAssets();
      }
      if (activeTab === TAB_EVIDENCE) {
        loadEvidence();
      }
      if (activeTab === TAB_TIMELINE) {
        loadTimeline();
      }
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [
    propertyId,
    hasFeature,
    fetchData,
    loadWorkOrders,
    loadMaintenanceIssues,
    loadInsights,
    loadRiskSignals,
    loadAssets,
    loadEvidence,
    loadComplianceExplainability,
    loadTimeline,
    activeTab,
  ]);

  useEffect(() => {
    if (!propertyId) return;
    if (hasFeature('maintenance_workflows')) loadWorkOrders();
  }, [propertyId, hasFeature, loadWorkOrders]);

  useEffect(() => {
    if (propertyId && activeTab === TAB_MAINTENANCE && hasFeature('maintenance_workflows')) loadMaintenanceIssues();
  }, [propertyId, activeTab, hasFeature, loadMaintenanceIssues]);

  useEffect(() => {
    if (!issueDetailDrawer) { setIssueDetailData(null); return; }
    setIssueDetailLoading(true);
    clientAPI.getMaintenanceIssue(issueDetailDrawer)
      .then((res) => setIssueDetailData(res.data || null))
      .catch(() => setIssueDetailData(null))
      .finally(() => setIssueDetailLoading(false));
  }, [issueDetailDrawer]);

  useEffect(() => {
    if (!woDetailDrawer) { setWoDetailData(null); setWoRecommendList(null); return; }
    setWoDetailLoading(true);
    setWoRecommendList(null);
    clientAPI.getMaintenanceWorkOrder(woDetailDrawer)
      .then((res) => { setWoDetailData(res.data || null); if (hasFeature('contractor_network')) { setWoRecommendLoading(true); clientAPI.getRecommendContractors(woDetailDrawer, { limit: 10 }).then((r) => setWoRecommendList(r.data?.contractors || [])).catch(() => setWoRecommendList([])).finally(() => setWoRecommendLoading(false)); } })
      .catch(() => setWoDetailData(null))
      .finally(() => setWoDetailLoading(false));
  }, [woDetailDrawer, hasFeature]);

  useEffect(() => {
    if (!propertyId) return;
    if (hasFeature('predictive_maintenance')) {
      loadInsights();
      loadRiskSignals();
    }
  }, [propertyId, hasFeature, loadInsights, loadRiskSignals]);

  useEffect(() => {
    if (!propertyId) return;
    if (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance')) loadAssets();
  }, [propertyId, hasFeature, loadAssets]);

  useEffect(() => {
    if (!propertyId) return;
    if (activeTab === TAB_COMPLIANCE || activeTab === TAB_OVERVIEW) {
      loadComplianceExplainability();
    }
  }, [propertyId, activeTab, loadComplianceExplainability]);

  useEffect(() => {
    if (propertyId && activeTab === TAB_EVIDENCE) loadEvidence();
  }, [propertyId, activeTab, loadEvidence]);

  const loadTimeline = useCallback((appendCursor = null) => {
    if (!propertyId) return;
    setTimelineError(null);
    if (!appendCursor) setTimelineLoading(true);
    const range = timelineFilters.dateRange;
    const to = new Date();
    const from = new Date();
    if (range === '7') from.setDate(from.getDate() - 7);
    else if (range === '90') from.setDate(from.getDate() - 90);
    else from.setDate(from.getDate() - 30);
    const params = {
      limit: 50,
      from_date: from.toISOString().slice(0, 10),
      to_date: to.toISOString().slice(0, 10),
    };
    if (timelineFilters.category) params.category = timelineFilters.category;
    if (timelineFilters.actor_type) params.actor_type = timelineFilters.actor_type;
    if (appendCursor) params.cursor = appendCursor;
    clientAPI.getPropertyTimeline(propertyId, params)
      .then((res) => {
        const items = res.data?.items || [];
        if (appendCursor) {
          setTimelineItems((prev) => [...prev, ...items]);
        } else {
          setTimelineItems(items);
        }
        setTimelineNextCursor(res.data?.next_cursor || null);
      })
      .catch((err) => {
        setTimelineError(err?.response?.data?.detail || 'Failed to load timeline');
        if (!appendCursor) setTimelineItems([]);
      })
      .finally(() => setTimelineLoading(false));
  }, [propertyId, timelineFilters.category, timelineFilters.dateRange, timelineFilters.actor_type]);

  useEffect(() => {
    if (propertyId && activeTab === TAB_TIMELINE) loadTimeline();
  }, [propertyId, activeTab, loadTimeline]);

  const handleCreateWorkOrder = (e) => {
    e.preventDefault();
    if (!createWoForm.description?.trim()) {
      toast.error('Enter a description');
      return;
    }
    setCreateWoSaving(true);
    clientAPI.createMaintenanceWorkOrder({
      property_id: propertyId,
      description: createWoForm.description.trim(),
      category: createWoForm.category || undefined,
      severity: createWoForm.severity || undefined,
    })
      .then(() => {
        toast.success('Work order created');
        setCreateWoOpen(false);
        setCreateWoForm({ description: '', category: 'general', severity: 'medium' });
        loadWorkOrders();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setCreateWoSaving(false));
  };

  const handleCreateIssue = (e) => {
    e.preventDefault();
    if (!createIssueForm.description?.trim()) {
      toast.error('Enter a description');
      return;
    }
    setCreateIssueSaving(true);
    clientAPI.createMaintenanceIssue({
      property_id: propertyId,
      description: createIssueForm.description.trim(),
      category: createIssueForm.category || undefined,
    })
      .then((res) => {
        toast.success('Issue created and triaged');
        setCreateIssueOpen(false);
        setCreateIssueForm({ description: '', category: 'general' });
        loadMaintenanceIssues();
        const issueId = res.data?.issue_id;
        if (issueId) setIssueDetailDrawer(issueId);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Create failed'))
      .finally(() => setCreateIssueSaving(false));
  };

  const handleCreateWoFromIssue = (issueId) => {
    clientAPI.createWorkOrderFromIssue(issueId)
      .then(() => {
        toast.success('Work order created from issue');
        loadWorkOrders();
        loadMaintenanceIssues();
        setIssueDetailDrawer(null);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed'));
  };

  const handleUpdateWorkOrderStatus = (workOrderId, status) => {
    setWoUpdateSaving(true);
    clientAPI.updateMaintenanceWorkOrder(workOrderId, { status })
      .then(() => {
        toast.success('Status updated');
        loadWorkOrders();
        if (woDetailDrawer === workOrderId) clientAPI.getMaintenanceWorkOrder(workOrderId).then((r) => setWoDetailData(r.data || null));
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
      .finally(() => setWoUpdateSaving(false));
  };

  const handleAssignContractor = (workOrderId, contractorId) => {
    setWoUpdateSaving(true);
    clientAPI.updateMaintenanceWorkOrder(workOrderId, { contractor_id: contractorId })
      .then(() => {
        toast.success('Contractor assigned');
        loadWorkOrders();
        if (woDetailDrawer === workOrderId) clientAPI.getMaintenanceWorkOrder(workOrderId).then((r) => setWoDetailData(r.data || null));
        setWoRecommendList(null);
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
      .finally(() => setWoUpdateSaving(false));
  };

  const maintenanceSummary = useMemo(() => {
    const openIssues = maintenanceIssues.filter((i) => (i.status || '').toLowerCase() !== 'closed').length;
    const draftWos = workOrders.filter((wo) => (wo.status || '') === 'DRAFT').length;
    const activeStatuses = ['OPEN', 'ASSIGNED', 'IN_PROGRESS', 'SCHEDULED', 'AWAITING_PARTS'];
    const activeWos = workOrders.filter((wo) => activeStatuses.includes(wo.status || '')).length;
    const slaBreaches = workOrders.filter((wo) => wo.sla_breached_at && !['COMPLETED', 'CANCELLED'].includes(wo.status || '')).length;
    const highSeverity = maintenanceIssues.filter((i) => ['high', 'urgent'].includes((i.severity || '').toLowerCase()) && (i.status || '').toLowerCase() !== 'closed').length;
    let lastActivityAt = null;
    [...maintenanceIssues, ...workOrders].forEach((x) => {
      const t = x.updated_at || x.created_at;
      if (t && (!lastActivityAt || new Date(t) > new Date(lastActivityAt))) lastActivityAt = t;
    });
    return { openIssues, draftWos, activeWos, slaBreaches, highSeverity, lastActivityAt };
  }, [maintenanceIssues, workOrders]);

  const filteredWorkOrders = useMemo(() => {
    if (!maintenanceWoFilter.status) return workOrders;
    return workOrders.filter((wo) => (wo.status || '') === maintenanceWoFilter.status);
  }, [workOrders, maintenanceWoFilter.status]);

  const slaAtRiskOrBreached = useMemo(() => {
    return workOrders.filter((wo) => {
      if (['COMPLETED', 'CANCELLED'].includes(wo.status || '')) return false;
      return wo.sla_breached_at || wo.sla_breach_risk_at;
    });
  }, [workOrders]);

  const assetLabel = (assetId) => {
    if (!assetId) return '—';
    const a = assets.find((x) => x.asset_id === assetId);
    return a ? (a.name || (a.asset_type || '').replace(/_/g, ' ')) : assetId;
  };

  const getStatus = (r) => getEvidenceStatus(r.status);
  const formatDate = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
  const formatRelativeTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const sec = Math.floor((now - d) / 1000);
    if (sec < 60) return 'Just now';
    if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)} hours ago`;
    if (sec < 172800) return 'Yesterday';
    if (sec < 604800) return `${Math.floor(sec / 86400)} days ago`;
    return formatDate(iso);
  };
  const daysLeft = (d) => {
    if (!d) return null;
    const diff = Math.ceil((new Date(d) - new Date()) / (1000 * 60 * 60 * 24));
    return diff;
  };
  const isMatrixRow = (r) => r.title != null || r.requirement_code != null;
  const rowTitle = (r) =>
    r?.title ||
    (r?.requirement_code || r?.requirement_type
      ? requirementLabel(r.requirement_code || r.requirement_type)
      : null) ||
    r?.description ||
    r?.name ||
    '—';
  const rowExpiry = (r) => r.expiry_date || r.due_date;
  const rowDays = (r) => (r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r)));
  const rowReqId = (r) => r.requirement_id || r.id;

  const evidenceDocStatusLabel = (doc) => {
    const s = (doc?.status || '').toUpperCase();
    if (s === 'VERIFIED') return 'Confirmed';
    if (s === 'REJECTED') return 'Rejected';
    if (s === 'EXPIRED') return 'Expired';
    const hasExtraction = doc?.extraction_id || (doc?.ai_extraction?.status === 'completed' && doc?.ai_extraction?.data);
    if (hasExtraction && s !== 'VERIFIED') return 'Pending Confirmation';
    if (s === 'UPLOADED') return 'Extracted';
    if (!doc?.requirement_id) return 'Unlinked';
    return 'Uploaded';
  };

  const handleEvidenceDocumentDownload = (doc) => {
    if (!doc?.document_id) return;
    apiClient.get(`/documents/${doc.document_id}/file`, { params: { download: true }, responseType: 'blob' })
      .then((res) => {
        const url = window.URL.createObjectURL(res.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.file_name || doc.original_filename || 'document';
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => toast.error('Could not download document'));
  };

  const isPendingConfirmation = (doc) => {
    const hasExtraction = doc?.extraction_id || (doc?.ai_extraction?.status === 'completed' && doc?.ai_extraction?.data);
    return !!hasExtraction && (doc?.status || '').toUpperCase() !== 'VERIFIED';
  };

  const complianceImpactLabel = (r) => {
    const c = (r.criticality || '').toUpperCase();
    if (c === 'HIGH') return { label: 'High', className: 'bg-red-100 text-red-700 border-red-200' };
    if (c === 'MED' || c === 'MEDIUM') return { label: 'Medium', className: 'bg-amber-100 text-amber-700 border-amber-200' };
    return { label: 'Low', className: 'bg-gray-100 text-gray-600 border-gray-200' };
  };

  const getComplianceSummary = () => {
    const kpis = complianceDetail?.kpis || {};
    const total = requirements.length;
    return {
      totalApplicable: total,
      valid: kpis.compliant ?? requirements.filter((r) => ['COMPLIANT', 'VALID'].includes((r.status || '').toUpperCase())).length,
      expiringSoon: kpis.expiring_30 ?? requirements.filter((r) => (r.status || '').toUpperCase() === 'EXPIRING_SOON').length,
      overdue: kpis.overdue ?? requirements.filter((r) => ['OVERDUE', 'EXPIRED'].includes((r.status || '').toUpperCase())).length,
      missingEvidence: kpis.missing ?? requirements.filter((r) => ['PENDING', 'MISSING'].includes((r.status || '').toUpperCase())).length,
    };
  };

  const getNextDueDate = () => {
    const withDue = requirements
      .filter((r) => r.expiry_date || r.due_date)
      .sort((a, b) => new Date(a.expiry_date || a.due_date) - new Date(b.expiry_date || b.due_date));
    return withDue[0] ? (withDue[0].expiry_date || withDue[0].due_date) : null;
  };

  const getFilteredRequirements = () => {
    let list = requirements;
    if (complianceStatusFilter) {
      const s = complianceStatusFilter.toUpperCase();
      if (s === 'VALID') list = list.filter((r) => ['COMPLIANT', 'VALID'].includes((r.status || '').toUpperCase()));
      else if (s === 'MISSING') list = list.filter((r) => ['PENDING', 'MISSING'].includes((r.status || '').toUpperCase()));
      else list = list.filter((r) => (r.status || '').toUpperCase() === s);
    }
    if (complianceSearchQuery.trim()) {
      const q = complianceSearchQuery.trim().toLowerCase();
      list = list.filter((r) => (rowTitle(r) || '').toLowerCase().includes(q) || (r.requirement_code || '').toLowerCase().includes(q));
    }
    return list;
  };

  const getUrgentRequirements = () => {
    return requirements.filter((r) => {
      const s = (r.status || '').toUpperCase();
      return s === 'OVERDUE' || s === 'EXPIRED' || (s === 'EXPIRING_SOON' && (r.days_to_expiry == null || r.days_to_expiry <= 30)) || s === 'MISSING' || s === 'PENDING';
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (!propertyId || propertyId === 'undefined' || propertyId === 'null') {
    return (
      <div>
        <ErrorBanner
          message="Invalid property link. Open a property from your portfolio."
          onRetry={() => navigate('/properties')}
          retryLabel="Back to properties"
        />
      </div>
    );
  }

  if (error && !property) {
    return (
      <div>
        <ErrorBanner
          message={error}
          onRetry={() => navigate('/properties')}
          retryLabel="Back to properties"
        />
      </div>
    );
  }

  const address = property
    ? [property.address_line_1, property.address_line_2, property.postcode].filter(Boolean).join(', ') || 'Unnamed property'
    : 'Property';

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-4">
        <Button variant="ghost" size="sm" className="-ml-2" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/properties'))}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="border-gray-200"
          data-testid="property-detail-refresh"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Property header card – executive summary + actions */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">{address}</h1>
            <div className="flex flex-wrap gap-2 mt-2 text-sm text-gray-600">
              {property?.property_type && <span>{property.property_type}</span>}
              {property?.jurisdiction && <span>{property.jurisdiction}</span>}
              {property?.is_hmo && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded">HMO</span>}
              {property?.occupancy != null && <span>Occupancy: {property.occupancy}</span>}
              {property?.has_gas !== undefined && <span>{property.has_gas ? 'Gas' : 'No gas'}</span>}
            </div>
            <div className="flex flex-wrap gap-4 mt-3 text-sm">
              {complianceDetail && (
                <span className="font-medium text-midnight-blue">
                  Score: {(complianceDetail.score ?? complianceDetail.property_score) ?? '—'}/100 · {formatRiskLabel(complianceDetail.risk_level)}
                </span>
              )}
              {hasFeature('maintenance_workflows') && (
                <span>Open work orders: {workOrders.filter((wo) => ['OPEN', 'ASSIGNED'].includes(wo.status)).length}</span>
              )}
              {(() => {
                const nextDue = requirements
                  .filter((r) => (r.expiry_date || r.due_date) && ['OVERDUE', 'EXPIRING_SOON', 'PENDING', 'MISSING'].includes((r.status || '').toUpperCase()))
                  .sort((a, b) => new Date(a.expiry_date || a.due_date) - new Date(b.expiry_date || b.due_date))[0];
                return nextDue ? (
                  <span className="text-amber-700">Next due: {rowTitle(nextDue)} — {formatDate(nextDue.expiry_date || nextDue.due_date)}</span>
                ) : null;
              })()}
              {complianceDetail?.last_updated_at && (
                <span className="text-gray-500">Updated: {new Date(complianceDetail.last_updated_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" className="border-gray-200" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
              <Upload className="w-4 h-4 mr-1.5" />
              Upload Evidence
            </Button>
            {hasFeature('maintenance_workflows') ? (
              <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => { setActiveTab(TAB_MAINTENANCE); setCreateWoOpen(true); }}>
                <Plus className="w-4 h-4 mr-1.5" />
                Add Issue
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => navigate('/app/billing?upgrade_to=PLAN_2_PORTFOLIO')}>
                <Lock className="w-4 h-4 mr-1.5" />
                Add Issue
              </Button>
            )}
            <Button variant="outline" size="sm" className="border-gray-200" onClick={() => navigate('/reports')}>
              <BarChart3 className="w-4 h-4 mr-1.5" />
              View Reports
            </Button>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        This is an evidence-based status summary. It is not legal advice.
      </p>

      {/* Tab navigation – all 8 tabs; locked icon when feature disabled */}
      <nav className="flex flex-wrap gap-1 border-b border-gray-200 mb-6">
        {[
          { id: TAB_OVERVIEW, label: 'Overview', icon: Building2, feature: null },
          { id: TAB_COMPLIANCE, label: 'Compliance', icon: ClipboardCheck, feature: null },
          { id: TAB_MAINTENANCE, label: 'Maintenance', icon: Wrench, feature: 'maintenance_workflows' },
          { id: TAB_EVIDENCE, label: 'Evidence', icon: FileText, feature: null },
          { id: TAB_CONTRACTORS, label: 'Contractors', icon: Users, feature: 'contractor_network' },
          { id: TAB_TIMELINE, label: 'Timeline', icon: Calendar, feature: null },
          { id: TAB_RISK_SIGNALS, label: 'Risk Signals', icon: AlertCircle, feature: 'predictive_maintenance' },
          { id: TAB_ASSETS, label: 'Assets', icon: Package, feature: 'maintenance_workflows' },
        ].map(({ id, label, icon: Icon, feature }) => {
          const enabled = id === TAB_ASSETS
            ? (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance'))
            : (!feature || hasFeature(feature));
          return (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === id
                  ? 'border-electric-teal text-electric-teal'
                  : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
              {!enabled && <Lock className="w-3.5 h-3.5 text-amber-600" />}
            </button>
          );
        })}
      </nav>

      {/* Tab: Overview */}
      {activeTab === TAB_OVERVIEW && (
        <div className="space-y-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {complianceDetail && (
              <Card className="border border-gray-200">
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Compliance score</p>
                  <p className="text-2xl font-bold text-midnight-blue">{(complianceDetail.score ?? complianceDetail.property_score) ?? '—'}/100</p>
                  <p className="text-sm text-gray-600 mt-0.5">{formatRiskLabel(complianceDetail.risk_level)}</p>
                  <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_COMPLIANCE)}>View compliance →</Button>
                </CardContent>
              </Card>
            )}
            <Card className="border border-gray-200">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Maintenance risk</p>
                <p className="text-2xl font-bold text-midnight-blue">{complianceDetail ? formatRiskLabel(complianceDetail.risk_level) : '—'}</p>
                {hasFeature('maintenance_workflows') && (
                  <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_MAINTENANCE)}>View maintenance →</Button>
                )}
              </CardContent>
            </Card>
            {hasFeature('maintenance_workflows') && (
              <Card className="border border-gray-200">
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Open work orders</p>
                  <p className="text-2xl font-bold text-midnight-blue">{workOrders.filter((wo) => ['OPEN', 'ASSIGNED'].includes(wo.status)).length}</p>
                  <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_MAINTENANCE)}>View maintenance →</Button>
                </CardContent>
              </Card>
            )}
            <Card className="border border-gray-200">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Upcoming compliance</p>
                <p className="text-2xl font-bold text-midnight-blue">{requirements.filter((r) => ['OVERDUE', 'EXPIRING_SOON', 'PENDING', 'MISSING'].includes((r.status || '').toUpperCase())).length}</p>
                <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_COMPLIANCE)}>View requirements →</Button>
              </CardContent>
            </Card>
            {hasFeature('predictive_maintenance') && (
              <Card className="border border-gray-200">
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Risk signals</p>
                  <p className="text-2xl font-bold text-midnight-blue">{(riskSignalsData?.summary?.total ?? predictiveInsights?.insights?.length) ?? 0}</p>
                  <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_RISK_SIGNALS)}>View risk signals →</Button>
                </CardContent>
              </Card>
            )}
            {hasFeature('contractor_network') && (
              <Card className="border border-gray-200">
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Contractor activity</p>
                  <p className="text-sm text-gray-600">View contractors and jobs</p>
                  <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_CONTRACTORS)}>View contractors →</Button>
                </CardContent>
              </Card>
            )}
            <Card className="border border-gray-200">
              <CardContent className="pt-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Evidence & documents</p>
                <Button variant="outline" size="sm" className="mt-2 text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_EVIDENCE)}>View documents →</Button>
              </CardContent>
            </Card>
          </div>

          {/* Current Alerts */}
          {(() => {
            const overdueReqs = requirements.filter((r) => (r.status || '').toUpperCase() === 'OVERDUE');
            const expiringReqs = requirements.filter((r) => (r.status || '').toUpperCase() === 'EXPIRING_SOON');
            const highRiskSignals = riskSignalsData?.signals?.filter((s) => ['high', 'critical'].includes((s.risk_level || '').toLowerCase())) ?? (predictiveInsights?.insights || []).filter((i) => (i.risk || '').toLowerCase() === 'high' || (i.risk || '').toLowerCase() === 'urgent');
            const openWOs = workOrders.filter((wo) => ['OPEN', 'ASSIGNED'].includes(wo.status));
            const hasAlerts = overdueReqs.length > 0 || expiringReqs.length > 0 || highRiskSignals.length > 0 || openWOs.length > 0;
            if (!hasAlerts) return null;
            return (
              <Card className="border border-amber-200 bg-amber-50/50">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2"><AlertCircle className="w-4 h-4 text-amber-600" />Current alerts</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm">
                    {overdueReqs.length > 0 && (
                      <li>
                        <button type="button" className="text-left text-amber-800 hover:underline font-medium" onClick={() => setActiveTab(TAB_COMPLIANCE)}>
                          {overdueReqs.length} requirement{overdueReqs.length !== 1 ? 's' : ''} overdue
                        </button>
                        <span className="text-amber-700"> — fix in Compliance</span>
                      </li>
                    )}
                    {expiringReqs.length > 0 && (
                      <li>
                        <button type="button" className="text-left text-amber-800 hover:underline font-medium" onClick={() => setActiveTab(TAB_COMPLIANCE)}>
                          {expiringReqs.length} expiring soon
                        </button>
                        <span className="text-amber-700"> — review in Compliance</span>
                      </li>
                    )}
                    {highRiskSignals.length > 0 && hasFeature('predictive_maintenance') && (
                      <li>
                        <button type="button" className="text-left text-amber-800 hover:underline font-medium" onClick={() => setActiveTab(TAB_RISK_SIGNALS)}>
                          {highRiskSignals.length} elevated risk signal{highRiskSignals.length !== 1 ? 's' : ''}
                        </button>
                        <span className="text-amber-700"> — view Risk Signals</span>
                      </li>
                    )}
                    {openWOs.length > 0 && hasFeature('maintenance_workflows') && (
                      <li>
                        <button type="button" className="text-left text-amber-800 hover:underline font-medium" onClick={() => setActiveTab(TAB_MAINTENANCE)}>
                          {openWOs.length} open work order{openWOs.length !== 1 ? 's' : ''}
                        </button>
                        <span className="text-amber-700"> — manage in Maintenance</span>
                      </li>
                    )}
                  </ul>
                </CardContent>
              </Card>
            );
          })()}

          {/* Priority actions for this property (orchestration layer) */}
          {priorityActions.actions?.length > 0 && (
            <Card className="border border-electric-teal/30 bg-white" data-testid="property-priority-actions-panel">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2 text-midnight-blue">
                  <Zap className="w-4 h-4 text-electric-teal" />
                  Priority actions
                </CardTitle>
                <CardDescription>Next steps for this property</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {priorityActions.actions.map((action, idx) => (
                    <li key={idx} className="flex items-start justify-between gap-4 py-2 border-b border-gray-100 last:border-0">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-midnight-blue">{action.title}</p>
                        {action.description && (
                          <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{action.description}</p>
                        )}
                      </div>
                      {action.recommended_url ? (
                        <Link
                          to={resolveClientPortalPath(action.recommended_url, propertyId ? `/properties/${propertyId}` : '/properties')}
                          className="shrink-0 inline-flex items-center justify-center px-3 py-1.5 bg-electric-teal hover:bg-electric-teal/90 text-white rounded-md text-sm font-medium no-underline cursor-pointer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {action.recommended_action_label || 'View'}
                        </Link>
                      ) : (
                        <span className="shrink-0 px-3 py-1.5 bg-gray-200 text-gray-500 rounded-md text-sm">—</span>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Recommended Next Actions */}
          {(() => {
            const actions = [];
            requirements.filter((r) => ['OVERDUE', 'EXPIRING_SOON', 'MISSING', 'PENDING'].includes((r.status || '').toUpperCase())).slice(0, 3).forEach((r) => {
              if (r.evidence_doc_id) actions.push({ label: `Confirm expiry for ${rowTitle(r)}`, tab: TAB_EVIDENCE });
              else actions.push({ label: `Upload evidence for ${rowTitle(r)}`, tab: TAB_EVIDENCE });
            });
            (riskSignalsData?.signals || predictiveInsights?.insights || []).filter((s) => ['high', 'critical'].includes((s.risk_level || s.risk || '').toLowerCase())).slice(0, 2).forEach((i) => {
              actions.push({ label: i.recommended_action || i.recommendation || 'Create inspection for risk', tab: TAB_RISK_SIGNALS });
            });
            if (actions.length === 0) return null;
            return (
              <Card className="border border-gray-200">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Recommended next actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm">
                    {actions.slice(0, 5).map((a, i) => (
                      <li key={i}>
                        <button type="button" className="text-electric-teal hover:underline font-medium" onClick={() => setActiveTab(a.tab)}>
                          {a.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            );
          })()}

          {/* Suggested Actions — active risk signals with action buttons */}
          {hasFeature('predictive_maintenance') && (riskSignalsData?.signals || []).filter((s) => (s.status || 'active') === 'active').length > 0 && (
            <Card className="border border-electric-teal/30 bg-white">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">Suggested actions</CardTitle>
                <CardDescription>Active risk signals — trigger an action or resolve</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {(riskSignalsData.signals || []).filter((s) => (s.status || 'active') === 'active').slice(0, 5).map((s) => {
                    const actions = Array.isArray(s.suggested_actions) ? s.suggested_actions : ['create_issue', 'create_work_order'];
                    return (
                      <li key={s.signal_id} className="p-3 rounded-lg border border-gray-100 bg-gray-50/80">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-medium text-gray-900">{humanRiskType(s)}</p>
                            <p className="text-sm text-gray-600 mt-0.5">{humanAction(s.recommended_action, s)}</p>
                            <span className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${['high', 'critical'].includes((s.risk_level || '').toLowerCase()) ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>
                              {humanSeverity(s.risk_level)}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 shrink-0">
                            {actions.includes('create_work_order') && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  if (hasFeature('maintenance_workflows')) {
                                    try {
                                      await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
                                      toast.success('Work order created');
                                      loadRiskSignals();
                                      setActiveTab(TAB_MAINTENANCE);
                                    } catch (e) {
                                      toast.error(e?.response?.data?.detail || 'Failed');
                                    }
                                  } else {
                                    setActiveTab(TAB_MAINTENANCE);
                                    setCreateWoOpen(true);
                                    setCreateWoForm((f) => ({ ...f, description: s.recommended_action }));
                                  }
                                }}
                              ><Wrench className="w-3 h-3 mr-1" /> Work order</Button>
                            )}
                            {actions.includes('create_issue') && (
                              <Button size="sm" variant="outline" onClick={async () => { try { await clientAPI.createIssueFromRiskSignal(s.signal_id, {}); toast.success('Issue created'); loadRiskSignals(); } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); } }}>Issue</Button>
                            )}
                            {actions.includes('schedule_inspection') && hasFeature('compliance_engine') && hasFeature('maintenance_workflows') && (
                              <Button size="sm" variant="outline" onClick={() => openBookInspectionFromRisk(s.signal_id)}>Book inspection</Button>
                            )}
                            {actions.includes('schedule_inspection') && hasFeature('maintenance_workflows') && !hasFeature('compliance_engine') && (
                              <Button size="sm" variant="outline" onClick={async () => { try { await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {}); toast.success('Inspection issue logged (maintenance)'); loadRiskSignals(); } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); } }}>Log inspection issue</Button>
                            )}
                            <Button size="sm" variant="ghost" className="text-gray-600" onClick={async () => { try { await clientAPI.updateRiskSignalStatus(s.signal_id, 'acknowledged'); loadRiskSignals(); } catch (_) {} }}>Acknowledge</Button>
                            <Button size="sm" variant="ghost" className="text-gray-600" onClick={async () => { try { await clientAPI.updateRiskSignalStatus(s.signal_id, 'resolved'); loadRiskSignals(); } catch (_) {} }}>Resolve</Button>
                          </div>
                        </div>
                      </li>
                    );
                  })})}
                </ul>
                <Button variant="outline" size="sm" className="mt-3 border-electric-teal text-electric-teal" onClick={() => setActiveTab(TAB_RISK_SIGNALS)}>View all risk signals</Button>
              </CardContent>
            </Card>
          )}

          {requirements.filter((r) => ['OVERDUE', 'EXPIRING_SOON', 'PENDING', 'MISSING'].includes((r.status || '').toUpperCase())).length > 0 && (
            <Card className="border border-amber-200 bg-amber-50/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2"><AlertCircle className="w-4 h-4 text-amber-600" />Next due / action needed</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-sm">
                  {requirements.filter((r) => ['OVERDUE', 'EXPIRING_SOON', 'PENDING', 'MISSING'].includes((r.status || '').toUpperCase())).slice(0, 5).map((r, i) => (
                    <li key={i} className="flex items-center justify-between">
                      <span>{rowTitle(r)}</span>
                      <span className="text-amber-700 font-medium">{complianceRequirementStatusLabel(r.status)}</span>
                    </li>
                  ))}
                </ul>
                <Button variant="outline" size="sm" className="mt-3 border-amber-300 text-amber-800" onClick={() => setActiveTab(TAB_COMPLIANCE)}>View all requirements</Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tab: Compliance */}
      {activeTab === TAB_COMPLIANCE && (
        <>
        <div className="space-y-6">
          {complianceDetail && (
            <>
              <div className="mb-4 flex flex-wrap gap-4 p-4 rounded-xl border border-gray-200 bg-gray-50">
                <span className="font-medium text-midnight-blue">Evidence readiness score: {(complianceDetail.score != null ? complianceDetail.score : complianceDetail.property_score) ?? '—'}/100</span>
                <span className="font-medium text-midnight-blue">Risk level: {formatRiskLabel(complianceDetail.risk_level)}</span>
                {complianceDetail.risk_index != null && complianceDetail.risk_index > 0 && (
                  <span className="text-gray-600">Risk index: {complianceDetail.risk_index}</span>
                )}
                {complianceDetail.last_updated_at && (
                  <span className="text-sm text-gray-500">Last updated: {new Date(complianceDetail.last_updated_at).toLocaleString()}</span>
                )}
              </div>
              {(complianceDetail.score_delta != null || complianceDetail.score_change_summary) && (
                <div className="mb-4 flex flex-wrap items-center gap-3 p-3 rounded-lg border border-gray-200 bg-white">
                  {complianceDetail.score_delta != null && complianceDetail.score_delta !== 0 && (
                    <span className={`inline-flex items-center gap-1 font-medium ${complianceDetail.score_delta > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {complianceDetail.score_delta > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                      {complianceDetail.score_delta > 0 ? '+' : ''}{complianceDetail.score_delta} pts
                    </span>
                  )}
                  {complianceDetail.score_change_summary && (
                    <span className="text-sm text-gray-600">{complianceDetail.score_change_summary}</span>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-electric-teal border-electric-teal"
                    onClick={async () => {
                      setScoreHistoryModal(true);
                      setScoreHistoryLoading(true);
                      try {
                        const res = await clientAPI.getScoreHistory(propertyId);
                        setScoreHistoryEntries(res.data?.entries ?? []);
                      } catch (_) {
                        setScoreHistoryEntries([]);
                      } finally {
                        setScoreHistoryLoading(false);
                      }
                    }}
                  >
                    <History className="w-3.5 h-3.5 mr-1" />
                    View change history
                  </Button>
                </div>
              )}
            </>
          )}

          <Card className="border border-gray-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-electric-teal" />
                Compliance Explainability
              </CardTitle>
              <CardDescription>
                Weighted score with requirement-level rationale and next best actions.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {complianceExplainabilityLoading ? (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading explainability...
                </div>
              ) : !complianceExplainability ? (
                <p className="text-sm text-gray-500">Explainability data is currently unavailable.</p>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3 text-sm">
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Score: <strong>{complianceExplainability.score ?? '—'}/100</strong>
                    </span>
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Jurisdiction: <strong>{String(complianceExplainability.jurisdiction || 'ENGLAND_WALES').replace('_', ' ')}</strong>
                    </span>
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Points: <strong>{Number(complianceExplainability.earned_points || 0).toFixed(1)} / {Number(complianceExplainability.applicable_points || 0).toFixed(1)}</strong>
                    </span>
                  </div>

                  {complianceExplainability.bucket_breakdown && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm">
                      {[
                        ['Legal core', complianceExplainability.bucket_breakdown?.legal_core?.percent],
                        ['Documentation', complianceExplainability.bucket_breakdown?.documentation_completeness?.percent],
                        ['Operational', complianceExplainability.bucket_breakdown?.operational_responsiveness?.percent],
                        ['Recency', complianceExplainability.bucket_breakdown?.recency_maintenance_confidence?.percent],
                      ].map(([label, pct]) => (
                        <div key={label} className="rounded border border-gray-200 p-2 bg-white">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
                          <p className="font-semibold text-midnight-blue">{Number(pct || 0).toFixed(0)}%</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {Array.isArray(complianceExplainability.top_next_actions) && complianceExplainability.top_next_actions.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-midnight-blue mb-1">Top next actions</p>
                      <ul className="space-y-1 text-sm text-gray-700">
                        {complianceExplainability.top_next_actions.slice(0, 5).map((a, idx) => (
                          <li key={`${a.requirement_code || 'req'}-${idx}`} className="flex items-center justify-between gap-2">
                            <span>• {a.action}</span>
                            <span className="text-xs text-gray-500">+{Number(a.impact_points || 0).toFixed(1)} pts</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {Array.isArray(complianceExplainability.score_breakdown) && complianceExplainability.score_breakdown.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-midnight-blue mb-1">Requirement breakdown</p>
                      <div className="overflow-x-auto rounded-lg border border-gray-200">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-50 text-left text-gray-600">
                              <th className="px-3 py-2">Requirement</th>
                              <th className="px-3 py-2">Status</th>
                              <th className="px-3 py-2">Risk if failed</th>
                              <th className="px-3 py-2">Expiry</th>
                              <th className="px-3 py-2 text-right">Missing points</th>
                              <th className="px-3 py-2 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {complianceExplainability.score_breakdown
                              .filter((r) => r?.applies_if)
                              .sort((a, b) => {
                                const aMiss = Number(a?.applicable_points || 0) - Number(a?.earned_points || 0);
                                const bMiss = Number(b?.applicable_points || 0) - Number(b?.earned_points || 0);
                                return bMiss - aMiss;
                              })
                              .slice(0, 8)
                              .map((r, idx) => {
                                const missing = Math.max(0, Number(r?.applicable_points || 0) - Number(r?.earned_points || 0));
                                const status = String(r?.status || '').toUpperCase();
                                const isMissingOrExpired = ['MISSING', 'MISSING_EVIDENCE', 'EXPIRED'].includes(status);
                                const actionLabel = isMissingOrExpired ? 'Upload' : 'Review';
                                const requirementCode = String(r?.requirement_code || '').toLowerCase();
                                return (
                                  <tr key={`${r?.requirement_code || 'req'}-${idx}`} className="border-t border-gray-100">
                                    <td className="px-3 py-2 font-medium text-midnight-blue">
                                      {r?.requirement_code ? requirementLabel(r.requirement_code) : '—'}
                                    </td>
                                    <td className="px-3 py-2 text-gray-700">{complianceRequirementStatusLabel(r?.status)}</td>
                                    <td className="px-3 py-2 text-gray-700">{String(r?.risk_level_if_failed || '—')}</td>
                                    <td className="px-3 py-2 text-gray-600">
                                      {r?.expiry_date
                                        ? r?.date_source === 'SYSTEM_ESTIMATED'
                                          ? `Est. ${formatDate(r.expiry_date)}`
                                          : formatDate(r.expiry_date)
                                        : '—'}
                                    </td>
                                    <td className="px-3 py-2 text-right text-gray-700">{missing.toFixed(1)}</td>
                                    <td className="px-3 py-2 text-right">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-electric-teal border-electric-teal"
                                        onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_code: requirementCode }))}
                                      >
                                        {actionLabel}
                                      </Button>
                                    </td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* A) Compliance Summary Row */}
          {(() => {
            const sum = getComplianceSummary();
            const nextDue = getNextDueDate();
            return (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <button type="button" onClick={() => setComplianceStatusFilter('')} className="text-left p-3 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Applicable</p>
                  <p className="text-lg font-semibold text-midnight-blue">{sum.totalApplicable}</p>
                </button>
                <button type="button" onClick={() => setComplianceStatusFilter('VALID')} className="text-left p-3 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Valid</p>
                  <p className="text-lg font-semibold text-green-600">{sum.valid}</p>
                </button>
                <button type="button" onClick={() => setComplianceStatusFilter('EXPIRING_SOON')} className="text-left p-3 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Expiring soon</p>
                  <p className="text-lg font-semibold text-amber-600">{sum.expiringSoon}</p>
                </button>
                <button type="button" onClick={() => setComplianceStatusFilter('OVERDUE')} className="text-left p-3 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Overdue</p>
                  <p className="text-lg font-semibold text-red-600">{sum.overdue}</p>
                </button>
                <button type="button" onClick={() => setComplianceStatusFilter('MISSING')} className="text-left p-3 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Missing evidence</p>
                  <p className="text-lg font-semibold text-gray-700">{sum.missingEvidence}</p>
                </button>
                <div className="p-3 rounded-lg border border-gray-200 bg-gray-50">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Next due</p>
                  <p className="text-lg font-semibold text-midnight-blue">{nextDue ? formatDate(nextDue) : '—'}</p>
                </div>
              </div>
            );
          })()}

          {/* B) Requirement Status Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {['', 'VALID', 'EXPIRING_SOON', 'OVERDUE', 'MISSING'].map((f) => (
              <Button
                key={f || 'all'}
                variant={complianceStatusFilter === f ? 'default' : 'outline'}
                size="sm"
                className={complianceStatusFilter === f ? 'bg-electric-teal text-white' : 'border-gray-200'}
                onClick={() => setComplianceStatusFilter(f)}
              >
                {f === '' ? 'All' : f === 'VALID' ? 'Valid' : f === 'EXPIRING_SOON' ? 'Expiring soon' : f === 'OVERDUE' ? 'Overdue' : 'Missing evidence'}
              </Button>
            ))}
            <input
              type="text"
              placeholder="Search obligation..."
              value={complianceSearchQuery}
              onChange={(e) => setComplianceSearchQuery(e.target.value)}
              className="ml-2 max-w-[200px] px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
            />
          </div>

          {/* C) Obligation Table / Cards */}
          {requirements.length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-12 text-center">
                <p className="text-gray-600 mb-2">No compliance obligations are currently configured for this property.</p>
                <Button variant="outline" onClick={handleRefresh}>Review property setup</Button>
              </CardContent>
            </Card>
          ) : getFilteredRequirements().length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-gray-500">
                No obligations match the current filter. Clear filters to see all.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {!requirements.some((r) => r.evidence_doc_id) && (
                <Card className="border-amber-200 bg-amber-50/30">
                  <CardContent className="py-6 text-center">
                    <p className="text-gray-700 mb-2">No evidence has been uploaded for this property yet.</p>
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button className="bg-electric-teal text-white hover:bg-electric-teal/90" onClick={() => navigate(resolveDocumentsPath(propertyId))}>Upload Evidence</Button>
                      <Button variant="outline" onClick={() => setActiveTab(TAB_EVIDENCE)}>View Evidence tab</Button>
                    </div>
                  </CardContent>
                </Card>
              )}

          {getFilteredRequirements().length > 0 && (
            <>
              <div className="hidden md:block rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 font-medium text-midnight-blue">Obligations</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-left text-gray-600">
                        <th className="p-3">Requirement</th>
                        <th className="p-3">Category</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Due date</th>
                        <th className="p-3">Evidence</th>
                        <th className="p-3">Impact</th>
                        <th className="p-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getFilteredRequirements().map((r, idx) => {
                        const status = getStatus(r);
                        const Icon = status.icon;
                        const days = rowDays(r);
                        const impact = complianceImpactLabel(r);
                        const hasEvidence = !!r.evidence_doc_id;
                        const statusKey = (r.status || '').toUpperCase();
                        const isOverdue = ['OVERDUE', 'EXPIRED'].includes(statusKey);
                        const isExpiringSoon = statusKey === 'EXPIRING_SOON';
                        const isMissing = ['PENDING', 'MISSING'].includes(statusKey);
                        const isValid = ['COMPLIANT', 'VALID'].includes(statusKey);
                        return (
                          <React.Fragment key={rowReqId(r) || r.requirement_code || idx}>
                            <tr
                              className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                              onClick={() => setComplianceExpandedReqId(complianceExpandedReqId === (rowReqId(r) || r.requirement_code) ? null : (rowReqId(r) || r.requirement_code))}
                              data-req-code={r.requirement_code || r.requirement_type || ''}
                            >
                              <td className="p-3 font-medium text-midnight-blue">{rowTitle(r)}</td>
                              <td className="p-3 text-gray-600">
                                {r.requirement_code || r.requirement_type
                                  ? requirementLabel(r.requirement_code || r.requirement_type)
                                  : '—'}
                              </td>
                              <td className="p-3">
                                <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs ${status.className}`}>
                                  <Icon className="w-3.5 h-3.5" />
                                  {status.text}
                                </span>
                              </td>
                              <td className="p-3 text-gray-600">{formatDate(rowExpiry(r))}</td>
                              <td className="p-3 text-gray-600">{hasEvidence ? 'Linked' : '—'}</td>
                              <td className="p-3">
                                <span className={`inline-flex px-2 py-1 rounded border text-xs ${impact.className}`}>{impact.label}</span>
                              </td>
                              <td className="p-3" onClick={(e) => e.stopPropagation()}>
                                <div className="flex flex-wrap gap-1">
                                  {isMissing && (
                                    <Button size="sm" variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>
                                      <Upload className="w-3.5 h-3.5 mr-1" /> Upload
                                    </Button>
                                  )}
                                  {hasEvidence && !isMissing && (
                                    <>
                                      <Button size="sm" variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>
                                        <Eye className="w-3.5 h-3.5 mr-1" /> View
                                      </Button>
                                      {(isOverdue || isExpiringSoon) && (
                                        <Button size="sm" variant="outline" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>Replace</Button>
                                      )}
                                    </>
                                  )}
                                  {isValid && hasEvidence && (
                                    <Button size="sm" variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>View details</Button>
                                  )}
                                  {isMissing && (r.requirement_code || r.requirement_type) && (
                                    <Button size="sm" variant="ghost" className="text-gray-600" onClick={(e) => { e.stopPropagation(); setNotApplicableModal({ requirement_code: r.requirement_code || r.requirement_type, title: rowTitle(r) }); setNotApplicableReason('not_applicable'); }} data-testid="mark-not-applicable">
                                      <MinusCircle className="w-3.5 h-3.5 mr-1" /> Not applicable
                                    </Button>
                                  )}
                                  <a href={`mailto:${SUPPORT_EMAIL}?subject=Support request: ${address}`} className="text-sm text-gray-500 hover:text-electric-teal" onClick={(e) => e.stopPropagation()}>Request help</a>
                                </div>
                              </td>
                            </tr>
                            {complianceExpandedReqId === (rowReqId(r) || r.requirement_code) && (
                              <tr className="bg-gray-50 border-b border-gray-200">
                                <td colSpan={7} className="p-4">
                                  <div className="text-sm space-y-2">
                                    <p><strong>Description:</strong> {rowTitle(r)}</p>
                                    <p><strong>Status:</strong> {status.text}. Status based on portal records.</p>
                                    <p><strong>Due date:</strong> {formatDate(rowExpiry(r))} {days != null && (days < 0 ? `(${Math.abs(days)} days overdue)` : `(${days} days left)`)}</p>
                                    <p><strong>Evidence:</strong> {hasEvidence ? 'Document linked' : 'No document linked'}</p>
                                    <p><strong>Impact:</strong> {impact.label}</p>
                                    <div className="flex flex-wrap gap-2 pt-2">
                                      <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_EVIDENCE)}>View Evidence tab</Button>
                                      <Button size="sm" variant="outline" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'COMPLIANCE' })); }}>View in Timeline</Button>
                                      <a href={`mailto:${SUPPORT_EMAIL}?subject=Support request: ${address}`} className="inline-flex items-center px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 text-gray-600">Request help</a>
                                      <Button size="sm" variant="ghost" onClick={() => setComplianceExpandedReqId(null)}><X className="w-4 h-4" /> Close</Button>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="md:hidden space-y-2">
                {getFilteredRequirements().map((r, idx) => {
                  const status = getStatus(r);
                  const Icon = status.icon;
                  const impact = complianceImpactLabel(r);
                  const hasEvidence = !!r.evidence_doc_id;
                  const statusKey = (r.status || '').toUpperCase();
                  const isMissing = ['PENDING', 'MISSING'].includes(statusKey);
                  return (
                    <Card key={rowReqId(r) || idx} className="border border-gray-200 p-3">
                      <div className="font-medium text-midnight-blue">{rowTitle(r)}</div>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${status.className}`}><Icon className="w-3 h-3" />{status.text}</span>
                        <span className={`inline-flex px-2 py-0.5 rounded border text-xs ${impact.className}`}>{impact.label}</span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{formatDate(rowExpiry(r))} · {hasEvidence ? 'Linked' : 'No evidence'}</div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {isMissing ? (
                          <Button size="sm" variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>Upload</Button>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>View</Button>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => setComplianceExpandedReqId(complianceExpandedReqId === (rowReqId(r) || r.requirement_code) ? null : (rowReqId(r) || r.requirement_code))}>Details</Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
            </div>
          )}

          {/* D) Urgent Items Panel */}
          {getUrgentRequirements().length > 0 && (
            <Card className="border-amber-200 bg-amber-50/30">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Urgent items</CardTitle>
                <p className="text-sm text-gray-600 font-normal">Overdue, expiring within 30 days, or missing evidence. Review required.</p>
              </CardHeader>
              <CardContent className="space-y-2">
                {getUrgentRequirements().slice(0, 10).map((r, i) => {
                  const status = getStatus(r);
                  const days = rowDays(r);
                  const statusKey = (r.status || '').toUpperCase();
                  const isOverdue = ['OVERDUE', 'EXPIRED'].includes(statusKey);
                  const isExpiring = statusKey === 'EXPIRING_SOON';
                  const isMissing = ['PENDING', 'MISSING'].includes(statusKey);
                  let explanation = '';
                  if (isOverdue && days != null) explanation = `Overdue by ${Math.abs(days)} days`;
                  else if (isExpiring && days != null) explanation = `Expires in ${days} days`;
                  else if (isMissing) explanation = 'Missing evidence';
                  else explanation = status.text;
                  const reqCode = r.requirement_code || r.requirement_type || `req-${i}`;
                  const isExplainOpen = urgentExplainKey === reqCode;
                  return (
                    <div key={rowReqId(r) || i} className="rounded border border-amber-200 bg-white overflow-hidden">
                      <div className="flex flex-wrap items-center justify-between gap-2 p-3">
                        <div>
                          <span className="font-medium text-midnight-blue">{rowTitle(r)}</span>
                          <span className="text-sm text-gray-600 ml-2">— {explanation}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            className="flex items-center gap-1 text-xs text-electric-teal hover:underline"
                            onClick={async () => {
                              const next = !isExplainOpen;
                              if (!next) {
                                setUrgentExplainKey(null);
                                setUrgentExplainData(null);
                                return;
                              }
                              setUrgentExplainKey(reqCode);
                              if (urgentExplainKey === reqCode && urgentExplainData) return;
                              setUrgentExplainData(null);
                              setUrgentExplainLoading(true);
                              try {
                                const res = await clientAPI.getRequirementExplanation(propertyId, { requirement_code: reqCode });
                                setUrgentExplainData(res.data);
                              } catch {
                                setUrgentExplainData(null);
                              } finally {
                                setUrgentExplainLoading(false);
                              }
                            }}
                          >
                            <Info className="w-3.5 h-3.5" /> Why this matters {isExplainOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          </button>
                          <Button size="sm" className="bg-electric-teal text-white hover:bg-electric-teal/90" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: rowReqId(r) }))}>
                            {isMissing ? 'Upload evidence' : 'View / replace'}
                          </Button>
                        </div>
                      </div>
                      {isExplainOpen && (
                        <div className="px-3 pb-3 pt-0 border-t border-amber-100 bg-amber-50/30">
                          {urgentExplainLoading ? (
                            <p className="text-sm text-gray-600 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</p>
                          ) : urgentExplainData ? (
                            <>
                              <p className="text-sm text-gray-700 mt-2">{urgentExplainData.why_it_matters}</p>
                              <p className="text-xs text-muted-foreground uppercase mt-2">Recommended action</p>
                              <p className="text-sm font-medium text-midnight-blue">{urgentExplainData.recommended_action_text}</p>
                            </>
                          ) : (
                            <p className="text-sm text-gray-500 mt-2">Could not load explanation.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* E) Compliance notes strip */}
          <p className="text-xs text-gray-500">Status based on portal records. Informational indicator only. Not legal advice.</p>
        </div>
        </>
      )}

      {/* Tab: Maintenance */}
      {activeTab === TAB_MAINTENANCE && !hasFeature('maintenance_workflows') && (
        <UpgradePrompt
          featureName={getFeatureDisplayInfo('maintenance_workflows').featureName}
          featureDescription="Create and manage work orders and issues for this property."
          requiredPlan={getFeatureDisplayInfo('maintenance_workflows').requiredPlan}
          requiredPlanName={getFeatureDisplayInfo('maintenance_workflows').requiredPlanName}
          variant="card"
        />
      )}
      {activeTab === TAB_MAINTENANCE && hasFeature('maintenance_workflows') && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-midnight-blue">Maintenance</h2>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setCreateIssueOpen(true)}>
                <FileText className="w-4 h-4 mr-2" />
                Report issue
              </Button>
              <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => setCreateWoOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add work order
              </Button>
            </div>
          </div>

          {/* Summary row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">Open issues</p><p className="text-lg font-semibold text-midnight-blue">{maintenanceSummary.openIssues}</p></div>
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">Draft WOs</p><p className="text-lg font-semibold text-midnight-blue">{maintenanceSummary.draftWos}</p></div>
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">Active WOs</p><p className="text-lg font-semibold text-midnight-blue">{maintenanceSummary.activeWos}</p></div>
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">SLA breaches</p><p className="text-lg font-semibold text-red-600">{maintenanceSummary.slaBreaches}</p></div>
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">High severity</p><p className="text-lg font-semibold text-amber-600">{maintenanceSummary.highSeverity}</p></div>
            <div className="p-3 rounded-lg border border-gray-200 bg-white"><p className="text-xs text-gray-500 uppercase tracking-wide">Last activity</p><p className="text-sm text-gray-700">{maintenanceSummary.lastActivityAt ? formatRelativeTime(maintenanceSummary.lastActivityAt) : '—'}</p></div>
          </div>

          {/* Issues queue */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Issues</CardTitle>
              <div className="flex flex-wrap gap-2 mt-2">
                <select value={maintenanceIssueFilter.status} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, status: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-1 text-sm">
                  <option value="">All statuses</option><option value="new">New</option><option value="triaged">Triaged</option><option value="ready_for_work_order">{issueStatusLabel('ready_for_work_order')}</option><option value="closed">Closed</option>
                </select>
                <select value={maintenanceIssueFilter.severity} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, severity: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-1 text-sm">
                  <option value="">All severities</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
                </select>
                <select value={maintenanceIssueFilter.category} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, category: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-1 text-sm">
                  <option value="">All categories</option><option value="general">General</option><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="heating">Heating</option>
                </select>
                <Button size="sm" variant="ghost" onClick={loadMaintenanceIssues}>Refresh</Button>
              </div>
            </CardHeader>
            <CardContent>
              {(workOrdersLoading && maintenanceIssues.length === 0) || maintenanceIssuesLoading ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : maintenanceIssues.length === 0 ? (
                <div className="py-8 text-center text-gray-500">
                  <p className="font-medium">No maintenance issues recorded for this property.</p>
                  <div className="flex flex-wrap gap-2 justify-center mt-3">
                    <Button size="sm" variant="outline" onClick={() => setCreateIssueOpen(true)}>Report issue</Button>
                    <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_ASSETS)}>View assets</Button>
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b text-left text-gray-600"><th className="p-2">Summary</th><th className="p-2">Category</th><th className="p-2">Severity</th><th className="p-2">Priority</th><th className="p-2">Asset</th><th className="p-2">Source</th><th className="p-2">Status</th><th className="p-2">Created</th><th className="p-2 text-right">Actions</th></tr></thead>
                    <tbody>
                      {maintenanceIssues.map((iss) => (
                        <tr key={iss.issue_id} className="border-b hover:bg-gray-50">
                          <td className="p-2 font-medium max-w-[180px] truncate" title={iss.description}>{iss.description || '—'}</td>
                          <td className="p-2 text-gray-600">{(iss.category || '—').replace(/_/g, ' ')}</td>
                          <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${(iss.severity || '').toLowerCase() === 'urgent' ? 'bg-red-100 text-red-800' : (iss.severity || '').toLowerCase() === 'high' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'}`}>{iss.severity || '—'}</span></td>
                          <td className="p-2">{iss.priority_score != null ? iss.priority_score : '—'}</td>
                          <td className="p-2 text-gray-600">{assetLabel(iss.asset_id)}</td>
                          <td className="p-2 text-gray-600">{iss.source || '—'}</td>
                          <td className="p-2">{issueStatusLabel(iss.status)}</td>
                          <td className="p-2 text-gray-600">{iss.created_at ? formatDate(iss.created_at) : '—'}</td>
                          <td className="p-2 text-right">
                            <Button size="sm" variant="ghost" onClick={() => setIssueDetailDrawer(iss.issue_id)}>View</Button>
                            {iss.status !== 'ready_for_work_order' && iss.status !== 'closed' && (
                              <Button size="sm" variant="outline" className="ml-1" onClick={() => handleCreateWoFromIssue(iss.issue_id)}>Create WO</Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Work orders queue */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Work orders</CardTitle>
              <div className="flex flex-wrap gap-2 mt-2">
                <select value={maintenanceWoFilter.status} onChange={(e) => setMaintenanceWoFilter((f) => ({ ...f, status: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-1 text-sm">
                  <option value="">All statuses</option><option value="OPEN">Open</option><option value="ASSIGNED">Assigned</option><option value="IN_PROGRESS">In progress</option><option value="COMPLETED">Completed</option><option value="CANCELLED">Cancelled</option>
                </select>
                <Button size="sm" variant="ghost" onClick={loadWorkOrders}>Refresh</Button>
              </div>
            </CardHeader>
            <CardContent>
              {workOrdersLoading && workOrders.length === 0 ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : filteredWorkOrders.length === 0 ? (
                <div className="py-8 text-center text-gray-500">
                  <p className="font-medium">No work orders created yet.</p>
                  <div className="flex flex-wrap gap-2 justify-center mt-3">
                    <Button size="sm" variant="outline" onClick={() => setCreateWoOpen(true)}>Create work order</Button>
                    {hasFeature('contractor_network') && <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_CONTRACTORS)}>Browse contractors</Button>}
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b text-left text-gray-600"><th className="p-2">Description</th><th className="p-2">Linked issue</th><th className="p-2">Asset</th><th className="p-2">Severity</th><th className="p-2">Status</th><th className="p-2">SLA due</th><th className="p-2">Updated</th><th className="p-2 text-right">Actions</th></tr></thead>
                    <tbody>
                      {filteredWorkOrders.map((wo) => (
                        <tr key={wo.work_order_id} className="border-b hover:bg-gray-50">
                          <td className="p-2 font-medium max-w-[180px] truncate" title={wo.description}>{wo.description || '—'}</td>
                          <td className="p-2 text-gray-600">{wo.issue_id ? <button type="button" className="text-electric-teal hover:underline" onClick={() => setIssueDetailDrawer(wo.issue_id)}>Issue</button> : '—'}</td>
                          <td className="p-2 text-gray-600">{assetLabel(wo.asset_id)}</td>
                          <td className="p-2"><span className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{wo.severity || '—'}</span></td>
                          <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${wo.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : wo.status === 'CANCELLED' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800'}`}>{wo.status || '—'}</span></td>
                          <td className="p-2 text-gray-600">{wo.sla_complete_by ? formatDate(wo.sla_complete_by) : '—'}</td>
                          <td className="p-2 text-gray-600">{wo.updated_at ? formatRelativeTime(wo.updated_at) : '—'}</td>
                          <td className="p-2 text-right"><Button size="sm" variant="ghost" onClick={() => setWoDetailDrawer(wo.work_order_id)}>View</Button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* SLA panel */}
          {slaAtRiskOrBreached.length > 0 && (
            <Card className="border-amber-200 bg-amber-50/30">
              <CardHeader><CardTitle className="text-base">SLA at risk or breached</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {slaAtRiskOrBreached.slice(0, 10).map((wo) => (
                    <li key={wo.work_order_id} className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-white border border-amber-100">
                      <span className="font-medium truncate max-w-[200px]">{wo.description || wo.work_order_id}</span>
                      <span className="text-xs text-gray-600">{wo.sla_complete_by ? formatDate(wo.sla_complete_by) : '—'}</span>
                      {wo.sla_breached_at ? <span className="text-xs text-red-600 font-medium">Breached</span> : <span className="text-xs text-amber-600">At risk</span>}
                      <Button size="sm" variant="outline" onClick={() => setWoDetailDrawer(wo.work_order_id)}>View</Button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Recurring / risk strip */}
          {hasFeature('predictive_maintenance') && (
            <Card className="border-gray-200">
              <CardContent className="py-3 flex items-center justify-between gap-4">
                <span className="text-sm text-gray-600">Recurring issues and repair history feed into risk signals.</span>
                <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_RISK_SIGNALS)}>View risk signals</Button>
              </CardContent>
            </Card>
          )}

          {createWoOpen && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCreateWoOpen(false)}>
              <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Add work order</h2>
                <form onSubmit={handleCreateWorkOrder} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                    <textarea value={createWoForm.description} onChange={(e) => setCreateWoForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={3} placeholder="Describe the issue..." required />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button type="submit" disabled={createWoSaving} className="bg-electric-teal hover:bg-electric-teal/90">{createWoSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create'}</Button>
                    <Button type="button" variant="outline" onClick={() => setCreateWoOpen(false)}>Cancel</Button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {createIssueOpen && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCreateIssueOpen(false)}>
              <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Report issue (triaged)</h2>
                <form onSubmit={handleCreateIssue} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                    <textarea value={createIssueForm.description} onChange={(e) => setCreateIssueForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={3} placeholder="Describe the issue..." required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                    <select value={createIssueForm.category} onChange={(e) => setCreateIssueForm((f) => ({ ...f, category: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full">
                      <option value="general">General</option><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="heating">Heating</option>
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
                    <dt className="text-gray-500">Category</dt><dd>{(issueDetailData.category || '—').replace(/_/g, ' ')}</dd>
                    <dt className="text-gray-500">Severity</dt><dd>{issueDetailData.severity || '—'}</dd>
                    <dt className="text-gray-500">Priority score</dt><dd>{issueDetailData.priority_score != null ? issueDetailData.priority_score : '—'}</dd>
                    <dt className="text-gray-500">Asset</dt><dd>{assetLabel(issueDetailData.asset_id)}</dd>
                    <dt className="text-gray-500">Source</dt><dd>{issueDetailData.source || '—'}</dd>
                    <dt className="text-gray-500">Status</dt><dd>{issueDetailData.status ? issueStatusLabel(issueDetailData.status) : '—'}</dd>
                    <dt className="text-gray-500">Created</dt><dd>{issueDetailData.created_at ? formatDate(issueDetailData.created_at) : '—'}</dd>
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
                      <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => handleCreateWoFromIssue(issueDetailData.issue_id)}>Create work order</Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => { setActiveTab(TAB_ASSETS); setIssueDetailDrawer(null); }}>View assets</Button>
                    <Button size="sm" variant="outline" onClick={() => setIssueDetailDrawer(null)}>Close</Button>
                  </div>
                </>
              ) : <p className="text-gray-500 py-4">Could not load issue.</p>}
            </div>
          </div>
        </div>
      )}

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
                    <dt className="text-gray-500">Status</dt><dd><span className={`px-1.5 py-0.5 rounded text-xs ${woDetailData.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : woDetailData.status === 'CANCELLED' ? 'bg-gray-100' : 'bg-amber-100 text-amber-800'}`}>{woDetailData.status || '—'}</span></dd>
                    <dt className="text-gray-500">Severity</dt><dd>{woDetailData.severity || '—'}</dd>
                    <dt className="text-gray-500">SLA complete by</dt><dd>{woDetailData.sla_complete_by ? formatDate(woDetailData.sla_complete_by) : '—'}</dd>
                    <dt className="text-gray-500">Asset</dt><dd>{assetLabel(woDetailData.asset_id)}</dd>
                    <dt className="text-gray-500">Linked issue</dt><dd>{woDetailData.issue_id ? <button type="button" className="text-electric-teal hover:underline" onClick={() => { setIssueDetailDrawer(woDetailData.issue_id); setWoDetailDrawer(null); }}>View issue</button> : '—'}</dd>
                    <dt className="text-gray-500">Updated</dt><dd>{woDetailData.updated_at ? formatRelativeTime(woDetailData.updated_at) : '—'}</dd>
                  </dl>
                  {woDetailData.resolution_outcome && <p className="text-sm text-gray-600 mb-2">Outcome: {woDetailData.resolution_outcome}</p>}
                  {woDetailData.cost_estimate_min != null && woDetailData.cost_estimate_max != null && <p className="text-sm text-gray-600 mb-4">Cost estimate: £{woDetailData.cost_estimate_min} – £{woDetailData.cost_estimate_max}</p>}
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-700">Update status</label>
                    <select
                      value={woDetailData.status || ''}
                      onChange={(e) => handleUpdateWorkOrderStatus(woDetailData.work_order_id, e.target.value)}
                      disabled={woUpdateSaving}
                      className="border border-gray-200 rounded-md px-3 py-2 text-sm"
                    >
                      <option value="DRAFT">Draft</option>
                      <option value="OPEN">Open</option>
                      <option value="ASSIGNED">Assigned</option>
                      <option value="SCHEDULED">Scheduled</option>
                      <option value="IN_PROGRESS">In progress</option>
                      <option value="AWAITING_PARTS">Awaiting parts</option>
                      <option value="COMPLETED">Completed</option>
                      <option value="VERIFIED">Verified</option>
                      <option value="CLOSED">Closed</option>
                      <option value="CANCELLED">Cancelled</option>
                    </select>
                  </div>
                  {hasFeature('contractor_network') && (
                    <div className="mt-4">
                      <h4 className="font-medium text-gray-700 mb-2">Recommended contractors</h4>
                      {woRecommendLoading ? <p className="text-sm text-gray-500">Loading…</p> : woRecommendList?.length > 0 ? (
                        <ul className="space-y-1">
                          {woRecommendList.slice(0, 5).map((c) => (
                            <li key={c.contractor_id || c.id} className="flex items-center justify-between gap-2 text-sm">
                              <span>{c.name || c.contractor_name || c.contractor_id}</span>
                              <Button size="sm" variant="outline" onClick={() => handleAssignContractor(woDetailData.work_order_id, c.contractor_id || c.id)} disabled={woUpdateSaving}>Assign</Button>
                            </li>
                          ))}
                        </ul>
                      ) : <p className="text-sm text-gray-500">No recommendations.</p>}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 mt-4">
                    <Button size="sm" variant="outline" onClick={() => { setActiveTab(TAB_CONTRACTORS); setWoDetailDrawer(null); }}>Browse contractors</Button>
                    <Button size="sm" variant="outline" onClick={() => setWoDetailDrawer(null)}>Close</Button>
                  </div>
                </>
              ) : <p className="text-gray-500 py-4">Could not load work order.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Evidence */}
      {activeTab === TAB_EVIDENCE && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-midnight-blue">Evidence vault</h2>
            <div className="flex items-center gap-2">
              <Button
                className="bg-electric-teal text-white hover:bg-electric-teal/90"
                onClick={() => navigate(resolveDocumentsPath(propertyId))}
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload Evidence
              </Button>
              <Button variant="outline" size="sm" className="border-gray-200" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                Open full list
              </Button>
            </div>
          </div>
          <p className="text-sm text-gray-500">Need help? See: <Link to="/help?article=uploading-evidence" className="text-electric-teal hover:underline">Uploading Evidence guide</Link> in Help Centre.</p>

          {evidenceLoading ? (
            <div className="flex items-center gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : !evidenceData ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-gray-500">
                Unable to load evidence. Try again or open the Documents page.
              </CardContent>
            </Card>
          ) : (
            <>
              {/* A) Evidence Summary Bar */}
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex flex-wrap gap-6 text-sm">
                  <span><strong className="text-midnight-blue">Total documents:</strong> {evidenceData.summary?.totalDocuments ?? 0}</span>
                  <span><strong className="text-midnight-blue">Linked:</strong> {evidenceData.summary?.linked ?? 0}</span>
                  <span><strong className="text-midnight-blue">Pending confirmation:</strong> {evidenceData.summary?.pendingConfirmation ?? 0}</span>
                  <span><strong className="text-midnight-blue">Missing critical evidence:</strong> {evidenceData.summary?.missingCriticalEvidence ?? 0}</span>
                  <span><strong className="text-midnight-blue">Last uploaded:</strong> {evidenceData.summary?.lastUploadedAt ? formatRelativeTime(evidenceData.summary.lastUploadedAt) : '—'}</span>
                </div>
              </div>

              {/* B) Upload / Add Evidence – CTA already above */}

              {/* Missing critical CTA */}
              {(evidenceData.summary?.missingCriticalEvidence ?? 0) > 0 && (
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardContent className="py-3 flex items-center justify-between gap-4">
                    <span className="text-sm text-amber-800">Some requirements are missing evidence. Upload documents to update score and risk.</span>
                    <Button size="sm" className="bg-electric-teal text-white hover:bg-electric-teal/90" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                      Upload required evidence
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* C) Evidence Table / Cards */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">All evidence</h3>
                {(evidenceData.documents?.length ?? 0) === 0 ? (
                  <Card className="border border-gray-200">
                    <CardContent className="py-12 text-center">
                      <p className="text-gray-600 mb-2">No evidence has been uploaded for this property yet.</p>
                      <div className="flex flex-wrap justify-center gap-2">
                        <Button className="bg-electric-teal text-white hover:bg-electric-teal/90" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                          Upload Evidence
                        </Button>
                        <Button variant="outline" onClick={() => setActiveTab(TAB_COMPLIANCE)}>
                          View Compliance Requirements
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <>
                    <div className="hidden md:block rounded-xl border border-gray-200 bg-white overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-200 text-left text-gray-600 bg-gray-50">
                              <th className="p-3">Document</th>
                              <th className="p-3">Document type</th>
                              <th className="p-3">Linked requirement</th>
                              <th className="p-3">Status</th>
                              <th className="p-3">Uploaded by</th>
                              <th className="p-3">Uploaded at</th>
                              <th className="p-3">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {evidenceData.documents.map((doc) => (
                              <tr key={doc.document_id} className="border-b border-gray-100 hover:bg-gray-50">
                                <td className="p-3 font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</td>
                                <td className="p-3 text-gray-600">{doc.document_type ? documentTypeLabel(doc.document_type) : '—'}</td>
                                <td className="p-3 text-gray-600">{doc.requirement_id || '—'}</td>
                                <td className="p-3">
                                  <span className="inline-flex px-2 py-1 rounded border text-xs bg-gray-100 text-gray-700 border-gray-200">{evidenceDocStatusLabel(doc)}</span>
                                </td>
                                <td className="p-3 text-gray-600">{doc.uploaded_by || '—'}</td>
                                <td className="p-3 text-gray-600">{doc.uploaded_at ? formatDate(doc.uploaded_at) : '—'}</td>
                                <td className="p-3">
                                  <div className="flex flex-wrap gap-1">
                                    <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}><Eye className="w-3 h-3 mr-1" /> View</Button>
                                    <Button variant="outline" size="sm" onClick={() => handleEvidenceDocumentDownload(doc)}><Download className="w-3 h-3 mr-1" /> Download</Button>
                                    {isPendingConfirmation(doc) && (
                                      <Button variant="outline" size="sm" className="border-amber-300 text-amber-700" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>Confirm details</Button>
                                    )}
                                    <Button variant="outline" size="sm" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}><Link2 className="w-3 h-3 mr-1" /> Link</Button>
                                    <Button variant="ghost" size="sm" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'EVIDENCE' })); }}><History className="w-3 h-3 mr-1" /> History</Button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <div className="md:hidden space-y-2">
                      {evidenceData.documents.map((doc) => (
                        <Card key={doc.document_id} className="border border-gray-200 p-3">
                          <div className="font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</div>
                          <div className="text-xs text-gray-600 mt-1">Type: {doc.document_type ? documentTypeLabel(doc.document_type) : '—'} · {evidenceDocStatusLabel(doc)} · {doc.uploaded_at ? formatDate(doc.uploaded_at) : '—'}</div>
                          <div className="flex flex-wrap gap-1 mt-2">
                            <Button variant="outline" size="sm" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>View</Button>
                            <Button variant="outline" size="sm" onClick={() => handleEvidenceDocumentDownload(doc)}>Download</Button>
                            {isPendingConfirmation(doc) && <Button variant="outline" size="sm" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>Confirm</Button>}
                            <Button variant="ghost" size="sm" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'EVIDENCE' })); }}>History</Button>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* D) Pending Confirmations */}
              {(() => {
                const pending = (evidenceData.documents || []).filter(isPendingConfirmation);
                if (pending.length === 0) return null;
                return (
                  <Card className="border-amber-200 bg-amber-50/30">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Pending confirmation</CardTitle>
                      <p className="text-sm text-gray-600 font-normal">Documents with extracted details not yet confirmed. Confirm to update requirement status and score.</p>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {pending.map((doc) => {
                        const ext = doc.ai_extracted_data || doc.ai_extraction?.data || {};
                        const conf = doc.confidence_score ?? doc.ai_extraction?.confidence;
                        return (
                          <div key={doc.document_id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-amber-200 bg-white p-3">
                            <div>
                              <span className="font-medium text-midnight-blue">{doc.file_name || doc.document_id}</span>
                              {(ext.expiry_date || ext.issue_date) && (
                                <span className="text-xs text-gray-500 ml-2">Expiry: {ext.expiry_date || '—'} · Issue: {ext.issue_date || '—'}</span>
                              )}
                              {conf != null && <span className="text-xs text-gray-500 ml-2">Confidence: {Math.round(Number(conf) * 100)}%</span>}
                            </div>
                            <Button size="sm" className="bg-electric-teal text-white hover:bg-electric-teal/90" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>
                              Confirm details
                            </Button>
                          </div>
                        );
                      })}
                    </CardContent>
                  </Card>
                );
              })()}

              {/* E) Evidence History / Audit strip */}
              {(evidenceData.recentEvents?.length ?? 0) > 0 && (
                <Card className="border border-gray-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Recent evidence activity</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {evidenceData.recentEvents.slice(0, 15).map((ev, i) => (
                        <li key={ev.id || i} className="flex flex-wrap gap-2 text-gray-600">
                          <span className="text-gray-400">{ev.timestamp ? formatRelativeTime(ev.timestamp) : '—'}</span>
                          <span>{ev.actorType || ev.actor_type || 'system'}</span>
                          <span>{ev.title || ev.eventType || ev.trigger_label || 'Event'}</span>
                          {ev.linkedEntityLabel && <span className="text-gray-500">· {ev.linkedEntityLabel}</span>}
                        </li>
                      ))}
                    </ul>
                    <Button variant="ghost" size="sm" className="mt-2 text-electric-teal" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'EVIDENCE' })); }}>
                      View full timeline
                    </Button>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}

      {/* Tab: Contractors */}
      {activeTab === TAB_CONTRACTORS && !hasFeature('contractor_network') && (
        <UpgradePrompt
          featureName={getFeatureDisplayInfo('contractor_network').featureName}
          featureDescription="View and manage contractors assigned to this property."
          requiredPlan={getFeatureDisplayInfo('contractor_network').requiredPlan}
          requiredPlanName={getFeatureDisplayInfo('contractor_network').requiredPlanName}
          variant="card"
        />
      )}
      {activeTab === TAB_CONTRACTORS && hasFeature('contractor_network') && (
        <Card className="border border-gray-200">
          <CardHeader><CardTitle className="text-lg">Contractors</CardTitle></CardHeader>
          <CardContent>
            <p className="text-gray-600 mb-4">Contractors assigned to work at this property or with past jobs here will appear in this list. You can also view all contractors from Operations.</p>
            <Button variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate('/operations/contractors')}>
              View all contractors
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Tab: Timeline */}
      {activeTab === TAB_TIMELINE && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-midnight-blue">Timeline</h2>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={timelineFilters.category}
                onChange={(e) => setTimelineFilters((f) => ({ ...f, category: e.target.value }))}
                className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                aria-label="Event type"
              >
                <option value="">All events</option>
                <option value="EVIDENCE">Evidence</option>
                <option value="COMPLIANCE">Compliance</option>
                <option value="MAINTENANCE">Maintenance</option>
                <option value="SCORE_RISK">Score & risk</option>
                <option value="SYSTEM">System</option>
              </select>
              <select
                value={timelineFilters.dateRange}
                onChange={(e) => setTimelineFilters((f) => ({ ...f, dateRange: e.target.value }))}
                className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                aria-label="Date range"
              >
                <option value="7">Last 7 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
              </select>
              <select
                value={timelineFilters.actor_type}
                onChange={(e) => setTimelineFilters((f) => ({ ...f, actor_type: e.target.value }))}
                className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                aria-label="Actor"
              >
                <option value="">All actors</option>
                <option value="user">You</option>
                <option value="admin">Admin</option>
                <option value="system">System</option>
              </select>
              <Button variant="outline" size="sm" onClick={loadTimeline} disabled={timelineLoading}>
                <RefreshCw className={`w-4 h-4 mr-1 ${timelineLoading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {timelineError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {timelineError}
            </div>
          )}

          {timelineLoading ? (
            <div className="flex items-center gap-2 text-gray-500 py-12">
              <Loader2 className="w-6 h-6 animate-spin" />
              Loading timeline…
            </div>
          ) : timelineItems.length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-12 text-center">
                <Calendar className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-700 font-medium">No activity has been recorded for this property yet.</p>
                <p className="text-sm text-gray-500 mt-1 mb-4">Upload evidence, report an issue, or complete property setup to see events here.</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                    <Upload className="w-4 h-4 mr-2" />
                    Upload Evidence
                  </Button>
                  {hasFeature('maintenance_workflows') && (
                    <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => { setActiveTab(TAB_MAINTENANCE); setCreateWoOpen(true); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Issue
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setActiveTab(TAB_OVERVIEW)}>
                    View property setup
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {timelineItems.map((item) => {
                const cat = item.category || 'SCORE_RISK';
                const Icon = cat === 'EVIDENCE' ? FileText : cat === 'COMPLIANCE' ? ClipboardCheck : cat === 'MAINTENANCE' ? Wrench : cat === 'SYSTEM' ? Building2 : BarChart3;
                const actionTab = cat === 'EVIDENCE' ? TAB_EVIDENCE : cat === 'COMPLIANCE' ? TAB_COMPLIANCE : cat === 'MAINTENANCE' ? TAB_MAINTENANCE : cat === 'SCORE_RISK' ? TAB_RISK_SIGNALS : null;
                const showLink = !actionTab || (actionTab === TAB_MAINTENANCE && hasFeature('maintenance_workflows')) || (actionTab === TAB_RISK_SIGNALS && hasFeature('predictive_maintenance')) || actionTab === TAB_EVIDENCE || actionTab === TAB_COMPLIANCE;
                return (
                  <li key={item.id} className="border border-gray-200 rounded-lg bg-white overflow-hidden hover:border-gray-300 transition-colors">
                    <div className="p-4 flex gap-4">
                      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600">
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-midnight-blue">{item.title}</p>
                        {item.description && <p className="text-sm text-gray-600 mt-0.5">{item.description}</p>}
                        <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-gray-500">
                          <span>{formatRelativeTime(item.timestamp)}</span>
                          <span>{item.actorLabel || item.actorType || 'System'}</span>
                          {item.linkedEntityLabel && <span className="text-gray-600">{item.linkedEntityLabel}</span>}
                        </div>
                        {item.impact?.scoreDelta != null && item.impact.scoreDelta !== 0 && (
                          <span className={`inline-block mt-2 text-xs font-medium px-2 py-0.5 rounded ${item.impact.scoreDelta > 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            Score {item.impact.scoreDelta > 0 ? '+' : ''}{item.impact.scoreDelta}
                          </span>
                        )}
                        {showLink && actionTab && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="mt-2 text-electric-teal hover:text-electric-teal/90 -ml-2"
                            onClick={() => setActiveTab(actionTab)}
                          >
                            View {actionTab === TAB_EVIDENCE ? 'Evidence' : actionTab === TAB_COMPLIANCE ? 'Compliance' : actionTab === TAB_MAINTENANCE ? 'Maintenance' : 'Risk Signals'}
                          </Button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {!timelineLoading && timelineItems.length > 0 && timelineNextCursor && (
            <div className="flex justify-center pt-2">
              <Button variant="outline" size="sm" onClick={() => loadTimeline(timelineNextCursor)}>
                Load more
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Tab: Risk Signals */}
      {activeTab === TAB_RISK_SIGNALS && !hasFeature('predictive_maintenance') && (
        <UpgradePrompt
          featureName={getFeatureDisplayInfo('predictive_maintenance').featureName}
          featureDescription="View risk signals and recommendations for this property."
          requiredPlan={getFeatureDisplayInfo('predictive_maintenance').requiredPlan}
          requiredPlanName={getFeatureDisplayInfo('predictive_maintenance').requiredPlanName}
          variant="card"
        />
      )}
      {activeTab === TAB_RISK_SIGNALS && hasFeature('predictive_maintenance') && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-midnight-blue">Risk signals</h2>
          {riskSignalsLoading ? (
            <div className="flex items-center gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : !(riskSignalsData?.signals?.length) ? (
            <Card className="border border-gray-200"><CardContent className="py-8 text-center text-gray-500">No risk signals for this property. Use Recalculate to generate from property data, or add assets and work orders.</CardContent></Card>
          ) : (
            <>
              {riskSignalsData?.summary && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                  <div className="p-3 rounded-lg border border-gray-200 bg-gray-50"><p className="text-xs text-gray-500 uppercase">Total</p><p className="text-lg font-semibold text-midnight-blue">{riskSignalsData.summary.total ?? 0}</p></div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-gray-50"><p className="text-xs text-gray-500 uppercase">High</p><p className="text-lg font-semibold text-amber-700">{riskSignalsData.summary.high ?? 0}</p></div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-gray-50"><p className="text-xs text-gray-500 uppercase">Medium</p><p className="text-lg font-semibold text-gray-700">{riskSignalsData.summary.medium ?? 0}</p></div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-gray-50"><p className="text-xs text-gray-500 uppercase">Last updated</p><p className="text-sm text-gray-600">{riskSignalsData.summary.lastRecalculatedAt ? new Date(riskSignalsData.summary.lastRecalculatedAt).toLocaleString() : '—'}</p></div>
                </div>
              )}
              <div className="flex justify-end mb-2">
                <Button size="sm" variant="outline" className="border-electric-teal text-electric-teal" disabled={riskSignalsRecalculating} onClick={async () => { setRiskSignalsRecalculating(true); try { await clientAPI.recalculatePropertyRiskSignals(propertyId); toast.success('Recalculated'); loadRiskSignals(); } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); } finally { setRiskSignalsRecalculating(false); }}}>
                  {riskSignalsRecalculating ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null} Recalculate
                </Button>
              </div>
              <ul className="space-y-3">
                {riskSignalsData.signals.map((s) => (
                  <li key={s.signal_id} className="flex flex-wrap items-start justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900">{humanRiskType(s)}</p>
                      <p className="text-sm text-gray-700 mt-0.5">{humanAction(s.recommended_action, s)}</p>
                      {Array.isArray(s.reasons) && s.reasons.length > 0 && <ul className="mt-1 text-xs text-gray-600 list-disc list-inside">{s.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
                      <span className={`inline-block mt-2 text-xs px-1.5 py-0.5 rounded ${['high','critical'].includes((s.risk_level||'').toLowerCase()) ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{humanSeverity(s.risk_level)}</span>
                      {s.status && s.status !== 'active' && <span className="ml-2 text-xs text-gray-500">{s.status}</span>}
                    </div>
                    <div className="flex flex-wrap gap-2 shrink-0">
                      {(() => {
                        const actions = Array.isArray(s.suggested_actions) ? s.suggested_actions : ['create_issue', 'create_work_order'];
                        return (
                          <>
                            {actions.includes('create_work_order') && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  if (hasFeature('maintenance_workflows')) {
                                    try {
                                      await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
                                      toast.success('Work order created');
                                      loadRiskSignals();
                                      setActiveTab(TAB_MAINTENANCE);
                                    } catch (e) {
                                      toast.error(e?.response?.data?.detail || 'Failed');
                                    }
                                  } else {
                                    setActiveTab(TAB_MAINTENANCE);
                                    setCreateWoOpen(true);
                                    setCreateWoForm((f) => ({ ...f, description: s.recommended_action }));
                                  }
                                }}
                              ><Wrench className="w-4 h-4 mr-1" /> Create work order</Button>
                            )}
                            {actions.includes('create_issue') && (
                              <Button size="sm" variant="outline" onClick={async () => { try { await clientAPI.createIssueFromRiskSignal(s.signal_id, {}); toast.success('Issue created'); loadRiskSignals(); } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); } }}>Create issue</Button>
                            )}
                            {actions.includes('schedule_inspection') && hasFeature('compliance_engine') && hasFeature('maintenance_workflows') && (
                              <Button size="sm" variant="outline" onClick={() => openBookInspectionFromRisk(s.signal_id)}>Book inspection</Button>
                            )}
                            {actions.includes('schedule_inspection') && hasFeature('maintenance_workflows') && !hasFeature('compliance_engine') && (
                              <Button size="sm" variant="outline" onClick={async () => { try { await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {}); toast.success('Inspection issue logged (maintenance)'); loadRiskSignals(); } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); } }}>Log inspection issue</Button>
                            )}
                          </>
                        );
                      })()}
                      {s.status === 'active' && (
                        <>
                          <Button size="sm" variant="ghost" className="text-gray-600" onClick={async () => { try { await clientAPI.updateRiskSignalStatus(s.signal_id, 'acknowledged'); loadRiskSignals(); } catch (_) {} }}>Acknowledge</Button>
                          <Button size="sm" variant="ghost" className="text-gray-600" onClick={async () => { try { await clientAPI.updateRiskSignalStatus(s.signal_id, 'resolved'); loadRiskSignals(); } catch (_) {} }}>Resolve</Button>
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {/* Tab: Assets */}
      {activeTab === TAB_ASSETS && !hasFeature('maintenance_workflows') && !hasFeature('predictive_maintenance') && (
        <UpgradePrompt
          featureName="Maintenance or Predictive"
          featureDescription="Track property assets (e.g. boiler, electrical) and link to maintenance and risk signals."
          requiredPlan="PLAN_2_PORTFOLIO"
          requiredPlanName="Portfolio"
          variant="card"
        />
      )}
      {activeTab === TAB_ASSETS && (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance')) && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-midnight-blue">Property assets</h2>
          <p className="text-sm text-gray-600">Key systems and equipment. Assets are created automatically during property setup or you can add more.</p>
          {assetsLoading ? (
            <div className="flex items-center gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : assets.length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-10 text-center">
                <Package className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 font-medium">No assets yet</p>
                <p className="text-sm text-gray-500 mt-1">Assets will be automatically created when property setup completes.</p>
                <div className="flex flex-wrap gap-2 justify-center mt-4">
                  <Button
                    variant="default"
                    size="sm"
                    className="bg-electric-teal hover:bg-electric-teal/90"
                    disabled={assetsInitialising}
                    onClick={async () => {
                      setAssetsInitialising(true);
                      try {
                        const res = await clientAPI.ensureDefaultAssetsForProperty(propertyId);
                        const created = res.data?.created ?? 0;
                        if (created > 0) toast.success(`${created} asset${created !== 1 ? 's' : ''} created`);
                        await loadAssets();
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || 'Failed to initialise assets');
                      } finally {
                        setAssetsInitialising(false);
                      }
                    }}
                  >
                    {assetsInitialising ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Initialise Assets
                  </Button>
                  <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={loadAssets}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh Assets
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* A) Asset Summary Row */}
              {assetsSummary && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  <div className="p-3 rounded-lg border border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Total assets</p>
                    <p className="text-lg font-semibold text-midnight-blue">{assetsSummary.total ?? 0}</p>
                  </div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Open issues</p>
                    <p className="text-lg font-semibold text-amber-600">{assetsSummary.with_open_issues ?? 0}</p>
                  </div>
                  {hasFeature('predictive_maintenance') && (
                    <div className="p-3 rounded-lg border border-gray-200 bg-white">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Elevated risk</p>
                      <p className="text-lg font-semibold text-red-600">{assetsSummary.with_elevated_risk ?? 0}</p>
                    </div>
                  )}
                  <div className="p-3 rounded-lg border border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Recent work orders</p>
                    <p className="text-lg font-semibold text-midnight-blue">{assetsSummary.recent_work_orders ?? 0}</p>
                  </div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Compliance linked</p>
                    <p className="text-lg font-semibold text-midnight-blue">{assetsSummary.with_compliance_linkage ?? 0}</p>
                  </div>
                </div>
              )}
              {/* B) Asset Table */}
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-left text-gray-600 bg-gray-50">
                        <th className="p-3">Asset</th>
                        <th className="p-3">Type</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Last service</th>
                        <th className="p-3">Open issues</th>
                        {hasFeature('predictive_maintenance') && <th className="p-3">Risk</th>}
                        <th className="p-3">Linked evidence</th>
                        <th className="p-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assets.map((a) => {
                        const per = assetsSummary?.per_asset?.[a.asset_id] || {};
                        const status = (a.status || 'active').toLowerCase();
                        const statusLabel = status === 'active' ? 'Active' : status === 'inactive' ? 'Inactive' : status === 'replaced' ? 'Replaced' : status === 'removed' ? 'Removed' : 'Active';
                        return (
                          <tr key={a.asset_id} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="p-3 font-medium text-midnight-blue">{a.name || (a.asset_type || '—').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</td>
                            <td className="p-3 text-gray-600">{(a.asset_type || '—').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</td>
                            <td className="p-3 text-gray-600">{statusLabel}</td>
                            <td className="p-3 text-gray-600">{a.last_service_date ? formatDate(a.last_service_date) : '—'}</td>
                            <td className="p-3 text-gray-600">{per.open_issues != null && per.open_issues > 0 ? per.open_issues : '—'}</td>
                            {hasFeature('predictive_maintenance') && (
                              <td className="p-3">
                                {per.risk ? (
                                  <span className={`inline-flex px-2 py-0.5 rounded text-xs ${per.risk === 'high' || per.risk === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>
                                    {(per.risk || '').replace(/^\w/, (c) => c.toUpperCase())}
                                  </span>
                                ) : '—'}
                              </td>
                            )}
                            <td className="p-3 text-gray-600">—</td>
                            <td className="p-3">
                              <div className="flex flex-wrap gap-1">
                                <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={() => {
                                  setAssetDetailDrawer(a.asset_id);
                                  setAssetDetailData(null);
                                  setAssetDetailLoading(true);
                                  clientAPI.getPropertyAsset(propertyId, a.asset_id)
                                    .then((res) => setAssetDetailData(res.data))
                                    .catch(() => setAssetDetailData(null))
                                    .finally(() => setAssetDetailLoading(false));
                                }}>
                                  <Eye className="w-3.5 h-3.5 mr-1" /> View
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => { setEditAssetModal(a); setEditAssetForm({ name: a.name ?? '', status: a.status ?? 'active', last_service_date: a.last_service_date ?? '', make: a.make ?? '', model: a.model ?? '' }); }}>
                                  Edit
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => setActiveTab(TAB_MAINTENANCE)}>
                                  View issues
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
              {/* Mobile cards */}
              <div className="md:hidden space-y-2">
                {assets.map((a) => {
                  const per = assetsSummary?.per_asset?.[a.asset_id] || {};
                  const statusLabel = (a.status || 'active') === 'active' ? 'Active' : (a.status || 'active');
                  return (
                    <Card key={a.asset_id} className="border border-gray-200 p-3">
                      <div className="font-medium text-midnight-blue">{a.name || (a.asset_type || '').replace(/_/g, ' ')}</div>
                      <div className="text-xs text-gray-500 mt-1">Type: {(a.asset_type || '').replace(/_/g, ' ')} · Status: {statusLabel} · Last service: {a.last_service_date ? formatDate(a.last_service_date) : '—'}</div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        <Button variant="outline" size="sm" onClick={() => { setAssetDetailDrawer(a.asset_id); setAssetDetailData(null); setAssetDetailLoading(true); clientAPI.getPropertyAsset(propertyId, a.asset_id).then((res) => setAssetDetailData(res.data)).catch(() => setAssetDetailData(null)).finally(() => setAssetDetailLoading(false)); }}>View</Button>
                        <Button variant="outline" size="sm" onClick={() => { setEditAssetModal(a); setEditAssetForm({ name: a.name ?? '', status: a.status ?? 'active', last_service_date: a.last_service_date ?? '', make: a.make ?? '', model: a.model ?? '' }); }}>Edit</Button>
                        <Button variant="outline" size="sm" onClick={() => setActiveTab(TAB_MAINTENANCE)}>View issues</Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* Asset Detail Drawer */}
      {assetDetailDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setAssetDetailDrawer(null)}>
          <div className="w-full max-w-md bg-white shadow-xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-midnight-blue">Asset details</h3>
              <button type="button" onClick={() => setAssetDetailDrawer(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4">
              {assetDetailLoading ? (
                <div className="flex items-center gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : assetDetailData?.asset ? (
                <>
                  <dl className="space-y-2 text-sm">
                    <div><dt className="text-gray-500">Name</dt><dd className="font-medium">{assetDetailData.asset.name || assetDetailData.asset.asset_type || '—'}</dd></div>
                    <div><dt className="text-gray-500">Type</dt><dd>{(assetDetailData.asset.asset_type || '—').replace(/_/g, ' ')}</dd></div>
                    <div><dt className="text-gray-500">Status</dt><dd>{(assetDetailData.asset.status || 'active').replace(/^\w/, (c) => c.toUpperCase())}</dd></div>
                    <div><dt className="text-gray-500">Last service</dt><dd>{assetDetailData.asset.last_service_date ? formatDate(assetDetailData.asset.last_service_date) : '—'}</dd></div>
                    <div><dt className="text-gray-500">Installed year</dt><dd>{assetDetailData.asset.installed_year ?? '—'}</dd></div>
                    <div><dt className="text-gray-500">Make / model</dt><dd>{(assetDetailData.asset.make || assetDetailData.asset.model) ? [assetDetailData.asset.make, assetDetailData.asset.model].filter(Boolean).join(' · ') : '—'}</dd></div>
                  </dl>
                  <h4 className="font-medium mt-4 mb-2">Linked compliance</h4>
                  <p className="text-sm text-gray-500">—</p>
                  <h4 className="font-medium mt-4 mb-2">Maintenance history</h4>
                  {(assetDetailData.events?.length ?? 0) > 0 ? (
                    <ul className="space-y-1 text-sm">
                      {assetDetailData.events.slice(0, 10).map((ev, i) => (
                        <li key={ev.event_id || i}>{ev.event_type} · {ev.timestamp ? formatRelativeTime(ev.timestamp) : '—'}</li>
                      ))}
                    </ul>
                  ) : <p className="text-sm text-gray-500">No events yet.</p>}
                  {hasFeature('predictive_maintenance') && (
                    <>
                      <h4 className="font-medium mt-4 mb-2">Risk signals</h4>
                      <p className="text-sm text-gray-500">View risk signals in the Risk Signals tab.</p>
                    </>
                  )}
                  <div className="mt-4 flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => { const a = assets.find((x) => x.asset_id === assetDetailDrawer); if (a) { setEditAssetModal(a); setEditAssetForm({ name: a.name ?? '', status: a.status ?? 'active', last_service_date: a.last_service_date ?? '', make: a.make ?? '', model: a.model ?? '' }); } setAssetDetailDrawer(null); }}>Edit asset</Button>
                    <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_MAINTENANCE)}>View issues</Button>
                  </div>
                </>
              ) : (
                <p className="text-gray-500">Could not load asset.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Asset Modal */}
      {editAssetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !editAssetSaving && setEditAssetModal(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full m-4 p-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-midnight-blue mb-4">Edit asset</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input type="text" value={editAssetForm.name ?? ''} onChange={(e) => setEditAssetForm((f) => ({ ...f, name: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g. Main boiler" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select value={editAssetForm.status ?? 'active'} onChange={(e) => setEditAssetForm((f) => ({ ...f, status: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="replaced">Replaced</option>
                  <option value="removed">Removed</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Last service date</label>
                <input type="date" value={(editAssetForm.last_service_date || '').toString().slice(0, 10)} onChange={(e) => setEditAssetForm((f) => ({ ...f, last_service_date: e.target.value || null }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Make</label>
                <input type="text" value={editAssetForm.make ?? ''} onChange={(e) => setEditAssetForm((f) => ({ ...f, make: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
                <input type="text" value={editAssetForm.model ?? ''} onChange={(e) => setEditAssetForm((f) => ({ ...f, model: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={() => setEditAssetModal(null)} disabled={editAssetSaving}>Cancel</Button>
              <Button
                onClick={() => {
                  setEditAssetSaving(true);
                  clientAPI.updatePropertyAsset(propertyId, editAssetModal.asset_id, {
                    name: editAssetForm.name || null,
                    status: editAssetForm.status || null,
                    last_service_date: editAssetForm.last_service_date || null,
                    make: editAssetForm.make || null,
                    model: editAssetForm.model || null,
                  })
                    .then(() => { toast.success('Asset updated'); setEditAssetModal(null); loadAssets(); })
                    .catch((err) => toast.error(err?.response?.data?.detail || 'Update failed'))
                    .finally(() => setEditAssetSaving(false));
                }}
                disabled={editAssetSaving}
              >
                {editAssetSaving ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {bookInspectionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !bookInspectionSaving && setBookInspectionOpen(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full m-4 p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-2 mb-3">
              <h3 className="font-semibold text-midnight-blue text-lg">Book compliance inspection</h3>
              <button type="button" onClick={() => !bookInspectionSaving && setBookInspectionOpen(false)} className="p-1 rounded hover:bg-gray-100" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Select the regulatory obligation this inspection satisfies. A compliance job (not a repair ticket) will be created and linked to this risk signal.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Obligation on this property</label>
            <select
              value={bookInspectionReqPick}
              onChange={(e) => setBookInspectionReqPick(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4 text-sm"
              disabled={bookInspectionSaving}
            >
              <option value="">— Select —</option>
              {requirements.map((r) => {
                const rid = r.requirement_id || r.id;
                if (!rid) return null;
                return (
                  <option key={rid} value={rid}>
                    {rowTitle(r)}
                  </option>
                );
              })}
            </select>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setBookInspectionOpen(false)} disabled={bookInspectionSaving}>Cancel</Button>
              <Button onClick={confirmBookInspectionFromRisk} disabled={bookInspectionSaving || !bookInspectionReqPick}>
                {bookInspectionSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Book inspection'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Score change history modal (global so it stays open when switching tabs) */}
      {scoreHistoryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setScoreHistoryModal(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden m-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-midnight-blue">Score change history</h3>
              <button type="button" onClick={() => setScoreHistoryModal(false)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4 overflow-auto max-h-[60vh]">
              {scoreHistoryLoading ? (
                <p className="text-gray-500">Loading…</p>
              ) : scoreHistoryEntries.length === 0 ? (
                <p className="text-gray-500">No score change history yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-600">
                      <th className="p-2">Date</th>
                      <th className="p-2">Previous</th>
                      <th className="p-2">New</th>
                      <th className="p-2">Delta</th>
                      <th className="p-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scoreHistoryEntries.map((e, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="p-2">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                        <td className="p-2">{e.previous_score ?? '—'}</td>
                        <td className="p-2">{e.new_score ?? '—'}</td>
                        <td className={`p-2 font-medium ${e.delta > 0 ? 'text-green-600' : e.delta < 0 ? 'text-red-600' : ''}`}>{e.delta != null ? (e.delta > 0 ? '+' : '') + e.delta : '—'}</td>
                        <td className="p-2 text-gray-600">{e.reason ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {notApplicableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !notApplicableSubmitting && setNotApplicableModal(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full m-4 p-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-midnight-blue mb-2">Mark as not applicable</h3>
            <p className="text-sm text-gray-600 mb-3">
              &ldquo;{notApplicableModal.title}&rdquo; will be excluded from this property&apos;s score and requirements list. You can change this later from the Requirements tab.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
            <select
              value={notApplicableReason}
              onChange={(e) => setNotApplicableReason(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4"
              data-testid="not-applicable-reason"
            >
              {NOT_REQUIRED_REASONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setNotApplicableModal(null)} disabled={notApplicableSubmitting}>Cancel</Button>
              <Button
                onClick={async () => {
                  setNotApplicableSubmitting(true);
                  try {
                    await clientAPI.markRequirementNotApplicable(propertyId, {
                      requirement_code: notApplicableModal.requirement_code,
                      not_required_reason: notApplicableReason,
                    });
                    toast.success('Requirement marked as not applicable. List will update.');
                    setNotApplicableModal(null);
                    fetchData();
                  } catch (err) {
                    toast.error(err.response?.data?.detail || 'Failed to update');
                  } finally {
                    setNotApplicableSubmitting(false);
                  }
                }}
                disabled={notApplicableSubmitting}
                data-testid="not-applicable-confirm"
              >
                {notApplicableSubmitting ? 'Saving…' : 'Confirm'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
