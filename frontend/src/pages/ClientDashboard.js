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
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User, Calendar, TrendingUp, TrendingDown, ArrowUp, ArrowDown, Zap, BarChart3, Users, Webhook, ChevronDown, ChevronUp, Info, ExternalLink, Minus, CreditCard, ClipboardCheck, Upload, History, Building2 } from 'lucide-react';
import api, { API_URL } from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import Sparkline from '../components/Sparkline';
import ScoreTrendChart from '../components/ScoreTrendChart';
import { formatRiskLabel, riskLevelToGradeColorMessage, getRiskBandExplanation, getRiskBandExplanationFromScore } from '../utils/riskLabel';

const SETUP_CHECKLIST_DONE_KEY = 'pleerity_setup_checklist_done';
const SETUP_INCOMPLETE_KEY = 'pleerity_setup_incomplete';

/** Map 0-100 score to grade/color/message (matches backend risk_bands). Use when displaying portfolio score for single-property consistency. */
function scoreToGradeColorMessage(score) {
  if (score == null || typeof score !== 'number') return { grade: '—', color: 'gray', message: '' };
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

  // Only load client dashboard data for client roles with a client_id (staff/owner have client_id null)
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

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
    // Intentionally depend only on role/client_id; fetch functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, user?.role, user?.client_id]);

  // Refetch score trend card when user switches Portfolio vs Property or selects another property
  useEffect(() => {
    if (!isClientUser) return;
    fetchScoreTrendCard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, scoreTrendView, selectedTrendPropertyId]);

  // Refetch score trend and "What Changed" when user returns to the dashboard tab so the graph updates after recalc
  useEffect(() => {
    if (!isClientUser) return;
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchScoreTimeline();
        fetchScoreTrendCard();
        fetchScoreChanges();
        fetchComplianceScore();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser]);

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

  // First-login: show setup checklist when ?first_login=1 and user has not completed/dismissed it
  const firstLogin = searchParams.get('first_login') === '1' || searchParams.get('first_login') === 'true';
  useEffect(() => {
    if (!isClientUser || loading || restrictReason) return;
    try {
      const checklistDone = sessionStorage.getItem(SETUP_CHECKLIST_DONE_KEY) === 'true';
      const incomplete = sessionStorage.getItem(SETUP_INCOMPLETE_KEY) === 'true';
      setSetupChecklistSeen(incomplete);
      if (firstLogin && !checklistDone && setupView === null) {
        setSetupView('checklist');
      }
    } catch (e) {
      // sessionStorage not available (e.g. private mode)
    }
  }, [isClientUser, loading, restrictReason, firstLogin, setupView]);

  const dismissSetupChecklist = (markIncomplete = false) => {
    try {
      sessionStorage.setItem(SETUP_CHECKLIST_DONE_KEY, 'true');
      if (markIncomplete) sessionStorage.setItem(SETUP_INCOMPLETE_KEY, 'true');
      else sessionStorage.removeItem(SETUP_INCOMPLETE_KEY);
      setSetupChecklistSeen(markIncomplete);
    } catch (e) {}
    setSetupView(null);
    setSearchParams({}, { replace: true });
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

        {/* First-login guided activation: Setup Checklist / Portfolio / Documents */}
        {setupView === 'checklist' && (
          <Card className="max-w-2xl mx-auto mt-8 border-2 border-electric-teal/30 shadow-lg" data-testid="setup-checklist-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-2xl text-midnight-blue">Welcome to Compliance Vault Pro</CardTitle>
              <p className="text-sm text-gray-600 mt-1">Complete these steps to get an accurate compliance overview. You can also skip and return later.</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm text-gray-700">
                <li className="flex items-center gap-2"><ClipboardCheck className="w-4 h-4 text-electric-teal" /> Confirm your portfolio details</li>
                <li className="flex items-center gap-2"><Upload className="w-4 h-4 text-electric-teal" /> Upload or confirm documents</li>
                <li className="flex items-center gap-2"><FileText className="w-4 h-4 text-electric-teal" /> Confirm certificate dates</li>
                <li className="flex items-center gap-2"><Bell className="w-4 h-4 text-electric-teal" /> Turn on reminders</li>
                <li className="flex items-center gap-2"><Shield className="w-4 h-4 text-electric-teal" /> View your compliance report</li>
              </ul>
              <div className="flex flex-wrap gap-3 pt-4">
                <Button onClick={() => setSetupView('portfolio')} className="bg-electric-teal hover:bg-electric-teal/90" data-testid="setup-start-btn">
                  Start Setup
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
        {/* Persistent banner when user skipped setup or chose "upload later" */}
        {setupChecklistSeen && (
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
        {!setupChecklistSeen && documentsAwaitingConfirmationCount > 0 && (
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
              <span className="text-2xl font-bold text-midnight-blue">{displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score ?? '—'}</span>
              <span className="text-gray-500">/100</span>
              <span className={`ml-1 text-lg font-semibold ${
                displayScoreInfo?.color === 'green' ? 'text-green-600' :
                displayScoreInfo?.color === 'amber' ? 'text-amber-600' :
                displayScoreInfo?.color === 'red' ? 'text-red-600' : 'text-gray-600'
              }`}>
                Grade {displayScoreInfo?.grade ?? complianceScore?.grade ?? '—'}
              </span>
            </div>
            <span className="text-sm text-gray-600">
              {formatRiskLabel(portfolioSummary?.risk_level) || displayScoreInfo?.message || complianceScore?.message || '—'}
            </span>
            {portfolioSummary?.updated_at && (
              <span className="text-xs text-gray-500">Updated {new Date(portfolioSummary.updated_at).toLocaleString()}</span>
            )}
            {(portfolioSummary?.properties?.length != null || complianceScore?.properties_count != null) && (
              <span className="text-xs text-gray-500">{portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0} propert{(portfolioSummary?.properties?.length ?? complianceScore?.properties_count ?? 0) === 1 ? 'y' : 'ies'}</span>
            )}
          </div>
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
                            if (item.document_id && item.property_id) navigate(`/documents?property_id=${item.property_id}`);
                            else if (item.requirement_id && item.property_id) navigate(`/requirements?property_id=${item.property_id}`);
                            else if (item.property_id) navigate(`/properties/${item.property_id}`);
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
                      {displayScoreInfo?.score ?? complianceScore?.score}
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
                    {displayScoreInfo?.grade ?? complianceScore?.grade}
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
                    <li>• <strong>Status (40%):</strong> {complianceScore?.stats?.compliant || 0}/{complianceScore?.stats?.total_requirements || 0} requirements valid</li>
                    <li>• <strong>Timeline (30%):</strong> {complianceScore?.stats?.expiring_soon || 0} items due within 30 days</li>
                    <li>• <strong>Documents (15%):</strong> {complianceScore?.stats?.document_coverage_percent?.toFixed(0) || 0}% requirement coverage</li>
                    <li>• <strong>Overdue Penalty (15%):</strong> {complianceScore?.stats?.overdue || 0} overdue items</li>
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
                    const actionLower = (rec.action || '').toLowerCase();
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
                          <p className="text-sm font-medium text-gray-800">{rec.action}</p>
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
                    {complianceScore?.stats?.days_until_next_expiry !== null && complianceScore?.stats?.days_until_next_expiry !== undefined ? complianceScore?.stats?.days_until_next_expiry : '—'}
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-600">
                    <th className="p-3">Property</th>
                    <th className="p-3">Score</th>
                    <th className="p-3">Risk level</th>
                    <th className="p-3">Overdue</th>
                    <th className="p-3">Expiring soon</th>
                    <th className="p-3">Missing evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolioSummary.properties.map((p) => (
                    <tr
                      key={p.property_id}
                      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                      onClick={() => navigate(`/properties/${p.property_id}`)}
                    >
                      <td className="p-3 font-medium text-midnight-blue">{p.name || p.property_id}</td>
                      <td className="p-3">{p.property_score ?? p.score ?? 0}/100</td>
                      <td className="p-3">{formatRiskLabel(p.risk_level)}</td>
                      <td className="p-3">{p.overdue_count ?? 0}</td>
                      <td className="p-3">{p.expiring_30_count ?? p.expiring_soon_count ?? 0}</td>
                      <td className="p-3">{p.missing_count ?? 0}</td>
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
                    {displayScoreInfo?.score ?? complianceScore?.score ?? portfolioSummary?.portfolio_score ?? '—'}
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
                        {a.description || a.requirement_code} · {getPropertyDisplayName(a.property_id)}
                      </span>
                      <Button
                        size="sm"
                        className="bg-electric-teal hover:bg-electric-teal/90 text-white"
                        onClick={() => navigate(`/properties/${a.property_id}#req=${encodeURIComponent(a.requirement_code)}`)}
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
                              onClick={() => navigate(`/properties/${p.property_id}`)}
                              data-testid="property-row"
                            >
                              <td className="p-3 font-medium text-midnight-blue">{p.name || p.address_line_1}</td>
                              <td className="p-3">{p.score != null ? `${p.score}/100` : '—'}</td>
                              <td className="p-3">{p.risk_level ? formatRiskLabel(p.risk_level) : '—'}</td>
                              <td className="p-3">{p.overdue_count ?? '—'}</td>
                              <td className="p-3">{p.expiring_30_count ?? '—'}</td>
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
