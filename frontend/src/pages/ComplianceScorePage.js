import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEntitlements } from '../contexts/EntitlementsContext';
import UpgradePrompt from '../components/UpgradePrompt';
import api from '../api/client';
import { toast } from '@/utils/portalNotifications';
import { 
  TrendingUp,
  ArrowLeft,
  Building2,
  CheckCircle,
  Clock,
  AlertTriangle,
  FileText,
  Info,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Target,
  Calendar,
  RefreshCw,
  Sparkles,
  Zap,
  HelpCircle,
  Download,
  FileDown,
  X,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '../components/ui/tooltip';
import { Skeleton } from '../components/ui/skeleton';
import { recordClientPortalInteraction, resolveClientPortalPath } from '../utils/clientPortalNavigation';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import {
  executeRequirementPrimaryCta,
  GUIDED_CTA_UNAVAILABLE_TITLE,
} from '../utils/requirementCtaParity';
import { projectResolvedRequirementSemantics } from '../utils/resolvedRequirementViewModel';
import { portalPageRoot } from '../components/client/ClientPortalPatterns';
import { cn } from '../lib/utils';
import { requirementDisplayTitle } from '../domain/presentDomain';
import { complianceRequirementStatusLabel } from '../domain/presentDomain';
import { portfolioHasV2BucketBreakdown } from '../utils/complianceScoreBuckets';
import { getTrackedRequirementsForProperty } from '../utils/portalRequirementAttention';
import {
  headlineScoreDisplayForDashboard,
  headlineScoreShowsOutOf100,
} from '../utils/scoringHeadlineDisplay';
import { findRequirementRowForScoreDriver, scoreDriverRowReactKey } from './ComplianceScorePage.driverRemediation';
import { COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE } from '../utils/scoreFreshnessUi';

function scoreDriverStatusLabel(raw) {
  const s = String(raw || '').trim().toUpperCase();
  if (s === 'OVERDUE') return 'Overdue';
  if (s === 'EXPIRING_SOON') return 'Expiring soon';
  if (s === 'MISSING_EVIDENCE') return 'No document uploaded';
  if (s === 'NEEDS_CONFIRMATION') return 'Awaiting verification';
  const lbl = complianceRequirementStatusLabel(s);
  return lbl && lbl !== '—' ? lbl : 'Needs attention';
}

function scoreDriverEvidenceLabel(driver, requirements) {
  const req = findRequirementRowForScoreDriver(requirements, driver);
  const hasTakeAction = !!(req && typeof req.take_action === 'object');
  if (req && hasTakeAction) {
    const sem = projectResolvedRequirementSemantics(req, { pagePropertyId: driver?.property_id || null });
    const status = req.status || driver?.status || 'PENDING';
    return sem.evidenceStatusForStatus(status).text;
  }
  return driver?.evidence_uploaded ? 'Uploaded' : 'Not uploaded';
}

/**
 * Score-driver remediation: only `take_action.primary` shapes that pass
 * {@link requirementUsesServerTakeActionPrimary} may render actionable labels/routes.
 * Heuristic driver `actions` (UPLOAD/VIEW/CONFIRM) are not used for navigation.
 */
function ScoreDriverRemediationActions({ driver, requirements, navigate, openGuidedEvidence }) {
  const req = findRequirementRowForScoreDriver(requirements, driver);
  const hasTakeAction = !!(req && typeof req.take_action === 'object');
  const sem =
    req && hasTakeAction ? projectResolvedRequirementSemantics(req, { pagePropertyId: driver?.property_id || null }) : null;
  const hasCanonical = !!sem?.server_take_action_primary;
  const propertyId = driver?.property_id != null ? String(driver.property_id).trim() : '';

  if (!hasCanonical) {
    return (
      <div
        className="text-xs text-gray-600 max-w-[240px] leading-snug"
        data-testid="score-driver-remediation-non-actionable"
        data-canonical-remediation="0"
      >
        <p>No server-confirmed remediation step is available on this summary.</p>
        {propertyId ? (
          <button
            type="button"
            className="mt-1.5 text-electric-teal hover:underline font-medium text-left"
            data-testid="score-driver-open-property-structural"
            onClick={(e) => {
              e.stopPropagation();
              const target = resolveClientPortalPath(`/properties/${propertyId}`, '/properties');
              recordClientPortalInteraction('compliance_score_open_property_structural', { property_id: propertyId });
              navigate(target);
            }}
          >
            Open property
          </button>
        ) : null}
      </div>
    );
  }

  const ta = sem.cta;

  const onPrimary = (e) => {
    e.stopPropagation();
    if (ta.primary_action_handler === 'guided_evidence_error') return;
    executeRequirementPrimaryCta({
      requirement: req,
      pagePropertyId: propertyId || null,
      navigate: (to) => {
        const raw = typeof to === 'string' ? to : to?.pathname;
        recordClientPortalInteraction('compliance_score_driver_canonical_primary', {
          property_id: propertyId,
          requirement_id: String(req.requirement_id),
        });
        navigate(resolveClientPortalPath(raw, '/properties'));
      },
      openGuidedEvidence,
      guidedInitialOverride: ta.guided_initial_evidence_mode || undefined,
    });
  };

  const onSecondary = (e) => {
    e.stopPropagation();
    const sec = ta.secondary_action;
    if (!sec?.route) return;
    if (sec.external) window.open(sec.route, '_blank', 'noopener,noreferrer');
    else {
      const target = resolveClientPortalPath(sec.route, '/properties');
      navigate(target);
    }
  };

  return (
    <div className="flex flex-wrap gap-1" data-canonical-remediation="1" data-testid="score-driver-canonical-remediation">
      {ta.primary_action_handler === 'guided_evidence_error' ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled
          title={GUIDED_CTA_UNAVAILABLE_TITLE}
          className="border-gray-200 text-gray-500 cursor-not-allowed"
          data-testid="score-driver-canonical-primary"
        >
          {ta.primary_action_label}
        </Button>
      ) : ta.primary_action_handler === 'none' ? (
        <span className="text-xs text-gray-500">{ta.primary_action_label}</span>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-electric-teal text-electric-teal hover:bg-electric-teal/10"
          data-testid="score-driver-canonical-primary"
          onClick={onPrimary}
        >
          {ta.primary_action_label}
        </Button>
      )}
      {ta.secondary_action?.route ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          data-testid="score-driver-canonical-secondary"
          onClick={onSecondary}
        >
          {ta.secondary_action.label}
        </Button>
      ) : null}
    </div>
  );
}

function scoreDriverRequirementTitle(d) {
  if (!d || typeof d !== 'object') return '—';
  return (
    requirementDisplayTitle(d.requirement_display, 'compact') ||
    requirementDisplayTitle(d.requirement_display, 'detail') ||
    d.requirement_name ||
    '—'
  );
}

const ComplianceScorePage = () => {
  const { hasFeature } = useEntitlements();
  const navigate = useNavigate();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const canExportScore = hasFeature('reports_pdf'); // Portfolio and Professional only
  const [scoreData, setScoreData] = useState(null);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [clientData, setClientData] = useState(null);
  const [showMethodology, setShowMethodology] = useState(false);
  const [showDefinitionsModal, setShowDefinitionsModal] = useState(false);
  const [showAdvancedDetails, setShowAdvancedDetails] = useState(false);
  const [driversFilterPropertyId, setDriversFilterPropertyId] = useState(null);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [showExportUpgradeModal, setShowExportUpgradeModal] = useState(false);

  const handleDownloadPdf = async () => {
    if (!canExportScore) {
      setShowExportUpgradeModal(true);
      return;
    }
    setExportingPdf(true);
    try {
      const res = await api.get('/reports/score-explanation.pdf', { responseType: 'blob' });
      const disposition = res.headers['content-disposition'];
      const filename = disposition?.match(/filename="?([^";\n]+)"?/)?.[1] || `compliance_score_summary_${new Date().toISOString().slice(0, 10)}.pdf`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(`Export generated at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      if (err.response?.status === 403) {
        setShowExportUpgradeModal(true);
      } else {
        toast.error('Export failed, please try again');
      }
    } finally {
      setExportingPdf(false);
    }
  };

  const handleDownloadCsv = async () => {
    if (!canExportScore) {
      setShowExportUpgradeModal(true);
      return;
    }
    setExportingCsv(true);
    try {
      const res = await api.get('/reports/score-drivers.csv', {
        responseType: 'blob',
        params: { scoring_metadata: true },
      });
      const disposition = res.headers['content-disposition'];
      const filename = disposition?.match(/filename="?([^";\n]+)"?/)?.[1] || `score_drivers_${new Date().toISOString().slice(0, 10)}.csv`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(`Export generated at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      if (err.response?.status === 403) {
        setShowExportUpgradeModal(true);
      } else {
        toast.error('Export failed, please try again');
      }
    } finally {
      setExportingCsv(false);
    }
  };

  const formatRelativeTime = (iso) => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      const now = new Date();
      const sec = Math.floor((now - d) / 1000);
      if (sec < 60) return 'Just now';
      const min = Math.floor(sec / 60);
      if (min < 60) return `${min} min ago`;
      const hr = Math.floor(min / 60);
      if (hr < 24) return `${hr} hour${hr !== 1 ? 's' : ''} ago`;
      const day = Math.floor(hr / 24);
      if (day < 30) return `${day} day${day !== 1 ? 's' : ''} ago`;
      return d.toLocaleDateString();
    } catch {
      return null;
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [scoreRes, dashboardRes, reqRes] = await Promise.all([
        api.get('/client/compliance-score'),
        api.get('/client/dashboard'),
        api.get('/client/requirements')
      ]);
      setScoreData(scoreRes.data);
      setClientData(dashboardRes.data);
      setProperties(dashboardRes.data.properties || []);
      setRequirements(reqRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  };

  const getPropertyRequirementCounts = (propertyId) => {
    const propertyReqs = getTrackedRequirementsForProperty(propertyId, requirements);
    const compliant = propertyReqs.filter((r) => r.status === 'COMPLIANT').length;
    const expiring = propertyReqs.filter((r) => r.status === 'EXPIRING_SOON').length;
    const overdue = propertyReqs.filter((r) => r.status === 'OVERDUE' || r.status === 'EXPIRED').length;
    return { compliant, expiring, overdue };
  };

  /** Authoritative persisted score from ``property_breakdown`` only (no dashboard property fallback). */
  const resolvePropertyRowScore = (row) => {
    if (row?.score != null && row.score !== '') return Number(row.score);
    return null;
  };

  if (loading) {
    return (
      <TooltipProvider>
        <div className={cn(portalPageRoot, 'py-2 space-y-4')} data-testid="compliance-score-page-loading">
          <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
            <Skeleton className="h-10 w-full sm:w-48" />
            <Skeleton className="h-10 w-full sm:w-44" />
          </div>
          <Card className="border-2 border-gray-200">
            <CardContent className="pt-6">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                  <Skeleton className="w-28 h-28 sm:w-32 sm:h-32 rounded-full shrink-0" />
                  <div className="space-y-2 w-full">
                    <Skeleton className="h-8 w-40 mx-auto sm:mx-0" />
                    <Skeleton className="h-5 w-full max-w-md" />
                    <Skeleton className="h-4 w-3/4" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 sm:gap-4 w-full lg:max-w-xs">
                  <Skeleton className="h-16 sm:h-20 rounded-lg" />
                  <Skeleton className="h-16 sm:h-20 rounded-lg" />
                  <Skeleton className="h-16 sm:h-20 rounded-lg" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <Skeleton className="h-5 w-40" />
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        </div>
      </TooltipProvider>
    );
  }

  const colorClass = scoreData?.color === 'green' ? 'text-green-600' :
                     scoreData?.color === 'amber' ? 'text-amber-600' :
                     scoreData?.color === 'red' ? 'text-red-600' : 'text-gray-600';
  
  const bgColorClass = scoreData?.color === 'green' ? 'bg-green-50 border-green-200' :
                       scoreData?.color === 'amber' ? 'bg-amber-50 border-amber-200' :
                       scoreData?.color === 'red' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200';

  return (
    <TooltipProvider>
    <div className={portalPageRoot} data-testid="compliance-score-page">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between mb-4">
          <h1 className="text-xl sm:text-2xl font-bold text-midnight-blue">Compliance score</h1>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            className="w-full sm:w-auto min-h-11 justify-center"
            onClick={handleDownloadPdf}
            disabled={exportingPdf}
          >
            {exportingPdf ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
            Score summary (PDF)
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full sm:w-auto min-h-11 justify-center"
            onClick={handleDownloadCsv}
            disabled={exportingCsv}
          >
            {exportingCsv ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <FileDown className="w-4 h-4 mr-2" />}
            Score drivers (CSV)
          </Button>
          </div>
        </div>
        {showExportUpgradeModal && (
          <UpgradePrompt
            featureName="Score report exports"
            featureDescription="Download score explanation (PDF) and export score drivers (CSV) are available on Portfolio and Professional plans."
            requiredPlan="PLAN_2_PORTFOLIO"
            requiredPlanName="Portfolio"
            variant="modal"
            onDismiss={() => setShowExportUpgradeModal(false)}
          />
        )}
        {/* Back Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
          className="text-gray-600 hover:text-midnight-blue mb-6"
          data-testid="back-to-dashboard"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        {/* Main Score Card */}
        <Card className={`mb-6 border-2 ${bgColorClass}`}>
          <CardContent className="pt-6">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              {/* Score Display */}
              <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6 text-center sm:text-left min-w-0 w-full lg:w-auto">
                <div className={`w-28 h-28 sm:w-32 sm:h-32 rounded-full border-8 flex items-center justify-center shrink-0 ${
                  scoreData?.color === 'green' ? 'border-green-500 bg-green-100' :
                  scoreData?.color === 'amber' ? 'border-amber-500 bg-amber-100' :
                  scoreData?.color === 'red' ? 'border-red-500 bg-red-100' : 'border-gray-300 bg-gray-100'
                }`}>
                  <div className="text-center">
                    <p className={`text-4xl font-bold ${colorClass}`}>
                      {headlineScoreDisplayForDashboard(scoreData?.score, scoreData?.score_status)}
                    </p>
                    {headlineScoreShowsOutOf100(scoreData?.score, scoreData?.score_status) ? (
                      <p className="text-sm text-gray-500">/100</p>
                    ) : null}
                  </div>
                </div>
                <div className="min-w-0 w-full sm:flex-1">
                  <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 mb-1">
                    <span className={`text-3xl font-bold ${colorClass}`}>Grade {scoreData?.grade ?? '—'}</span>
                    <Target className={`w-6 h-6 ${colorClass}`} />
                    {scoreData?.score_last_calculated_at && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-sm font-normal text-gray-500">
                            Last recalculated: {formatRelativeTime(scoreData.score_last_calculated_at)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>{scoreData.score_last_calculated_at}</TooltipContent>
                      </Tooltip>
                    )}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium">
                          Portfolio score
                          <HelpCircle className="w-3.5 h-3.5" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        Overall score is the simple average of each property&apos;s stored compliance score (each already 0–100).
                      </TooltipContent>
                    </Tooltip>
                    {scoreData?.data_completeness_percent != null ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-50 text-teal-800 text-xs font-medium">
                            Data completeness: {scoreData.data_completeness_percent}%
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          Completeness is the percentage of applicable tracked items with verified documents and dates confirmed.
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-100 text-gray-500 text-xs font-medium">
                            Data completeness: —
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>Not yet calculated</TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                  <p className="text-lg text-gray-700">{scoreData?.message}</p>
                  {scoreData?.score_status && (
                    <p className="text-xs text-gray-600 mt-1">
                      Score status: {scoreData.score_status}
                      {(scoreData.last_calculated_at || scoreData.portfolio_last_calculated_at) && (
                        <>
                          {' '}
                          · Last calculated:{' '}
                          {new Date(scoreData.last_calculated_at || scoreData.portfolio_last_calculated_at).toLocaleString()}
                        </>
                      )}
                    </p>
                  )}
                  {scoreData?.score_status_message && String(scoreData.score_status_message).trim() ? (
                    <p
                      className="text-xs text-gray-800 bg-gray-50 border border-gray-200 rounded-md px-2 py-1.5 mt-2 leading-snug"
                      data-testid="compliance-score-status-message"
                    >
                      {String(scoreData.score_status_message).trim()}
                    </p>
                  ) : null}
                  <p className="text-sm text-gray-600 mt-1">
                    Informational indicator based on portal records. Not legal advice.
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    Based on {scoreData?.stats?.total_requirements ?? 0} tracked items across {scoreData?.properties_count ?? 0} {scoreData?.properties_count === 1 ? 'property' : 'properties'}.
                    {scoreData?.properties_count != null && scoreData.properties_count > 1 && (
                      <span className="block mt-0.5">Your overall score is the average of each property&apos;s score.</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-2 sm:gap-4 w-full lg:max-w-md min-w-0">
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-green-600">{scoreData?.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-600">Valid</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-amber-600">{scoreData?.stats?.expiring_soon || 0}</p>
                  <p className="text-xs text-gray-600">Expiring Soon</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-red-600">{scoreData?.stats?.overdue || 0}</p>
                  <p className="text-xs text-gray-600">Overdue</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Score scope & definitions block */}
        <Card className="mb-8">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-midnight-blue">Score scope</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-700">
            <ul className="list-disc list-inside space-y-1">
              <li><strong>What&apos;s included:</strong> Applicable tracked items for each property (e.g., Gas Safety, EICR, EPC, Licence if configured).</li>
              <li><strong>What&apos;s excluded:</strong> Council-specific rules unless configured. Optional uploads not tracked. Evidence not uploaded/confirmed.</li>
              <li><strong>How &apos;tracked items&apos; are counted:</strong> An item is tracked only if marked applicable for this property.</li>
              <li><strong>How it updates:</strong> Recalculates automatically when documents, dates, applicability, or status changes.</li>
            </ul>
            <button
              type="button"
              onClick={() => setShowDefinitionsModal(true)}
              className="text-electric-teal hover:underline font-medium text-sm mt-2"
            >
              View definitions
            </button>
          </CardContent>
        </Card>

        {/* How Score is Calculated - Expandable */}
        <Card className="mb-8" data-testid="score-methodology">
          <CardHeader 
            className="cursor-pointer hover:bg-gray-50"
            onClick={() => setShowMethodology(!showMethodology)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Info className="w-5 h-5 text-electric-teal" />
                How This Score is Calculated
              </CardTitle>
              {showMethodology ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showMethodology && (
            <CardContent className="border-t">
              <div className="space-y-6">
                {scoreData?.properties_count != null && scoreData.properties_count > 1 && (
                  <p className="text-sm text-gray-600 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <strong>Multiple properties:</strong> Your overall score is the average of each property&apos;s score. Each property has its own score from its requirements and documents; the number shown is the average across all {scoreData.properties_count} properties.
                  </p>
                )}
                <p className="text-sm text-gray-700">
                  Each applicable tracked item carries a weight (by requirement type and jurisdiction). Those weighted contributions roll up
                  into your property score; the headline number is built from the same engine as the rest of the portal — not from a
                  hand-tuned percentage split shown here.
                </p>
                {portfolioHasV2BucketBreakdown(scoreData?.bucket_breakdown) ? (
                  <div>
                    <h4 className="font-semibold text-midnight-blue mb-3">Score components</h4>
                    <p className="text-xs text-gray-600 mb-3">
                      Values are how much credit you are earning within each bucket (0–100%), averaged across properties that have a
                      current breakdown — not the model&apos;s bucket emphasis (that is described under Advanced details).
                    </p>
                    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-blue-700">Legal core</span>
                          <span className="text-lg font-bold text-blue-700">
                            {Number(scoreData.bucket_breakdown.legal_core.percent).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-blue-600">Weighted legal obligations: validity, coverage, and expiry signals.</p>
                      </div>
                      <div className="p-4 bg-teal-50 rounded-lg border border-teal-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-teal-700">Verified documentation</span>
                          <span className="text-lg font-bold text-teal-700">
                            {Number(scoreData.bucket_breakdown.documentation_completeness.percent).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-teal-600">Share of applicable items with verified evidence.</p>
                      </div>
                      <div className="p-4 bg-amber-50 rounded-lg border border-amber-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-amber-800">Operational responsiveness</span>
                          <span className="text-lg font-bold text-amber-800">
                            {Number(scoreData.bucket_breakdown.operational_responsiveness.percent).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-amber-800/90">Open issues and overdue maintenance work reduce this bucket.</p>
                      </div>
                      <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-purple-700">Recency &amp; maintenance confidence</span>
                          <span className="text-lg font-bold text-purple-700">
                            {Number(scoreData.bucket_breakdown.recency_maintenance_confidence.percent).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-purple-600">Predictive and expiring-soon pressure on maintenance confidence.</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <h4 className="font-semibold text-midnight-blue mb-2">Score components</h4>
                    <p className="text-sm text-gray-700">
                      A per-bucket breakdown (legal core, verified documentation, operational responsiveness, recency) will appear here
                      after each property has been scored on the current model. Your headline score and drivers still reflect the current
                      engine.
                    </p>
                  </div>
                )}

                {/* Advanced details accordion */}
                <div className="border-t pt-4">
                  <button
                    type="button"
                    onClick={() => setShowAdvancedDetails(!showAdvancedDetails)}
                    className="flex items-center gap-2 text-sm font-medium text-midnight-blue hover:underline"
                  >
                    {showAdvancedDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    Advanced details
                  </button>
                  {showAdvancedDetails && (
                    <div className="mt-3 p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700 space-y-2">
                      <p>
                        Property scores use weighted requirements, evidence validity, and expiry — not a single public points table. Credit
                        per obligation is a fraction of that requirement&apos;s weight (varies by jurisdiction and type). Document-based
                        paths can use different status fractions than requirement-row paths; there is no fixed &quot;100 / 70 / 30 / 0&quot;
                        schedule for every case.
                      </p>
                      <p>
                        Current engine groups credit into four buckets with approximate emphasis: roughly <strong>60%</strong> legal core,{' '}
                        <strong>20%</strong> verified documentation, <strong>10%</strong> operational responsiveness, <strong>10%</strong>{' '}
                        recency / maintenance confidence. Exact points depend on your data; the split is a design guide, not a rigid
                        formula you can reconstruct from counts alone.
                      </p>
                      <p>Verified evidence counts toward the documentation bucket; uploads alone may not.</p>
                      <p>Portfolio score: average of property scores shown for your account.</p>
                      {(scoreData?.score_model_version || scoreData?.model_updated_at) && (
                        <p className="pt-2 border-t border-gray-200 font-medium">
                          Model: CVP Score v{scoreData.score_model_version ?? '—'}. Model updated: {scoreData.model_updated_at ?? '—'}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Concrete Breakdown */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold text-midnight-blue mb-3">Your Current Status</h4>
                  <div className="grid md:grid-cols-3 gap-4 text-sm">
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                      <div>
                        <p className="font-medium">Valid tracked items</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.compliant || 0}/{scoreData?.stats?.total_requirements || 0} tracked items currently valid
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <Clock className="w-5 h-5 text-amber-600" />
                      <div>
                        <p className="font-medium">Expiry Timeline</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.expiring_soon ?? 0} items due within 30 days
                          {scoreData?.stats?.days_until_next_expiry != null && (
                            <span className="block text-xs">
                              Next expiry: {scoreData.stats.days_until_next_expiry} days
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">Overdue items are not counted as &apos;due soon&apos; because their due date has already passed.</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <FileText className="w-5 h-5 text-teal-600" />
                      <div>
                        <p className="font-medium">Documents</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.documents_uploaded ?? 0} documents uploaded
                          <span className="block text-xs">
                            {(scoreData?.stats?.verified_coverage_percent ?? scoreData?.stats?.document_coverage_percent) != null ? `${Number(scoreData.stats.verified_coverage_percent ?? scoreData.stats.document_coverage_percent).toFixed(0)}%` : '—'} tracked item coverage
                          </span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Score drivers */}
        <Card className="mb-8" id="score-drivers">
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-electric-teal" />
              Score drivers (what is affecting your score)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(scoreData?.drivers?.length ?? 0) > 0 ? (
              <p
                className="text-xs text-gray-600 mb-3 leading-snug"
                data-testid="compliance-score-drivers-persisted-note"
              >
                {COMPLIANCE_SCORE_DRIVERS_VS_HEADLINE_NOTE}
              </p>
            ) : null}
            {!(scoreData?.drivers?.length) ? (
              <p className="text-gray-500 py-6 text-center">No issues detected based on current portal records.</p>
            ) : (
              <>
                {scoreData.drivers.some(d => !d.property_id || !d.requirement_id) && (
                  <p className="text-sm text-gray-600 mb-3">Some drivers may be hidden until a document is uploaded or dates are confirmed.</p>
                )}
                {/* Desktop: table */}
                <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0" data-testid="score-drivers-table-desktop">
                  <div className="min-w-[640px] md:min-w-0">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-gray-600 font-medium">
                          <th className="py-2 pr-2">Requirement</th>
                          <th className="py-2 pr-2">Property</th>
                          <th className="py-2 pr-2">Status</th>
                          <th className="py-2 pr-2">Date used</th>
                          <th className="py-2 pr-2">Evidence</th>
                          <th className="py-2 pl-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(driversFilterPropertyId ? scoreData.drivers.filter(d => d.property_id === driversFilterPropertyId) : scoreData.drivers).map((d, idx) => (
                          <tr key={scoreDriverRowReactKey(d, idx)} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="py-3 pr-2">{scoreDriverRequirementTitle(d)}</td>
                            <td className="py-3 pr-2">{d.property_name || d.property_id || '—'}</td>
                            <td className="py-3 pr-2">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                d.status === 'OVERDUE' ? 'bg-red-100 text-red-700' :
                                d.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-700' :
                                d.status === 'MISSING_EVIDENCE' ? 'bg-orange-100 text-orange-700' :
                                d.status === 'NEEDS_CONFIRMATION' ? 'bg-amber-100 text-amber-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {scoreDriverStatusLabel(d.status)}
                              </span>
                            </td>
                            <td className="py-3 pr-2">
                              {d.date_used ? new Date(d.date_used).toLocaleDateString() : '—'}
                              {d.date_confidence && d.date_confidence !== 'UNKNOWN' && (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span className="ml-1 text-gray-400" title={d.date_confidence}>{d.date_confidence === 'VERIFIED' ? '✓' : '?'}</span>
                                  </TooltipTrigger>
                                  <TooltipContent>{d.date_confidence}</TooltipContent>
                                </Tooltip>
                              )}
                            </td>
                            <td className="py-3 pr-2">{scoreDriverEvidenceLabel(d, requirements)}</td>
                            <td className="py-3 pl-2">
                              <ScoreDriverRemediationActions
                                driver={d}
                                requirements={requirements}
                                navigate={navigate}
                                openGuidedEvidence={openGuidedEvidence}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {/* Mobile: stacked cards */}
                <div className="md:hidden space-y-3" data-testid="score-drivers-cards-mobile">
                  {(driversFilterPropertyId ? scoreData.drivers.filter(d => d.property_id === driversFilterPropertyId) : scoreData.drivers).map((d, idx) => (
                    <div key={scoreDriverRowReactKey(d, idx)} className="p-4 border rounded-lg bg-gray-50 space-y-3">
                      <p className="font-medium text-midnight-blue">{scoreDriverRequirementTitle(d)}</p>
                      <p className="text-sm text-gray-600">{d.property_name || d.property_id}</p>
                      <p className="text-sm">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          d.status === 'OVERDUE' ? 'bg-red-100 text-red-700' :
                          d.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-700' :
                          d.status === 'MISSING_EVIDENCE' ? 'bg-orange-100 text-orange-700' :
                          d.status === 'NEEDS_CONFIRMATION' ? 'bg-amber-100 text-amber-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {scoreDriverStatusLabel(d.status)}
                        </span>
                        {' · '}
                        {d.date_used ? new Date(d.date_used).toLocaleDateString() : '—'} · {scoreDriverEvidenceLabel(d, requirements)}
                      </p>
                      <div className="flex flex-col gap-2 pt-1">
                        <ScoreDriverRemediationActions
                          driver={d}
                          requirements={requirements}
                          navigate={navigate}
                          openGuidedEvidence={openGuidedEvidence}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex justify-end">
                  {driversFilterPropertyId && (
                    <Button variant="ghost" size="sm" onClick={() => setDriversFilterPropertyId(null)}>
                      Clear filter
                    </Button>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        {scoreData?.recommendations?.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Zap className="w-5 h-5 text-electric-teal" />
                Actions to Improve Your Score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {scoreData.recommendations.map((rec, idx) => {
                  const pri = (rec.priority != null && rec.priority !== '') ? String(rec.priority).toLowerCase() : 'low';
                  return (
                  <div 
                    key={idx}
                    className={`flex items-start gap-3 p-4 rounded-lg border ${
                      pri === 'high' || pri === 'critical' ? 'bg-red-50 border-red-200' :
                      pri === 'medium' ? 'bg-amber-50 border-amber-200' :
                      'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                      pri === 'high' || pri === 'critical' ? 'bg-red-500' :
                      pri === 'medium' ? 'bg-amber-500' :
                      'bg-gray-400'
                    }`} />
                    <div className="flex-1">
                      <p className="font-medium text-gray-800">{rec.action || '—'}</p>
                      <p className="text-sm text-gray-500 mt-1">Potential impact: {rec.impact != null && rec.impact !== '' ? rec.impact : '—'}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      pri === 'high' || pri === 'critical' ? 'bg-red-100 text-red-700' :
                      pri === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {pri.toUpperCase()}
                    </span>
                  </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Per-Property Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <Building2 className="w-5 h-5 text-electric-teal" />
              Score by Property
            </CardTitle>
          </CardHeader>
          <CardContent>
            {properties.length === 0 && (!scoreData?.property_breakdown?.length) ? (
              <p className="text-gray-500 text-center py-8">No properties to display</p>
            ) : (
              <div className="space-y-4">
                {(scoreData?.property_breakdown?.length ? scoreData.property_breakdown : properties.map((p) => {
                  const c = getPropertyRequirementCounts(p.property_id);
                  return {
                    property_id: p.property_id,
                    name: p.nickname || p.address_line_1,
                    postcode: p.postcode,
                    score: p.compliance_score,
                    valid: c.compliant,
                    expiring: c.expiring,
                    overdue: c.overdue,
                  };
                })).map((row, rowIdx) => {
                  const counts = getPropertyRequirementCounts(row.property_id);
                  const score = resolvePropertyRowScore(row);
                  const valid = row.valid ?? counts.compliant;
                  const expiring = row.expiring ?? counts.expiring;
                  const overdue = row.overdue ?? counts.overdue;
                  const propertyColor =
                    score == null ? 'gray' : score >= 80 ? 'green' : score >= 40 ? 'amber' : 'red';
                  const rowPropertyId = row.property_id != null && String(row.property_id).trim() !== '' && String(row.property_id) !== 'undefined'
                    ? String(row.property_id).trim()
                    : null;
                  return (
                    <div
                      key={rowPropertyId || `row-${rowIdx}`}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                      data-testid={rowPropertyId ? `property-score-${rowPropertyId}` : `property-score-missing-${rowIdx}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                          propertyColor === 'green' ? 'bg-green-100' :
                          propertyColor === 'amber' ? 'bg-amber-100' :
                          propertyColor === 'red' ? 'bg-red-100' : 'bg-gray-100'
                        }`}>
                          <Building2 className={`w-6 h-6 ${
                            propertyColor === 'green' ? 'text-green-600' :
                            propertyColor === 'amber' ? 'text-amber-600' :
                            propertyColor === 'red' ? 'text-red-600' : 'text-gray-500'
                          }`} />
                        </div>
                        <div>
                          <h4 className="font-semibold text-midnight-blue">
                            {row.name || 'Property'}
                          </h4>
                          <p className="text-sm text-gray-500">{row.postcode || ''}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${valid > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {valid} valid
                          </span>
                          {expiring > 0 && (
                            <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                              {expiring} expiring
                            </span>
                          )}
                          {overdue > 0 && (
                            <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700">
                              {overdue} overdue
                            </span>
                          )}
                        </div>
                        <div className={`text-2xl font-bold ${
                          propertyColor === 'green' ? 'text-green-600' :
                          propertyColor === 'amber' ? 'text-amber-600' :
                          propertyColor === 'red' ? 'text-red-600' : 'text-gray-500'
                        }`}>
                          {headlineScoreDisplayForDashboard(row.score, row.score_status)}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            disabled={!rowPropertyId}
                            onClick={() => {
                              if (!rowPropertyId) return;
                              setDriversFilterPropertyId(rowPropertyId);
                              document.getElementById('score-drivers')?.scrollIntoView({ behavior: 'smooth' });
                            }}
                            className={`text-sm ${rowPropertyId ? 'text-electric-teal hover:underline' : 'text-gray-400 cursor-not-allowed'}`}
                          >
                            View drivers
                          </button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!rowPropertyId}
                            onClick={() => {
                              if (!rowPropertyId) return;
                              const target = resolveClientPortalPath(`/properties/${rowPropertyId}`, '/properties');
                              recordClientPortalInteraction('compliance_score_view_property', { property_id: rowPropertyId, target });
                              navigate(target);
                            }}
                          >
                            View property dashboard
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Definitions modal */}
        {showDefinitionsModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowDefinitionsModal(false)}>
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full portal-modal-scroll p-6" onClick={e => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-midnight-blue">Definitions</h3>
                <button type="button" onClick={() => setShowDefinitionsModal(false)} className="p-1 rounded hover:bg-gray-100">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <dl className="space-y-3 text-sm text-gray-700">
                <div>
                  <dt className="font-medium text-gray-900">Valid</dt>
                  <dd>Tracked item is current and within date; documents verified where required.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Expiring Soon</dt>
                  <dd>Due date or expiry falls within the configured window (e.g. 30–60 days).</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Overdue</dt>
                  <dd>Due date or expiry has passed; action needed.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Applicable vs Not applicable</dt>
                  <dd>An item is applicable if it is required for this property (e.g. Gas Safety for a gas-equipped property). Not applicable items are excluded from the score.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Date confidence (Verified vs Unverified)</dt>
                  <dd>Verified: date has been confirmed from document or manual entry. Unverified: date is estimated or not yet confirmed.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Tracked item</dt>
                  <dd>A requirement type (e.g. Gas Safety, EICR) that is marked applicable for a property and counted in the score.</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
    </div>
    </TooltipProvider>
  );
};

export default ComplianceScorePage;
