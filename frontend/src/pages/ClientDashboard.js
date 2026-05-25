import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Alert, AlertDescription } from '../components/ui/alert';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User, Calendar, TrendingUp, TrendingDown, ArrowUp, ArrowDown, Zap, BarChart3, Users, Webhook, ChevronDown, ChevronUp, Info, ExternalLink, Minus, CreditCard, ClipboardCheck, Upload, History, Building2, Wrench, ListTodo, Gauge, Target } from 'lucide-react';
import api, { API_URL, parseApiError } from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import Sparkline from '../components/Sparkline';
import ScoreTrendChart from '../components/ScoreTrendChart';
import { formatRiskLabel, riskLevelToGradeColorMessage, getRiskBandExplanation, getRiskBandExplanationFromScore } from '../utils/riskLabel';
import { UrgencyRow, timingLabelFromDueAtIso } from '../components/client/UrgencyDisplay';
import { requirementLabel, slaStateLabel, riskTypeLabelClient } from '../domain/presentDomain';
import {
  buildEntityRoute,
  normalizeRouteId,
  recordClientPortalInteraction,
  resolveClientPortalPath,
  resolvePropertyPath,
} from '../utils/clientPortalNavigation';
import { resolveTaskCta } from '../utils/ctaRegistry';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import {
  PortalPageShell,
  PortalSectionSkeleton,
  PortalStaleRefreshBanner,
  portalPageRoot,
} from '../components/client/ClientPortalPatterns';
import {
  fetchOperational,
  OPERATIONAL_CACHE_KEYS,
} from '../utils/clientOperationalFetch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Checkbox } from '../components/ui/checkbox';
import {
  JURISDICTION_FALLBACK_ALERT_BODY,
  JURISDICTION_FALLBACK_ALERT_TITLE,
  JURISDICTION_FALLBACK_ACK_CHECKBOX_LABEL,
  JURISDICTION_FALLBACK_ACK_SUBMIT_LABEL,
  JURISDICTION_FALLBACK_ACK_VALIDATION_ERROR,
  JURISDICTION_FALLBACK_CTA,
  JURISDICTION_CHECKLIST_SET_JURISDICTIONS_NOTE,
  JURISDICTION_IMPACT_INTRO,
  JURISDICTION_ONBOARDING_GATE_CONSEQUENCE,
  JURISDICTION_ONBOARDING_GATE_CTA_HINT,
  JURISDICTION_ONBOARDING_GATE_LEAD,
  JURISDICTION_ONBOARDING_GATE_TITLE,
  JURISDICTION_PORTFOLIO_REMINDER_COMPACT,
  JURISDICTION_SCOPE_GLOBAL,
  jurisdictionSourceLabel,
} from '../utils/jurisdictionComplianceCopy';
import { portfolioJurisdictionBannerState } from '../utils/jurisdictionUiPolicy';
import { getPropertyDisplayName } from '../utils/propertyDisplayName';
import {
  alignTodayPayloadTaskSections,
  requirementMapFromList,
} from '../utils/portalRequirementAttention';
import { resolveClientRequirementLifecycle } from '../utils/clientRequirementLifecycle';
import { portfolioHasV2BucketBreakdown } from '../utils/complianceScoreBuckets';
import {
  headlineScoreDisplayForDashboard,
  headlineScoreShowsOutOf100,
} from '../utils/scoringHeadlineDisplay';
import {
  formatScoreLastCalculatedForUi,
  pickScoreLastCalculatedIso,
  portfolioScoreRecalcPendingNote as resolvePortfolioScoreRecalcPendingNote,
  resolveDashboardFreshnessExplanation,
} from '../utils/scoreFreshnessUi';
import { workspaceDashboardWelcomeLead } from '../utils/workspaceOrientationCopy';
const KPI_NO_DATA = 'No data yet';

/** Compact (i) hint for dashboard KPIs — must sit under TooltipProvider. */
function DashboardKpiHint({ label, children }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex ml-1 text-gray-400 hover:text-gray-600 align-middle rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
          aria-label={label || 'Metric details'}
        >
          <Info className="w-3.5 h-3.5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-left text-xs font-normal bg-gray-900 text-gray-50 border-0 px-3 py-2">
        {children}
      </TooltipContent>
    </Tooltip>
  );
}

function navigateToPropertyDashboard(navigate, propertyId, hash = '') {
  if (!normalizeRouteId(propertyId)) return;
  const h = hash ? (hash.startsWith('#') ? hash : `#${hash}`) : '';
  navigate(`${resolvePropertyPath(propertyId)}${h}`);
}
const FRESH_SCORE_STALE_HOURS = 48;
const FRESH_RISK_STALE_HOURS = 72;

function isTimestampStale(iso, maxAgeHours) {
  if (!iso || !maxAgeHours) return false;
  try {
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return false;
    return Date.now() - t > maxAgeHours * 3600000;
  } catch {
    return false;
  }
}

function formatDashboardScore(score) {
  if (score == null || score === '' || (typeof score === 'number' && Number.isNaN(score))) return KPI_NO_DATA;
  return score;
}

function formatDashboardGrade(grade) {
  if (grade == null || grade === '' || grade === '—') return KPI_NO_DATA;
  return grade;
}

/** Short label for compact UI (e.g. grade circle). */
function formatDashboardGradeShort(grade) {
  if (grade == null || grade === '' || grade === '—') return 'N/A';
  return grade;
}

const SETUP_CHECKLIST_DONE_KEY = 'pleerity_setup_checklist_done';
const SETUP_INCOMPLETE_KEY = 'pleerity_setup_incomplete';

/** Map 0-100 score to grade/color/message (matches backend risk_bands). Use when displaying portfolio score for single-property consistency. */
function scoreToGradeColorMessage(score) {
  if (score == null || typeof score !== 'number') return { grade: null, color: 'gray', message: '' };
  if (score >= 80) return { grade: score >= 90 ? 'A' : 'B', color: 'green', message: 'Low risk - good standing' };
  if (score >= 60) return { grade: 'C', color: 'amber', message: 'Moderate risk - action required' };
  if (score >= 40) return { grade: 'D', color: 'amber', message: 'High risk - action required' };
  return { grade: 'F', color: 'red', message: 'High urgency: overdue items detected' };
}

/** Customer-friendly property label: nickname, else address + postcode, else address/postcode/name/id. */
function getPropertyDisplayLabel(p) {
  if (!p) return '';
  return getPropertyDisplayName(p) || p.property_id || '';
}

/** Max rows for dashboard “Focus” strip (distinct from full Portfolio summary table). */
const DASHBOARD_FOCUS_PROPERTY_LIMIT = 6;

/** Single-line summary of open compliance gaps (different lens than separate columns in Portfolio summary). */
function buildDashboardComplianceGapsLine(p, openJobsMap, showOpenJobs) {
  const overdue = Number(p.overdue_count ?? 0);
  const exp = Number(p.expiring_30_count ?? p.expiring_soon_count ?? 0);
  const missing = Number(p.missing_count ?? 0);
  const parts = [];
  if (overdue > 0) parts.push(`${overdue} overdue`);
  if (exp > 0) parts.push(`${exp} expiring soon`);
  if (missing > 0) parts.push(`${missing} missing documents`);
  if (showOpenJobs) {
    const jobs = Number(openJobsMap?.[p.property_id] ?? 0);
    if (jobs > 0) parts.push(`${jobs} open jobs`);
  }
  if (parts.length === 0) return 'No open gaps in this snapshot';
  return parts.join(' · ');
}

/** One-line label for dashboard tasks digest activity feed (matches inbox actions). */
function formatTaskDigestActivityLine(row) {
  if (!row) return '';
  const act = String(row.action || '').toLowerCase();
  const title = row.extra?.title;
  const verbs = { snooze: 'Snoozed', dismiss: 'Dismissed', done: 'Marked done', restore: 'Restored' };
  const v = verbs[act] || (act ? act : 'Activity');
  const t = title && String(title).trim() ? ` — ${String(title).trim()}` : '';
  return `${v}${t}`;
}

const ClientDashboard = () => {
  const navigate = useNavigate();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, logout } = useAuth();
  const { hasFeature } = useEntitlements();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dashboardRefreshing, setDashboardRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notificationPrefs, setNotificationPrefs] = useState(null);
  const [complianceScore, setComplianceScore] = useState(null);
  const [scoreTrend, setScoreTrend] = useState(null);
  const [scoreTimeline, setScoreTimeline] = useState(null);
  const [scoreTrendData, setScoreTrendData] = useState(null); // { points, current, delta_30, best_90, worst_90 } from score-trend API
  const [scoreTrendView, setScoreTrendView] = useState('portfolio'); // 'portfolio' | 'property'
  const [selectedTrendPropertyId, setSelectedTrendPropertyId] = useState(null);
  const [scoreChanges, setScoreChanges] = useState(null);
  const [showScoreExplanation, setShowScoreExplanation] = useState(false);
  const [portfolioSummary, setPortfolioSummary] = useState(null);
  const [requirementsList, setRequirementsList] = useState([]);
  const [showComplianceFramework, setShowComplianceFramework] = useState(false);
  // Explicit UI states instead of blank screen (Goal C)
  const [restrictReason, setRestrictReason] = useState(null); // 'plan' | 'not_provisioned' | 'provisioning_incomplete' | null
  const [redirectPath, setRedirectPath] = useState(null); // from 403 X-Redirect header
  const [networkError, setNetworkError] = useState(false); // true when no response (CORS/network)
  // First-login guided activation: 'checklist' | 'portfolio' | 'documents' | null (null = show main dashboard)
  const [setupView, setSetupView] = useState(null);
  const [setupChecklistSeen, setSetupChecklistSeen] = useState(false);
  const [skippedChecklistThisSession, setSkippedChecklistThisSession] = useState(false);
  const [onboardingChecklist, setOnboardingChecklist] = useState(null);
  const [completingItemId, setCompletingItemId] = useState(null);
  const [onboardingItemError, setOnboardingItemError] = useState('');
  const [jurisdictionAckConfirm, setJurisdictionAckConfirm] = useState(false);
  const [jurisdictionAckSubmitting, setJurisdictionAckSubmitting] = useState(false);
  const [valueInsights, setValueInsights] = useState(null);
  // Operations data for dashboard KPIs and action queue
  const [workOrdersList, setWorkOrdersList] = useState([]);
  const [predictiveInsightsData, setPredictiveInsightsData] = useState(null);
  const [riskSignalsData, setRiskSignalsData] = useState(null);
  const [openIssuesCountKpi, setOpenIssuesCountKpi] = useState(null);
  const [openIssuesKpiLoading, setOpenIssuesKpiLoading] = useState(false);
  const [maintenanceSpendMonth, setMaintenanceSpendMonth] = useState(null);
  /** undefined = not loaded yet; null = load failed (hide digest card); object = digest payload */
  const [tasksDigest, setTasksDigest] = useState(undefined);
  /** GET /client/today/items body — bucket counts align with Today page after tracked-requirement filter. */
  const [todayInboxPayload, setTodayInboxPayload] = useState(undefined);
  /** Composed bundle: urgent rows, risks, compliance (same fetch backs tasks digest summary + activity) */
  const [commandCenter, setCommandCenter] = useState(undefined);
  /** Read-only protection / continuity snapshot (aligned with billing cancel context). */
  const [protectionSnapshot, setProtectionSnapshot] = useState(null);
  const [protectionSnapshotLoading, setProtectionSnapshotLoading] = useState(false);
  /** Since last acknowledged visit — server-backed deltas (audit, score, work orders, uploads). */
  const [activitySince, setActivitySince] = useState(null);
  const [activitySinceLoading, setActivitySinceLoading] = useState(false);
  const [activitySinceAckBusy, setActivitySinceAckBusy] = useState(false);
  /** Admin-managed operational banners (incidents / maintenance). */
  const [systemBanners, setSystemBanners] = useState([]);
  /** Landlord contractors: submitted for network review vs rejected (CONTRACTOR_NETWORK). */
  const [contractorNetworkActivity, setContractorNetworkActivity] = useState(null);
  /** undefined = loading; null = error; object = GET /client/dashboard/roi-summary (non-blocking). */
  const [roiSummary, setRoiSummary] = useState(undefined);
  /** Inbox digest + priority preview: collapsed by default (overview-first). */
  const [dashboardInboxExpanded, setDashboardInboxExpanded] = useState(false);
  /** Zone 3 — subscription / security / activity telemetry (single disclosure; default closed). */
  const [dashboardSystemInsightsOpen, setDashboardSystemInsightsOpen] = useState(false);

  // Only load client dashboard data for client roles with a client_id (staff/owner have client_id null)
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  const commandCenterScopePropertyId =
    scoreTrendView === 'property' && selectedTrendPropertyId ? selectedTrendPropertyId : null;
  const commandCenterScopeLabel = useMemo(() => {
    if (!commandCenterScopePropertyId) return null;
    const p = portfolioSummary?.properties?.find((x) => x.property_id === commandCenterScopePropertyId);
    return p ? getPropertyDisplayLabel(p) : commandCenterScopePropertyId;
  }, [commandCenterScopePropertyId, portfolioSummary?.properties]);

  const fetchTodayInbox = useCallback(
    ({ reset } = {}) => {
      if (!isClientUser) return;
      const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
      if (reset) setTodayInboxPayload(undefined);
      clientAPI
        .getTodayItems(params)
        .then((r) => setTodayInboxPayload(r.data ?? null))
        .catch(() => setTodayInboxPayload(null));
    },
    [isClientUser, commandCenterScopePropertyId],
  );

  const [portalRequirementsForInbox, setPortalRequirementsForInbox] = useState([]);

  const loadPortalRequirements = useCallback(() => {
    if (!isClientUser) return;
    clientAPI
      .getRequirements()
      .then((r) => setPortalRequirementsForInbox(Array.isArray(r.data?.requirements) ? r.data.requirements : []))
      .catch(() => setPortalRequirementsForInbox([]));
  }, [isClientUser]);

  useEffect(() => {
    loadPortalRequirements();
  }, [loadPortalRequirements]);

  useEffect(() => {
    if (!isClientUser) return undefined;
    const onOutcome = () => {
      loadPortalRequirements();
      fetchTodayInbox({ reset: false });
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [isClientUser, loadPortalRequirements, fetchTodayInbox]);

  const contractorNetworkEnabled = hasFeature('contractor_network');

  const showJurisdictionOnboardingGate = useMemo(
    () =>
      Boolean(
        isClientUser &&
          onboardingChecklist &&
          !onboardingChecklist.completed_at &&
          onboardingChecklist.jurisdiction_onboarding &&
          onboardingChecklist.jurisdiction_onboarding.jurisdiction_required &&
          !onboardingChecklist.jurisdiction_onboarding.jurisdiction_fallback_acknowledged,
      ),
    [isClientUser, onboardingChecklist],
  );

  useEffect(() => {
    if (!isClientUser || !contractorNetworkEnabled) {
      setContractorNetworkActivity(null);
      return undefined;
    }
    let cancelled = false;
    clientAPI
      .getContractors({ source_type: 'landlord_added', skip: 0, limit: 100 })
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.contractors || [];
        let pendingNetwork = 0;
        let rejectedCount = 0;
        list.forEach((c) => {
          if ((c.network_submission_rejection_reason || '').trim()) {
            rejectedCount += 1;
          } else if (c.submitted_to_network_at && !c.approved_for_network_at) {
            pendingNetwork += 1;
          }
        });
        setContractorNetworkActivity({ pendingNetwork, rejectedCount });
      })
      .catch(() => {
        if (!cancelled) setContractorNetworkActivity(null);
      });
    return () => {
      cancelled = true;
    };
  }, [isClientUser, contractorNetworkEnabled]);

  useEffect(() => {
    if (!isClientUser) {
      setRoiSummary(undefined);
      return undefined;
    }
    let cancelled = false;
    clientAPI
      .getDashboardRoiSummary()
      .then((res) => {
        if (!cancelled) setRoiSummary(res.data ?? null);
      })
      .catch(() => {
        if (!cancelled) setRoiSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [isClientUser]);

  useEffect(() => {
    if (!isClientUser) {
      setLoading(false);
      if (user && !user.client_id) setError('Client not found. Use the correct portal for your role.');
      return;
    }
    fetchDashboard();
    fetchNotificationPrefs();
    fetchComplianceScore();
    fetchScoreTrend();
    fetchScoreTimeline();
    fetchScoreChanges();
    fetchPortfolioSummary();
    fetchRequirements();
    clientAPI.getOnboardingChecklist().then((r) => setOnboardingChecklist(r.data)).catch(() => {});
    clientAPI.getValueInsights().then((r) => setValueInsights(r.data)).catch(() => setValueInsights(null));
    // Intentionally depend only on role/client_id; fetch functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, user?.role, user?.client_id]);

  // Operations data for Executive KPIs and Action Required (feature-gated)
  useEffect(() => {
    if (!isClientUser) return;
    if (hasFeature('maintenance_workflows')) {
      clientAPI.getMaintenanceWorkOrders({ skip: 0, limit: 500 })
        .then((res) => setWorkOrdersList(res.data?.work_orders || []))
        .catch(() => setWorkOrdersList([]));
    }
    if (hasFeature('predictive_maintenance')) {
      clientAPI.getPredictiveInsights({ limit: 100 })
        .then((res) => setPredictiveInsightsData(res.data))
        .catch(() => setPredictiveInsightsData(null));
      clientAPI.getRiskSignals({ limit: 500 })
        .then((res) => setRiskSignalsData(res.data))
        .catch(() => setRiskSignalsData(null));
    }
  }, [isClientUser, hasFeature]);

  useEffect(() => {
    if (!isClientUser || !hasFeature('maintenance_workflows')) {
      setOpenIssuesCountKpi(null);
      setOpenIssuesKpiLoading(false);
      return;
    }
    setOpenIssuesKpiLoading(true);
    clientAPI
      .getOpenIssuesCount()
      .then((res) => setOpenIssuesCountKpi(res.data?.open_issues_count ?? 0))
      .catch(() => setOpenIssuesCountKpi(null))
      .finally(() => setOpenIssuesKpiLoading(false));
  }, [isClientUser, hasFeature]);

  useEffect(() => {
    if (!isClientUser || !hasFeature('invoicing')) {
      setMaintenanceSpendMonth(null);
      return;
    }
    clientAPI
      .getMaintenanceSpendThisMonth()
      .then((res) => setMaintenanceSpendMonth(res.data))
      .catch(() => setMaintenanceSpendMonth(null));
  }, [isClientUser, hasFeature]);

  useEffect(() => {
    if (!isClientUser) {
      setSystemBanners([]);
      return;
    }
    clientAPI
      .getActiveSystemBanners()
      .then((res) => setSystemBanners(Array.isArray(res.data?.items) ? res.data.items : []))
      .catch(() => setSystemBanners([]));
  }, [isClientUser]);

  const dashboardInboxRequirementById = useMemo(
    () => requirementMapFromList(portalRequirementsForInbox),
    [portalRequirementsForInbox],
  );

  const dashboardAlignedInboxSections = useMemo(
    () => alignTodayPayloadTaskSections(todayInboxPayload, dashboardInboxRequirementById),
    [todayInboxPayload, dashboardInboxRequirementById],
  );

  const todayInboxSum = useMemo(() => {
    if (todayInboxPayload === undefined || todayInboxPayload === null) return null;
    const s = dashboardAlignedInboxSections;
    return s.urgent.length + s.upcoming.length + s.in_progress.length;
  }, [todayInboxPayload, dashboardAlignedInboxSections]);

  // Command center bundle: digest summary + activity + urgent rows + risks + compliance (one round-trip)
  useEffect(() => {
    if (!isClientUser) {
      setTasksDigest(undefined);
      setCommandCenter(undefined);
      setTodayInboxPayload(undefined);
      return;
    }
    const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
    fetchTodayInbox({ reset: true });
    clientAPI
      .getCommandCenter(params)
      .then((res) => {
        const b = res.data || {};
        setCommandCenter(b);
        setTasksDigest({
          summary: b.tasks_digest_summary || {},
          activity_feed: Array.isArray(b.recent_activity) ? b.recent_activity.slice(0, 8) : [],
          freshness: b.freshness || {},
        });
      })
      .catch(() => {
        setTasksDigest(null);
        setCommandCenter(null);
      });
  }, [isClientUser, commandCenterScopePropertyId, fetchTodayInbox]);

  useEffect(() => {
    if (!isClientUser) {
      setProtectionSnapshot(null);
      setProtectionSnapshotLoading(false);
      return;
    }
    const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
    setProtectionSnapshotLoading(true);
    clientAPI
      .getProtectionSnapshot(params)
      .then((res) => setProtectionSnapshot(res.data || null))
      .catch(() => setProtectionSnapshot(null))
      .finally(() => setProtectionSnapshotLoading(false));
  }, [isClientUser, commandCenterScopePropertyId]);

  useEffect(() => {
    if (!isClientUser) {
      setActivitySince(null);
      return undefined;
    }
    let cancelled = false;
    setActivitySinceLoading(true);
    clientAPI
      .getActivitySince()
      .then((res) => {
        if (cancelled) return;
        setActivitySince(res.data);
        if (typeof sessionStorage !== 'undefined' && !sessionStorage.getItem('pleerity_activity_since_viewed')) {
          sessionStorage.setItem('pleerity_activity_since_viewed', '1');
          clientAPI.postAnalyticsEvent({ event: 'activity_since_viewed', path: '/dashboard' }).catch(() => {});
        }
      })
      .catch(() => {
        if (!cancelled) setActivitySince(null);
      })
      .finally(() => {
        if (!cancelled) setActivitySinceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isClientUser]);

  // Real-time Action -> Outcome updates: refresh score/risk/status widgets instantly after meaningful actions.
  useEffect(() => {
    if (!isClientUser) return undefined;
    const onOutcome = () => {
      fetchComplianceScore();
      fetchScoreTimeline();
      fetchScoreTrendCard();
      fetchScoreChanges();
      fetchPortfolioSummary();
      if (hasFeature('predictive_maintenance')) {
        clientAPI.getRiskSignals({ limit: 1 })
          .then((res) => setRiskSignalsData(res.data))
          .catch(() => {});
      }
      const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
      fetchTodayInbox({ reset: false });
      clientAPI
        .getCommandCenter(params)
        .then((res) => {
          const b = res.data || {};
          setCommandCenter(b);
          setTasksDigest({
            summary: b.tasks_digest_summary || {},
            activity_feed: Array.isArray(b.recent_activity) ? b.recent_activity.slice(0, 8) : [],
            freshness: b.freshness || {},
          });
        })
        .catch(() => {});
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, hasFeature, commandCenterScopePropertyId, fetchTodayInbox]);

  const handleAckActivitySince = () => {
    setActivitySinceAckBusy(true);
    clientAPI
      .acknowledgeActivitySince()
      .then(() => clientAPI.getActivitySince())
      .then((res) => setActivitySince(res.data))
      .catch(() => {})
      .finally(() => setActivitySinceAckBusy(false));
  };

  // Refetch score trend card when user switches Portfolio vs Property or selects another property
  useEffect(() => {
    if (!isClientUser) return;
    fetchScoreTrendCard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, scoreTrendView, selectedTrendPropertyId]);

  // Refetch score trend, "What Changed", and onboarding checklist when user returns to the dashboard tab
  useEffect(() => {
    if (!isClientUser) return;
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchScoreTimeline();
        fetchScoreTrendCard();
        fetchScoreChanges();
        fetchComplianceScore();
        clientAPI.getOnboardingChecklist().then((r) => setOnboardingChecklist(r.data)).catch(() => {});
        clientAPI.getValueInsights().then((r) => setValueInsights(r.data)).catch(() => setValueInsights(null));
        const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
        fetchTodayInbox({ reset: false });
        clientAPI
          .getCommandCenter(params)
          .then((res) => {
            const b = res.data || {};
            setCommandCenter(b);
            setTasksDigest({
              summary: b.tasks_digest_summary || {},
              activity_feed: Array.isArray(b.recent_activity) ? b.recent_activity.slice(0, 8) : [],
              freshness: b.freshness || {},
            });
          })
          .catch(() => {
            setTasksDigest(null);
            setCommandCenter(null);
          });
        clientAPI
          .getProtectionSnapshot(params)
          .then((res) => setProtectionSnapshot(res.data || null))
          .catch(() => setProtectionSnapshot(null));
        clientAPI
          .getActivitySince()
          .then((res) => setActivitySince(res.data))
          .catch(() => {});
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, commandCenterScopePropertyId, fetchTodayInbox]);

  const fetchDashboard = async () => {
    try {
      setRestrictReason(null);
      const response = await clientAPI.getDashboard();
      setData(response.data);
      const h = response.data?.compliance_score_headline;
      if (h && typeof h === 'object') {
        setComplianceScore((prev) => prev || h);
      }
      // Defensive: detect missing plan/entitlement (test accounts not fully provisioned)
      const client = result.data?.client;
      if (client && client.billing_plan == null && client.plan_code == null) {
        setRestrictReason('not_provisioned');
      }
    } catch (err) {
      setNetworkError(!err.response);
      const detail = err.response?.data?.detail ?? '';
      const status = err.response?.status;
      const redirect = err.response?.headers?.['x-redirect'];
      if (redirect) setRedirectPath(redirect);
      if (status === 403) {
        const msg = typeof detail === 'string' ? detail.toLowerCase() : String(detail).toLowerCase();
        if (msg.includes('plan') || msg.includes('feature') || msg.includes('entitlement') || msg.includes('restricted')) {
          setRestrictReason('plan');
        } else if (msg.includes('provisioning') || msg.includes('incomplete') || msg.includes('password not set')) {
          setRestrictReason('provisioning_incomplete');
        }
      }
      if (!err.response) {
        setError(`Cannot reach server. Backend: ${API_URL || '(not set)'}`);
      } else {
        const msg = typeof detail === 'string' ? detail : (detail && typeof detail === 'object' && detail.message ? detail.message : JSON.stringify(detail));
        setError(msg || 'Failed to load dashboard');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchNotificationPrefs = async () => {
    try {
      const response = await api.get('/profile/notifications');
      setNotificationPrefs(response.data);
    } catch (err) {
      // Silently fail - not critical for dashboard
      console.log('Could not load notification preferences');
    }
  };

  const fetchComplianceScore = async () => {
    try {
      const response = await api.get('/client/compliance-score');
      setComplianceScore(response.data);
    } catch (err) {
      console.log('Could not load compliance score');
    }
  };

  const fetchScoreTrend = async () => {
    try {
      const response = await api.get('/client/compliance-score/trend?days=30');
      setScoreTrend(response.data);
    } catch (err) {
      console.log('Could not load score trend');
    }
  };

  const fetchScoreTimeline = async () => {
    try {
      const response = await api.get('/client/score/timeline?days=90&interval=week');
      setScoreTimeline(response.data);
    } catch (err) {
      console.log('Could not load score timeline');
    }
  };

  const fetchScoreTrendCard = async (view = null, propertyId = null) => {
    const viewToUse = view ?? scoreTrendView;
    const propId = propertyId ?? selectedTrendPropertyId;
    try {
      if (viewToUse === 'property' && propId) {
        const response = await api.get(`/client/score-trend/property/${propId}?days=90`);
        setScoreTrendData(response.data);
      } else {
        const response = await api.get('/client/score-trend/portfolio?days=90');
        setScoreTrendData(response.data);
      }
    } catch (err) {
      console.log('Could not load score trend');
      setScoreTrendData(null);
    }
  };

  const fetchScoreChanges = async () => {
    try {
      const response = await api.get('/client/score/changes?limit=20');
      setScoreChanges(response.data);
    } catch (err) {
      console.log('Could not load score changes');
    }
  };

  const fetchPortfolioSummary = async () => {
    try {
      const response = await clientAPI.getComplianceSummary();
      setPortfolioSummary(response.data);
    } catch (err) {
      if (err.response?.status !== 404) console.warn('Portfolio compliance-summary not available:', err);
    }
  };

  const fetchRequirements = async () => {
    try {
      const response = await clientAPI.getRequirements();
      setRequirementsList(response.data?.requirements || []);
    } catch (err) {
      if (err.response?.status !== 404) console.warn('Requirements not available for next actions:', err);
    }
  };

  // Server-driven checklist: when API says completed, always show main dashboard (no overlay)
  useEffect(() => {
    if (onboardingChecklist?.completed_at) {
      setSetupView(null);
      setSetupChecklistSeen(false);
      setSkippedChecklistThisSession(false);
    }
  }, [onboardingChecklist?.completed_at]);

  // Show checklist when server says not completed (completed_at null), we have items, and user has not skipped this session
  useEffect(() => {
    if (!isClientUser || loading || restrictReason) return;
    if (onboardingChecklist?.completed_at) return;
    const hasItems = onboardingChecklist?.items?.length > 0;
    if (!hasItems || setupView !== null || skippedChecklistThisSession) return;
    setSetupView('checklist');
  }, [isClientUser, loading, restrictReason, onboardingChecklist?.completed_at, onboardingChecklist?.items?.length, setupView, skippedChecklistThisSession]);

  // Sync sessionStorage-based "incomplete" for fallback banner (no server checklist items)
  useEffect(() => {
    try {
      const incomplete = sessionStorage.getItem(SETUP_INCOMPLETE_KEY) === 'true';
      setSetupChecklistSeen(incomplete);
    } catch (e) {}
  }, []);

  const dismissSetupChecklist = (markIncomplete = false) => {
    try {
      sessionStorage.setItem(SETUP_CHECKLIST_DONE_KEY, 'true');
      if (markIncomplete) sessionStorage.setItem(SETUP_INCOMPLETE_KEY, 'true');
      else sessionStorage.removeItem(SETUP_INCOMPLETE_KEY);
      setSetupChecklistSeen(markIncomplete);
    } catch (e) {}
    setSkippedChecklistThisSession(true);
    setSetupView(null);
    setSearchParams({}, { replace: true });
  };

  const showChecklistView = () => {
    setSkippedChecklistThisSession(false);
    setSetupView('checklist');
  };

  const completeSetupFlow = () => {
    try {
      sessionStorage.setItem(SETUP_CHECKLIST_DONE_KEY, 'true');
      sessionStorage.removeItem(SETUP_INCOMPLETE_KEY);
      setSetupChecklistSeen(false);
    } catch (e) {}
    setSetupView(null);
    setSearchParams({}, { replace: true });
  };

  const refetchOnboardingChecklist = () => {
    if (!isClientUser) return;
    clientAPI.getOnboardingChecklist()
      .then((r) => setOnboardingChecklist(r.data))
      .catch(() => {});
    clientAPI.getValueInsights().then((r) => setValueInsights(r.data)).catch(() => setValueInsights(null));
  };

  const completeOnboardingItem = (itemId) => {
    setOnboardingItemError('');
    setCompletingItemId(itemId);
    clientAPI.completeOnboardingItem(itemId)
      .then(() => refetchOnboardingChecklist())
      .catch((err) => {
        setOnboardingItemError(
          parseApiError(err, 'Could not mark this step complete. Complete the action in the app first, then try again.'),
        );
      })
      .finally(() => setCompletingItemId(null));
  };

  useEffect(() => {
    if (!showJurisdictionOnboardingGate) setJurisdictionAckConfirm(false);
  }, [showJurisdictionOnboardingGate]);

  const submitJurisdictionFallbackAck = () => {
    if (!jurisdictionAckConfirm) {
      setOnboardingItemError(JURISDICTION_FALLBACK_ACK_VALIDATION_ERROR);
      return;
    }
    setOnboardingItemError('');
    setJurisdictionAckSubmitting(true);
    clientAPI
      .acknowledgeJurisdictionFallbackAssumptions({ confirm: true })
      .then((r) => setOnboardingChecklist(r.data))
      .catch((err) => {
        setOnboardingItemError(parseApiError(err, 'Could not record acknowledgement. Please try again.'));
      })
      .finally(() => setJurisdictionAckSubmitting(false));
  };

  /** Hard amber only when jurisdiction_compliance_notice is active for default_fallback — never from compliance_confidence alone. */
  const jurisdictionPortfolioBanner = useMemo(() => {
    const summary = commandCenter?.compliance_status_summary;
    if (!summary || typeof summary !== 'object') {
      return { showFull: false, showCompact: false };
    }
    return portfolioJurisdictionBannerState(
      summary.jurisdiction_compliance_notice,
      summary.jurisdiction_fallback_acknowledged,
    );
  }, [commandCenter]);

  // Whether to show the "documents missing" step: requirements that may need docs/confirmation (REQUIRED/UNKNOWN without confirmed expiry)
  const needsDocumentsStep = useMemo(() => {
    if (!requirementsList.length) return false;
    return requirementsList.some((r) => {
      if (resolveClientRequirementLifecycle(r).state === 'NOT_APPLICABLE') return false;
      return (
        (r.applicability === 'REQUIRED' || (r.applicability || 'UNKNOWN') === 'UNKNOWN') && !r.confirmed_expiry_date
      );
    });
  }, [requirementsList]);

  // Count requirements with a document uploaded but expiry not yet confirmed (for "X documents awaiting confirmation" banner)
  const documentsAwaitingConfirmationCount = useMemo(() => {
    return requirementsList.filter((r) => {
      const linked = Boolean(r.document_id || r.evidence_doc_id);
      return linked && !r.confirmed_expiry_date;
    }).length;
  }, [requirementsList]);

  const getComplianceColor = (status) => {
    switch (status) {
      case 'GREEN': return 'bg-green-50 text-green-700 border-green-200';
      case 'AMBER': return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case 'RED': return 'bg-red-50 text-red-700 border-red-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  // Single property: use portfolio summary score so main card and portfolio table show the same number.
  // Use backend risk_level for grade/message when present; for Low Risk derive grade from score (90+ → A, 80–89 → B) so 100/100 shows Grade A.
  const displayScoreInfo = useMemo(() => {
    const portfolioStatus = portfolioSummary?.score_status;
    const singleProperty =
      portfolioSummary?.properties?.length === 1 && portfolioSummary?.portfolio_score != null;
    if (singleProperty) {
      const score = portfolioSummary.portfolio_score;
      const riskLevel = portfolioSummary.risk_level || portfolioSummary.portfolio_risk_level;
      if (['unavailable', 'reconciliation_required', 'unknown', 'calculating'].includes(portfolioStatus || '')) {
        return {
          score: null,
          grade: null,
          color: 'gray',
          message: portfolioSummary?.score_status_message || complianceScore?.message || 'Compliance score is not available for this view.',
          scoreStatus: portfolioStatus,
          scoreStatusMessage: portfolioSummary?.score_status_message ?? complianceScore?.score_status_message,
        };
      }
      if (riskLevel) {
        const s = (riskLevel || '').trim();
        const { grade, color, message } = s === 'Low Risk'
          ? scoreToGradeColorMessage(score)
          : riskLevelToGradeColorMessage(riskLevel);
        return {
          score,
          grade,
          color,
          message,
          scoreStatus: portfolioStatus,
          scoreStatusMessage: portfolioSummary?.score_status_message ?? complianceScore?.score_status_message,
        };
      }
      const { grade, color, message } = scoreToGradeColorMessage(score);
      return {
        score,
        grade,
        color,
        message,
        scoreStatus: portfolioStatus,
        scoreStatusMessage: portfolioSummary?.score_status_message ?? complianceScore?.score_status_message,
      };
    }
    if (complianceScore) {
      const st = complianceScore.score_status;
      return {
        score: complianceScore.score,
        grade: complianceScore.grade,
        color: complianceScore.color,
        message: complianceScore.message,
        scoreStatus: st,
        scoreStatusMessage: complianceScore.score_status_message,
        scoreCoverage: complianceScore.score_coverage,
      };
    }
    return null;
  }, [complianceScore, portfolioSummary]);

  /** Top strip + cards: authoritative headline label (no silent 0 when status forbids numerics). */
  const portfolioHeadlineUi = useMemo(() => {
    const score = displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score;
    const st =
      displayScoreInfo?.scoreStatus ??
      complianceScore?.score_status ??
      portfolioSummary?.score_status;
    const h = headlineScoreDisplayForDashboard(score, st);
    const display = typeof h === 'number' ? formatDashboardScore(h) : h;
    const showOutOf100 = headlineScoreShowsOutOf100(score, st);
    return { display, showOutOf100 };
  }, [displayScoreInfo, complianceScore, portfolioSummary]);

  /** Portfolio headline freshness: non-ok status copy + when stored scores were last calculated (no new APIs). */
  const dashboardScoreFreshness = useMemo(() => {
    const stRaw =
      displayScoreInfo?.scoreStatus ?? complianceScore?.score_status ?? portfolioSummary?.score_status ?? '';
    const st = String(stRaw).trim().toLowerCase();
    const msg =
      displayScoreInfo?.scoreStatusMessage ??
      complianceScore?.score_status_message ??
      portfolioSummary?.score_status_message ??
      data?.compliance_score_headline?.score_status_message;
    const explanation = resolveDashboardFreshnessExplanation(stRaw, msg);
    const lastIso =
      pickScoreLastCalculatedIso(complianceScore) ||
      pickScoreLastCalculatedIso(portfolioSummary) ||
      pickScoreLastCalculatedIso(data?.compliance_score_headline);
    const lastCalculatedLine = formatScoreLastCalculatedForUi(lastIso);
    const isPartialOrStale = st === 'partial' || st === 'stale';
    return {
      statusKey: st,
      explanation,
      lastCalculatedLine,
      isPartialOrStale,
      hasAny: Boolean(explanation || lastCalculatedLine),
    };
  }, [displayScoreInfo, complianceScore, portfolioSummary, data]);

  const portfolioRecalcPendingLine = useMemo(
    () => resolvePortfolioScoreRecalcPendingNote(complianceScore),
    [complianceScore],
  );

  // Missing-evidence bucket from canonical score stats (portal projection); no client-side pending+overdue sum.
  const actionableMissingCount = useMemo(() => {
    if (complianceScore?.stats != null) {
      const m = complianceScore.stats.missing_evidence;
      if (m != null && !Number.isNaN(Number(m))) return Number(m);
      return Number(complianceScore.stats.pending ?? 0);
    }
    return portfolioSummary?.kpis?.missing ?? 0;
  }, [complianceScore, portfolioSummary]);

  // Net change last 30 days from timeline (single trend source: score_events)
  const netChange30 = useMemo(() => {
    const points = scoreTimeline?.points;
    if (!points || points.length < 2) return null;
    const now = new Date();
    const cutoff = new Date(now);
    cutoff.setDate(cutoff.getDate() - 30);
    const lastScore = points[points.length - 1].score;
    const firstInWindow = points.find((p) => new Date(p.date) >= cutoff);
    const baseScore = firstInWindow ? firstInWindow.score : points[0].score;
    const delta = lastScore - baseScore;
    return delta;
  }, [scoreTimeline?.points]);

  // Inline risk band explanation under grade (single source: portfolio risk_level or score)
  const riskBandExplanation = useMemo(() => {
    const level = portfolioSummary?.risk_level || portfolioSummary?.portfolio_risk_level;
    if (level) return getRiskBandExplanation(level);
    const score = displayScoreInfo?.score ?? complianceScore?.score;
    return getRiskBandExplanationFromScore(score);
  }, [portfolioSummary?.risk_level, portfolioSummary?.portfolio_risk_level, displayScoreInfo?.score, complianceScore?.score]);

  // Audit readiness: Low / Moderate / High from overdue, missing %, expiring (single canonical snapshot)
  const auditReadiness = useMemo(() => {
    const total =
      complianceScore?.stats?.total_requirements ??
      (portfolioSummary?.kpis
        ? (portfolioSummary.kpis.compliant ?? 0) +
          (portfolioSummary.kpis.overdue ?? 0) +
          (portfolioSummary.kpis.expiring_30 ?? 0) +
          (portfolioSummary.kpis.missing ?? 0)
        : 0);
    if (total == null || total === 0) return null;
    const overdue = complianceScore?.stats?.overdue ?? portfolioSummary?.kpis?.overdue ?? 0;
    const expiringSoon = complianceScore?.stats?.expiring_soon ?? portfolioSummary?.kpis?.expiring_30 ?? 0;
    const missing = actionableMissingCount;
    const compliant = complianceScore?.stats?.compliant ?? portfolioSummary?.kpis?.compliant ?? 0;
    const missingPct = total > 0 ? (missing / total) * 100 : 0;
    const confirmedPct = total > 0 ? (compliant / total) * 100 : 0;
    const level = (overdue > 0 || missingPct > 30) ? 'Low' : (missingPct > 10 || expiringSoon > 5) ? 'Moderate' : 'High';
    const drivers = [];
    if (overdue > 0) drivers.push(`${overdue} overdue`);
    if (missing > 0) drivers.push(`${missingPct.toFixed(0)}% missing documents`);
    drivers.push(`${confirmedPct.toFixed(0)}% confirmed`);
    return { level, drivers, overdue, missingPct, confirmedPct };
  }, [complianceScore?.stats, portfolioSummary?.kpis, actionableMissingCount]);

  // Operations: open issues (real issues, not work orders), work order funnel, risk signals count
  const openIssuesCount = openIssuesCountKpi;
  const slaBreachedCount = useMemo(
    () => workOrdersList.filter((wo) => wo.sla_breached_at != null && String(wo.sla_breached_at).trim() !== '').length,
    [workOrdersList]
  );
  const slaNearBreachCount = useMemo(
    () =>
      workOrdersList.filter(
        (wo) =>
          (wo.sla_breach_risk_at != null && String(wo.sla_breach_risk_at).trim() !== '') &&
          !(wo.sla_breached_at != null && String(wo.sla_breached_at).trim() !== '')
      ).length,
    [workOrdersList]
  );
  const workOrderFunnel = useMemo(() => {
    const open = workOrdersList.filter((wo) => wo.status === 'OPEN').length;
    const assigned = workOrdersList.filter((wo) => wo.status === 'ASSIGNED').length;
    const inProgress = workOrdersList.filter((wo) => wo.status === 'IN_PROGRESS').length;
    const completed = workOrdersList.filter((wo) => wo.status === 'COMPLETED').length;
    const cancelled = workOrdersList.filter((wo) => wo.status === 'CANCELLED').length;
    return { open, assigned, inProgress, completed, cancelled };
  }, [workOrdersList]);
  /** Prefer protection snapshot (count_documents) so KPI matches Security card; else API list summary (up to 500 rows). */
  const riskSignalsCount = useMemo(() => {
    if (protectionSnapshot?.risk?.predictive_enabled && protectionSnapshot.risk?.active_risk_signals_count != null) {
      return Number(protectionSnapshot.risk.active_risk_signals_count);
    }
    if (riskSignalsData?.summary?.total != null) return Number(riskSignalsData.summary.total);
    if (!predictiveInsightsData?.properties?.length) return 0;
    return predictiveInsightsData.properties.reduce((sum, p) => sum + (p.insights?.length || 0), 0);
  }, [protectionSnapshot, riskSignalsData, predictiveInsightsData]);

  const trackedPropertyCount = useMemo(() => {
    const n = portfolioSummary?.properties?.length;
    if (n != null && n > 0) return n;
    const c = complianceScore?.properties_count;
    if (c != null && Number(c) > 0) return Number(c);
    return null;
  }, [portfolioSummary?.properties?.length, complianceScore?.properties_count]);
  const openJobsByProperty = useMemo(() => {
    const map = {};
    workOrdersList.filter((wo) => ['OPEN', 'ASSIGNED'].includes(wo.status)).forEach((wo) => {
      if (wo.property_id) map[wo.property_id] = (map[wo.property_id] || 0) + 1;
    });
    return map;
  }, [workOrdersList]);

  /** Subset for “Focus” card: lowest scores first — full grid stays in Portfolio summary. */
  const dashboardFocusProperties = useMemo(() => {
    const props = portfolioSummary?.properties;
    if (!props?.length) return [];
    return [...props]
      .sort((a, b) => {
        const sa = Number(a.property_score ?? a.score);
        const sb = Number(b.property_score ?? b.score);
        const na = Number.isFinite(sa) ? sa : 101;
        const nb = Number.isFinite(sb) ? sb : 101;
        if (na !== nb) return na - nb;
        const oa = Number(a.overdue_count ?? 0);
        const ob = Number(b.overdue_count ?? 0);
        if (oa !== ob) return ob - oa;
        const ma = Number(a.missing_count ?? 0);
        const mb = Number(b.missing_count ?? 0);
        return mb - ma;
      })
      .slice(0, DASHBOARD_FOCUS_PROPERTY_LIMIT);
  }, [portfolioSummary?.properties]);

  const dashboardFreshness = useMemo(() => {
    if (commandCenter && typeof commandCenter === 'object' && commandCenter.freshness) return commandCenter.freshness;
    if (tasksDigest && typeof tasksDigest === 'object' && tasksDigest.freshness) return tasksDigest.freshness;
    return {};
  }, [commandCenter, tasksDigest]);

  /** Discoverability budget: avoid stacked billing CTAs + amber “nudge” when plan comparison strip already present. */
  const showPlanComparisonStrip = useMemo(
    () =>
      !!valueInsights &&
      !!valueInsights.plan_comparison?.next &&
      !valueInsights.upgrade_path?.at_highest_public_tier,
    [valueInsights],
  );
  const showUpgradeNudgeAlert = useMemo(
    () =>
      !!valueInsights &&
      (valueInsights.upgrade_nudge_reasons || []).length > 0 &&
      !valueInsights.upgrade_path?.at_highest_public_tier &&
      !showPlanComparisonStrip,
    [valueInsights, showPlanComparisonStrip],
  );


  if (loading && !data) {
    return (
      <PortalPageShell
        title="Dashboard"
        subtitle={workspaceDashboardWelcomeLead(data?.client?.name)}
        refreshing={dashboardRefreshing}
        testId="client-dashboard-loading"
      >
        <PortalSectionSkeleton rows={6} />
      </PortalPageShell>
    );
  }

  return (
    <TooltipProvider delayDuration={250}>
    <div className={portalPageRoot} data-testid="client-dashboard">
        <PortalStaleRefreshBanner refreshing={dashboardRefreshing} />
        <ErrorBanner message={error} onRetry={fetchDashboard} retryLabel="Retry" />

        <Dialog open={showJurisdictionOnboardingGate} modal>
          <DialogContent
            className="max-w-md [&>button.absolute]:hidden sm:max-w-lg"
            onPointerDownOutside={(e) => e.preventDefault()}
            onEscapeKeyDown={(e) => e.preventDefault()}
            data-testid="jurisdiction-onboarding-gate-dialog"
          >
            <DialogHeader>
              <DialogTitle className="text-midnight-blue">{JURISDICTION_ONBOARDING_GATE_TITLE}</DialogTitle>
              <DialogDescription asChild>
                <div className="text-left text-gray-600 space-y-3 text-sm">
                  <p>{JURISDICTION_ONBOARDING_GATE_LEAD}</p>
                  <p className="text-gray-800 font-medium">{JURISDICTION_ONBOARDING_GATE_CONSEQUENCE}</p>
                  <p className="text-gray-600">{JURISDICTION_ONBOARDING_GATE_CTA_HINT}</p>
                </div>
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-3 text-sm text-gray-700">
              <Button
                type="button"
                className="w-full bg-electric-teal hover:bg-electric-teal/90"
                onClick={() => navigate('/settings/jurisdiction?from=onboarding')}
              >
                {JURISDICTION_FALLBACK_CTA}
              </Button>
              <label className="flex items-start gap-3 cursor-pointer rounded-md border border-gray-200 p-3">
                <Checkbox
                  checked={jurisdictionAckConfirm}
                  onCheckedChange={(v) => setJurisdictionAckConfirm(v === true)}
                  className="mt-0.5"
                  data-testid="jurisdiction-fallback-ack-checkbox"
                />
                <span>{JURISDICTION_FALLBACK_ACK_CHECKBOX_LABEL}</span>
              </label>
            </div>
            <DialogFooter className="sm:justify-start">
              <Button
                type="button"
                variant="outline"
                disabled={!jurisdictionAckConfirm || jurisdictionAckSubmitting}
                onClick={submitJurisdictionFallbackAck}
                data-testid="jurisdiction-fallback-ack-submit"
              >
                {jurisdictionAckSubmitting ? 'Saving…' : JURISDICTION_FALLBACK_ACK_SUBMIT_LABEL}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {systemBanners.length > 0 && (
          <div className="mb-6 space-y-2">
            {systemBanners.map((b) => {
              const sev = (b.severity || 'info').toLowerCase();
              const bar =
                sev === 'critical'
                  ? 'border-red-300 bg-red-50 text-red-900'
                  : sev === 'warning'
                    ? 'border-amber-200 bg-amber-50 text-amber-900'
                    : 'border-slate-200 bg-slate-50 text-slate-900';
              return (
                <Alert key={b.banner_id} className={`${bar}`} data-testid={`system-banner-${b.banner_id}`}>
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <AlertDescription className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <span>
                      <span className="font-semibold block">{b.title}</span>
                      <span className="block text-sm mt-1 opacity-90">{b.message}</span>
                    </span>
                    {!b.persistent_display && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        onClick={() =>
                          clientAPI.dismissSystemBanner(b.banner_id).then(() => {
                            setSystemBanners((prev) => prev.filter((x) => x.banner_id !== b.banner_id));
                          })
                        }
                      >
                        Dismiss
                      </Button>
                    )}
                  </AlertDescription>
                </Alert>
              );
            })}
          </div>
        )}

        {/* Explicit "Access restricted by plan" UI (no blank screen) */}
        {restrictReason === 'plan' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-restricted-by-plan">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Access restricted by plan.</span>
              <span className="block mt-1 text-amber-800">This feature or area is not included in your current plan. Contact support or upgrade to access it.</span>
              <a href={`mailto:${SUPPORT_EMAIL}`} className="inline-block mt-2 text-sm font-medium text-electric-teal hover:underline">Contact support</a>
            </AlertDescription>
          </Alert>
        )}

        {/* Defensive: missing plan/entitlement (account not provisioned properly) */}
        {restrictReason === 'not_provisioned' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-not-provisioned">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Account not provisioned properly.</span>
              <span className="block mt-1 text-amber-800">Your account is missing plan or entitlement information. Please contact support to complete setup.</span>
              <a href={`mailto:${SUPPORT_EMAIL}`} className="inline-block mt-2 text-sm font-medium text-electric-teal hover:underline">Contact support</a>
            </AlertDescription>
          </Alert>
        )}

        {/* 403 Provisioning incomplete / Password not set — show next steps */}
        {restrictReason === 'provisioning_incomplete' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-provisioning-incomplete">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Not provisioned or action needed.</span>
              <span className="block mt-1 text-amber-800">{error || 'Complete onboarding or set your password to access the dashboard.'}</span>
              {redirectPath && (
                <Button
                  size="sm"
                  className="mt-3 bg-electric-teal hover:bg-electric-teal/90"
                  onClick={() => navigate(redirectPath)}
                >
                  Continue
                </Button>
              )}
              {!redirectPath && (
                <Button size="sm" className="mt-3 bg-electric-teal hover:bg-electric-teal/90" onClick={() => navigate('/onboarding-status')}>
                  Check onboarding status
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* First-login guided activation: Setup Checklist / Portfolio / Documents (server-driven when available) */}
        {setupView === 'checklist' && (
          <Card className="max-w-2xl mx-auto mt-8 border-2 border-electric-teal/30 shadow-lg" data-testid="setup-checklist-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-2xl text-midnight-blue">Welcome to Compliance Vault Pro</CardTitle>
              <p className="text-sm text-gray-600 mt-1">Complete these steps to get an accurate compliance overview. You can also skip and return later.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              {onboardingChecklist?.progress != null && onboardingChecklist.progress.total > 0 && (
                <div className="mb-2" data-testid="onboarding-progress-bar">
                  <div className="flex justify-between text-xs text-gray-600 mb-1">
                    <span>Your progress</span>
                    <span>
                      {onboardingChecklist.progress.completed}/{onboardingChecklist.progress.total} (
                      {onboardingChecklist.progress.percent}%)
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-electric-teal transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, onboardingChecklist.progress.percent))}%` }}
                    />
                  </div>
                </div>
              )}
              {onboardingChecklist?.next_step && (
                <p className="text-sm font-medium text-midnight-blue" data-testid="onboarding-next-step">
                  Next step: {onboardingChecklist.next_step.label}
                </p>
              )}
              {onboardingItemError && (
                <Alert className="border-red-200 bg-red-50" data-testid="onboarding-item-error">
                  <AlertDescription className="text-red-800 text-sm">{onboardingItemError}</AlertDescription>
                </Alert>
              )}
              {onboardingChecklist?.items?.length > 0 ? (
                <ul className="space-y-3 text-sm text-gray-700">
                  {onboardingChecklist.items.map((item) => (
                    <li key={item.id} className="p-2 rounded-lg bg-gray-50 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 flex-1 min-w-0">
                          {item.completed_at ? (
                            <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                          ) : (
                            <ClipboardCheck className="w-4 h-4 text-electric-teal shrink-0" />
                          )}
                          <span className={item.completed_at ? 'text-gray-500 line-through' : 'font-medium text-midnight-blue'}>
                            {item.label}
                          </span>
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          {!item.completed_at && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  const base = item.deep_link || '/properties';
                                  const extra =
                                    item.id === 'set_jurisdictions' && setupView === 'checklist'
                                      ? `${base.includes('?') ? '&' : '?'}from=onboarding`
                                      : '';
                                  navigate(`${base}${extra}`);
                                }}
                              >
                                Go
                              </Button>
                              <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => completeOnboardingItem(item.id)} disabled={completingItemId === item.id}>
                                {completingItemId === item.id ? '…' : 'Mark done'}
                              </Button>
                            </>
                          )}
                        </span>
                      </div>
                      {item.id === 'set_jurisdictions' && !item.completed_at ? (
                        <div className="pl-6 sm:pl-8 border-l-2 border-electric-teal/40 text-xs text-gray-700 space-y-1.5">
                          <p className="font-medium text-gray-900">Core compliance configuration</p>
                          <p>{JURISDICTION_IMPACT_INTRO}</p>
                          <p className="text-gray-600">{JURISDICTION_SCOPE_GLOBAL}</p>
                          <p className="text-amber-900/90 bg-amber-50/80 border border-amber-200/80 rounded-md px-2 py-1.5">
                            {JURISDICTION_CHECKLIST_SET_JURISDICTIONS_NOTE}
                          </p>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-600">Setup steps will appear here when needed. You can go to Properties or Documents from the menu to get started.</p>
              )}
              <div className="flex flex-wrap gap-3 pt-4">
                <Button onClick={() => setSetupView('portfolio')} className="bg-electric-teal hover:bg-electric-teal/90" data-testid="setup-start-btn">
                  {onboardingChecklist?.items?.length ? 'Continue' : 'Start Setup'}
                </Button>
                <Button variant="outline" onClick={() => dismissSetupChecklist(true)} data-testid="setup-skip-btn">
                  Skip for now
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {setupView === 'portfolio' && (
          <Card className="max-w-2xl mx-auto mt-8 border-2 border-electric-teal/30 shadow-lg" data-testid="setup-portfolio-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-xl text-midnight-blue">Confirm your portfolio</CardTitle>
              <p className="text-sm text-gray-600 mt-1">Review your properties from intake. You can edit details from the Properties page later.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              {data?.properties?.length > 0 ? (
                <ul className="space-y-2 text-sm">
                  {data.properties.map((p) => {
                    const displayName = p.nickname || p.address_line_1 || (p.address_line_1 && p.city ? `${p.address_line_1}, ${p.city}` : null) || (p.postcode ? `Property ${p.postcode}` : null) || p.property_id;
                    return (
                      <li key={p.property_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <span className="font-medium text-midnight-blue">{displayName}</span>
                          {(p.effective_jurisdiction_label || p.jurisdiction_source) && (
                            <p className="text-xs text-gray-500 mt-1">
                              {p.effective_jurisdiction_label ? `Jurisdiction: ${p.effective_jurisdiction_label}` : 'Jurisdiction: —'}
                              {p.jurisdiction_source ? ` · Source: ${jurisdictionSourceLabel(p.jurisdiction_source)}` : ''}
                            </p>
                          )}
                        </div>
                        <span className="text-gray-500 text-xs">{p.property_type || '—'}{p.bedrooms != null ? ` · ${p.bedrooms} bed` : ''}</span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-gray-600 text-sm">No properties yet. Add one from the Properties page after setup.</p>
              )}
              <div className="flex flex-wrap gap-3 pt-4">
                <Button onClick={() => navigate('/properties')} variant="outline" size="sm">Edit properties</Button>
                <Button onClick={() => needsDocumentsStep ? setSetupView('documents') : completeSetupFlow()} className="bg-electric-teal hover:bg-electric-teal/90" data-testid="setup-portfolio-continue-btn">
                  Save &amp; Continue
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setSetupView('checklist')}>Back</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {setupView === 'documents' && (
          <Card className="max-w-2xl mx-auto mt-8 border-2 border-electric-teal/30 shadow-lg" data-testid="setup-documents-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-xl text-midnight-blue">Upload certificates for an accurate score</CardTitle>
              <p className="text-sm text-gray-600 mt-1">You&apos;re almost done. Upload your certificates so we can track expiry dates. Use &quot;tracked items&quot; language — these may apply depending on your situation.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              {requirementsList.filter((r) => (r.applicability === 'REQUIRED' || (r.applicability || 'UNKNOWN') === 'UNKNOWN') && !r.confirmed_expiry_date).length > 0 && (
                <div className="text-sm text-gray-700">
                  <p className="font-medium mb-2">Tracked items that may need documents:</p>
                  <ul className="list-disc pl-5 space-y-1">
                    {requirementsList.filter((r) => (r.applicability === 'REQUIRED' || (r.applicability || 'UNKNOWN') === 'UNKNOWN') && !r.confirmed_expiry_date).slice(0, 8).map((r) => (
                      <li key={r.requirement_id}>{r.requirement_type || r.requirement_id}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-3 pt-4">
                <Button onClick={() => { completeSetupFlow(); navigate('/documents'); }} className="bg-electric-teal hover:bg-electric-teal/90" data-testid="setup-upload-now-btn">
                  Upload now
                </Button>
                <Button variant="outline" onClick={() => dismissSetupChecklist(true)} data-testid="setup-upload-later-btn">
                  I&apos;ll upload later
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setSetupView('portfolio')}>Back</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main dashboard (hidden when in setup flow) */}
        {!setupView && (
        <>
        {/* Server-driven "Complete setup" banner when checklist is not completed (deep-links to each incomplete item) */}
        {onboardingChecklist && !onboardingChecklist.completed_at && (onboardingChecklist.items?.length > 0) && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="setup-incomplete-banner">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-800">Complete setup to get an accurate score.</span>
              <span className="text-amber-700 ml-1">Finish these steps so your compliance overview is accurate.</span>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button
                  size="sm"
                  className="bg-amber-600 hover:bg-amber-700 text-white"
                  onClick={showChecklistView}
                >
                  Complete setup
                </Button>
                {onboardingChecklist.items.filter((i) => !i.completed_at).map((item) => (
                  <Button
                    key={item.id}
                    variant="outline"
                    size="sm"
                    className="border-amber-300 text-amber-800 hover:bg-amber-100"
                    onClick={() => {
                      const base = item.deep_link || '/properties';
                      const extra =
                        item.id === 'set_jurisdictions' ? `${base.includes('?') ? '&' : '?'}from=onboarding` : '';
                      navigate(`${base}${extra}`);
                    }}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </AlertDescription>
          </Alert>
        )}
        {/* Fallback: persistent banner when user skipped setup (sessionStorage) and server checklist not incomplete */}
        {!onboardingChecklist?.completed_at && !(onboardingChecklist?.items?.length > 0) && setupChecklistSeen && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="setup-incomplete-banner">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-800">Complete setup to get an accurate score.</span>
              <span className="text-amber-700 ml-1">Confirm portfolio details and upload or confirm certificate dates for tracked items.</span>
              {documentsAwaitingConfirmationCount > 0 && (
                <span className="block mt-2 text-amber-700 text-sm">{documentsAwaitingConfirmationCount} document{documentsAwaitingConfirmationCount !== 1 ? 's' : ''} awaiting confirmation.</span>
              )}
              <Button variant="outline" size="sm" className="mt-2 border-amber-300 text-amber-800 hover:bg-amber-100" onClick={() => navigate('/documents')}>
                Go to Documents
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Documents awaiting confirmation (any user who has uploads but not yet confirmed expiry) */}
        {documentsAwaitingConfirmationCount > 0 && (
          <Alert className="mb-6 border-blue-200 bg-blue-50" data-testid="documents-awaiting-confirmation-banner">
            <Info className="h-4 w-4 text-blue-600" />
            <AlertDescription>
              <span className="font-medium text-blue-800">{documentsAwaitingConfirmationCount} document{documentsAwaitingConfirmationCount !== 1 ? 's' : ''} awaiting confirmation.</span>
              <span className="text-blue-700 ml-1">Confirm certificate details so your score and calendar are up to date.</span>
              <Button variant="outline" size="sm" className="mt-2 border-blue-300 text-blue-800 hover:bg-blue-100" onClick={() => navigate('/documents')}>
                Review documents
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Welcome – executive overview */}
        <div className="mb-5 sm:mb-6">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-2">Dashboard</h2>
          <p className="text-gray-600 text-sm sm:text-base">
            {workspaceDashboardWelcomeLead(data?.client?.full_name)}
          </p>
          <p className="text-xs text-gray-500 mt-1.5">
            Work in order in <span className="font-medium text-midnight-blue">Today</span> or{' '}
            <span className="font-medium text-midnight-blue">Command Center</span>. Not legal advice.
          </p>
        </div>

        {/* ZONE 1 — Operational overview: headline KPIs + freshness metadata */}
        {(displayScoreInfo || complianceScore || portfolioSummary) && (
          <div
            className={`mb-5 rounded-xl border px-3 py-3 sm:px-4 flex flex-col gap-2 ${
              dashboardScoreFreshness.isPartialOrStale && dashboardScoreFreshness.explanation
                ? 'bg-amber-50/50 border-amber-200'
                : 'bg-gray-50 border-gray-200'
            }`}
            data-testid="dashboard-top-strip"
          >
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-midnight-blue">{portfolioHeadlineUi.display}</span>
                {portfolioHeadlineUi.showOutOf100 ? <span className="text-gray-500">/100</span> : null}
                <span
                  className={`ml-1 text-lg font-semibold ${
                    displayScoreInfo?.color === 'green'
                      ? 'text-green-600'
                      : displayScoreInfo?.color === 'amber'
                        ? 'text-amber-600'
                        : displayScoreInfo?.color === 'red'
                          ? 'text-red-600'
                          : 'text-gray-600'
                  }`}
                >
                  Grade {formatDashboardGrade(displayScoreInfo?.grade ?? complianceScore?.grade)}
                </span>
              </div>
              <span className="text-sm text-gray-600">
                {formatRiskLabel(portfolioSummary?.risk_level) || displayScoreInfo?.message || complianceScore?.message || KPI_NO_DATA}
              </span>
              {portfolioSummary?.updated_at && (
                <span className="text-xs text-gray-500">Updated {new Date(portfolioSummary.updated_at).toLocaleString()}</span>
              )}
              {(portfolioSummary?.properties?.length != null || complianceScore?.properties_count != null) && (
                <span className="text-xs text-gray-500">
                  {portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0} propert
                  {(portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0) === 1 ? 'y' : 'ies'}
                </span>
              )}
            </div>
            {dashboardScoreFreshness.hasAny ? (
              <div
                className={`rounded-md px-2 py-1.5 text-xs ${
                  dashboardScoreFreshness.isPartialOrStale && dashboardScoreFreshness.explanation
                    ? 'border border-amber-200 bg-amber-50 text-amber-950'
                    : 'border border-gray-200 bg-slate-50 text-gray-800'
                }`}
                data-testid="dashboard-score-freshness"
              >
                {dashboardScoreFreshness.explanation ? (
                  <p className="leading-snug" data-testid="dashboard-score-freshness-explanation">
                    {dashboardScoreFreshness.explanation}
                  </p>
                ) : null}
                {dashboardScoreFreshness.lastCalculatedLine ? (
                  <p
                    className={`leading-snug text-gray-700 ${dashboardScoreFreshness.explanation ? 'mt-1.5' : ''}`}
                    data-testid="dashboard-score-freshness-last-calculated"
                  >
                    {dashboardScoreFreshness.lastCalculatedLine}
                  </p>
                ) : null}
              </div>
            ) : null}
            {portfolioRecalcPendingLine ? (
              <p
                className="text-xs text-slate-800 leading-snug border-t border-slate-200/80 pt-2 mt-0.5"
                data-testid="dashboard-score-recalc-pending"
              >
                {portfolioRecalcPendingLine}
              </p>
            ) : null}
            {(dashboardFreshness?.score_updated_at ||
              dashboardFreshness?.risk_signals_updated_at ||
              dashboardFreshness?.last_automation_score_recalc_at ||
              dashboardFreshness?.last_automation_risk_refresh_at) && (
              <div
                className="w-full border-t border-gray-200 pt-2 mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500"
                data-testid="dashboard-freshness-strip"
              >
                {dashboardFreshness.score_updated_at ? (
                  <span>
                    Last score data: {new Date(dashboardFreshness.score_updated_at).toLocaleString()}
                    {isTimestampStale(dashboardFreshness.score_updated_at, FRESH_SCORE_STALE_HOURS) ? (
                      <span className="ml-1 text-amber-700">(may be outdated)</span>
                    ) : null}
                  </span>
                ) : null}
                {dashboardFreshness.risk_signals_updated_at ? (
                  <span>
                    Risk refresh: {new Date(dashboardFreshness.risk_signals_updated_at).toLocaleString()}
                    {isTimestampStale(dashboardFreshness.risk_signals_updated_at, FRESH_RISK_STALE_HOURS) ? (
                      <span className="ml-1 text-amber-700">(may be outdated)</span>
                    ) : null}
                  </span>
                ) : null}
                {dashboardFreshness.last_automation_score_recalc_at ? (
                  <span>Auto score recalc: {new Date(dashboardFreshness.last_automation_score_recalc_at).toLocaleString()}</span>
                ) : null}
                {dashboardFreshness.last_automation_risk_refresh_at ? (
                  <span>Auto risk refresh: {new Date(dashboardFreshness.last_automation_risk_refresh_at).toLocaleString()}</span>
                ) : null}
              </div>
            )}
          </div>
        )}

        {/* ZONE 1 — Executive KPI row */}
        {!setupView && (
          <div className="mb-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3" data-testid="executive-kpi-row">
            <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/today')}>
              <CardContent className="p-3 sm:p-4 min-w-0">
                <p className="text-xs text-gray-500 uppercase tracking-wide flex items-center">
                  Today (inbox)
                  <DashboardKpiHint label="Today inbox total">
                    Sum of urgent, upcoming, and in-progress items from the same Today inbox as the Today page, after the same
                    tracked-requirement filter. Snoozed and hidden are separate buckets below. If this fails to load, open Today for
                    live counts.
                  </DashboardKpiHint>
                </p>
                {tasksDigest === undefined || todayInboxPayload === undefined ? (
                  <p className="text-xl font-bold text-midnight-blue mt-1">…</p>
                ) : tasksDigest === null ? (
                  <>
                    <p className="text-xl font-bold text-gray-500 mt-1">{KPI_NO_DATA}</p>
                    <p className="text-xs text-gray-500 mt-1">Could not load inbox summary.</p>
                  </>
                ) : todayInboxPayload === null ? (
                  <>
                    <p className="text-xl font-bold text-gray-500 mt-1">{KPI_NO_DATA}</p>
                    <p className="text-xs text-gray-500 mt-1">Could not load Today buckets.</p>
                  </>
                ) : (
                  <>
                    <p className="text-xl font-bold text-midnight-blue mt-1">{todayInboxSum ?? 0}</p>
                    {todayInboxSum === 0 && (
                      <p className="text-xs text-gray-500 mt-1">Nothing in those buckets in this snapshot.</p>
                    )}
                  </>
                )}
                <p className="text-xs text-electric-teal mt-1">Continue in Today →</p>
              </CardContent>
            </Card>
            <Card className="hidden sm:block cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/compliance-score')}>
              <CardContent className="p-3 sm:p-4 min-w-0">
                <p className="text-xs text-gray-500 uppercase tracking-wide flex items-center">
                  Portfolio compliance
                  <DashboardKpiHint label="Portfolio compliance score">
                    Document-backed portfolio score (0–100) from your latest compliance calculation. Updates when requirements, documents,
                    or related jobs change. Same metric as the Compliance score page — not a legal certification.
                  </DashboardKpiHint>
                </p>
                <p className="text-xl font-bold text-midnight-blue">{portfolioHeadlineUi.display}</p>
              </CardContent>
            </Card>
            {hasFeature('maintenance_workflows') && (
              <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/operations/issues')}>
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Open issues</p>
                  <p className="text-xl font-bold text-midnight-blue">
                    {openIssuesKpiLoading ? '…' : openIssuesCount == null ? KPI_NO_DATA : openIssuesCount}
                  </p>
                </CardContent>
              </Card>
            )}
            {hasFeature('maintenance_workflows') && (
              <Card
                className="cursor-pointer hover:shadow-md transition-shadow min-w-0"
                title="Jobs where the agreed response time has passed (current list, up to 500 loaded)."
                onClick={() => navigate('/operations/work-orders?sla_state=breached')}
              >
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Jobs · {slaStateLabel('breached')}</p>
                  <p className="text-xl font-bold text-midnight-blue">{slaBreachedCount}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {slaStateLabel('near_breach')}: {slaNearBreachCount}
                  </p>
                </CardContent>
              </Card>
            )}
            {hasFeature('predictive_maintenance') && (
              <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/operations/risk-signals')}>
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide flex items-center">
                    Risk signals
                    <DashboardKpiHint label="Active risk signals count">
                      Open predictive risk signals for your portfolio (active status). Matches the security snapshot when loaded.
                      Resolved or dismissed signals are excluded. Open the list for detail — not every item needs immediate work.
                      Acknowledging or dismissing a signal does not clear compliance obligations by itself.
                    </DashboardKpiHint>
                  </p>
                  <p className="text-xl font-bold text-midnight-blue">{riskSignalsCount}</p>
                </CardContent>
              </Card>
            )}
            {hasFeature('invoicing') && maintenanceSpendMonth && maintenanceSpendMonth.has_any_invoices && (
              <Card
                className="cursor-pointer hover:shadow-md transition-shadow min-w-0"
                title={maintenanceSpendMonth.calculation_summary || 'Paid contractor invoices this UTC month.'}
                onClick={() => navigate('/operations/approvals')}
              >
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Maintenance spend (month)</p>
                  <p className="text-xl font-bold text-midnight-blue">
                    {new Intl.NumberFormat('en-GB', { style: 'currency', currency: maintenanceSpendMonth.currency || 'GBP' }).format(
                      Number(maintenanceSpendMonth.total_amount ?? 0),
                    )}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Paid invoices · UTC month</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* ZONE 2 — Portfolio intelligence: impact snapshot (compact KPIs) */}
        {valueInsights && (
          <div
            className="mb-6 rounded-xl border border-slate-200 bg-white p-3 sm:p-4 shadow-sm"
            data-testid="value-insights-strip"
          >
            <h3 className="text-sm font-semibold text-midnight-blue mb-3">Your impact</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5">
                <p className="text-[11px] text-gray-500 uppercase tracking-wide flex items-center gap-1">
                  Achieved
                  <DashboardKpiHint label="About achievements">
                    Counts from your live account: compliant requirements, documents stored, and maintenance jobs completed in the last 30 days.
                    They update as you record activity — zeros mean nothing yet in that window, not a broken metric.
                  </DashboardKpiHint>
                </p>
                <p className="text-2xl font-bold text-midnight-blue tabular-nums mt-1">
                  {valueInsights.achievements?.requirements_compliant ?? 0}
                </p>
                <p className="text-xs text-gray-600 mt-0.5">Requirements compliant</p>
                <p className="text-2xl font-bold text-midnight-blue tabular-nums mt-2">
                  {valueInsights.achievements?.documents_on_file ?? 0}
                </p>
                <p className="text-xs text-gray-600 mt-0.5">Documents on file</p>
                <p className="text-2xl font-bold text-midnight-blue tabular-nums mt-2">
                  {valueInsights.achievements?.work_orders_completed_last_30_days ?? 0}
                </p>
                <p className="text-xs text-gray-600 mt-0.5">Jobs completed (30d)</p>
                {(valueInsights.achievements?.requirements_compliant ?? 0) === 0 &&
                  (valueInsights.achievements?.documents_on_file ?? 0) === 0 &&
                  (valueInsights.achievements?.work_orders_completed_last_30_days ?? 0) === 0 && (
                    <p className="text-[11px] text-gray-500 mt-2">No data in this window yet.</p>
                  )}
              </div>
              <div className="rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5">
                <p className="text-[11px] text-gray-500 uppercase tracking-wide flex items-center gap-1">
                  Needs attention
                  <DashboardKpiHint label="About attention counts">
                    From current compliance and your unified task inbox: overdue and expiring-soon requirements, plus open urgent items.
                    Excludes snoozed or hidden tasks.
                  </DashboardKpiHint>
                </p>
                <p className="text-2xl font-bold text-amber-800 tabular-nums mt-1">{valueInsights.at_risk?.overdue_requirements ?? 0}</p>
                <p className="text-xs text-gray-600 mt-0.5">Overdue requirements</p>
                <p className="text-2xl font-bold text-amber-800 tabular-nums mt-2">{valueInsights.at_risk?.expiring_soon_requirements ?? 0}</p>
                <p className="text-xs text-gray-600 mt-0.5">Expiring soon</p>
                <p className="text-2xl font-bold text-midnight-blue tabular-nums mt-2">{valueInsights.at_risk?.command_centre_urgent_open ?? 0}</p>
                <p className="text-xs text-gray-600 mt-0.5">Urgent inbox items</p>
              </div>
              <div className="rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5">
                <p className="text-[11px] text-gray-500 uppercase tracking-wide">Next tier</p>
                {valueInsights.upgrade_path?.at_highest_public_tier ? (
                  <p className="text-sm text-gray-700 mt-2">Top public tier for published limits.</p>
                ) : (
                  <>
                    <ul className="mt-2 text-xs text-gray-700 space-y-1 list-disc pl-4 max-h-28 overflow-y-auto">
                      {(valueInsights.upgrade_path?.unlocks_on_next_tier || []).slice(0, 5).map((u) => (
                        <li key={u}>{u}</li>
                      ))}
                    </ul>
                    {valueInsights.show_upgrade_for_property_cap && !showPlanComparisonStrip ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-3 w-full sm:w-auto"
                        onClick={() => navigate('/billing')}
                        data-testid="value-insights-upgrade-cta"
                      >
                        Compare capacity in Billing
                      </Button>
                    ) : null}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {valueInsights?.plan_comparison?.next && !valueInsights.upgrade_path?.at_highest_public_tier && (
          <div
            className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            data-testid="plan-comparison-strip"
          >
            <h3 className="text-sm font-semibold text-midnight-blue mb-3">Your plan vs next tier</h3>
            <div className="grid sm:grid-cols-2 gap-4 text-sm">
              <div className="border border-gray-100 rounded-lg p-3">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Current</p>
                <p className="font-semibold text-gray-900 mt-1">{valueInsights.plan_comparison.current?.display_name || valueInsights.plan}</p>
                <p className="text-gray-600 mt-1">
                  Property cap: {valueInsights.plan_comparison.current?.max_properties ?? valueInsights.max_properties ?? '—'}
                </p>
              </div>
              <div className="border border-electric-teal/50 rounded-lg p-3 bg-teal-50/40">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Next</p>
                <p className="font-semibold text-midnight-blue mt-1">{valueInsights.plan_comparison.next?.display_name}</p>
                <p className="text-gray-700 mt-1">
                  Property cap: {valueInsights.plan_comparison.next?.max_properties ?? '—'}
                </p>
                {valueInsights.plan_comparison.immediate_benefit_line && (
                  <p className="text-gray-800 mt-2 font-medium">{valueInsights.plan_comparison.immediate_benefit_line}</p>
                )}
                {(valueInsights.plan_comparison.you_get_on_next_tier || []).length > 0 && (
                  <ul className="mt-2 text-gray-700 space-y-1 list-disc pl-4">
                    {(valueInsights.plan_comparison.you_get_on_next_tier || []).slice(0, 6).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              className="mt-4 border-slate-200 text-midnight-blue hover:bg-slate-50"
              size="sm"
              onClick={() => navigate('/settings/billing')}
            >
              View plans in Billing
            </Button>
          </div>
        )}

        {showUpgradeNudgeAlert && (
            <Alert className="mb-6 border-slate-200 bg-slate-50" data-testid="upgrade-nudge-contextual">
              <Info className="h-4 w-4 text-midnight-blue shrink-0" />
              <AlertDescription>
                <span className="font-medium text-midnight-blue">When your operations scale</span>
                <ul className="mt-2 space-y-2 text-sm text-slate-700 list-disc pl-4">
                  {(valueInsights.upgrade_nudge_reasons || []).map((r) => (
                    <li key={r.code}>
                      <span className="font-medium text-midnight-blue">{r.headline}</span>
                      <span className="mt-0.5 block text-slate-600">{r.why_now}</span>
                    </li>
                  ))}
                </ul>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3 border-slate-200 text-midnight-blue hover:bg-slate-100"
                  onClick={() => navigate('/settings/billing')}
                >
                  Review plans and limits
                </Button>
              </AlertDescription>
            </Alert>
          )}

        {!setupView && tasksDigest && typeof tasksDigest === 'object' && (() => {
          const cc = commandCenter && typeof commandCenter === 'object' ? commandCenter : null;
          const inboxReady = todayInboxPayload !== undefined && todayInboxPayload !== null;
          const urgentN = inboxReady ? dashboardAlignedInboxSections.urgent.length : null;
          const upN = inboxReady ? dashboardAlignedInboxSections.upcoming.length : null;
          const ipN = inboxReady ? dashboardAlignedInboxSections.in_progress.length : null;
          const snoozedN = inboxReady ? dashboardAlignedInboxSections.snoozed.length : null;
          const hiddenN = inboxReady ? dashboardAlignedInboxSections.hidden.length : null;
          const queueN = inboxReady ? dashboardAlignedInboxSections.urgent.length : 0;
          const riskN = hasFeature('predictive_maintenance') ? (cc?.upcoming_risks?.length ?? 0) : 0;
          const n = (v) => (v === null ? '…' : v);
          return (
          <Card
            className="mb-6 border border-gray-200 shadow-sm"
            data-testid="tasks-digest-card"
          >
            <CardHeader className="pb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
              <div className="min-w-0">
                <CardTitle className="text-base flex items-center gap-2 break-words">
                  <ListTodo className="w-4 h-4 text-teal-600 shrink-0" />
                  Inbox snapshot
                </CardTitle>
                <p className="text-xs text-gray-600 mt-1 break-words">
                  Counts only — prioritisation and execution stay in{' '}
                  <span className="font-medium text-midnight-blue">Command Center</span> and{' '}
                  <span className="font-medium text-midnight-blue">Today</span>.
                </p>
                {(tasksDigest.freshness?.tasks_refreshed_at || cc?.freshness?.tasks_refreshed_at) && (
                  <p className="text-xs text-gray-500 mt-1 break-words">
                    Refreshed{' '}
                    {new Date(
                      tasksDigest.freshness?.tasks_refreshed_at || cc?.freshness?.tasks_refreshed_at,
                    ).toLocaleString()}
                  </p>
                )}
                {commandCenterScopeLabel && (
                  <p className="text-xs text-electric-teal mt-1 break-words">Scoped to: {commandCenterScopeLabel}</p>
                )}
              </div>
              <div className="flex flex-col sm:flex-row flex-wrap gap-2 w-full sm:w-auto shrink-0">
                <Button
                  type="button"
                  size="sm"
                  className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0 bg-midnight-blue hover:bg-midnight-blue/90 text-white inline-flex items-center justify-center gap-2"
                  onClick={() => navigate('/command-center')}
                  data-testid="dashboard-open-command-center"
                >
                  <Gauge className="w-4 h-4 shrink-0" aria-hidden />
                  Open Command Center
                </Button>
                <Button variant="outline" size="sm" className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0" onClick={() => navigate('/today')}>
                  Today
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0"
                  onClick={() => navigate('/work-queue')}
                  data-testid="dashboard-link-work-queue"
                >
                  Work queue
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3 text-sm text-gray-800 space-y-1.5">
                <p>
                  <span className="font-semibold text-midnight-blue">Buckets: </span>
                  Urgent {n(urgentN)} · Upcoming {n(upN)} · In progress {n(ipN)} · Snoozed {n(snoozedN)} · Hidden {n(hiddenN)}
                </p>
                {todayInboxPayload === null ? (
                  <p className="text-xs text-amber-800">Today inbox could not be loaded — open Today for bucket counts.</p>
                ) : null}
                {cc ? (
                  <p className="text-xs text-gray-700">
                    <span className="font-medium text-midnight-blue">This snapshot: </span>
                    {queueN} prioritised row{queueN === 1 ? '' : 's'}
                    {hasFeature('predictive_maintenance') && riskN > 0
                      ? ` · ${riskN} risk signal${riskN === 1 ? '' : 's'} preview`
                      : ''}
                    . <span className="text-gray-600">Use Command Center to work the queue in order.</span>
                  </p>
                ) : null}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-auto py-1.5 px-0 text-electric-teal hover:text-midnight-blue hover:bg-transparent font-medium"
                onClick={() => setDashboardInboxExpanded((v) => !v)}
                aria-expanded={dashboardInboxExpanded}
                data-testid="dashboard-inbox-expand-toggle"
              >
                {dashboardInboxExpanded ? (
                  <>
                    <ChevronUp className="w-4 h-4 inline-block mr-1 align-middle" aria-hidden />
                    Hide breakdown &amp; activity
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4 inline-block mr-1 align-middle" aria-hidden />
                    Show breakdown &amp; activity
                  </>
                )}
              </Button>
              {dashboardInboxExpanded && (
                <div className="space-y-4 pt-1 border-t border-gray-100">
                  <p className="sm:hidden text-sm text-gray-700 font-medium pt-3">
                    Urgent {n(urgentN)} · Upcoming {n(upN)} · In progress {n(ipN)}
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3 text-sm">
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Urgent</p>
                      <p className="text-lg font-semibold text-midnight-blue">{n(urgentN)}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Upcoming</p>
                      <p className="text-lg font-semibold text-midnight-blue">{n(upN)}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">In progress</p>
                      <p className="text-lg font-semibold text-midnight-blue">{n(ipN)}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Snoozed</p>
                      <p className="text-lg font-semibold text-midnight-blue">{n(snoozedN)}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Hidden</p>
                      <p className="text-lg font-semibold text-midnight-blue">{n(hiddenN)}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Acknowledged (7d)</p>
                      <p className="text-lg font-semibold text-midnight-blue">
                        {tasksDigest.summary?.habit?.tasks_acknowledged_last_7_days ?? 0}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Due / expiring in 7d: {tasksDigest.summary?.habit?.items_due_or_expiring_in_7_days ?? 0}
                      </p>
                    </div>
                  </div>
                  {(tasksDigest.activity_feed?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Recent inbox activity</p>
                      <ul className="space-y-1.5 text-sm text-gray-700">
                        {tasksDigest.activity_feed.map((row) => (
                          <li key={row.event_id || `${row.task_id}-${row.created_at}`} className="flex gap-2">
                            <span className="text-gray-400 shrink-0 tabular-nums">
                              {row.created_at ? new Date(row.created_at).toLocaleString() : ''}
                            </span>
                            <span className="min-w-0">{formatTaskDigestActivityLine(row)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {inboxReady && dashboardAlignedInboxSections.urgent.length > 0 && (
                    <div className="rounded-xl border border-red-100 bg-red-50/40 p-3 sm:p-4" data-testid="command-center-snapshot-card">
                      <p className="text-xs font-semibold text-red-900 uppercase tracking-wide mb-2">Urgent queue (preview)</p>
                      <ul className="space-y-2 text-sm">
                        {dashboardAlignedInboxSections.urgent.slice(0, 6).map((t) => (
                          <li key={t.id || t.title} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                            <button
                              type="button"
                              className="text-left text-midnight-blue hover:underline font-medium min-w-0 break-words"
                              onClick={() => {
                                const cta = resolveTaskCta(t, 'primary');
                                if (cta.guidedEvidence) {
                                  openGuidedEvidence({
                                    propertyId: cta.guidedEvidence.propertyId,
                                    requirementId: cta.guidedEvidence.requirementId,
                                    initialEvidenceMode: cta.guidedEvidence.initialEvidenceMode || undefined,
                                  });
                                  return;
                                }
                                const url = cta.route || t.primary_action_url || t.cta_url;
                                if (url && url.startsWith('/')) {
                                  const target = resolveClientPortalPath(url, '/today');
                                  recordClientPortalInteraction('command_center_urgent_task', { task_id: t.id, target });
                                  navigate(target);
                                } else if (url) window.location.assign(url);
                                else navigate('/today');
                              }}
                            >
                              {t.title || 'Task'}
                            </button>
                            <span className="text-xs text-gray-500 shrink-0 break-words sm:text-right sm:max-w-[40%]">
                              {[t.property_label, t.timing_label || t.urgency_level].filter(Boolean).join(' · ')}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {cc && hasFeature('predictive_maintenance') && (cc.upcoming_risks?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Risk signals (preview)</p>
                      <ul className="space-y-2 text-sm">
                        {cc.upcoming_risks.slice(0, 4).map((r) => (
                          <li key={r.signal_id || r.description} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                            <button
                              type="button"
                              className="text-left text-midnight-blue hover:underline min-w-0 break-words"
                              onClick={() => {
                                const target = resolveClientPortalPath(r.cta_url, '/operations/risk-signals');
                                recordClientPortalInteraction('command_center_risk_cta', { target });
                                navigate(target);
                              }}
                            >
                              {r.description || r.risk_type_label_client || riskTypeLabelClient(r.risk_type) || 'Issue'}
                            </button>
                            <span className="text-xs text-gray-500 shrink-0">{formatRiskLabel(r.risk_level)}</span>
                          </li>
                        ))}
                      </ul>
                      <Button variant="link" className="h-auto p-0 mt-1 text-electric-teal" onClick={() => navigate('/operations/risk-signals')}>
                        View all risk signals
                      </Button>
                    </div>
                  )}
                  {cc && cc.compliance_status_summary && (cc.compliance_status_summary.score != null || cc.compliance_status_summary.score_status) && (
                    <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3 text-sm">
                      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Compliance (snapshot)</p>
                      <p className="font-semibold text-midnight-blue">
                        Grade {formatDashboardGrade(cc.compliance_status_summary.grade)} · Score{' '}
                        {headlineScoreDisplayForDashboard(
                          cc.compliance_status_summary.score,
                          cc.compliance_status_summary.score_status
                        )}
                      </p>
                      {cc.compliance_status_summary.score_status && (
                        <p className="text-xs text-gray-600 mt-1">
                          Status: {cc.compliance_status_summary.score_status}
                          {cc.compliance_status_summary.last_calculated_at
                            ? ` · Last calculated ${new Date(cc.compliance_status_summary.last_calculated_at).toLocaleString()}`
                            : ''}
                        </p>
                      )}
                      {cc.compliance_status_summary.message && (
                        <p className="text-gray-600 mt-1">{cc.compliance_status_summary.message}</p>
                      )}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-600">
                        {cc.compliance_status_summary.requirements_overdue != null && (
                          <span>Overdue: {cc.compliance_status_summary.requirements_overdue}</span>
                        )}
                        {cc.compliance_status_summary.requirements_expiring_soon != null && (
                          <span>Expiring soon: {cc.compliance_status_summary.requirements_expiring_soon}</span>
                        )}
                      </div>
                    </div>
                  )}
                  {cc &&
                    inboxReady &&
                    dashboardAlignedInboxSections.urgent.length === 0 &&
                    (!hasFeature('predictive_maintenance') || (cc.upcoming_risks?.length ?? 0) === 0) &&
                    !(
                      cc.compliance_status_summary &&
                      (cc.compliance_status_summary.score != null || cc.compliance_status_summary.score_status)
                    ) && (
                      <p className="text-sm text-gray-500">No priority rows in this snapshot — open Command Center or Today for the full inbox.</p>
                    )}
                </div>
              )}
            </CardContent>
          </Card>
          );
        })()}

        {/* ZONE 3 — Subscription, security/continuity, activity since last visit (single disclosure; default closed) */}
        {!setupView && isClientUser && (
          <Collapsible
            open={dashboardSystemInsightsOpen}
            onOpenChange={setDashboardSystemInsightsOpen}
            className="mb-6 rounded-xl border border-slate-200 bg-white shadow-sm"
            data-testid="dashboard-system-insights-zone"
          >
            <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 rounded-xl px-4 py-3.5 text-left hover:bg-slate-50/80 min-h-[48px] [&[data-state=open]]:rounded-b-none">
              <div className="min-w-0 pr-2">
                <p className="text-sm font-semibold text-midnight-blue">System & activity insights</p>
                <p className="text-xs text-gray-500 mt-0.5 leading-snug">
                  Subscription value summary, security and continuity readout, and changes since your last acknowledged visit.
                </p>
              </div>
              <ChevronDown
                className={`h-5 w-5 shrink-0 text-gray-500 transition-transform duration-200 ${dashboardSystemInsightsOpen ? 'rotate-180' : ''}`}
                aria-hidden
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="border-t border-slate-100 px-3 pb-4 pt-3 sm:px-4 space-y-4">
              <Card
                className="border border-teal-100 bg-gradient-to-br from-teal-50/40 to-white shadow-sm"
                data-testid="dashboard-roi-summary"
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                    <TrendingUp className="h-4 w-4 text-teal-600 shrink-0" aria-hidden />
                    Value from your subscription
                    <DashboardKpiHint label="Value from subscription (full detail)">
                      Month-to-date style tallies from your account only. Compliance row counts requirements/items marked compliant in the
                      period (or current portfolio snapshot when the API falls back). Jobs on time = maintenance jobs closed before their SLA
                      deadline in the period. SLA clears = jobs that showed SLA pressure but finished without a recorded breach — descriptive
                      only, not attributed to a single action. Excludes other accounts. Updates when the value-summary endpoint runs; may lag
                      Today or Jobs by a few minutes. Not legal advice.
                    </DashboardKpiHint>
                  </CardTitle>
                  <p className="text-xs text-gray-500 font-normal mt-1">
                    Three concrete counts for this period — each line below says exactly what the number means.
                  </p>
                </CardHeader>
                <CardContent className="space-y-3">
                  {roiSummary === undefined && <p className="text-sm text-gray-500">Loading value summary…</p>}
                  {roiSummary === null && <p className="text-sm text-gray-600">Value summary is temporarily unavailable.</p>}
                  {roiSummary != null && (
                    <>
                      {(roiSummary.compliance_items_up_to_date ?? 0) === 0 &&
                        (roiSummary.jobs_completed_on_time ?? 0) === 0 &&
                        (roiSummary.sla_breaches_avoided ?? 0) === 0 &&
                        !roiSummary.unavailable && (
                          <p className="text-sm text-gray-700 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">
                            No outcomes recorded in this period yet — zeros are normal until you have compliant items and completed jobs in the
                            window.
                          </p>
                        )}
                      <p className="text-sm font-semibold text-midnight-blue">{roiSummary.period_label || 'This month'}</p>
                      <div className="grid sm:grid-cols-3 gap-4 text-sm">
                        <div className="rounded-lg border border-gray-100 bg-white p-3">
                          <p className="text-2xl font-bold text-midnight-blue tabular-nums">
                            {roiSummary.compliance_basis === 'unavailable' ? '—' : roiSummary.compliance_items_up_to_date ?? 0}
                          </p>
                          <p className="font-medium text-gray-900 mt-1">Up to date</p>
                          <p className="text-xs text-gray-600 mt-1 leading-snug">
                            Count of requirements (or certificate slots) counted as compliant in this period&apos;s tally — from the live
                            compliance engine, not a legal sign-off.
                            {roiSummary.compliance_basis === 'portfolio_snapshot'
                              ? ' This month uses your current compliant portfolio because nothing changed in-period (not strictly new activity).'
                              : roiSummary.compliance_basis === 'unavailable'
                                ? ' Compliance basis could not be loaded.'
                                : ''}
                          </p>
                        </div>
                        <div className="rounded-lg border border-gray-100 bg-white p-3">
                          <p className="text-2xl font-bold text-midnight-blue tabular-nums">{roiSummary.jobs_completed_on_time ?? 0}</p>
                          <p className="font-medium text-gray-900 mt-1">Jobs on time</p>
                          <p className="text-xs text-gray-600 mt-1 leading-snug">
                            Maintenance jobs completed before their response or completion SLA in this period. Missed or open jobs are not
                            counted here.
                          </p>
                        </div>
                        <div className="rounded-lg border border-gray-100 bg-white p-3">
                          <p className="text-2xl font-bold text-midnight-blue tabular-nums">{roiSummary.sla_breaches_avoided ?? 0}</p>
                          <p className="font-medium text-gray-900 mt-1">SLA pressure cleared</p>
                          <p className="text-xs text-gray-600 mt-1 leading-snug">
                            Jobs that had an SLA near-breach signal, then finished without a recorded breach and within the deadline — a
                            descriptive count only; we do not claim which action &quot;caused&quot; the outcome.
                          </p>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500">
                        Loaded separately from the rest of the dashboard for speed; figures are approximate for the labelled period.
                      </p>
                      {roiSummary.unavailable && (
                        <p className="text-xs text-amber-800">Some underlying data could not be fully loaded.</p>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>

              {(protectionSnapshotLoading || protectionSnapshot) && (
                <Card className="border border-gray-200 shadow-sm" data-testid="protection-snapshot-card">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Shield className="w-4 h-4 text-teal-600" />
                      Security & continuity snapshot
                    </CardTitle>
                    <p className="text-xs text-gray-500 mt-1">
                      Read-only summary of sign-in activity, requirement counts, maintenance issues, and open predictive risk signals. Not legal advice.
                    </p>
                  </CardHeader>
                  <CardContent className="text-sm text-gray-700 space-y-2 pt-0">
                    {protectionSnapshotLoading && <p className="text-gray-500">Loading…</p>}
                    {!protectionSnapshotLoading && protectionSnapshot && (
                      <>
                        <ul className="list-disc list-inside space-y-1">
                          <li>
                            Last portal sign-in:{' '}
                            {protectionSnapshot.account?.last_login_at
                              ? new Date(protectionSnapshot.account.last_login_at).toLocaleString()
                              : 'Not recorded'}
                          </li>
                          <li>
                            Compliance requirements:{' '}
                            {Number(protectionSnapshot.compliance?.requirements_overdue || 0)} overdue,{' '}
                            {Number(protectionSnapshot.compliance?.requirements_expiring_soon || 0)} expiring soon,{' '}
                            {Number(protectionSnapshot.compliance?.requirements_pending || 0)} pending
                          </li>
                          {protectionSnapshot.operations?.maintenance_workflows_enabled &&
                            protectionSnapshot.operations?.open_maintenance_issues != null && (
                              <li>Open maintenance issues: {protectionSnapshot.operations.open_maintenance_issues}</li>
                            )}
                          {protectionSnapshot.risk?.predictive_enabled &&
                            protectionSnapshot.risk?.active_risk_signals_count != null && (
                              <li>
                                Active risk signals: {protectionSnapshot.risk.active_risk_signals_count}
                                {Number(protectionSnapshot.risk.high_or_critical_active_count || 0) > 0
                                  ? ` (${protectionSnapshot.risk.high_or_critical_active_count} high or critical)`
                                  : ''}
                              </li>
                            )}
                        </ul>
                        {commandCenterScopePropertyId && (
                          <p className="text-xs text-electric-teal">
                            Maintenance issues and risk-signal counts are scoped to the selected property; compliance totals are portfolio-wide.
                          </p>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              )}

              {(activitySinceLoading || activitySince) && (
                <Card className="border border-gray-200 shadow-sm" data-testid="activity-since-card">
                  <CardHeader className="pb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                    <div className="min-w-0">
                      <CardTitle className="text-base flex items-center gap-2 break-words">
                        <History className="w-4 h-4 text-teal-600 shrink-0" />
                        Since your last visit
                      </CardTitle>
                      {activitySince?.window?.since && activitySince?.window?.until && (
                        <p className="text-xs text-gray-500 mt-1 break-words">
                          Compared {new Date(activitySince.window.since).toLocaleString()} →{' '}
                          {new Date(activitySince.window.until).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0"
                      disabled={activitySinceAckBusy || activitySinceLoading}
                      onClick={handleAckActivitySince}
                      data-testid="activity-since-ack-btn"
                    >
                      Mark as seen
                    </Button>
                  </CardHeader>
                  <CardContent>
                    {activitySinceLoading ? (
                      <p className="text-sm text-gray-500">Loading what changed…</p>
                    ) : Array.isArray(activitySince?.lines) && activitySince.lines.length > 0 ? (
                      <ul className="list-disc list-inside space-y-1.5 text-sm text-gray-800">
                        {activitySince.lines.map((line, idx) => (
                          <li key={idx}>{line}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-600">
                        No qualifying changes in audit logs, score snapshots, jobs, or uploads for this window.
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}
            </CollapsibleContent>
          </Collapsible>
        )}

        {!setupView && jurisdictionPortfolioBanner.showFull && (
            <Alert
              className="mb-6 border-amber-300 bg-amber-50/95 text-amber-950"
              data-testid="jurisdiction-fallback-dashboard-alert"
            >
              <AlertCircle className="h-4 w-4 text-amber-800" />
              <AlertDescription>
                <p className="font-semibold text-amber-950">{JURISDICTION_FALLBACK_ALERT_TITLE}</p>
                <p className="text-sm mt-1.5 text-amber-950/95">{JURISDICTION_FALLBACK_ALERT_BODY}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3 border-amber-400 bg-white hover:bg-amber-100"
                  onClick={() => navigate('/settings/jurisdiction')}
                >
                  {JURISDICTION_FALLBACK_CTA}
                </Button>
              </AlertDescription>
            </Alert>
          )}

        {!setupView && jurisdictionPortfolioBanner.showCompact && (
          <Alert
            className="mb-6 border-amber-200/90 bg-amber-50/60 text-amber-950"
            data-testid="jurisdiction-fallback-dashboard-reminder"
          >
            <Info className="h-4 w-4 text-amber-700 shrink-0" />
            <AlertDescription className="text-sm text-amber-950/95">
              <span>{JURISDICTION_PORTFOLIO_REMINDER_COMPACT} </span>
              <Link to="/settings/jurisdiction" className="font-medium text-electric-teal hover:underline">
                {JURISDICTION_FALLBACK_CTA}
              </Link>
            </AlertDescription>
          </Alert>
        )}

        {/* ZONE 2 — Portfolio intelligence: score trend + what changed */}
        {/* Score Trend (90 days) + What Changed */}
        <div className="mb-8 grid lg:grid-cols-2 gap-6" data-testid="score-trend-and-changes">
          {/* Left: Score Trend (90 days) */}
          <Card className="border border-gray-200 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-teal-600" />
                Score Trend (90 days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Portfolio | Property toggle */}
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-3">
                <div className="flex rounded-lg border border-gray-200 p-0.5 bg-gray-50">
                  <button
                    type="button"
                    onClick={() => { setScoreTrendView('portfolio'); setSelectedTrendPropertyId(null); }}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      scoreTrendView === 'portfolio' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                    }`}
                    data-testid="score-trend-toggle-portfolio"
                  >
                    Portfolio
                  </button>
                  <button
                    type="button"
                    onClick={() => setScoreTrendView('property')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      scoreTrendView === 'property' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                    }`}
                    data-testid="score-trend-toggle-property"
                  >
                    Property
                  </button>
                </div>
                {scoreTrendView === 'property' && (
                  <select
                    value={selectedTrendPropertyId ?? ''}
                    onChange={(e) => setSelectedTrendPropertyId(e.target.value || null)}
                    className="sm:ml-2 px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:ring-2 focus:ring-teal-500 focus:border-teal-500 min-w-0 max-w-full"
                    data-testid="score-trend-property-select"
                  >
                    <option value="">Select property</option>
                    {(portfolioSummary?.properties ?? []).map((p) => (
                      <option key={p.property_id} value={p.property_id}>
                        {getPropertyDisplayLabel(p)}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <ScoreTrendChart
                points={scoreTrendData?.points ?? []}
                summary={{
                  current: scoreTrendData?.current,
                  delta_30: scoreTrendData?.delta_30,
                  best_90: scoreTrendData?.best_90,
                  worst_90: scoreTrendData?.worst_90,
                }}
                onPointClick={() => navigate('/compliance-score')}
              />
              <p className="text-xs text-gray-500 mt-3">
                {scoreTrendView === 'portfolio'
                  ? trackedPropertyCount != null
                    ? `Portfolio trend across ${trackedPropertyCount} propert${trackedPropertyCount === 1 ? 'y' : 'ies'} with tracked requirements.`
                    : 'Portfolio trend across your tracked requirements (per compliance score service).'
                  : 'Single property score history'}
              </p>
            </CardContent>
          </Card>

          {/* Right: What Changed */}
          <Card className="border border-gray-200 shadow-sm">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <History className="w-4 h-4 text-electric-teal" />
                  What Changed
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-electric-teal hover:text-electric-teal/90 text-xs"
                  onClick={() => navigate('/audit-log?tab=score-history')}
                  data-testid="view-score-history-link"
                >
                  View full history →
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {scoreChanges?.items?.length > 0 ? (
                <ul className="space-y-3 max-h-64 overflow-y-auto">
                  {scoreChanges.items.map((item, idx) => {
                    const hasLink = item.document_id || item.requirement_id || item.property_id;
                    const Icon =
                      item.event_type === 'DOCUMENT_CONFIRMED' || item.event_type === 'DOCUMENT_UPLOADED'
                        ? FileText
                        : item.event_type === 'REQUIREMENT_STATUS_CHANGED'
                          ? ClipboardCheck
                          : item.event_type === 'PROPERTY_ADDED' || item.event_type === 'PROPERTY_UPDATED'
                            ? Building2
                            : item.event_type === 'SCORE_RECALCULATED'
                              ? TrendingUp
                              : History;
                    return (
                      <li key={idx}>
                        <button
                          type="button"
                          onClick={() => {
                            if (!hasLink) return;
                            const rawPid = item.property_id;
                            const pid =
                              rawPid != null && String(rawPid).trim() !== '' && String(rawPid) !== 'undefined' && String(rawPid) !== 'null'
                                ? String(rawPid).trim()
                                : null;
                            if (item.document_id && pid) navigate(resolveClientPortalPath(`/documents?property_id=${encodeURIComponent(pid)}`, '/documents'));
                            else if (item.requirement_id && pid) {
                              navigate(resolveClientPortalPath(`/requirements?property_id=${encodeURIComponent(pid)}`, '/requirements'));
                            } else if (pid) navigate(resolveClientPortalPath(`/properties/${encodeURIComponent(pid)}`, '/properties'));
                          }}
                          className={`w-full text-left flex items-start gap-3 p-2 rounded-lg transition-colors ${
                            hasLink ? 'hover:bg-gray-50 cursor-pointer' : 'cursor-default'
                          }`}
                        >
                          <div className="mt-0.5 rounded-full bg-gray-100 p-1.5">
                            <Icon className="w-3.5 h-3.5 text-gray-600" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-gray-900">{item.title}</p>
                            {item.details && <p className="text-xs text-gray-600 truncate">{item.details}</p>}
                            <p className="text-xs text-gray-400 mt-0.5">
                              {item.created_at &&
                                (function () {
                                  try {
                                    const d = new Date(item.created_at);
                                    const now = new Date();
                                    const mins = Math.floor((now - d) / (1000 * 60));
                                    if (mins < 1) return 'Just now';
                                    if (mins < 60) return `${mins} min ago`;
                                    const hours = Math.floor(mins / 60);
                                    if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
                                    const days = Math.floor(hours / 24);
                                    if (days < 7) return `${days} day${days !== 1 ? 's' : ''} ago`;
                                    return d.toLocaleDateString();
                                  } catch (_) {
                                    return '';
                                  }
                                })()}
                            </p>
                          </div>
                          {item.delta != null && (
                            <span
                              className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded ${
                                item.delta > 0 ? 'bg-green-100 text-green-800' : item.delta < 0 ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {item.delta > 0 ? `+${item.delta}` : item.delta}
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="py-8 flex flex-col items-center justify-center text-center text-gray-500">
                  <History className="w-10 h-10 text-gray-300 mb-2" />
                  <p className="text-sm">Score change events will appear here.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* UNKNOWN applicability banner: prompt to confirm property details */}
        {requirementsList.length > 0 && requirementsList.some(r => (r.applicability || 'UNKNOWN') === 'UNKNOWN') && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="unknown-applicability-banner">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-800">Confirm your property details.</span>
              <span className="text-amber-700 ml-1">Some tracked items depend on your property settings. Update your properties so we can show the right items and dates.</span>
              <Button variant="outline" size="sm" className="mt-2 border-amber-300 text-amber-800 hover:bg-amber-100" onClick={() => navigate('/requirements')}>
                Review requirements
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Provisional score banner: REQUIRED tracked items missing confirmed expiry */}
        {requirementsList.length > 0 && requirementsList.some(r => (r.applicability || '').toUpperCase() === 'REQUIRED' && !r.confirmed_expiry_date) && (
          <Alert className="mb-6 border-blue-200 bg-blue-50" data-testid="provisional-score-banner">
            <Info className="h-4 w-4 text-blue-600" />
            <AlertDescription>
              <span className="font-medium text-blue-800">Score is provisional.</span>
              <span className="text-blue-700 ml-1">Confirm expiry dates for tracked items to finalise your score. Some items that apply to your properties do not yet have a confirmed expiry date.</span>
              <Button variant="outline" size="sm" className="mt-2 border-blue-300 text-blue-800 hover:bg-blue-100" onClick={() => navigate('/requirements')}>
                Confirm expiry dates
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Compliance Score Widget */}
        {(complianceScore || displayScoreInfo) && (
          <div className="mb-8 grid lg:grid-cols-3 gap-6" data-testid="compliance-score-widget">
            {/* Main Score Card - CLICKABLE; single property uses portfolio score so card and table match */}
            <div 
              className={`lg:col-span-1 rounded-2xl p-6 border-2 cursor-pointer hover:shadow-lg transition-all group ${
                displayScoreInfo?.color === 'green' ? 'bg-gradient-to-br from-green-50 to-green-100 border-green-200 hover:border-green-400' :
                displayScoreInfo?.color === 'amber' ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200 hover:border-amber-400' :
                displayScoreInfo?.color === 'red' ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200 hover:border-red-400' :
                'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200 hover:border-gray-400'
              }`}
              onClick={() => navigate('/compliance-score')}
              data-testid="compliance-score-card-clickable"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide flex items-center">
                      Compliance score
                      <DashboardKpiHint label="Compliance score">
                        Built from the same scoring engine as Compliance score: weighted requirements, verified evidence, operational
                        items, and recency — not a separate manual model. Excludes legal advice. Updates when you upload, confirm dates, or
                        resolve linked work.
                      </DashboardKpiHint>
                    </h3>
                    <ExternalLink className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className={`text-5xl font-bold ${
                      displayScoreInfo?.color === 'green' ? 'text-green-700' :
                      displayScoreInfo?.color === 'amber' ? 'text-amber-700' :
                      displayScoreInfo?.color === 'red' ? 'text-red-700' :
                      'text-gray-700'
                    }`}>
                      {portfolioHeadlineUi.display}
                    </span>
                    {portfolioHeadlineUi.showOutOf100 ? <span className="text-2xl text-gray-400">/100</span> : null}
                  </div>
                </div>
                <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
                  displayScoreInfo?.color === 'green' ? 'bg-green-200' :
                  displayScoreInfo?.color === 'amber' ? 'bg-amber-200' :
                  displayScoreInfo?.color === 'red' ? 'bg-red-200' :
                  'bg-gray-200'
                }`}>
                  <span className={`text-3xl font-bold ${
                    displayScoreInfo?.color === 'green' ? 'text-green-700' :
                    displayScoreInfo?.color === 'amber' ? 'text-amber-700' :
                    displayScoreInfo?.color === 'red' ? 'text-red-700' :
                    'text-gray-700'
                  }`}>
                    {formatDashboardGradeShort(displayScoreInfo?.grade ?? complianceScore?.grade)}
                  </span>
                </div>
              </div>
              <p className={`text-sm ${
                displayScoreInfo?.color === 'green' ? 'text-green-700' :
                displayScoreInfo?.color === 'amber' ? 'text-amber-700' :
                displayScoreInfo?.color === 'red' ? 'text-red-700' :
                'text-gray-600'
              }`}>
                {displayScoreInfo?.message ?? complianceScore?.message}
              </p>
              {riskBandExplanation && (
                <p className="text-xs text-gray-600 mt-1" data-testid="risk-band-explanation">{riskBandExplanation}</p>
              )}
              {(complianceScore?.properties_count != null && (complianceScore?.properties_count ?? 0) > 1) && (
                <p className="text-xs text-gray-500 mt-1">Overall score: average across your {complianceScore?.properties_count} properties.</p>
              )}

              {/* Score breakdown and explanation – single trend is shown in Score Trend (90 days) card */}
              <div className="mt-4 pt-4 border-t border-white/50 space-y-2">
                {portfolioHasV2BucketBreakdown(complianceScore?.bucket_breakdown) ? (
                  <>
                    <p className="text-xs text-gray-500 mb-1">Score components (credit within each bucket, 0–100%)</p>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Legal core</span>
                      <span className="font-medium">{Number(complianceScore.bucket_breakdown.legal_core.percent).toFixed(0)}%</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Verified documentation</span>
                      <span className="font-medium">
                        {Number(complianceScore.bucket_breakdown.documentation_completeness.percent).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Operational responsiveness</span>
                      <span className="font-medium">
                        {Number(complianceScore.bucket_breakdown.operational_responsiveness.percent).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Recency &amp; maintenance confidence</span>
                      <span className="font-medium">
                        {Number(complianceScore.bucket_breakdown.recency_maintenance_confidence.percent).toFixed(0)}%
                      </span>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-gray-600">
                    Per-bucket component scores appear here after each property has a current stored breakdown. Your headline score and
                    drivers already use the current model.
                  </p>
                )}
                {(complianceScore?.earned_points != null && complianceScore?.applicable_points != null) && (
                  <div className="flex justify-between text-xs pt-1 border-t border-gray-200">
                    <span className="text-gray-600">Points earned</span>
                    <span className="font-medium">
                      {Number(complianceScore?.earned_points || 0).toFixed(1)} / {Number(complianceScore?.applicable_points || 0).toFixed(1)}
                    </span>
                  </div>
                )}
              </div>
              
              {/* Expandable Explanation Toggle */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowScoreExplanation(!showScoreExplanation);
                }}
                className="mt-3 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 w-full justify-center"
                data-testid="toggle-score-explanation"
              >
                <Info className="w-3 h-3" />
                How is this calculated?
                {showScoreExplanation ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
              
              {/* Inline Explanation */}
              {showScoreExplanation && (
                <div className="mt-3 pt-3 border-t border-white/50 text-xs space-y-2" onClick={(e) => e.stopPropagation()}>
                  <p className="font-medium text-gray-700">Score components</p>
                  <ul className="space-y-1 text-gray-600">
                    {portfolioHasV2BucketBreakdown(complianceScore?.bucket_breakdown) ? (
                      <>
                        <li>
                          • <strong>Legal core:</strong> weighted by requirement type and jurisdiction; credit from evidence validity,
                          expiry, and coverage — not fixed per-status point numbers.
                        </li>
                        <li>
                          • <strong>Verified documentation:</strong> applicable obligations with <strong>verified</strong> evidence only.
                        </li>
                        <li>
                          • <strong>Operational responsiveness:</strong> open maintenance issues and overdue jobs reduce this bucket.
                        </li>
                        <li>
                          • <strong>Recency / maintenance confidence:</strong> open predictive issues and expiring-soon items reduce this
                          bucket.
                        </li>
                      </>
                    ) : (
                      <>
                        <li>
                          • The headline score uses the current engine. Bucket-level lines above fill in once each property has a stored
                          breakdown. Counts today: {complianceScore?.stats?.compliant || 0}/
                          {complianceScore?.stats?.total_requirements || 0} valid, {complianceScore?.stats?.expiring_soon || 0} expiring
                          soon, {complianceScore?.stats?.overdue || 0} overdue.
                        </li>
                      </>
                    )}
                  </ul>
                  <p className="text-electric-teal pt-1">Click card for full breakdown →</p>
                </div>
              )}
            </div>

            {/* Recommendations Card */}
            <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="w-5 h-5 text-electric-teal" />
                <h3 className="font-semibold text-midnight-blue">Quick Actions to Improve Your Score</h3>
              </div>
              
              {complianceScore?.recommendations?.length > 0 ? (
                <div className="space-y-3">
                  {(complianceScore?.recommendations ?? []).slice(0, 3).map((rec, idx) => {
                    let actionDisplay = rec.action || '';
                    const code = rec.requirement_code;
                    if (code && actionDisplay.includes(code)) {
                      const lbl = rec.display_label || requirementLabel(code);
                      actionDisplay = actionDisplay.split(code).join(lbl);
                    }
                    const codeLower = (code || '').toString().trim().toLowerCase();
                    const recPropertyId = normalizeRouteId(rec.property_id || rec.related_property_id);
                    const recReqId = normalizeRouteId(rec.requirement_id || rec.related_requirement_id);
                    const candidates = requirementsList.filter((r) => {
                      const rCode = String(r.requirement_code || r.requirement_type || '').trim().toLowerCase();
                      const propOk = recPropertyId ? String(r.property_id || '') === recPropertyId : true;
                      const codeOk = codeLower ? rCode === codeLower : true;
                      return propOk && codeOk;
                    });
                    const sorted = [...candidates].sort((a, b) => {
                      const wa =
                        (String(a.status || '').toUpperCase() === 'OVERDUE' ? 0 : String(a.status || '').toUpperCase() === 'EXPIRING_SOON' ? 1 : 2);
                      const wb =
                        (String(b.status || '').toUpperCase() === 'OVERDUE' ? 0 : String(b.status || '').toUpperCase() === 'EXPIRING_SOON' ? 1 : 2);
                      if (wa !== wb) return wa - wb;
                      return 0;
                    });
                    const bestReq = sorted[0] || null;
                    const bestRequirementId = recReqId || normalizeRouteId(bestReq?.requirement_id);
                    const bestPropertyId = recPropertyId || normalizeRouteId(bestReq?.property_id);
                    const fixNowPath = buildEntityRoute(
                      {
                        requirement_id: bestRequirementId,
                        property_id: bestPropertyId,
                        work_order_id: normalizeRouteId(rec.work_order_id || rec.related_work_order_id),
                        mode: 'upload',
                      },
                      '/today'
                    );
                    const hasEntityRoute = fixNowPath !== '/today';
                    return (
                    <div 
                      key={idx}
                      className={`flex items-start gap-3 p-3 rounded-lg ${
                          rec.priority === 'high' || rec.priority === 'critical' ? 'bg-red-50 border border-red-100' :
                        rec.priority === 'medium' ? 'bg-amber-50 border border-amber-100' :
                        'bg-gray-50 border border-gray-100'
                      }`}
                    >
                        <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                          rec.priority === 'high' || rec.priority === 'critical' ? 'bg-red-500' :
                        rec.priority === 'medium' ? 'bg-amber-500' :
                        'bg-gray-400'
                      }`} />
                        <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800">{actionDisplay}</p>
                        <p className="text-xs text-gray-500 mt-0.5">Potential impact: {rec.impact}</p>
                      </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="shrink-0"
                          disabled={!hasEntityRoute}
                          onClick={(e) => { e.stopPropagation(); if (hasEntityRoute) navigate(fixNowPath); }}
                          data-testid={`quick-action-fix-${idx}`}
                        >
                          Fix now
                        </Button>
                    </div>
                    );
                  })}
                </div>
              ) : (() => {
                const total = complianceScore?.stats?.total_requirements ?? 0;
                const valid = complianceScore?.stats?.compliant ?? 0;
                const rawEncouragement =
                  displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score;
                const stEncouragement =
                  displayScoreInfo?.scoreStatus ??
                  complianceScore?.score_status ??
                  portfolioSummary?.score_status;
                const headlineNum =
                  rawEncouragement != null &&
                  headlineScoreShowsOutOf100(rawEncouragement, stEncouragement)
                    ? Number(rawEncouragement)
                    : null;
                const allValid =
                  total > 0 &&
                  valid === total &&
                  actionableMissingCount === 0 &&
                  headlineNum != null &&
                  !Number.isNaN(headlineNum) &&
                  headlineNum >= 80;
                if (allValid) {
                  return (
                <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-100">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">Excellent work!</p>
                    <p className="text-sm text-green-600">Your compliance is in great shape. Keep it up!</p>
                  </div>
                </div>
                  );
                }
                return (
                  <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg border border-gray-100">
                    <Zap className="w-5 h-5 text-gray-500" />
                    <div>
                      <p className="text-sm text-gray-600">
                        {total === 0
                          ? 'Add properties and requirements to see actions here.'
                          : 'Upload documents and confirm expiry dates to improve your score.'}
                      </p>
                    </div>
                  </div>
                );
              })()}

              {/* Stats Row - Clickable */}
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-3 gap-4">
                <div 
                  className="text-center cursor-pointer hover:bg-gray-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/requirements')}
                  data-testid="stat-requirements"
                >
                  <p className="text-2xl font-bold text-midnight-blue">{complianceScore?.stats?.total_requirements || 0}</p>
                  <p className="text-xs text-gray-500">Requirements</p>
                </div>
                <div 
                  className="text-center cursor-pointer hover:bg-green-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/requirements?status=COMPLIANT')}
                  data-testid="stat-valid"
                >
                  <p className="text-2xl font-bold text-green-600">{complianceScore?.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-500">Valid</p>
                </div>
                <div 
                  className="text-center cursor-pointer hover:bg-amber-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/requirements?window=30&status=DUE_SOON')}
                  data-testid="stat-expiry"
                >
                  <p className="text-2xl font-bold text-amber-600">
                    {complianceScore?.stats?.days_until_next_expiry !== null && complianceScore?.stats?.days_until_next_expiry !== undefined
                      ? complianceScore?.stats?.days_until_next_expiry
                      : KPI_NO_DATA}
                  </p>
                  <p className="text-xs text-gray-500">Days to Next Expiry</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Audit readiness: single canonical snapshot (v2 Row 2) */}
        {auditReadiness && (
          <Card className="mb-8 border border-gray-200 shadow-sm max-w-md" data-testid="audit-readiness-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                <ClipboardCheck className="w-4 h-4 text-electric-teal" />
                Audit readiness
                <DashboardKpiHint label="Audit readiness">
                  Derived from your current requirement snapshot: overdue count, share of items missing evidence, and share with confirmed
                  documents. High / moderate / low is a readiness signal only — not an audit pass or legal opinion. Recalculates with
                  compliance and document changes.
                </DashboardKpiHint>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-lg font-semibold ${
                auditReadiness.level === 'Low' ? 'text-red-600' :
                auditReadiness.level === 'Moderate' ? 'text-amber-600' : 'text-green-600'
              }`}>
                {auditReadiness.level}
              </p>
              <p className="text-xs text-gray-500 mt-1">{auditReadiness.drivers.join(' · ')}</p>
            </CardContent>
          </Card>
        )}

        {/* Operations overview: work order funnel + risk signals (feature-gated) */}
        {!setupView && (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance')) && (
          <div className="mb-8 grid md:grid-cols-2 gap-6">
            {hasFeature('maintenance_workflows') && (
              <Card className="border border-gray-200 shadow-sm" data-testid="operations-overview-wo">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                    <Wrench className="w-4 h-4 text-electric-teal" />
                    Jobs
                    <DashboardKpiHint label="Jobs snapshot">
                      Counts from maintenance jobs loaded for this dashboard (up to 500 active rows). Terminal or cancelled jobs are
                      excluded from open pipeline stages. Completed is historical in that window — open Jobs for the full queue and filters.
                    </DashboardKpiHint>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <span className="font-medium text-amber-700">Open: {workOrderFunnel.open}</span>
                    <span className="font-medium text-blue-700">Assigned: {workOrderFunnel.assigned}</span>
                    <span className="font-medium text-blue-600">In progress: {workOrderFunnel.inProgress}</span>
                    <span className="font-medium text-green-700">Completed: {workOrderFunnel.completed}</span>
                  </div>
                  {workOrderFunnel.open + workOrderFunnel.assigned + workOrderFunnel.inProgress === 0 && (
                    <p className="text-xs text-gray-500 mt-2">
                      No open, assigned, or in-progress jobs in this snapshot — appears when maintenance work is active.
                    </p>
                  )}
                  <Button variant="outline" size="sm" className="mt-3 text-electric-teal border-electric-teal" onClick={() => navigate('/operations/work-orders')}>
                    View all jobs
                  </Button>
                </CardContent>
              </Card>
            )}
            {hasFeature('predictive_maintenance') && (
              <Card className="border border-gray-200 shadow-sm" data-testid="operations-overview-risk">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                    <TrendingUp className="w-4 h-4 text-electric-teal" />
                    Risk signals
                    <DashboardKpiHint label="Risk signals">
                      Count of active predictive risk signals for your portfolio (same basis as the KPI row when the security snapshot has loaded).
                      Clearing a signal is risk-layer housekeeping only — it does not restore compliance by itself.
                    </DashboardKpiHint>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-midnight-blue">{riskSignalsCount}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Open predictive risk signals across your properties — review, acknowledge, or dismiss as appropriate. Follow
                    compliance and evidence paths separately where obligations still apply.
                  </p>
                  <Button variant="outline" size="sm" className="mt-3 text-electric-teal border-electric-teal" onClick={() => navigate('/operations/risk-signals')}>
                    View risk signals
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {!setupView && contractorNetworkEnabled && contractorNetworkActivity && contractorNetworkActivity.pendingNetwork > 0 && (
          <Alert className="mb-8 border-sky-200 bg-sky-50" data-testid="contractor-network-dashboard-alert">
            <AlertCircle className="h-4 w-4 text-sky-600" />
            <AlertDescription>
              <span className="font-medium text-sky-900">Contractor network</span>
              <span className="block mt-1 text-sky-800">
                {contractorNetworkActivity.pendingNetwork} private contractor{contractorNetworkActivity.pendingNetwork !== 1 ? 's are' : ' is'} with Pleerity for platform network review (submitted from your account).
              </span>
              {contractorNetworkActivity.rejectedCount > 0 && (
                <span className="block mt-2 text-sm text-sky-900/85">
                  {contractorNetworkActivity.rejectedCount} earlier submission{contractorNetworkActivity.rejectedCount !== 1 ? 's were' : ' was'} declined — open Contractors for the reason.
                </span>
              )}
              <Button
                size="sm"
                className="mt-3 bg-electric-teal hover:bg-electric-teal/90"
                onClick={() => navigate('/operations/contractors')}
              >
                Open Contractors
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Action Required: operations items (deep links to Issues, Risk Signals) */}
        {!setupView && ((openIssuesCount ?? 0) > 0 || riskSignalsCount > 0) && (
          <Card className="mb-8 border-amber-200 bg-amber-50/50" data-testid="action-required-operations">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2 text-amber-900">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                Action required
              </CardTitle>
              <p className="text-sm text-amber-800">Items needing your attention</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {(openIssuesCount ?? 0) > 0 && hasFeature('maintenance_workflows') && (
                  <li className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between py-3 border-b border-amber-200 last:border-0">
                    <span className="text-sm text-gray-800 min-w-0 break-words">{openIssuesCount} open maintenance issue{openIssuesCount !== 1 ? 's' : ''}</span>
                    <Button size="sm" className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0 bg-electric-teal hover:bg-electric-teal/90 shrink-0" onClick={() => navigate('/operations/issues')}>
                      View maintenance issues
                    </Button>
                  </li>
                )}
                {riskSignalsCount > 0 && hasFeature('predictive_maintenance') && (
                  <li className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between py-3 border-b border-amber-200 last:border-0">
                    <span className="text-sm text-gray-800 min-w-0 break-words">
                      {riskSignalsCount} active risk signal{riskSignalsCount !== 1 ? 's' : ''}
                    </span>
                    <Button size="sm" className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0 bg-electric-teal hover:bg-electric-teal/90 shrink-0" onClick={() => navigate('/operations/risk-signals')}>
                      View risk signals
                    </Button>
                  </li>
                )}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* De-duplicated: score/risk/last updated/properties are in top strip and KPI tiles below */}
        {/* Compliance Framework explanation (static, no legal advice) */}
        <div className="mb-8 rounded-xl border border-gray-200 bg-white overflow-hidden">
          <button
            type="button"
            onClick={() => setShowComplianceFramework(!showComplianceFramework)}
            className="w-full flex items-center justify-between px-4 py-3 text-left text-sm font-medium text-midnight-blue hover:bg-gray-50"
          >
            <span className="flex items-center gap-2">
              <Info className="w-4 h-4 text-electric-teal" />
              Compliance Framework – how scoring works
            </span>
            {showComplianceFramework ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showComplianceFramework && (
            <div className="px-4 pb-4 pt-0 text-sm text-gray-600 border-t border-gray-100 space-y-3">
              <p className="text-gray-800">
                Scores are based on <strong>document validity</strong>, <strong>expiry</strong>, <strong>evidence coverage</strong>, and{' '}
                <strong>risk-style weighting</strong> across requirements — not on a single fixed points table. Each applicable
                requirement contributes according to its weight; those contributions combine into the property score. The engine runs on
                our servers; exact fractions depend on requirement status, which document is chosen as evidence, verification, and
                jurisdiction rules (including different &quot;expiring soon&quot; windows per requirement where configured).
              </p>
              <p className="font-medium text-midnight-blue">Property score (0–100)</p>
              <p>Each property score combines four buckets (current model):</p>
              <ul className="list-disc pl-5 space-y-1.5">
                <li>
                  <strong>Legal core (~60%)</strong> — Applicable legal obligations for the property&apos;s jurisdiction, each with its
                  own weight (e.g. gas safety and electrical checks typically count more than lower-weight items). Credit is a{' '}
                  <em>fraction</em> of that weight from validity, missing evidence, expiry, and related signals — not a universal
                  &quot;100 / 70 / 30 / 0&quot; schedule. System-estimated dates can slightly reduce credit versus confirmed evidence.
                </li>
                <li>
                  <strong>Documentation completeness (~20%)</strong> — Share of applicable obligations that have{' '}
                  <strong>verified</strong> evidence, not merely an upload.
                </li>
                <li>
                  <strong>Operational responsiveness (~10%)</strong> — Open maintenance issues and overdue maintenance jobs reduce this
                  portion.
                </li>
                <li>
                  <strong>Recency / maintenance confidence (~10%)</strong> — Open predictive issues and items in an expiring-soon state
                  reduce this portion.
                </li>
              </ul>
              <p className="font-medium text-midnight-blue">Portfolio score</p>
              <p>
                The portfolio figure is the <strong>simple average</strong> of stored property scores (each already 0–100). It is not a
                separate weighted re-aggregation by requirement count at portfolio level.
              </p>
              <p className="font-medium text-midnight-blue">Risk labels (document-backed, not legal advice)</p>
              <p>Band colours and grades follow the same bands you see elsewhere: 80–100 low; 60–79 moderate; 40–59 high; 0–39 critical.</p>
              <p className="text-gray-500 italic">
                This is a document-backed operational summary. It is not legal advice and does not constitute legal certification. For
                detail on your account, open Compliance score.
              </p>
            </div>
          )}
        </div>

        {/* Portfolio summary table (Audit Intelligence) */}
        {portfolioSummary?.properties?.length > 0 && (
          <div className="mb-8 rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 font-medium text-midnight-blue">
              Portfolio summary
            </div>
            <div className="md:hidden p-3 space-y-3 client-portal-prose">
              {portfolioSummary.properties.map((p) => (
                <button
                  key={p.property_id}
                  type="button"
                  className="w-full text-left rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:border-electric-teal/40 transition-colors min-h-[44px]"
                  onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                >
                  <p className="font-semibold text-midnight-blue break-words">{getPropertyDisplayLabel(p) || p.name || p.property_id}</p>
                  <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-gray-600">
                    <span>
                      Score: {headlineScoreDisplayForDashboard(p.property_score ?? p.score, p.score_status)}
                      {headlineScoreShowsOutOf100(p.property_score ?? p.score, p.score_status) ? '/100' : ''}
                    </span>
                    <span>{formatRiskLabel(p.risk_level)}</span>
                    <span>Overdue: {p.overdue_count ?? 0}</span>
                    <span>Expiring: {p.expiring_30_count ?? p.expiring_soon_count ?? 0}</span>
                  </div>
                  <span className="mt-2 inline-block text-sm text-electric-teal font-medium">View property →</span>
                </button>
              ))}
            </div>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-600">
                    <th className="p-3">Property</th>
                    <th className="p-3">Score</th>
                    <th className="p-3">Risk level</th>
                    <th className="p-3">Overdue</th>
                    <th className="p-3">Expiring soon</th>
                    <th className="p-3">Missing documents</th>
                    {hasFeature('maintenance_workflows') && <th className="p-3">Open jobs</th>}
                    <th className="p-3">View</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolioSummary.properties.map((p) => (
                    <tr
                      key={p.property_id}
                      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                      onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                    >
                      <td className="p-3 font-medium text-midnight-blue max-w-[14rem] break-words">{getPropertyDisplayLabel(p) || p.name || p.property_id}</td>
                      <td className="p-3">
                        {headlineScoreDisplayForDashboard(p.property_score ?? p.score, p.score_status)}
                        {headlineScoreShowsOutOf100(p.property_score ?? p.score, p.score_status) ? '/100' : ''}
                      </td>
                      <td className="p-3 whitespace-nowrap">{formatRiskLabel(p.risk_level)}</td>
                      <td className="p-3">{p.overdue_count ?? 0}</td>
                      <td className="p-3">{p.expiring_30_count ?? p.expiring_soon_count ?? 0}</td>
                      <td className="p-3">{p.missing_count ?? 0}</td>
                      {hasFeature('maintenance_workflows') && (
                        <td className="p-3" onClick={(e) => e.stopPropagation()}>
                          {openJobsByProperty[p.property_id] ?? 0}
                        </td>
                      )}
                      <td className="p-3" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" className="text-electric-teal hover:bg-teal-50" onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}>
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 4 KPI cards: Score+Risk, Overdue, Expiring soon, Missing documents */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-electric-teal group"
            onClick={() => navigate('/compliance-score')}
            data-testid="tile-score-risk"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1 flex items-center">
                    Score &amp; Risk
                    <DashboardKpiHint label="Score and risk tile">
                      Same portfolio compliance score and risk band as the strip above, from your latest calculation. Click through for
                      methodology and breakdown.
                    </DashboardKpiHint>
                  </p>
                  <p className="text-3xl font-bold text-midnight-blue">
                    {portfolioHeadlineUi.display}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {displayScoreInfo?.message ?? (portfolioSummary?.risk_level ? formatRiskLabel(portfolioSummary.risk_level) : (complianceScore?.message || 'Portfolio'))}
                  </p>
                  <p className="text-xs text-electric-teal opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    View score →
                  </p>
                </div>
                <Shield className="w-12 h-12 text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-red-300 group"
            onClick={() => navigate('/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="tile-overdue"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1 flex items-center">
                    Overdue
                    <DashboardKpiHint label="Overdue requirements">
                      Canonical count from compliance score (runtime projection, portal-visible rows). Same source as
                      Command Centre and compliance score header — not the separate portfolio KPI merge.
                    </DashboardKpiHint>
                  </p>
                  <p className="text-3xl font-bold text-red-600">
                    {complianceScore?.stats?.overdue ?? data?.compliance_summary?.overdue ?? 0}
                  </p>
                  <p className="text-xs text-red-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    View →
                  </p>
                </div>
                <XCircle
                  className={`w-12 h-12 ${
                    (complianceScore?.stats?.overdue ?? data?.compliance_summary?.overdue ?? 0) > 0 ? 'text-red-600' : 'text-gray-300'
                  }`}
                  aria-hidden
                />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-amber-300 group"
            onClick={() => navigate('/requirements?status=DUE_SOON')}
            data-testid="tile-expiring-soon"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1 flex items-center">
                    Expiring soon
                    <DashboardKpiHint label="Expiring soon">
                      Canonical count from compliance score stats (same runtime projection as overdue).
                    </DashboardKpiHint>
                  </p>
                  <p className="text-3xl font-bold text-amber-600">
                    {complianceScore?.stats?.expiring_soon ?? data?.compliance_summary?.expiring_soon ?? 0}
                  </p>
                  <p className="text-xs text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    View →
                  </p>
                </div>
                <Clock className="w-12 h-12 text-amber-600" />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-gray-300 group"
            onClick={() => navigate('/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="tile-missing-evidence"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1 flex items-center">
                    Missing documents
                    <DashboardKpiHint label="Missing documents">
                      Missing-evidence count from compliance score (PENDING + MISSING on portal-visible projected rows). Not a
                      client-side merge with overdue.
                    </DashboardKpiHint>
                  </p>
                  <p className="text-3xl font-bold text-gray-700">
                    {actionableMissingCount}
                  </p>
                  <p className="text-xs text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    View →
                  </p>
                </div>
                <FileText className="w-12 h-12 text-gray-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Focus strip: prioritised subset — not a second copy of Portfolio summary */}
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <Card className="enterprise-card h-full" data-testid="dashboard-focus-properties-card">
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <CardTitle className="text-midnight-blue flex items-center gap-2">
                      <Target className="w-5 h-5 text-electric-teal shrink-0" />
                      Focus: highest-risk properties
                    </CardTitle>
                    <p className="text-sm text-gray-600 mt-2 font-normal leading-snug">
                      Lowest scores first, with compliance gaps on one line so you can see where to act. The{' '}
                      <span className="font-medium text-midnight-blue">Portfolio summary</span> table above is the full grid with
                      separate columns.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 shrink-0">
                    <Button variant="outline" size="sm" onClick={() => navigate('/properties')} data-testid="view-all-properties-btn">
                      All properties
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate('/properties/import')}
                      data-testid="bulk-import-btn"
                    >
                      <FileText className="w-4 h-4 mr-1" />
                      Bulk Import
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {portfolioSummary?.properties?.length > 0 ? (
                  <>
                    <div className="md:hidden space-y-3">
                      {dashboardFocusProperties.map((p) => {
                        const score = p.property_score ?? p.score;
                        const st = p.score_status;
                        const gaps = buildDashboardComplianceGapsLine(p, openJobsByProperty, hasFeature('maintenance_workflows'));
                        return (
                          <button
                            key={p.property_id}
                            type="button"
                            className="w-full text-left rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:border-electric-teal/40 transition-colors min-h-[44px]"
                            onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                            data-testid={`dashboard-focus-property-row-${p.property_id}`}
                          >
                            <p className="font-semibold text-midnight-blue break-words">
                              {getPropertyDisplayLabel(p) || p.name || p.property_id}
                            </p>
                            <p className="text-sm text-gray-800 mt-1">
                              <span className="font-semibold">
                                {headlineScoreDisplayForDashboard(score, st)}
                                {headlineScoreShowsOutOf100(score, st) ? '/100' : ''}
                              </span>
                              {p.risk_level ? (
                                <span className="text-gray-600"> · {formatRiskLabel(p.risk_level)}</span>
                              ) : null}
                            </p>
                            <p className="text-xs text-gray-600 mt-2">{gaps}</p>
                            <span className="mt-2 inline-block text-sm text-electric-teal font-medium">View property →</span>
                          </button>
                        );
                      })}
                    </div>
                    <div className="hidden md:block overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 text-left text-gray-600">
                            <th className="p-3">Property</th>
                            <th className="p-3">Score &amp; risk</th>
                            <th className="p-3 min-w-[12rem]">Where to focus</th>
                            <th className="p-3">View</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dashboardFocusProperties.map((p) => {
                            const score = p.property_score ?? p.score;
                            const st = p.score_status;
                            const gaps = buildDashboardComplianceGapsLine(p, openJobsByProperty, hasFeature('maintenance_workflows'));
                            return (
                              <tr
                                key={p.property_id}
                                className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                                onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                                data-testid={`dashboard-focus-property-row-${p.property_id}`}
                              >
                                <td className="p-3 font-medium text-midnight-blue max-w-[14rem] break-words">
                                  {getPropertyDisplayLabel(p) || p.name || p.property_id}
                                </td>
                                <td className="p-3 whitespace-nowrap">
                                  <div className="font-semibold text-midnight-blue">
                                    {headlineScoreDisplayForDashboard(score, st)}
                                    {headlineScoreShowsOutOf100(score, st) ? '/100' : ''}
                                  </div>
                                  <div className="text-xs text-gray-600">
                                    {p.risk_level ? formatRiskLabel(p.risk_level) : KPI_NO_DATA}
                                  </div>
                                </td>
                                <td className="p-3 text-gray-700">{gaps}</td>
                                <td className="p-3" onClick={(e) => e.stopPropagation()}>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-electric-teal hover:bg-teal-50"
                                    onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                                  >
                                    View
                                  </Button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (data?.properties || []).length > 0 ? (
                  <div className="space-y-3">
                    <p className="text-sm text-gray-600">
                      Per-property scores will appear in <strong className="text-midnight-blue">Portfolio summary</strong> when
                      compliance data is available. Open a property below or manage the full list.
                    </p>
                    <ul className="divide-y divide-gray-100 border border-gray-200 rounded-lg">
                      {(data.properties || []).map((p) => (
                        <li key={p.property_id}>
                          <button
                            type="button"
                            className="w-full text-left px-4 py-3 text-sm font-medium text-midnight-blue hover:bg-gray-50 flex items-center justify-between gap-2"
                            onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                            data-testid={`dashboard-property-quicklink-${p.property_id}`}
                          >
                            <span className="break-words">{p.nickname || p.address_line_1 || p.property_id}</span>
                            <span className="text-electric-teal shrink-0 text-xs font-semibold">Open →</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <EmptyState
                    icon={FileText}
                    title="No properties found"
                    description="Add properties to track compliance."
                    actionLabel="Import Properties from CSV"
                    onAction={() => navigate('/properties/import')}
                    actionTestId="import-first-property-btn"
                    className="py-6"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Notification Preferences Widget */}
          <div className="lg:col-span-1">
            <Card className="enterprise-card h-full" data-testid="notification-prefs-widget">
              <CardHeader className="pb-3">
                <CardTitle className="text-midnight-blue flex items-center gap-2 text-lg">
                  <Bell className="w-5 h-5 text-electric-teal" />
                  Notification Settings
                </CardTitle>
              </CardHeader>
              <CardContent>
                {notificationPrefs ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Status Alerts</span>
                      {notificationPrefs.status_change_alerts ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Expiry Reminders</span>
                      {notificationPrefs.expiry_reminders ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Monthly Digest</span>
                      {notificationPrefs.monthly_digest ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-600">Reminder Timing</span>
                      <span className="text-sm font-medium text-midnight-blue">
                        {notificationPrefs.reminder_days_before} days
                      </span>
                    </div>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full mt-3 border-electric-teal text-electric-teal hover:bg-teal-50"
                      onClick={() => navigate('/settings/notifications')}
                      data-testid="manage-notifications-btn"
                    >
                      <Settings className="w-4 h-4 mr-2" />
                      Manage Preferences
                    </Button>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500 mb-3">Configure your notification preferences</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-electric-teal text-electric-teal hover:bg-teal-50"
                      onClick={() => navigate('/settings/notifications')}
                    >
                      Set Up Notifications
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

      {/* Build stamp for deployment verification */}
      {process.env.REACT_APP_BUILD_SHA && (
        <footer className="text-center py-2 text-xs text-gray-400" data-testid="build-stamp">
          Build: {process.env.REACT_APP_BUILD_SHA}
        </footer>
      )}
        </>
      )}
    </div>
    </TooltipProvider>
  );
};

export default ClientDashboard;
