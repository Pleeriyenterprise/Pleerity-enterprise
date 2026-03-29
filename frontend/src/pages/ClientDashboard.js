import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import ErrorBanner from '../components/ErrorBanner';
import EmptyState from '../components/EmptyState';
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User, Calendar, TrendingUp, TrendingDown, ArrowUp, ArrowDown, Zap, BarChart3, Users, Webhook, ChevronDown, ChevronUp, Info, ExternalLink, Minus, CreditCard, ClipboardCheck, Upload, History, Building2, Wrench, ListTodo, LayoutDashboard } from 'lucide-react';
import api, { API_URL } from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import Sparkline from '../components/Sparkline';
import ScoreTrendChart from '../components/ScoreTrendChart';
import { formatRiskLabel, riskLevelToGradeColorMessage, getRiskBandExplanation, getRiskBandExplanationFromScore } from '../utils/riskLabel';
import { UrgencyRow, timingLabelFromDueAtIso } from '../components/client/UrgencyDisplay';
import { requirementLabel, slaStateLabel, riskTypeLabelClient } from '../domain/presentDomain';
import { normalizeRouteId, recordClientPortalInteraction, resolveClientPortalPath, resolvePriorityActionNavigateTarget, resolvePropertyPath } from '../utils/clientPortalNavigation';

const KPI_NO_DATA = 'No data yet';

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
  if (p.nickname && p.nickname.trim()) return p.nickname.trim();
  if (p.address_line_1 && p.postcode) return `${p.address_line_1.trim()}, ${p.postcode.trim()}`;
  if (p.address_line_1 && p.address_line_1.trim()) return p.address_line_1.trim();
  if (p.postcode && p.postcode.trim()) return p.postcode.trim();
  if (p.name && p.name.trim()) return p.name.trim();
  return p.property_id || '';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, logout } = useAuth();
  const { hasFeature } = useEntitlements();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
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
  const [propertiesSort, setPropertiesSort] = useState({ key: 'score', dir: 'asc' });
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
  // Operations data for dashboard KPIs and action queue
  const [workOrdersList, setWorkOrdersList] = useState([]);
  const [predictiveInsightsData, setPredictiveInsightsData] = useState(null);
  const [riskSignalsData, setRiskSignalsData] = useState(null);
  // Priority actions (orchestration/copilot layer)
  const [priorityActions, setPriorityActions] = useState({ actions: [], total: 0 });
  const [openIssuesCountKpi, setOpenIssuesCountKpi] = useState(null);
  const [openIssuesKpiLoading, setOpenIssuesKpiLoading] = useState(false);
  const [maintenanceSpendMonth, setMaintenanceSpendMonth] = useState(null);
  /** undefined = not loaded yet; null = load failed (hide digest card); object = digest payload */
  const [tasksDigest, setTasksDigest] = useState(undefined);
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

  // Only load client dashboard data for client roles with a client_id (staff/owner have client_id null)
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;
  const contractorNetworkEnabled = hasFeature('contractor_network');

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
      clientAPI.getRiskSignals({ limit: 1 })
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

  // Priority actions (orchestration layer) — always fetch when client user
  useEffect(() => {
    if (!isClientUser) return;
    clientAPI.getPriorityActions({ limit: 10 })
      .then((res) => setPriorityActions({ actions: res.data?.actions || [], total: res.data?.total ?? 0 }))
      .catch(() => setPriorityActions({ actions: [], total: 0 }));
  }, [isClientUser]);

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

  // When score trend is in "Property" mode, scope command center + tasks digest to that property (API filter).
  const commandCenterScopePropertyId =
    scoreTrendView === 'property' && selectedTrendPropertyId ? selectedTrendPropertyId : null;
  const commandCenterScopeLabel = useMemo(() => {
    if (!commandCenterScopePropertyId) return null;
    const p = portfolioSummary?.properties?.find((x) => x.property_id === commandCenterScopePropertyId);
    return p ? getPropertyDisplayLabel(p) : commandCenterScopePropertyId;
  }, [commandCenterScopePropertyId, portfolioSummary?.properties]);

  // Command center bundle: digest summary + activity + urgent rows + risks + compliance (one round-trip)
  useEffect(() => {
    if (!isClientUser) {
      setTasksDigest(undefined);
      setCommandCenter(undefined);
      return;
    }
    const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
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
  }, [isClientUser, commandCenterScopePropertyId]);

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
  }, [isClientUser, hasFeature, commandCenterScopePropertyId]);

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
        const params = commandCenterScopePropertyId ? { property_id: commandCenterScopePropertyId } : {};
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
  }, [isClientUser, commandCenterScopePropertyId]);

  const fetchDashboard = async () => {
    try {
      setRestrictReason(null);
      const response = await clientAPI.getDashboard();
      setData(response.data);
      // Defensive: detect missing plan/entitlement (test accounts not fully provisioned)
      const client = response.data?.client;
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
  };

  const completeOnboardingItem = (itemId) => {
    setCompletingItemId(itemId);
    clientAPI.completeOnboardingItem(itemId)
      .then(() => refetchOnboardingChecklist())
      .catch(() => {})
      .finally(() => setCompletingItemId(null));
  };

  // Whether to show the "documents missing" step: requirements that may need docs/confirmation (REQUIRED/UNKNOWN without confirmed expiry)
  const needsDocumentsStep = useMemo(() => {
    if (!requirementsList.length) return false;
    const needsAttention = requirementsList.some(
      (r) => (r.applicability === 'REQUIRED' || (r.applicability || 'UNKNOWN') === 'UNKNOWN') && !r.confirmed_expiry_date
    );
    return needsAttention;
  }, [requirementsList]);

  // Count requirements with a document uploaded but expiry not yet confirmed (for "X documents awaiting confirmation" banner)
  const documentsAwaitingConfirmationCount = useMemo(() => {
    return requirementsList.filter((r) => r.document_id && !r.confirmed_expiry_date).length;
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
    const singleProperty = portfolioSummary?.properties?.length === 1 && portfolioSummary?.portfolio_score != null;
    if (singleProperty) {
      const score = portfolioSummary.portfolio_score;
      const riskLevel = portfolioSummary.risk_level || portfolioSummary.portfolio_risk_level;
      if (riskLevel) {
        const s = (riskLevel || '').trim();
        const { grade, color, message } = s === 'Low Risk'
          ? scoreToGradeColorMessage(score)
          : riskLevelToGradeColorMessage(riskLevel);
        return { score, grade, color, message };
      }
      const { grade, color, message } = scoreToGradeColorMessage(score);
      return { score, grade, color, message };
    }
    if (complianceScore) {
      return { score: complianceScore.score, grade: complianceScore.grade, color: complianceScore.color, message: complianceScore.message };
    }
    return null;
  }, [complianceScore, portfolioSummary]);

  // Actionable missing = requirement rows that are PENDING or OVERDUE (matches Requirements page filter OVERDUE_OR_MISSING)
  // Use this so "Missing evidence" count matches what the user sees when they click through
  const actionableMissingCount = useMemo(() => {
    const pending = complianceScore?.stats?.pending ?? 0;
    const overdue = complianceScore?.stats?.overdue ?? 0;
    if (complianceScore?.stats != null) return pending + overdue;
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
    const total = complianceScore?.stats?.total_requirements ?? (portfolioSummary?.kpis ? (portfolioSummary.kpis.compliant ?? 0) + (portfolioSummary.kpis.overdue ?? 0) + (portfolioSummary.kpis.expiring_30 ?? 0) + (portfolioSummary.kpis.missing ?? 0) : 0);
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
    if (missing > 0) drivers.push(`${missingPct.toFixed(0)}% missing evidence`);
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
  const riskSignalsCount = useMemo(() => {
    if (riskSignalsData?.summary?.total != null) return riskSignalsData.summary.total;
    if (!predictiveInsightsData?.properties?.length) return 0;
    return predictiveInsightsData.properties.reduce((sum, p) => sum + (p.insights?.length || 0), 0);
  }, [riskSignalsData, predictiveInsightsData]);
  const openJobsByProperty = useMemo(() => {
    const map = {};
    workOrdersList.filter((wo) => ['OPEN', 'ASSIGNED'].includes(wo.status)).forEach((wo) => {
      if (wo.property_id) map[wo.property_id] = (map[wo.property_id] || 0) + 1;
    });
    return map;
  }, [workOrdersList]);

  const dashboardFreshness = useMemo(() => {
    if (commandCenter && typeof commandCenter === 'object' && commandCenter.freshness) return commandCenter.freshness;
    if (tasksDigest && typeof tasksDigest === 'object' && tasksDigest.freshness) return tasksDigest.freshness;
    return {};
  }, [commandCenter, tasksDigest]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div data-testid="client-dashboard">
        <ErrorBanner message={error} onRetry={fetchDashboard} retryLabel="Retry" />

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
              {onboardingChecklist?.items?.length > 0 ? (
                <ul className="space-y-3 text-sm text-gray-700">
                  {onboardingChecklist.items.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 p-2 rounded-lg bg-gray-50">
                      <span className="flex items-center gap-2 flex-1">
                        {item.completed_at ? (
                          <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
                        ) : (
                          <ClipboardCheck className="w-4 h-4 text-electric-teal shrink-0" />
                        )}
                        <span className={item.completed_at ? 'text-gray-500 line-through' : ''}>{item.label}</span>
                      </span>
                      <span className="flex items-center gap-2 shrink-0">
                        {!item.completed_at && (
                          <>
                            <Button variant="outline" size="sm" onClick={() => navigate(item.deep_link || '/properties')}>
                              Go
                            </Button>
                            <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => completeOnboardingItem(item.id)} disabled={completingItemId === item.id}>
                              {completingItemId === item.id ? '…' : 'Mark done'}
                            </Button>
                          </>
                        )}
                      </span>
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
                        <span className="font-medium text-midnight-blue">{displayName}</span>
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
                    onClick={() => navigate(item.deep_link || '/properties')}
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

        {/* Welcome – Compliance Command Centre */}
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-2">Compliance Command Centre</h2>
          <p className="text-gray-600">Welcome, {data?.client?.full_name}. Here&apos;s your compliance overview.</p>
          <p className="text-xs text-gray-500 mt-2">This is an evidence-based status summary. It is not legal advice.</p>
        </div>

        {/* Compact top strip: score, grade, risk band, last updated, properties count */}
        {(displayScoreInfo || complianceScore || portfolioSummary) && (
          <div className="mb-6 flex flex-wrap items-center gap-4 py-3 px-4 rounded-xl bg-gray-50 border border-gray-200" data-testid="dashboard-top-strip">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-midnight-blue">
                {formatDashboardScore(displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score)}
              </span>
              <span className="text-gray-500">/100</span>
              <span className={`ml-1 text-lg font-semibold ${
                displayScoreInfo?.color === 'green' ? 'text-green-600' :
                displayScoreInfo?.color === 'amber' ? 'text-amber-600' :
                displayScoreInfo?.color === 'red' ? 'text-red-600' : 'text-gray-600'
              }`}>
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
              <span className="text-xs text-gray-500">{portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0} propert{(portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0) === 1 ? 'y' : 'ies'}</span>
            )}
          </div>
        )}

        {!setupView && isClientUser &&
          (dashboardFreshness?.score_updated_at ||
            dashboardFreshness?.risk_signals_updated_at ||
            dashboardFreshness?.last_automation_score_recalc_at ||
            dashboardFreshness?.last_automation_risk_refresh_at) && (
          <div
            className="mb-4 rounded-lg border border-gray-200 bg-white px-4 py-3 text-xs text-gray-600"
            data-testid="dashboard-freshness-strip"
          >
            <p className="font-medium text-gray-700 mb-1">Data freshness</p>
            <ul className="space-y-1">
              {dashboardFreshness.score_updated_at && (
                <li>
                  Compliance score updated: {new Date(dashboardFreshness.score_updated_at).toLocaleString()}
                  {isTimestampStale(dashboardFreshness.score_updated_at, FRESH_SCORE_STALE_HOURS) && (
                    <span className="ml-2 text-amber-700" title="Snapshot may be outdated; open Command Centre or recalc from admin if needed.">
                      May be outdated
                    </span>
                  )}
                </li>
              )}
              {dashboardFreshness.risk_signals_updated_at && (
                <li>
                  Risk signals updated: {new Date(dashboardFreshness.risk_signals_updated_at).toLocaleString()}
                  {isTimestampStale(dashboardFreshness.risk_signals_updated_at, FRESH_RISK_STALE_HOURS) && (
                    <span className="ml-2 text-amber-700" title="Risk data may be stale.">
                      May be outdated
                    </span>
                  )}
                </li>
              )}
              {dashboardFreshness.last_automation_score_recalc_at && (
                <li className="text-gray-500">
                  Last automated score recalc: {new Date(dashboardFreshness.last_automation_score_recalc_at).toLocaleString()}
                  {isTimestampStale(dashboardFreshness.last_automation_score_recalc_at, FRESH_SCORE_STALE_HOURS) && (
                    <span className="ml-2 text-amber-700" title="Scheduled recalc may be overdue.">
                      May be outdated
                    </span>
                  )}
                </li>
              )}
              {dashboardFreshness.last_automation_risk_refresh_at && (
                <li className="text-gray-500">
                  Last automated risk refresh: {new Date(dashboardFreshness.last_automation_risk_refresh_at).toLocaleString()}
                  {isTimestampStale(dashboardFreshness.last_automation_risk_refresh_at, FRESH_RISK_STALE_HOURS) && (
                    <span className="ml-2 text-amber-700" title="Scheduled risk job may be overdue.">
                      May be outdated
                    </span>
                  )}
                </li>
              )}
            </ul>
          </div>
        )}

        {!setupView && isClientUser && (protectionSnapshotLoading || protectionSnapshot) && (
          <Card
            className="mb-6 border border-gray-200 shadow-sm"
            data-testid="protection-snapshot-card"
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Shield className="w-4 h-4 text-teal-600" />
                Security &amp; continuity snapshot
              </CardTitle>
              <p className="text-xs text-gray-500 mt-1">
                Read-only summary of account activity signals and open operational work. Not legal advice.
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
                      Issues and risk counts are scoped to the selected property; compliance totals are portfolio-wide.
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}

        {/* Executive KPI row (compliance + operations) */}
        {!setupView && (
          <div className="mb-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3" data-testid="executive-kpi-row">
            <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/today')}>
              <CardContent className="p-3 sm:p-4 min-w-0">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Today</p>
                <p className="text-xl font-bold text-midnight-blue">
                  {tasksDigest && typeof tasksDigest === 'object'
                    ? (Number(tasksDigest.summary?.urgent_count ?? 0)
                      + Number(tasksDigest.summary?.upcoming_count ?? 0)
                      + Number(tasksDigest.summary?.in_progress_count ?? 0))
                    : 'Open'}
                </p>
                <p className="text-xs text-electric-teal mt-1">Open Today →</p>
              </CardContent>
            </Card>
            <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/compliance-score')}>
              <CardContent className="p-3 sm:p-4 min-w-0">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Portfolio compliance</p>
                <p className="text-xl font-bold text-midnight-blue">
                  {formatDashboardScore(displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score)}
                </p>
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
                title="Work orders where the agreed response time has passed (current list, up to 500 loaded)."
                onClick={() => navigate('/operations/work-orders?sla_state=breached')}
              >
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Work orders · {slaStateLabel('breached')}</p>
                  <p className="text-xl font-bold text-midnight-blue">{slaBreachedCount}</p>
                  <p className="text-xs text-gray-500 mt-1">{slaStateLabel('near_breach')}: {slaNearBreachCount}</p>
                </CardContent>
              </Card>
            )}
            {hasFeature('predictive_maintenance') && (
              <Card className="cursor-pointer hover:shadow-md transition-shadow min-w-0" onClick={() => navigate('/operations/risk-signals')}>
                <CardContent className="p-3 sm:p-4 min-w-0">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Risk signals</p>
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
                    {new Intl.NumberFormat('en-GB', { style: 'currency', currency: maintenanceSpendMonth.currency || 'GBP' }).format(Number(maintenanceSpendMonth.total_amount ?? 0))}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">Paid invoices · UTC month</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {!setupView && tasksDigest && typeof tasksDigest === 'object' && (
          <Card
            className="mb-6 border border-gray-200 shadow-sm"
            data-testid="tasks-digest-card"
          >
            <CardHeader className="pb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="min-w-0">
                <CardTitle className="text-base flex items-center gap-2 break-words">
                  <ListTodo className="w-4 h-4 text-teal-600 shrink-0" />
                  Today — this week
                </CardTitle>
                {tasksDigest.freshness?.tasks_refreshed_at && (
                  <p className="text-xs text-gray-500 mt-1 break-words">
                    Snapshot refreshed {new Date(tasksDigest.freshness.tasks_refreshed_at).toLocaleString()}
                  </p>
                )}
                {commandCenterScopeLabel && (
                  <p className="text-xs text-electric-teal mt-1 break-words">Scoped to: {commandCenterScopeLabel}</p>
                )}
              </div>
              <Button variant="outline" size="sm" className="shrink-0 w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0" onClick={() => navigate('/today')}>
                Open Today
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3 text-sm">
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Urgent</p>
                  <p className="text-lg font-semibold text-midnight-blue">{tasksDigest.summary?.urgent_count ?? 0}</p>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Upcoming</p>
                  <p className="text-lg font-semibold text-midnight-blue">{tasksDigest.summary?.upcoming_count ?? 0}</p>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">In progress</p>
                  <p className="text-lg font-semibold text-midnight-blue">{tasksDigest.summary?.in_progress_count ?? 0}</p>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Snoozed</p>
                  <p className="text-lg font-semibold text-midnight-blue">{tasksDigest.summary?.snoozed_count ?? 0}</p>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Hidden</p>
                  <p className="text-lg font-semibold text-midnight-blue">{tasksDigest.summary?.hidden_count ?? 0}</p>
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
            </CardContent>
          </Card>
        )}

        {!setupView && isClientUser && (activitySinceLoading || activitySince) && (
          <Card className="mb-6 border border-gray-200 shadow-sm" data-testid="activity-since-card">
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
                  No qualifying changes in audit logs, score snapshots, work orders, or uploads for this window.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {!setupView && commandCenter && typeof commandCenter === 'object' && (
          <Card
            className="mb-6 border border-gray-200 shadow-sm"
            data-testid="command-center-snapshot-card"
          >
            <CardHeader className="pb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
              <div className="min-w-0">
                <CardTitle className="text-base flex items-center gap-2 break-words">
                  <LayoutDashboard className="w-4 h-4 text-teal-600 shrink-0" />
                  Command center snapshot
                </CardTitle>
                {commandCenter.freshness?.tasks_refreshed_at && (
                  <p className="text-xs text-gray-500 mt-1 break-words">
                    Tasks snapshot {new Date(commandCenter.freshness.tasks_refreshed_at).toLocaleString()}
                  </p>
                )}
                {commandCenterScopeLabel && (
                  <p className="text-xs text-electric-teal mt-1 break-words">Scoped to: {commandCenterScopeLabel}</p>
                )}
        </div>
              <Button variant="outline" size="sm" className="shrink-0 w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0" onClick={() => navigate('/today')}>
                Open Today
              </Button>
            </CardHeader>
            <CardContent className="space-y-5">
              {(commandCenter.urgent_actions?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Urgent &amp; in progress</p>
                  <ul className="space-y-2 text-sm">
                    {commandCenter.urgent_actions.slice(0, 6).map((t) => (
                      <li key={t.id || t.title} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                        <button
                          type="button"
                          className="text-left text-midnight-blue hover:underline font-medium min-w-0 break-words"
                          onClick={() => {
                            const url = t.primary_action_url || t.cta_url;
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
              {hasFeature('predictive_maintenance') && (commandCenter.upcoming_risks?.length ?? 0) > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Active risk signals</p>
                  <ul className="space-y-2 text-sm">
                    {commandCenter.upcoming_risks.slice(0, 4).map((r) => (
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
                          {r.description || r.risk_type_label_client || riskTypeLabelClient(r.risk_type) || 'Risk signal'}
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
              {commandCenter.compliance_status_summary && commandCenter.compliance_status_summary.score != null && (
                <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3 text-sm">
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Compliance</p>
                  <p className="font-semibold text-midnight-blue">
                    Grade {formatDashboardGrade(commandCenter.compliance_status_summary.grade)} · Score{' '}
                    {commandCenter.compliance_status_summary.score != null
                      ? Math.round(Number(commandCenter.compliance_status_summary.score))
                      : KPI_NO_DATA}
                  </p>
                  {commandCenter.compliance_status_summary.message && (
                    <p className="text-gray-600 mt-1">{commandCenter.compliance_status_summary.message}</p>
                  )}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-600">
                    {commandCenter.compliance_status_summary.requirements_overdue != null && (
                      <span>Overdue: {commandCenter.compliance_status_summary.requirements_overdue}</span>
                    )}
                    {commandCenter.compliance_status_summary.requirements_expiring_soon != null && (
                      <span>Expiring soon: {commandCenter.compliance_status_summary.requirements_expiring_soon}</span>
                    )}
                  </div>
                </div>
              )}
              {(commandCenter.urgent_actions?.length ?? 0) === 0 &&
                (!hasFeature('predictive_maintenance') || (commandCenter.upcoming_risks?.length ?? 0) === 0) &&
                !(commandCenter.compliance_status_summary && commandCenter.compliance_status_summary.score != null) && (
                  <p className="text-sm text-gray-500">No urgent items in this snapshot. Open tasks for the full inbox.</p>
                )}
            </CardContent>
          </Card>
        )}

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
                {scoreTrendView === 'portfolio' ? 'Calculated across all tracked items' : 'Single property score history'}
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
                    <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">Compliance Score</h3>
                    <ExternalLink className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className={`text-5xl font-bold ${
                      displayScoreInfo?.color === 'green' ? 'text-green-700' :
                      displayScoreInfo?.color === 'amber' ? 'text-amber-700' :
                      displayScoreInfo?.color === 'red' ? 'text-red-700' :
                      'text-gray-700'
                    }`}>
                      {formatDashboardScore(displayScoreInfo?.score ?? complianceScore?.score)}
                    </span>
                    <span className="text-2xl text-gray-400">/100</span>
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
                {complianceScore?.bucket_breakdown ? (
                  <>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Legal core (60%)</span>
                      <span className="font-medium">{Number(complianceScore?.bucket_breakdown?.legal_core?.percent || 0).toFixed(0)}%</span>
                  </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Documentation (20%)</span>
                      <span className="font-medium">{Number(complianceScore?.bucket_breakdown?.documentation_completeness?.percent || 0).toFixed(0)}%</span>
                  </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Operational (10%)</span>
                      <span className="font-medium">{Number(complianceScore?.bucket_breakdown?.operational_responsiveness?.percent || 0).toFixed(0)}%</span>
                </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Recency confidence (10%)</span>
                      <span className="font-medium">{Number(complianceScore?.bucket_breakdown?.recency_maintenance_confidence?.percent || 0).toFixed(0)}%</span>
                    </div>
                  </>
                ) : (
                  <>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Status (40%)</span>
                      <span className="font-medium">{complianceScore?.breakdown?.status_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Timeline (30%)</span>
                      <span className="font-medium">{complianceScore?.breakdown?.expiry_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Documents (15%)</span>
                      <span className="font-medium">{complianceScore?.breakdown?.document_score?.toFixed(0)}%</span>
                </div>
                  </>
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
                  <p className="font-medium text-gray-700">Score Components:</p>
                  <ul className="space-y-1 text-gray-600">
                    {complianceScore?.bucket_breakdown ? (
                      <>
                        <li>• <strong>Legal core (60%):</strong> weighted legal obligations by applicability and validity</li>
                        <li>• <strong>Documentation (20%):</strong> verified evidence completeness for applicable obligations</li>
                        <li>• <strong>Operational (10%):</strong> unresolved issues/work orders reduce confidence</li>
                        <li>• <strong>Recency (10%):</strong> unresolved risk signals and expiring obligations reduce confidence</li>
                      </>
                    ) : (
                      <>
                        <li>• <strong>Status (40%):</strong> {complianceScore?.stats?.compliant || 0}/{complianceScore?.stats?.total_requirements || 0} requirements valid</li>
                        <li>• <strong>Timeline (30%):</strong> {complianceScore?.stats?.expiring_soon || 0} items due within 30 days</li>
                        <li>• <strong>Documents (15%):</strong> {complianceScore?.stats?.document_coverage_percent?.toFixed(0) || 0}% requirement coverage</li>
                        <li>• <strong>Overdue Penalty (15%):</strong> {complianceScore?.stats?.overdue || 0} overdue items</li>
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
                    const actionLower = actionDisplay.toLowerCase();
                    const fixNowPath =
                      actionLower.includes('overdue') ? '/requirements?status=OVERDUE_OR_MISSING' :
                      actionLower.includes('expir') ? '/requirements?window=30&status=DUE_SOON' :
                      actionLower.includes('verif') || actionLower.includes('confirm') ? '/documents' :
                      actionLower.includes('upload') ? '/documents' :
                      '/requirements';
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
                          onClick={(e) => { e.stopPropagation(); navigate(fixNowPath); }}
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
                const displayScore = displayScoreInfo?.score ?? complianceScore?.score ?? 0;
                const allValid = total > 0 && valid === total && actionableMissingCount === 0 && displayScore >= 80;
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
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardCheck className="w-4 h-4 text-electric-teal" />
                Audit readiness
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
                  <CardTitle className="text-base flex items-center gap-2">
                    <Wrench className="w-4 h-4 text-electric-teal" />
                    Work orders
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <span className="font-medium text-amber-700">Open: {workOrderFunnel.open}</span>
                    <span className="font-medium text-blue-700">Assigned: {workOrderFunnel.assigned}</span>
                    <span className="font-medium text-blue-600">In progress: {workOrderFunnel.inProgress}</span>
                    <span className="font-medium text-green-700">Completed: {workOrderFunnel.completed}</span>
                  </div>
                  <Button variant="outline" size="sm" className="mt-3 text-electric-teal border-electric-teal" onClick={() => navigate('/operations/work-orders')}>
                    View all work orders
                  </Button>
                </CardContent>
              </Card>
            )}
            {hasFeature('predictive_maintenance') && (
              <Card className="border border-gray-200 shadow-sm" data-testid="operations-overview-risk">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-electric-teal" />
                    Risk signals
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-midnight-blue">{riskSignalsCount}</p>
                  <p className="text-sm text-gray-500 mt-1">Risk signals across your properties</p>
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

        {/* Priority Actions: ranked next steps from compliance, operations, risk, approvals */}
        {!setupView && priorityActions.actions?.length > 0 && (
          <Card className="mb-8 border-electric-teal/30 bg-white" data-testid="priority-actions-panel">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2 text-midnight-blue">
                <Zap className="w-4 h-4 text-electric-teal" />
                Priority actions
              </CardTitle>
              <p className="text-sm text-gray-600">Most important next steps</p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {priorityActions.actions.map((action, idx) => (
                  <li key={idx} className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4 py-3 border-b border-gray-100 last:border-0">
                    <div className="min-w-0 flex-1">
                      <UrgencyRow
                        urgencyLevel={action.severity || 'medium'}
                        timingLabel={timingLabelFromDueAtIso(action.due_at)}
                        className="mb-1"
                      />
                      <p className="text-sm font-medium text-midnight-blue break-words">{action.title}</p>
                      {action.description && (
                        <p className="text-xs text-gray-600 mt-0.5 line-clamp-3 break-words">{action.description}</p>
                      )}
                    </div>
                    <Button
                      size="sm"
                      className="shrink-0 w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0 bg-electric-teal hover:bg-electric-teal/90"
                      onClick={() => {
                        const target = resolvePriorityActionNavigateTarget(action, '/today');
                        recordClientPortalInteraction('dashboard_priority_action', {
                          target,
                          related_property_id: action.related_property_id ?? null,
                          action_type: action.action_type ?? null,
                        });
                        navigate(target);
                      }}
                    >
                      {action.recommended_action_label || 'View'}
                    </Button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
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
                    <span className="text-sm text-gray-800 min-w-0 break-words">{openIssuesCount} open issue{openIssuesCount !== 1 ? 's' : ''}</span>
                    <Button size="sm" className="w-full sm:w-auto min-h-11 h-11 sm:h-9 sm:min-h-0 bg-electric-teal hover:bg-electric-teal/90 shrink-0" onClick={() => navigate('/operations/issues')}>
                      View issues
                    </Button>
                  </li>
                )}
                {riskSignalsCount > 0 && hasFeature('predictive_maintenance') && (
                  <li className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between py-3 border-b border-amber-200 last:border-0">
                    <span className="text-sm text-gray-800 min-w-0 break-words">{riskSignalsCount} risk signal{riskSignalsCount !== 1 ? 's' : ''} flagged</span>
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
            <div className="px-4 pb-4 pt-0 text-sm text-gray-600 border-t border-gray-100">
              <p className="mb-2">Evidence status is used to derive requirement-level points:</p>
              <ul className="list-disc pl-5 space-y-1 mb-3">
                <li>Valid evidence: 100</li>
                <li>Expiring soon: 70</li>
                <li>Missing evidence: 30</li>
                <li>Overdue: 0</li>
              </ul>
              <p className="mb-2">Property score is the average of requirement scores for that property. Portfolio score is the average across all properties weighted by requirement count.</p>
              <p className="mb-2">Risk levels (evidence-based, not legal advice): 80–100 = Low risk; 60–79 = Medium risk; 40–59 = High risk; 0–39 = Critical risk.</p>
              <p className="text-gray-500 italic">This is an evidence-based status summary. It is not legal advice and does not constitute legal certification.</p>
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
                    <span>Score: {p.property_score ?? p.score ?? 0}/100</span>
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
                    <th className="p-3">Missing evidence</th>
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
                      <td className="p-3">{p.property_score ?? p.score ?? 0}/100</td>
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

        {/* 4 KPI cards: Score+Risk, Overdue, Expiring soon, Missing evidence */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-electric-teal group"
            onClick={() => navigate('/compliance-score')}
            data-testid="tile-score-risk"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Score &amp; Risk</p>
                  <p className="text-3xl font-bold text-midnight-blue">
                    {formatDashboardScore(displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score)}
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
                  <p className="text-sm text-gray-600 mb-1">Overdue</p>
                  <p className="text-3xl font-bold text-red-600">
                    {portfolioSummary?.kpis?.overdue ?? data?.compliance_summary?.overdue ?? 0}
                  </p>
                  <p className="text-xs text-red-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    View →
                  </p>
                </div>
                <XCircle className="w-12 h-12 text-red-600" />
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
                  <p className="text-sm text-gray-600 mb-1">Expiring soon</p>
                  <p className="text-3xl font-bold text-amber-600">
                    {portfolioSummary?.kpis?.expiring_30 ?? data?.compliance_summary?.expiring_soon ?? 0}
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
                  <p className="text-sm text-gray-600 mb-1">Missing evidence</p>
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

        {/* Next Actions: Fix now → /properties/:id#req=code */}
        {(() => {
          const actionStatuses = ['OVERDUE', 'EXPIRED', 'EXPIRING_SOON', 'PENDING', 'MISSING'];
          const properties = data?.properties || [];
          const getPropertyDisplayName = (propertyId) => {
            const p = properties.find((pr) => pr.property_id === propertyId);
            return p ? (p.nickname || p.address_line_1 || (p.postcode ? p.postcode : null) || propertyId) : propertyId;
          };
          const nextItems = requirementsList
            .filter((r) => actionStatuses.includes((r.status || '').toUpperCase()))
            .map((r) => ({
              property_id: r.property_id,
              requirement_code: (r.requirement_code || r.requirement_type || r.requirement_id || '').toString(),
              status: r.status,
              description: r.description || r.requirement_type,
            }))
            .filter((a) => a.property_id && a.requirement_code)
            .slice(0, 10);
          const seen = new Set();
          const deduped = nextItems.filter((a) => {
            const key = `${a.property_id}:${a.requirement_code}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          return deduped.length > 0 ? (
            <Card className="enterprise-card mb-8" data-testid="next-actions-card">
              <CardHeader>
                <CardTitle className="text-midnight-blue">Next Actions</CardTitle>
                <p className="text-sm text-gray-500 mt-1">Items that need evidence or are expiring</p>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {deduped.map((a, i) => (
                    <li key={`${a.property_id}-${a.requirement_code}-${i}`} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                      <span className="text-sm text-gray-700 truncate mr-2">
                        {a.description || requirementLabel(a.requirement_code)} · {getPropertyDisplayName(a.property_id)}
                      </span>
                      <Button
                        size="sm"
                        className="bg-electric-teal hover:bg-electric-teal/90 text-white"
                        onClick={() => navigateToPropertyDashboard(navigate, a.property_id, `req=${encodeURIComponent(a.requirement_code)}`)}
                        data-testid={`fix-now-${a.property_id}-${a.requirement_code}`}
                      >
                        Fix now
                      </Button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null;
        })()}

        {/* Properties: sortable table */}
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <Card className="enterprise-card h-full">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-midnight-blue">Your Properties</CardTitle>
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
              </CardHeader>
              <CardContent>
                {(() => {
                  const tableSource = (portfolioSummary?.properties?.length > 0
                    ? portfolioSummary.properties.map((p) => ({
                        property_id: p.property_id,
                        name: p.name || p.property_id,
                        address_line_1: p.name || p.property_id,
                        city: '',
                        postcode: '',
                        score: p.property_score ?? p.score ?? 0,
                        risk_level: p.risk_level,
                        overdue_count: p.overdue_count ?? 0,
                        expiring_30_count: p.expiring_30_count ?? p.expiring_soon_count ?? 0,
                      }))
                    : (data?.properties || []).map((p) => ({
                        ...p,
                        name: p.nickname || p.address_line_1 || p.property_id,
                        score: null,
                        risk_level: null,
                        overdue_count: null,
                        expiring_30_count: null,
                      }))
                  );
                  if (tableSource.length === 0) {
                    return (
                      <EmptyState
                        icon={FileText}
                        title="No properties found"
                        description="Add properties to track compliance."
                        actionLabel="Import Properties from CSV"
                        onAction={() => navigate('/properties/import')}
                        actionTestId="import-first-property-btn"
                        className="py-6"
                      />
                    );
                  }
                  const sortKey = propertiesSort.key;
                  const dir = propertiesSort.dir === 'asc' ? 1 : -1;
                  const sorted = [...tableSource].sort((a, b) => {
                    const av = a[sortKey] ?? (sortKey === 'name' ? a.address_line_1 : 0);
                    const bv = b[sortKey] ?? (sortKey === 'name' ? b.address_line_1 : 0);
                    if (typeof av === 'string' && typeof bv === 'string') return dir * (av.localeCompare(bv));
                    return dir * ((Number(av) ?? 0) - (Number(bv) ?? 0));
                  });
                  const toggleSort = (key) => {
                    setPropertiesSort((s) => ({ key, dir: s.key === key && s.dir === 'asc' ? 'desc' : 'asc' }));
                  };
                  return (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 text-left text-gray-600">
                            <th className="p-3 cursor-pointer hover:bg-gray-50" onClick={() => toggleSort('name')}>
                              Property {propertiesSort.key === 'name' && (propertiesSort.dir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th className="p-3 cursor-pointer hover:bg-gray-50" onClick={() => toggleSort('score')}>
                              Score {propertiesSort.key === 'score' && (propertiesSort.dir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th className="p-3 cursor-pointer hover:bg-gray-50">Risk</th>
                            <th className="p-3 cursor-pointer hover:bg-gray-50" onClick={() => toggleSort('overdue_count')}>
                              Overdue {propertiesSort.key === 'overdue_count' && (propertiesSort.dir === 'asc' ? '↑' : '↓')}
                            </th>
                            <th className="p-3 cursor-pointer hover:bg-gray-50">Expiring soon</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sorted.map((p) => (
                            <tr
                              key={p.property_id}
                              className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                              onClick={() => navigateToPropertyDashboard(navigate, p.property_id)}
                              data-testid="property-row"
                            >
                              <td className="p-3 font-medium text-midnight-blue">{p.name || p.address_line_1}</td>
                              <td className="p-3">{p.score != null ? `${p.score}/100` : KPI_NO_DATA}</td>
                              <td className="p-3">{p.risk_level ? formatRiskLabel(p.risk_level) : KPI_NO_DATA}</td>
                              <td className="p-3">{p.overdue_count != null ? p.overdue_count : KPI_NO_DATA}</td>
                              <td className="p-3">{p.expiring_30_count != null ? p.expiring_30_count : KPI_NO_DATA}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                  </div>
                  );
                })()}
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
  );
};

export default ClientDashboard;
