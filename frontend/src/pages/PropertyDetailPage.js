import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import apiClient, { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Alert, AlertDescription } from '../components/ui/alert';
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
  Layers,
  Package,
  BarChart3,
  Eye,
  Download,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { getFeatureDisplayInfo } from '../components/UpgradePrompt';
import { DiscoverabilityHint } from '../components/client/PlanGatingDiscoverability';
import { projectResolvedRequirementSemantics } from '../utils/resolvedRequirementViewModel';
import { formatRiskLabel } from '../utils/riskLabel';
import { humanRiskType, humanSeverity, humanAction, humanizeRiskReasonBullet } from '../utils/riskPresentation';
import { presentPropertyTimelineItem, presentScoreChangeReason } from '../utils/timelinePresent';
import {
  clientCurrentUpdateSummary,
  jobPreviewManageJobCtaLabel,
  jobPreviewNextStepLine,
  maintenanceWorkOrderPreviewDecision,
  workOrderKindBadgeClassName,
  workOrderKindClientLabel,
} from '../utils/jobWorkflowUi';
import {
  requirementTitleFromRow,
  requirementLabel,
  normalizeRequirementCode,
  documentTypeLabel,
  issueStatusLabel,
  requirementDocumentUploadLabel,
  workOrderStatusLabel,
  predictiveIssueStatusLabel,
} from '../domain/presentDomain';
import {
  buildNeedsAttentionSubset,
  isRequirementMissingDocument,
  listRequirementsMissingDocumentsSorted,
  sortRequirementsCriticalityThenTitle,
  sortRequirementsAttentionOrder,
} from '../utils/propertyDocumentsMatrix';
import { suppressMarkNotApplicableCta } from '../utils/clientApplicabilityPresentation';
import {
  filterInboxTasksForTrackedRequirements,
  getTrackedRequirementsForProperty,
  requirementMapFromList,
} from '../utils/portalRequirementAttention';
import { resolveClientRequirementLifecycle } from '../utils/clientRequirementLifecycle';
import {
  getLifecycleTierBadge,
  getRequirementLifecycleCardShellClass,
  getRequirementLifecycleRowSurfaceClass,
} from '../utils/requirementLifecyclePresentation';
import { resolveRiskSignalPrimaryKey } from '../utils/primaryActionResolver';
import {
  canonicalComplianceInlineNarrative,
  complianceWhatChangedLine,
  complianceObligationStatusLabel,
  compliancePriorityRecommendedNext,
  isRedundantUploadStyleSecondaryAction,
} from '../utils/complianceObligationPresent';
import {
  executeRequirementPrimaryCta,
  GUIDED_CTA_UNAVAILABLE_TITLE,
  resolvePrimaryCtaNavigatedAway,
} from '../utils/requirementCtaParity';
import {
  clientFacingVerificationLabel,
  clientVerificationLabelRedundantWithPrimary,
} from '../utils/evidenceReviewUi';
import {
  getClientDocumentRowStatusLabel,
  isPendingConfirmationForRequirementAttention,
} from '../utils/documentClientPresentation';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import {
  guidedMixedEvidenceInitialMode,
  isRightToRentMixedEvidencePendingReview,
} from '../utils/rightToRentTrustPresentation';
import { isConditionStandardActiveStandardRow } from '../utils/workflowSemantics';
import { requirementHasPersistedClientSubmission } from '../utils/clientPersistedSubmissionPresentation';
import ClientDocumentPreviewModal from '../components/client/ClientDocumentPreviewModal';
import { downloadClientDocumentFile } from '../utils/clientDocumentPreview';
import { toast } from '@/utils/portalNotifications';
import { buildEntityRoute, buildSafeQueryPath, resolveClientPortalPath, resolveDocumentsPath } from '../utils/clientPortalNavigation';
import { cn } from '../lib/utils';
import { operationalLabelForToken } from '../utils/presentationLanguage';
import {
  PortalLoadingPanel,
  PortalFilterStack,
  portalPageRoot,
  portalPrimaryButtonClass,
  portalSecondaryButtonClass,
  portalDrawerPanelClass,
} from '../components/client/ClientPortalPatterns';
import RequirementIntelligenceModal from '../components/client/RequirementIntelligenceModal';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import {
  JURISDICTION_ACCOUNT_DEFAULT_NOTICE_TITLE,
  JURISDICTION_FALLBACK_ALERT_BODY_PROPERTY,
  JURISDICTION_FALLBACK_ALERT_TITLE,
  JURISDICTION_FALLBACK_CTA,
  JURISDICTION_OPTIONS,
  jurisdictionAccountDefaultNoticeBody,
  jurisdictionSourceLabel,
} from '../utils/jurisdictionComplianceCopy';
import { propertyPageJurisdictionBanners } from '../utils/jurisdictionUiPolicy';
import PropertyOperatingHub from '../components/property/PropertyOperatingHub';
import { PropertyFinancialSnapshotCard } from '../components/rent/PropertyFinancialSnapshotCard';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';
import {
  headlineScoreDisplayForDashboard,
  headlineScoreShowsOutOf100,
} from '../utils/scoringHeadlineDisplay';
import { PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE } from '../utils/scoreFreshnessUi';
import { WORKSPACE_PROPERTY_SCORE_STRIP_FOOTNOTE } from '../utils/workspaceOrientationCopy';
import { NotApplicableGovernedNotice } from '../utils/notApplicableGovernedCopy';

const NOT_REQUIRED_REASONS = [
  { value: 'no_gas_supply', label: 'No gas supply' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'not_applicable', label: 'Not applicable' },
  { value: 'other', label: 'Other' },
];

/** Radix Select forbids `SelectItem value=""` (empty string is reserved for clearing the control). */
const PROPERTY_JURISDICTION_SELECT_UNSET = '__property_jurisdiction_unset__';

/** Default landing: single-property operating hub (not a mini-dashboard). */
const TAB_OPERATING = 'operating';
const TAB_COMPLIANCE = 'compliance';
const TAB_MAINTENANCE = 'maintenance';
const TAB_EVIDENCE = 'evidence';
const TAB_CONTRACTORS = 'contractors';
const TAB_TIMELINE = 'timeline';
const TAB_RISK_SIGNALS = 'risk_signals';
const TAB_ASSETS = 'assets';

const UUID_V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function formatEvidenceUploaderLabel(uploadedBy, currentPortalUserId) {
  if (uploadedBy == null || uploadedBy === '') return '—';
  const u = String(uploadedBy).trim();
  if (!u) return '—';
  if (currentPortalUserId && u === String(currentPortalUserId).trim()) return 'You';
  const up = u.toUpperCase();
  if (up === 'INTAKE_WIZARD' || up === 'INTAKE_MIGRATION') return 'Intake';
  if (UUID_V4_RE.test(u)) return 'Another team member';
  return u;
}

function linkedRequirementLabelForDocument(doc, requirements, rowTitleFn) {
  if (!doc?.requirement_id) return '—';
  const r = requirements.find((x) => String(x.requirement_id || x.id || '') === String(doc.requirement_id));
  return r ? rowTitleFn(r) : 'Requirement (open Documents workspace for details)';
}

function looksLikeContractorUuid(s) {
  return UUID_V4_RE.test(String(s || '').trim());
}

/** Prefer directory `name`, then non-UUID work-order name; never surface raw IDs. */
function resolveContractorDisplayName(contractorId, nameFromWorkOrders, directoryContractorName) {
  const fromDir = String(directoryContractorName ?? '').trim();
  if (fromDir) return fromDir;
  const fromWo = String(nameFromWorkOrders ?? '').trim();
  if (fromWo && !looksLikeContractorUuid(fromWo)) return fromWo;
  if (String(contractorId || '').trim()) return 'Unnamed contractor';
  // fromWo is empty or UUID-like; do not return it (avoids surfacing mistaken UUID-as-name with no id key).
  return 'Unnamed contractor';
}

/**
 * Obligations missing a linked document — same filter and order as Compliance → Missing documents.
 */
export function PropertyDocumentsMissingRequirementList({
  items,
  propertyId,
  navigate,
  rowTitle,
  rowReqId,
  maxItems = 25,
  /** Same contract as GuidedEvidenceModalContext.openGuidedEvidence */
  openGuidedEvidenceModal,
  onSubmitted,
}) {
  if (!items?.length) return null;
  const truncated = maxItems != null && items.length > maxItems;
  const list = truncated ? items.slice(0, maxItems) : items;
  return (
    <>
    <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
      {list.map((r) => {
        const code = r.requirement_code || r.requirement_type;
        const rid = rowReqId(r);
        const uploadQuery = rid ? { requirement_id: rid } : code ? { requirement_code: code } : {};
        const reqHref =
          rid && propertyId
            ? buildEntityRoute({ requirement_id: rid, property_id: propertyId, mode: 'requirement' }, '')
            : '';
        const sem = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId });
        const ta = sem.cta;
        const showDocumentsSecondary = ta.secondary_action?.route && !isRedundantUploadStyleSecondaryAction(ta);
        const docsHref = resolveDocumentsPath(propertyId, {
          ...uploadQuery,
          ...(ta.primary_intent === 'upload_evidence' ? { focus: 'upload' } : {}),
        });
        return (
          <li
            key={rid || code || 'row'}
            className="flex flex-col gap-3 px-4 py-4 min-w-0"
          >
            <div className="min-w-0">
              <p className="font-medium text-midnight-blue leading-snug">{rowTitle(r)}</p>
              <p className="text-xs text-gray-500 mt-1">{sem.evidenceStatusForStatus(r.status).text}</p>
            </div>
            <div className="flex w-full max-w-lg flex-col gap-2">
              <Button
                type="button"
                className={
                  ta.primary_action_handler === 'guided_evidence_error'
                    ? 'min-h-11 w-full bg-electric-teal/40 text-white cursor-not-allowed'
                    : 'min-h-11 w-full bg-electric-teal text-white hover:bg-electric-teal/90'
                }
                disabled={ta.primary_action_handler === 'guided_evidence_error'}
                title={ta.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined}
                onClick={() => {
                  if (ta.primary_action_handler === 'guided_evidence_error') return;
                  const { handled } = executeRequirementPrimaryCta({
                    requirement: r,
                    pagePropertyId: propertyId,
                    navigate,
                    openGuidedEvidence: openGuidedEvidenceModal,
                    openRequirementIntel: (row) => {
                      setRequirementIntelRow(row);
                      setRequirementIntelFocusSubmission(true);
                    },
                    onSubmitted,
                  });
                  if (!handled && docsHref) navigate(docsHref);
                }}
              >
                {ta.primary_action_label}
              </Button>
              {showDocumentsSecondary ? (
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-10 w-full border-gray-300 text-gray-800 text-sm font-normal"
                  onClick={() =>
                    ta.secondary_action.external
                      ? window.open(ta.secondary_action.route, '_blank', 'noopener,noreferrer')
                      : navigate(ta.secondary_action.route)
                  }
                >
                  {ta.secondary_action.label}
                </Button>
              ) : null}
              {reqHref ? (
                <Link
                  to={reqHref}
                  className="text-xs font-normal text-gray-600 hover:text-midnight-blue py-0.5 underline-offset-2 decoration-gray-300 hover:underline hover:decoration-midnight-blue/40"
                >
                  Review requirement details
                </Link>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
    {truncated ? (
      <p className="text-xs text-gray-500 mt-2">
        Showing {maxItems} of {items.length}. Open Compliance with the Missing documents filter for the full matrix.
      </p>
    ) : null}
    </>
  );
}

export default function PropertyDetailPage() {
  const { propertyId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
  const { hasFeature } = useEntitlements();
  const { user: authUser } = useAuth();
  const portalUserId = authUser?.portal_user_id;
  const [activeTab, setActiveTab] = useState(TAB_OPERATING);
  const [property, setProperty] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [complianceDetail, setComplianceDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scoreHistoryModal, setScoreHistoryModal] = useState(false);
  const [scoreHistoryEntries, setScoreHistoryEntries] = useState([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [propertyDocumentPreview, setPropertyDocumentPreview] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [notApplicableModal, setNotApplicableModal] = useState(null);
  const [notApplicablePreset, setNotApplicablePreset] = useState('not_applicable');
  const [notApplicableAuditText, setNotApplicableAuditText] = useState('');
  const [notApplicableSubmitting, setNotApplicableSubmitting] = useState(false);
  /** Compliance matrix / cards: full requirement intelligence (GET /requirements/:id). */
  const [requirementIntelRow, setRequirementIntelRow] = useState(null);
  const [requirementIntelFocusSubmission, setRequirementIntelFocusSubmission] = useState(false);
  const openComplianceRequirementIntel = useCallback((row) => {
    setRequirementIntelRow(row);
    setRequirementIntelFocusSubmission(requirementHasPersistedClientSubmission(row));
  }, []);
  // Tab-specific data
  const [workOrders, setWorkOrders] = useState([]);
  const [workOrdersLoading, setWorkOrdersLoading] = useState(false);
  /** Contractor directory rows for resolving IDs on the Contractors tab (`name` is primary display field). */
  const [contractorsDirectory, setContractorsDirectory] = useState([]);
  const [predictiveInsights, setPredictiveInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [riskSignalsData, setRiskSignalsData] = useState(null);
  const [riskSignalsLoading, setRiskSignalsLoading] = useState(false);
  const [createWoOpen, setCreateWoOpen] = useState(false);
  const [createWoForm, setCreateWoForm] = useState({
    description: '',
    category: 'general',
    severity: 'medium',
    inspection_required: false,
  });
  const [createWoSaving, setCreateWoSaving] = useState(false);
  const [maintenanceIssues, setMaintenanceIssues] = useState([]);
  const [maintenanceIssuesLoading, setMaintenanceIssuesLoading] = useState(false);
  const [maintenanceIssueFilter, setMaintenanceIssueFilter] = useState({ status: '', severity: '', category: '' });
  const [maintenanceWoFilter, setMaintenanceWoFilter] = useState({ status: '' });
  const [issueDetailDrawer, setIssueDetailDrawer] = useState(null);
  const [issueDetailData, setIssueDetailData] = useState(null);
  const [issueDetailLoading, setIssueDetailLoading] = useState(false);
  const [woDetailDrawer, setWoDetailDrawer] = useState(null);
  /** `{ source: 'workflow', job }` from `GET /jobs/:id`, or `{ source: 'maintenance', wo }` if that fails. */
  const [woPreviewPayload, setWoPreviewPayload] = useState(null);
  const [woDetailLoading, setWoDetailLoading] = useState(false);
  const [createIssueOpen, setCreateIssueOpen] = useState(false);
  const [createIssueForm, setCreateIssueForm] = useState({ description: '', category: 'general' });
  const [createIssueSaving, setCreateIssueSaving] = useState(false);
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
  const [priorityUrgentRaw, setPriorityUrgentRaw] = useState([]);
  const [urgentExplainOpenId, setUrgentExplainOpenId] = useState(null);
  /** Deep-link: `/properties/:id?open=resolve&requirement_id=…` opens compliance tab + guided flow when data is ready. */
  const [pendingComplianceResolve, setPendingComplianceResolve] = useState(null);
  /** Prevents double-opening guided modal when resolve query + requirements hydration replay. */
  const complianceResolveConsumedRef = useRef(null);
  /** Deeplink `?open=intel&requirement_id=&focus=submission` for post-submit inspect (GF-CLOSURE-01). */
  const [pendingIntelOpen, setPendingIntelOpen] = useState(null);
  const [operatingFeedItems, setOperatingFeedItems] = useState([]);
  const [operatingFeedLoading, setOperatingFeedLoading] = useState(false);

  const [bookInspectionOpen, setBookInspectionOpen] = useState(false);
  const [bookInspectionSignalId, setBookInspectionSignalId] = useState(null);
  const [bookInspectionReqPick, setBookInspectionReqPick] = useState('');
  const [bookInspectionSaving, setBookInspectionSaving] = useState(false);
  const [planJobGate, setPlanJobGate] = useState(null);
  const [jurisdictionDraft, setJurisdictionDraft] = useState('');
  const [jurisdictionSaving, setJurisdictionSaving] = useState(false);
  /** True while user chose "Change jurisdiction" on an already property_explicit record; false when not explicit or after save/cancel. */
  const [jurisdictionEditing, setJurisdictionEditing] = useState(false);

  useEffect(() => {
    const raw = (location.hash || window.location.hash || '').replace(/^#/, '');
    const firstSeg = raw.split('&')[0];
    if (firstSeg === 'compliance') {
      setActiveTab(TAB_COMPLIANCE);
    }
  }, [location.hash]);

  useEffect(() => {
    const onHashChange = () => {
      const raw = (window.location.hash || '').replace(/^#/, '');
      const firstSeg = raw.split('&')[0];
      if (firstSeg === 'compliance') {
        setActiveTab(TAB_COMPLIANCE);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

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

  useEffect(() => {
    const q = new URLSearchParams(location.search || '');
    if (q.get('open') !== 'resolve') return;
    const rid = q.get('requirement_id');
    if (!rid || !propertyId) return;
    const evMode = q.get('evidence_mode');
    setActiveTab(TAB_COMPLIANCE);
    setPendingComplianceResolve({ requirementId: rid, initialEvidenceMode: evMode || null });
  }, [location.search, propertyId]);

  useEffect(() => {
    const q = new URLSearchParams(location.search || '');
    if (q.get('open') !== 'intel') return;
    const rid = q.get('requirement_id');
    if (!rid || !propertyId) return;
    setActiveTab(TAB_COMPLIANCE);
    setPendingIntelOpen({
      requirementId: rid,
      focusSubmission: q.get('focus') === 'submission',
    });
  }, [location.search, propertyId]);

  useEffect(() => {
    if (!pendingIntelOpen || !propertyId || !requirements.length) return;
    const { requirementId, focusSubmission } = pendingIntelOpen;
    const row = requirements.find((r) => String(r.requirement_id || r.id || '') === String(requirementId));
    setPendingIntelOpen(null);
    navigate({ pathname: `/properties/${propertyId}`, search: '', hash: location.hash || '' }, { replace: true });
    if (!row) return;
    setRequirementIntelRow(row);
    setRequirementIntelFocusSubmission(Boolean(focusSubmission) || requirementHasPersistedClientSubmission(row));
  }, [pendingIntelOpen, requirements, propertyId, navigate, location.hash]);

  useEffect(() => {
    complianceResolveConsumedRef.current = null;
  }, [propertyId]);

  useEffect(() => {
    if (!pendingComplianceResolve || !propertyId || loading) return;
    const { requirementId, initialEvidenceMode } = pendingComplianceResolve;
    const rid = String(requirementId || '').trim();
    if (!rid) return;
    if (complianceResolveConsumedRef.current === rid) return;

    const row = requirements.find((r) => String(r.requirement_id || r.id || '') === rid);
    if (!row && requirements.length === 0) return;

    const guidedMode = initialEvidenceMode || guidedMixedEvidenceInitialMode() || null;
    const reqForModal =
      row && typeof row === 'object'
        ? row
        : { requirement_id: rid, property_id: propertyId };

    complianceResolveConsumedRef.current = rid;
    setPendingComplianceResolve(null);

    let primaryResult = null;

    if (row && isRightToRentMixedEvidencePendingReview(row) && openGuidedEvidence) {
      openGuidedEvidence({
        propertyId,
        requirement: row,
        onSubmitted: fetchData,
        initialEvidenceMode: guidedMode || undefined,
      });
    } else if (row) {
      primaryResult = executeRequirementPrimaryCta({
        requirement: row,
        pagePropertyId: propertyId,
        navigate,
        openGuidedEvidence,
        openRequirementIntel: (r) => {
          setRequirementIntelRow(r);
          setRequirementIntelFocusSubmission(true);
        },
        onSubmitted: fetchData,
        guidedInitialOverride: guidedMode,
      });
      if (
        isConditionStandardActiveStandardRow(row) &&
        !resolvePrimaryCtaNavigatedAway(primaryResult)
      ) {
        const fallbackRoute =
          primaryResult?.ta?.primary_route ||
          `/operations/issues?property_id=${encodeURIComponent(String(propertyId))}`;
        navigate(fallbackRoute);
        primaryResult = {
          handled: true,
          ta: {
            ...(primaryResult?.ta || {}),
            primary_route: fallbackRoute,
            primary_action_handler: 'navigate',
          },
        };
      }
    } else if (openGuidedEvidence) {
      openGuidedEvidence({
        propertyId,
        requirement: reqForModal,
        onSubmitted: fetchData,
        initialEvidenceMode: guidedMode || undefined,
      });
    }

    const q = new URLSearchParams(location.search || '');
    if (q.get('open') === 'resolve' && !resolvePrimaryCtaNavigatedAway(primaryResult)) {
      navigate({ pathname: `/properties/${propertyId}`, search: '', hash: location.hash || '' }, { replace: true });
    }
  }, [
    pendingComplianceResolve,
    requirements,
    propertyId,
    loading,
    navigate,
    location.hash,
    location.search,
    openGuidedEvidence,
    fetchData,
  ]);

  useEffect(() => {
    if (property?.property_id !== propertyId) return;
    if (jurisdictionEditing) return;
    setJurisdictionDraft(property.jurisdiction ?? '');
  }, [propertyId, property, jurisdictionEditing]);

  useEffect(() => {
    setJurisdictionEditing(false);
  }, [propertyId]);

  const jurisdictionDirty = useMemo(() => {
    if (!property) return false;
    const cur = property.jurisdiction ?? '';
    return (jurisdictionDraft ?? '') !== cur;
  }, [property, jurisdictionDraft]);

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
      toast.success('Inspection job started. Open Operations → Jobs to assign a contractor next.');
      setBookInspectionOpen(false);
      setBookInspectionSignalId(null);
      loadRiskSignals();
      if (wid) navigate(buildSafeQueryPath('/operations/work-orders', { work_order_id: wid }));
    } catch (e) {
      if (
        openPlanRestrictedJobGate(e, setPlanJobGate, {
          propertyId,
          requirementId: bookInspectionReqPick,
        })
      ) {
        return;
      }
      toast.error(e?.response?.data?.detail || 'Could not book inspection');
    } finally {
      setBookInspectionSaving(false);
    }
  }, [bookInspectionSignalId, bookInspectionReqPick, requirements, navigate, loadRiskSignals, propertyId]);

  useEffect(() => {
    if (!propertyId) return;
    clientAPI.getCommandCenter({ property_id: propertyId })
      .then((res) => {
        const urgent = Array.isArray(res.data?.urgent_actions) ? res.data.urgent_actions : [];
        setPriorityUrgentRaw(urgent);
      })
      .catch(() => setPriorityUrgentRaw([]));
  }, [propertyId]);

  const priorityActions = useMemo(() => {
    const map = requirementMapFromList(requirements);
    const aligned = filterInboxTasksForTrackedRequirements(priorityUrgentRaw, map);
    return { actions: aligned, total: aligned.length };
  }, [priorityUrgentRaw, requirements]);

  const operatingHubPriorityRequirementsById = useMemo(() => requirementMapFromList(requirements), [requirements]);

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

  const savePropertyJurisdiction = useCallback(async () => {
    if (!propertyId || !property) return;
    setJurisdictionSaving(true);
    try {
      await clientAPI.patchProperty(propertyId, { jurisdiction: (jurisdictionDraft ?? '').trim() || '' });
      toast.success('Jurisdiction saved', {
        description: 'Compliance score and requirements were recalculated for this property.',
      });
      setJurisdictionEditing(false);
      await fetchData();
      loadComplianceExplainability();
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Could not update jurisdiction.');
    } finally {
      setJurisdictionSaving(false);
    }
  }, [propertyId, property, jurisdictionDraft, fetchData, loadComplianceExplainability]);

  const startJurisdictionEdit = useCallback(() => {
    setJurisdictionDraft(property?.jurisdiction ?? '');
    setJurisdictionEditing(true);
  }, [property]);

  const cancelJurisdictionEdit = useCallback(() => {
    setJurisdictionDraft(property?.jurisdiction ?? '');
    setJurisdictionEditing(false);
  }, [property]);

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
    if (!propertyId || activeTab !== TAB_CONTRACTORS) return;
    if (hasFeature('maintenance_workflows')) loadWorkOrders();
  }, [propertyId, activeTab, hasFeature, loadWorkOrders]);

  useEffect(() => {
    if (!propertyId || !hasFeature('contractor_network')) {
      setContractorsDirectory([]);
      return undefined;
    }
    let cancelled = false;
    clientAPI
      .getContractors({ limit: 200 })
      .then((res) => {
        if (!cancelled) setContractorsDirectory(Array.isArray(res.data?.contractors) ? res.data.contractors : []);
      })
      .catch(() => {
        if (!cancelled) setContractorsDirectory([]);
      });
    return () => {
      cancelled = true;
    };
  }, [propertyId, hasFeature]);

  const contractorNameById = useMemo(() => {
    const m = new Map();
    contractorsDirectory.forEach((c) => {
      const id = String(c?.contractor_id || '').trim();
      if (!id) return;
      const n =
        String(c?.name || '').trim() ||
        String(c?.company_name || '').trim() ||
        String(c?.contact_name || '').trim();
      if (n) m.set(id, n);
    });
    return m;
  }, [contractorsDirectory]);

  useEffect(() => {
    if (!issueDetailDrawer) { setIssueDetailData(null); return; }
    setIssueDetailLoading(true);
    clientAPI.getMaintenanceIssue(issueDetailDrawer)
      .then((res) => setIssueDetailData(res.data || null))
      .catch(() => setIssueDetailData(null))
      .finally(() => setIssueDetailLoading(false));
  }, [issueDetailDrawer]);

  useEffect(() => {
    if (!woDetailDrawer) {
      setWoPreviewPayload(null);
      return undefined;
    }
    let cancelled = false;
    setWoPreviewPayload(null);
    setWoDetailLoading(true);
    (async () => {
      const loadMaintenanceWorkOrderPreview = async () => {
        try {
          const r2 = await clientAPI.getMaintenanceWorkOrder(woDetailDrawer);
          if (cancelled) return;
          setWoPreviewPayload({ source: 'maintenance', wo: r2.data || {} });
        } catch {
          if (!cancelled) setWoPreviewPayload(null);
        }
      };
      try {
        const res = await clientAPI.getComplianceWorkflowJob(woDetailDrawer);
        if (cancelled) return;
        const job = res.data;
        if (job && typeof job === 'object' && job.work_order_id) {
          setWoPreviewPayload({ source: 'workflow', job });
        } else {
          await loadMaintenanceWorkOrderPreview();
        }
      } catch {
        await loadMaintenanceWorkOrderPreview();
      } finally {
        if (!cancelled) setWoDetailLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [woDetailDrawer]);

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
    if (activeTab === TAB_COMPLIANCE || activeTab === TAB_OPERATING) {
      loadComplianceExplainability();
    }
  }, [propertyId, activeTab, loadComplianceExplainability]);

  useEffect(() => {
    if (propertyId && activeTab === TAB_EVIDENCE) loadEvidence();
  }, [propertyId, activeTab, loadEvidence]);

  const loadOperatingFeed = useCallback(() => {
    if (!propertyId) return;
    setOperatingFeedLoading(true);
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - 30);
    clientAPI
      .getPropertyTimeline(propertyId, {
        limit: 8,
        from_date: from.toISOString().slice(0, 10),
        to_date: to.toISOString().slice(0, 10),
      })
      .then((res) => setOperatingFeedItems(res.data?.items || []))
      .catch(() => setOperatingFeedItems([]))
      .finally(() => setOperatingFeedLoading(false));
  }, [propertyId]);

  useEffect(() => {
    if (propertyId && activeTab === TAB_TIMELINE) loadTimeline();
  }, [propertyId, activeTab, loadTimeline]);

  useEffect(() => {
    if (!propertyId || activeTab !== TAB_OPERATING) return;
    loadOperatingFeed();
    loadEvidence();
    loadDocuments();
  }, [propertyId, activeTab, loadOperatingFeed, loadEvidence, loadDocuments]);

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
      ...(createWoForm.inspection_required ? { inspection_required: true } : {}),
    })
      .then(() => {
        toast.success('Job created');
        setCreateWoOpen(false);
        setCreateWoForm({ description: '', category: 'general', severity: 'medium', inspection_required: false });
        loadWorkOrders();
      })
      .catch((err) => {
        if (openPlanRestrictedJobGate(err, setPlanJobGate, { propertyId })) return;
        toast.error(err?.response?.data?.detail || 'Create failed');
      })
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
    clientAPI
      .createWorkOrderFromIssue(issueId)
      .then(() => {
        toast.success('Job created from issue');
        loadWorkOrders();
        loadMaintenanceIssues();
        setIssueDetailDrawer(null);
      })
      .catch((err) => {
        if (openPlanRestrictedJobGate(err, setPlanJobGate, { propertyId })) return;
        toast.error(err?.response?.data?.detail || 'Failed');
      });
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

  const complianceWorkOrdersFiltered = useMemo(
    () => filteredWorkOrders.filter((wo) => (wo.work_order_kind || '').toUpperCase() === 'COMPLIANCE'),
    [filteredWorkOrders],
  );
  const repairWorkOrdersFiltered = useMemo(
    () => filteredWorkOrders.filter((wo) => (wo.work_order_kind || '').toUpperCase() !== 'COMPLIANCE'),
    [filteredWorkOrders],
  );

  const contractorsFromPropertyJobs = useMemo(() => {
    const byKey = new Map();
    workOrders.forEach((wo) => {
      const id = String(wo.contractor_id || '').trim();
      const name = String(wo.contractor_name || '').trim();
      if (!id && !name) return;
      const key = id || `name:${name}`;
      const ts = wo.updated_at || wo.created_at;
      const isCompliance = (wo.work_order_kind || '').toUpperCase() === 'COMPLIANCE';
      const cur = byKey.get(key);
      if (!cur) {
        byKey.set(key, {
          contractor_id: id || null,
          contractorNameFromJobs: name,
          jobCount: 1,
          complianceJobCount: isCompliance ? 1 : 0,
          repairJobCount: isCompliance ? 0 : 1,
          lastActivity: ts,
        });
      } else {
        cur.jobCount += 1;
        if (isCompliance) cur.complianceJobCount += 1;
        else cur.repairJobCount += 1;
        if (ts && (!cur.lastActivity || new Date(ts) > new Date(cur.lastActivity))) cur.lastActivity = ts;
        if (!cur.contractorNameFromJobs && name) cur.contractorNameFromJobs = name;
        if (!cur.contractor_id && id) cur.contractor_id = id;
      }
    });
    return Array.from(byKey.values()).sort(
      (a, b) => new Date(b.lastActivity || 0) - new Date(a.lastActivity || 0),
    );
  }, [workOrders]);

  const contractorsTabRows = useMemo(
    () =>
      contractorsFromPropertyJobs.map((row) => ({
        ...row,
        displayLabel: resolveContractorDisplayName(
          row.contractor_id,
          row.contractorNameFromJobs,
          row.contractor_id ? contractorNameById.get(row.contractor_id) : undefined,
        ),
        rowKey: row.contractor_id || `name:${row.contractorNameFromJobs || 'unknown'}`,
      })),
    [contractorsFromPropertyJobs, contractorNameById],
  );

  const slaAtRiskOrBreached = useMemo(() => {
    return workOrders.filter((wo) => {
      if (['COMPLETED', 'CANCELLED'].includes(wo.status || '')) return false;
      return wo.sla_breached_at || wo.sla_breach_risk_at;
    });
  }, [workOrders]);

  const assetLabel = (assetId) => {
    if (!assetId) return '—';
    const a = assets.find((x) => x.asset_id === assetId);
    return a ? (a.name || operationalLabelForToken(a.asset_type, { emptyLabel: '' }) || assetId) : assetId;
  };

  const getStatus = (r) =>
    projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId }).evidenceStatusForStatus(r.status);
  const formatDate = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
  const formatJobPreviewDateTime = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return '—';
    }
  };
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
  const rowTitle = (r) => requirementTitleFromRow(r, 'detail');
  const rowCompactTitle = (r) => requirementTitleFromRow(r, 'compact');
  const rowExpiry = (r) => r.expiry_date || r.due_date;
  const rowDays = (r) => (r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r)));
  const rowReqId = (r) => r.requirement_id || r.id;

  const runCompliancePrimaryCta = React.useCallback(
    (r) => {
      const taPre = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId }).cta;
      const docsHref = resolveDocumentsPath(propertyId, {
        requirement_id: rowReqId(r),
        ...(taPre.primary_intent === 'upload_evidence' ? { focus: 'upload' } : {}),
      });
      const { handled } = executeRequirementPrimaryCta({
        requirement: r,
        pagePropertyId: propertyId,
        navigate,
        openGuidedEvidence,
        openRequirementIntel: (row) => {
          setRequirementIntelRow(row);
          setRequirementIntelFocusSubmission(true);
        },
        onSubmitted: fetchData,
      });
      if (!handled && docsHref) navigate(docsHref);
    },
    [propertyId, navigate, openGuidedEvidence, fetchData],
  );

  const evidenceDocStatusLabel = (doc) => getClientDocumentRowStatusLabel(doc);

  const handleEvidenceDocumentDownload = async (doc) => {
    if (!doc?.document_id) return;
    try {
      await downloadClientDocumentFile(apiClient, doc, {
        onError: (msg) => toast.error(msg),
      });
    } catch {
      /* errors surfaced via onError */
    }
  };

  const isPendingConfirmation = (doc) => isPendingConfirmationForRequirementAttention(doc);

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
      missingDocuments: kpis.missing ?? requirements.filter(isRequirementMissingDocument).length,
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
      else if (s === 'MISSING') list = list.filter(isRequirementMissingDocument);
      else list = list.filter((r) => (r.status || '').toUpperCase() === s);
    }
    if (complianceSearchQuery.trim()) {
      const q = complianceSearchQuery.trim().toLowerCase();
      list = list.filter((r) => (rowTitle(r) || '').toLowerCase().includes(q) || (r.requirement_code || '').toLowerCase().includes(q));
    }
    if (complianceStatusFilter && complianceStatusFilter.toUpperCase() === 'MISSING') {
      list = sortRequirementsCriticalityThenTitle(list);
    }
    return list;
  };

  const hubPrioritizedRequirements = useMemo(() => {
    const scoped = getTrackedRequirementsForProperty(propertyId, requirements);
    const filtered = scoped.filter((r) => {
      const st = (r.status || '').toUpperCase();
      if (st === 'EXPIRING_SOON') return true;
      const lc = resolveClientRequirementLifecycle(r).state;
      if (lc === 'ACTION_REQUIRED') return true;
      if (lc === 'PENDING_REVIEW' || lc === 'VERIFIED' || lc === 'SATISFIED_UNVERIFIED') return false;
      return ['OVERDUE', 'EXPIRED', 'MISSING', 'PENDING'].includes(st);
    });
    return sortRequirementsAttentionOrder(filtered, rowExpiry).slice(0, 8);
  }, [propertyId, requirements]);

  /** Same urgent rules as before, sorted like the obligations matrix (single source: `requirements`). */
  const urgentRequirementsOrdered = useMemo(() => {
    const scoped = getTrackedRequirementsForProperty(propertyId, requirements);
    return sortRequirementsAttentionOrder(scoped, (r) => r.expiry_date || r.due_date);
  }, [propertyId, requirements]);
  const NEEDS_ATTENTION_CAP = 8;
  const urgentNeedsAttention = useMemo(
    () => buildNeedsAttentionSubset(urgentRequirementsOrdered, (r) => r.expiry_date || r.due_date, NEEDS_ATTENTION_CAP),
    [urgentRequirementsOrdered],
  );
  const urgentRequirementsCapped = urgentNeedsAttention.items;
  const urgentRequirementsOverflow = urgentNeedsAttention.overflowCount;

  /** Same filter and order as Compliance → Missing documents (PENDING / MISSING, criticality first). */
  const requirementsMissingDocuments = useMemo(
    () => listRequirementsMissingDocumentsSorted(getTrackedRequirementsForProperty(propertyId, requirements)),
    [propertyId, requirements],
  );

  const hubActiveWorkOrders = useMemo(() => {
    const terminal = ['COMPLETED', 'CANCELLED', 'CLOSED', 'VERIFIED'];
    return workOrders.filter((wo) => !terminal.includes(wo.status || ''));
  }, [workOrders]);

  const assetActivitySummary = (a, per) => {
    const parts = [];
    if (a.last_service_date) parts.push(`Last service ${formatDate(a.last_service_date)}`);
    if (per.open_issues != null && per.open_issues > 0) {
      parts.push(`${per.open_issues} open issue${per.open_issues === 1 ? '' : 's'}`);
    }
    if (hasFeature('predictive_maintenance') && per.risk) {
      parts.push(`Risk: ${String(per.risk).replace(/^\w/, (c) => c.toUpperCase())}`);
    }
    return parts.length ? parts.join(' · ') : 'No activity recorded yet — open the asset for details.';
  };

  if (loading) {
    return <PortalLoadingPanel message="Loading property…" />;
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

  // compliance_basis is authoritative: property_explicit | client_default | default_fallback (from portfolio + properties APIs).
  const effectiveComplianceBasis =
    complianceDetail?.compliance_basis ?? property?.compliance_basis ?? null;
  const effectiveJurisdictionLabel =
    complianceDetail?.effective_jurisdiction_label ?? property?.effective_jurisdiction_label ?? '';
  const effectiveJurisdictionSource =
    complianceDetail?.jurisdiction_source ?? property?.jurisdiction_source ?? null;
  const { showHardWarning: showJurisdictionHardWarning, showSoftAccountDefaultNotice: showJurisdictionAccountDefaultNotice } =
    propertyPageJurisdictionBanners(effectiveComplianceBasis);

  const isJurisdictionConfigured = effectiveComplianceBasis === 'property_explicit';
  const showJurisdictionEditor = !isJurisdictionConfigured || jurisdictionEditing;

  return (
    <div className={portalPageRoot}>
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

      {showJurisdictionHardWarning && (
        <Alert
          className="mb-4 border-amber-300 bg-amber-50/95 text-amber-950"
          data-testid="jurisdiction-fallback-property-alert"
        >
          <AlertCircle className="h-4 w-4 text-amber-800 shrink-0" />
          <AlertDescription>
            <p className="font-semibold text-amber-950">{JURISDICTION_FALLBACK_ALERT_TITLE}</p>
            <p className="text-sm mt-1.5 text-amber-950/95">{JURISDICTION_FALLBACK_ALERT_BODY_PROPERTY}</p>
            <Button type="button" variant="outline" size="sm" className="mt-3 border-amber-400 bg-white hover:bg-amber-100" asChild>
              <Link to="/settings/jurisdiction">{JURISDICTION_FALLBACK_CTA}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {showJurisdictionAccountDefaultNotice && (
        <Alert
          className="mb-4 border-sky-200 bg-sky-50/95 text-sky-950"
          data-testid="jurisdiction-account-default-notice"
        >
          <Info className="h-4 w-4 text-sky-700 shrink-0" />
          <AlertDescription>
            <p className="font-semibold text-sky-950">{JURISDICTION_ACCOUNT_DEFAULT_NOTICE_TITLE}</p>
            <p className="text-sm mt-1.5 text-sky-950/95">
              {jurisdictionAccountDefaultNoticeBody(effectiveJurisdictionLabel)}
            </p>
          </AlertDescription>
        </Alert>
      )}

      {property ? (
        <Card className="mb-4 border border-gray-200 bg-white" data-testid="property-jurisdiction-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-midnight-blue">Jurisdiction on this property</CardTitle>
            <CardDescription className="text-sm text-gray-600 space-y-1">
              <p>
                <span className="text-gray-500">Source: </span>
                <span className="font-medium text-midnight-blue">{jurisdictionSourceLabel(effectiveJurisdictionSource)}</span>
              </p>
              <p>
                <span className="text-gray-500">Effective region for scoring: </span>
                <span className="font-medium text-midnight-blue">{effectiveJurisdictionLabel || '—'}</span>
              </p>
            </CardDescription>
          </CardHeader>
          {isJurisdictionConfigured && !showJurisdictionEditor ? (
            <CardContent className="flex flex-col gap-4 pt-0">
              <p className="text-sm text-gray-600">
                This property is using its own jurisdiction for compliance scoring.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
                <div className="min-w-0">
                  <p className="text-xs text-gray-500 mb-0.5">Region</p>
                  <p className="text-sm font-medium text-midnight-blue" data-testid="property-jurisdiction-display">
                    {property.jurisdiction || effectiveJurisdictionLabel || '—'}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className={cn(portalSecondaryButtonClass, 'w-full sm:w-auto shrink-0')}
                  onClick={startJurisdictionEdit}
                  data-testid="property-jurisdiction-change"
                >
                  Change jurisdiction
                </Button>
              </div>
            </CardContent>
          ) : (
            <CardContent className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end pt-0">
              <div className="space-y-2 flex-1 min-w-[220px] max-w-md">
                <Label htmlFor="property-jurisdiction-select" className="text-sm text-midnight-blue">
                  Region
                </Label>
                <Select
                  value={
                    (jurisdictionDraft ?? '').trim()
                      ? jurisdictionDraft.trim()
                      : PROPERTY_JURISDICTION_SELECT_UNSET
                  }
                  onValueChange={(v) =>
                    setJurisdictionDraft(v === PROPERTY_JURISDICTION_SELECT_UNSET ? '' : v)
                  }
                  disabled={jurisdictionSaving}
                >
                  <SelectTrigger id="property-jurisdiction-select" data-testid="property-jurisdiction-select">
                    <SelectValue placeholder="Choose" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={PROPERTY_JURISDICTION_SELECT_UNSET}>
                      Not set (account default, then system default if needed)
                    </SelectItem>
                    {JURISDICTION_OPTIONS.map((j) => (
                      <SelectItem key={j} value={j}>
                        {j}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  className="bg-electric-teal hover:bg-electric-teal/90"
                  disabled={!jurisdictionDirty || jurisdictionSaving}
                  onClick={savePropertyJurisdiction}
                  data-testid="property-jurisdiction-save"
                >
                  {jurisdictionSaving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Save jurisdiction
                </Button>
                {isJurisdictionConfigured && jurisdictionEditing ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className={portalSecondaryButtonClass}
                    disabled={jurisdictionSaving}
                    onClick={cancelJurisdictionEdit}
                    data-testid="property-jurisdiction-cancel"
                  >
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          )}
        </Card>
      ) : null}

      {/* A — Property header: identity, compliance snapshot, primary actions only */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 sm:p-6 mb-4 min-w-0">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between min-w-0">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl sm:text-2xl font-bold text-midnight-blue leading-snug">{address}</h1>
            {complianceDetail ? (
              <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5">
                <p className="text-sm text-midnight-blue">
                  <span className="font-semibold">
                    {headlineScoreDisplayForDashboard(complianceDetail.score, complianceDetail.score_status)}
                    {headlineScoreShowsOutOf100(complianceDetail.score, complianceDetail.score_status) ? '/100' : ''}
                  </span>
                  <span className="text-gray-500"> · </span>
                  <span>{formatRiskLabel(complianceDetail.risk_level)}</span>
                </p>
                {complianceDetail.score_status && (
                  <p className="text-xs text-gray-600 mt-1">
                    Score status: {complianceDetail.score_status}
                    {complianceDetail.last_calculated_at
                      ? ` · Last calculated: ${new Date(complianceDetail.last_calculated_at).toLocaleString()}`
                      : ''}
                  </p>
                )}
                {!complianceDetail.score_status && complianceDetail.last_calculated_at && (
                  <p className="text-xs text-gray-600 mt-1">
                    Last calculated: {new Date(complianceDetail.last_calculated_at).toLocaleString()}
                  </p>
                )}
                {complianceDetail.score_status_message && String(complianceDetail.score_status_message).trim() ? (
                  <p className="text-xs text-gray-600 mt-1 border-t border-gray-200 pt-1.5">
                    {String(complianceDetail.score_status_message).trim()}
                  </p>
                ) : null}
                <p className="text-xs text-gray-500 mt-1">Compliance snapshot for this property — not legal advice.</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-electric-teal h-9 px-2 -ml-2"
                    onClick={() => setActiveTab(TAB_COMPLIANCE)}
                  >
                    {PORTAL_COPY.viewDetails} (requirements)
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-gray-600 h-9 px-2"
                    onClick={() => navigate('/reports')}
                  >
                    {PORTAL_COPY.viewReports}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 mt-2">Compliance detail is not available for this property yet.</p>
            )}
            <details className="mt-3 sm:hidden rounded-lg border border-gray-100 bg-white px-3 py-2 text-sm">
              <summary className="cursor-pointer font-medium text-midnight-blue">Property details</summary>
              <div className="flex flex-wrap gap-2 mt-2 text-gray-600">
                {property?.property_type && <span>{property.property_type}</span>}
                {property?.jurisdiction && <span>{property.jurisdiction}</span>}
                {property?.is_hmo && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">HMO</span>}
                {property?.occupancy != null && <span>Occupancy: {property.occupancy}</span>}
                {property?.has_gas !== undefined && <span>{property.has_gas ? 'Gas' : 'No gas'}</span>}
              </div>
            </details>
            <div className="hidden sm:flex flex-wrap gap-2 mt-2 text-sm text-gray-600">
              {property?.property_type && <span>{property.property_type}</span>}
              {property?.jurisdiction && <span>{property.jurisdiction}</span>}
              {property?.is_hmo && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded">HMO</span>}
              {property?.occupancy != null && <span>Occupancy: {property.occupancy}</span>}
              {property?.has_gas !== undefined && <span>{property.has_gas ? 'Gas' : 'No gas'}</span>}
            </div>
          </div>
          <div className="flex flex-col gap-2 w-full lg:w-auto lg:min-w-[220px] shrink-0">
            <Button type="button" className={cn(portalPrimaryButtonClass, 'w-full justify-center')} onClick={() => navigate(resolveDocumentsPath(propertyId))}>
              <Upload className="w-4 h-4 mr-2 shrink-0" />
              {PORTAL_COPY.uploadDocument}
            </Button>
            {hasFeature('maintenance_workflows') ? (
              <Button
                type="button"
                className={cn(portalPrimaryButtonClass, 'w-full justify-center bg-electric-teal hover:bg-electric-teal/90')}
                onClick={() => {
                  setActiveTab(TAB_MAINTENANCE);
                  setCreateWoOpen(true);
                }}
              >
                <Plus className="w-4 h-4 mr-2 shrink-0" />
                {PORTAL_COPY.addWorkOrder}
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                className={cn(portalSecondaryButtonClass, 'w-full justify-center')}
                onClick={() => navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: 'PLAN_2_PORTFOLIO' }))}
              >
                <Layers className="mr-2 h-4 w-4 shrink-0 text-midnight-blue/60" aria-hidden />
                {PORTAL_COPY.upgradeForWorkOrders}
              </Button>
            )}
            {hasFeature('maintenance_workflows') && (
              <Button
                type="button"
                variant="outline"
                className={cn(portalSecondaryButtonClass, 'w-full justify-center text-sm')}
                onClick={() => navigate(buildSafeQueryPath('/operations/work-orders', { property_id: propertyId }))}
              >
                <Wrench className="w-4 h-4 mr-2 shrink-0" />
                {PORTAL_COPY.workOrders}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tab navigation — wrap on small screens (no horizontal tab strip) */}
      <nav className="flex flex-wrap gap-1 border-b border-gray-200 mb-6 pb-px" aria-label="Property sections">
        {[
          { id: TAB_OPERATING, label: 'Operating', icon: Building2, feature: null },
          { id: TAB_COMPLIANCE, label: 'Compliance', icon: ClipboardCheck, feature: null },
          { id: TAB_MAINTENANCE, label: 'Jobs & issues', icon: Wrench, feature: 'maintenance_workflows' },
          { id: TAB_EVIDENCE, label: 'Documents', icon: FileText, feature: null },
          { id: TAB_CONTRACTORS, label: 'Contractors', icon: Users, feature: 'contractor_network' },
          { id: TAB_TIMELINE, label: 'Timeline', icon: Calendar, feature: null },
          { id: TAB_RISK_SIGNALS, label: 'Risk signals', icon: AlertCircle, feature: 'predictive_maintenance' },
          { id: TAB_ASSETS, label: 'Assets', icon: Package, feature: 'maintenance_workflows' },
        ].map(({ id, label, icon: Icon, feature }) => {
          const enabled = id === TAB_ASSETS
            ? (hasFeature('maintenance_workflows') || hasFeature('predictive_maintenance'))
            : (!feature || hasFeature(feature));
          return (
            <button
              key={id}
              type="button"
              data-testid={id === TAB_COMPLIANCE ? 'property-tab-compliance' : undefined}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-3 sm:px-4 py-3 min-h-11 text-sm font-medium border-b-2 -mb-px transition-colors rounded-t-md ${
                activeTab === id
                  ? 'border-electric-teal text-electric-teal bg-electric-teal/5'
                  : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
              {!enabled ? (
                <span className="inline-flex shrink-0" title="Portfolio-scale add-on">
                  <Layers className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      {activeTab === TAB_OPERATING && (
        <>
        <PropertyOperatingHub
          propertyId={propertyId}
          hasFeature={hasFeature}
          tabs={{
            compliance: TAB_COMPLIANCE,
            maintenance: TAB_MAINTENANCE,
            evidence: TAB_EVIDENCE,
            timeline: TAB_TIMELINE,
            riskSignals: TAB_RISK_SIGNALS,
            contractors: TAB_CONTRACTORS,
          }}
          onSelectTab={setActiveTab}
          priorityActions={priorityActions}
          riskSignalsData={riskSignalsData}
          loadRiskSignals={loadRiskSignals}
          loadWorkOrders={loadWorkOrders}
          hubPrioritizedRequirements={hubPrioritizedRequirements}
          getComplianceSummary={getComplianceSummary}
          hubActiveWorkOrders={hubActiveWorkOrders}
          workOrdersLoading={workOrdersLoading}
          evidenceData={evidenceData}
          evidenceLoading={evidenceLoading}
          operatingFeedItems={operatingFeedItems}
          operatingFeedLoading={operatingFeedLoading}
          setComplianceStatusFilter={setComplianceStatusFilter}
          openBookInspectionFromRisk={openBookInspectionFromRisk}
          onOpenNotApplicable={(payload) => {
            setNotApplicableModal(payload);
            setNotApplicablePreset('not_applicable');
            setNotApplicableAuditText('');
          }}
          onCreateWoFromRiskDescription={(description) => {
            setActiveTab(TAB_MAINTENANCE);
            setCreateWoOpen(true);
            setCreateWoForm((f) => ({ ...f, description }));
          }}
          onPlanRestrictedJobError={(err, ctx) => openPlanRestrictedJobGate(err, setPlanJobGate, ctx)}
          onRefreshAfterEvidence={fetchData}
          priorityTaskRequirementsById={operatingHubPriorityRequirementsById}
        />
        <PropertyFinancialSnapshotCard propertyId={propertyId} />
        </>
      )}

      {/* Tab: Compliance */}
      {activeTab === TAB_COMPLIANCE && (
        <>
        <div className="space-y-6" data-testid="property-compliance-panel">
          <Card className="border border-electric-teal/25 bg-electric-teal/[0.06]">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-midnight-blue">Compliance priority for this property</CardTitle>
              <CardDescription>Counts follow the requirements table below — one list, same definitions.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {(() => {
                const sum = getComplianceSummary();
                const nextDue = getNextDueDate();
                return (
                  <>
                    <div className="flex flex-wrap gap-x-6 gap-y-2 text-midnight-blue">
                      <span>
                        <strong className="tabular-nums">{sum.missingDocuments}</strong> missing documents
                      </span>
                      <span>
                        <strong className="tabular-nums">{sum.expiringSoon}</strong> expiring
                      </span>
                      <span>
                        <strong className="tabular-nums">{sum.overdue}</strong> overdue
                      </span>
                      <span className="text-gray-600">
                        Next due: {nextDue ? formatDate(nextDue) : 'None scheduled'}
                      </span>
                    </div>
                    <p className="font-medium text-midnight-blue leading-snug">
                      {compliancePriorityRecommendedNext(requirements, urgentRequirementsCapped, rowTitle)}
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button type="button" variant={complianceStatusFilter === '' ? 'default' : 'outline'} size="sm" className={complianceStatusFilter === '' ? 'bg-electric-teal text-white' : 'border-gray-200'} onClick={() => setComplianceStatusFilter('')}>
                        All requirements ({sum.totalApplicable})
                      </Button>
                      <Button type="button" variant={complianceStatusFilter === 'VALID' ? 'default' : 'outline'} size="sm" className={complianceStatusFilter === 'VALID' ? 'bg-electric-teal text-white' : 'border-gray-200'} onClick={() => setComplianceStatusFilter('VALID')}>
                        Valid ({sum.valid})
                      </Button>
                      <Button type="button" variant={complianceStatusFilter === 'EXPIRING_SOON' ? 'default' : 'outline'} size="sm" className={complianceStatusFilter === 'EXPIRING_SOON' ? 'bg-electric-teal text-white' : 'border-gray-200'} onClick={() => setComplianceStatusFilter('EXPIRING_SOON')}>
                        Expiring ({sum.expiringSoon})
                      </Button>
                      <Button type="button" variant={complianceStatusFilter === 'OVERDUE' ? 'default' : 'outline'} size="sm" className={complianceStatusFilter === 'OVERDUE' ? 'bg-electric-teal text-white' : 'border-gray-200'} onClick={() => setComplianceStatusFilter('OVERDUE')}>
                        Overdue ({sum.overdue})
                      </Button>
                      <Button type="button" variant={complianceStatusFilter === 'MISSING' ? 'default' : 'outline'} size="sm" className={complianceStatusFilter === 'MISSING' ? 'bg-electric-teal text-white' : 'border-gray-200'} onClick={() => setComplianceStatusFilter('MISSING')}>
                        Missing documents ({sum.missingDocuments})
                      </Button>
                    </div>
                  </>
                );
              })()}
            </CardContent>
          </Card>

          {complianceDetail && (
            <>
              <div className="mb-4 flex flex-wrap gap-4 p-4 rounded-xl border border-gray-200 bg-gray-50">
                <span className="font-medium text-midnight-blue">
                  Compliance score:{' '}
                  {headlineScoreDisplayForDashboard(complianceDetail.score, complianceDetail.score_status)}
                  {headlineScoreShowsOutOf100(complianceDetail.score, complianceDetail.score_status) ? '/100' : ''}
                </span>
                <span className="font-medium text-midnight-blue">Risk level: {formatRiskLabel(complianceDetail.risk_level)}</span>
                {complianceDetail.risk_index != null && complianceDetail.risk_index > 0 && (
                  <span className="text-gray-600">Risk index: {complianceDetail.risk_index}</span>
                )}
                {complianceDetail.last_updated_at && (
                  <span className="text-sm text-gray-500">Last updated: {new Date(complianceDetail.last_updated_at).toLocaleString()}</span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-2 max-w-prose leading-relaxed">{WORKSPACE_PROPERTY_SCORE_STRIP_FOOTNOTE}</p>
              {complianceExplainability ? (
                <div
                  className="mb-4 rounded-lg border border-gray-200 bg-gray-50/90 px-3 py-2.5 text-xs text-gray-700 space-y-1.5"
                  data-testid="property-compliance-stored-vs-preview-note"
                >
                  <p>{PROPERTY_DETAIL_STORED_VS_PREVIEW_NOTE}</p>
                  {complianceDetail.score_status_message && String(complianceDetail.score_status_message).trim() ? (
                    <p className="text-gray-800">{String(complianceDetail.score_status_message).trim()}</p>
                  ) : null}
                  {complianceDetail.last_calculated_at ? (
                    <p className="text-gray-600">
                      Last calculated: {new Date(complianceDetail.last_calculated_at).toLocaleString()}
                    </p>
                  ) : null}
                </div>
              ) : null}
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
                Score summary
              </CardTitle>
              <CardDescription>
                How your property score is built — details for each requirement are in the table below, not duplicated here.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {complianceExplainabilityLoading ? (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading score summary…
                </div>
              ) : !complianceExplainability ? (
                <p className="text-sm text-gray-700">
                  Score breakdown will appear here when available. Use the priority counts and requirements table to see what needs attention; upload or renew documents on the{' '}
                  <button type="button" className="text-electric-teal font-medium underline-offset-2 hover:underline" onClick={() => setActiveTab(TAB_EVIDENCE)}>
                    Documents
                  </button>{' '}
                  tab.
                </p>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3 text-sm">
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Score (persisted):{' '}
                      <strong>
                        {(() => {
                          const auth = complianceExplainability?.authoritative;
                          const exp = auth || complianceExplainability;
                          const st = exp?.score_status ?? complianceExplainability?.score_status;
                          const lbl = headlineScoreDisplayForDashboard(exp?.score, st);
                          const suffix = headlineScoreShowsOutOf100(exp?.score, st) ? '/100' : '';
                          return `${lbl}${suffix}`;
                        })()}
                      </strong>
                    </span>
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Portfolio jurisdiction (live preview):{' '}
                      <strong>
                        {(complianceExplainability?.operational_preview?.live_engine_snapshot || {}).effective_jurisdiction_label ??
                          complianceExplainability.effective_jurisdiction_label ??
                          '—'}
                      </strong>
                    </span>
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Scoring rules:{' '}
                      <strong>
                        {operationalLabelForToken(
                          String(
                            (complianceExplainability?.authoritative || complianceExplainability)?.scoring_jurisdiction_bucket ??
                              (complianceExplainability?.authoritative || complianceExplainability)?.jurisdiction ??
                              (complianceExplainability?.operational_preview?.live_engine_snapshot || {}).scoring_jurisdiction_bucket ??
                              (complianceExplainability?.operational_preview?.live_engine_snapshot || {}).jurisdiction ??
                              'ENGLAND_WALES',
                          ).trim() || 'ENGLAND_WALES',
                          { emptyLabel: '—' },
                        )}
                      </strong>
                    </span>
                    <span className="px-2 py-1 rounded border border-gray-200 bg-gray-50">
                      Points:{' '}
                      <strong>
                        {Number((complianceExplainability?.authoritative || complianceExplainability)?.earned_points || 0).toFixed(1)} /{' '}
                        {Number((complianceExplainability?.authoritative || complianceExplainability)?.applicable_points || 0).toFixed(1)}
                      </strong>
                    </span>
                  </div>

                  {(complianceExplainability?.authoritative || complianceExplainability)?.bucket_breakdown && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-sm">
                      {[
                        ['Legal core', (complianceExplainability?.authoritative || complianceExplainability)?.bucket_breakdown?.legal_core?.percent],
                        ['Documentation', (complianceExplainability?.authoritative || complianceExplainability)?.bucket_breakdown?.documentation_completeness?.percent],
                        ['Operational', (complianceExplainability?.authoritative || complianceExplainability)?.bucket_breakdown?.operational_responsiveness?.percent],
                        ['Recency', (complianceExplainability?.authoritative || complianceExplainability)?.bucket_breakdown?.recency_maintenance_confidence?.percent],
                      ].map(([label, pct]) => (
                        <div key={label} className="rounded border border-gray-200 p-2 bg-white">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
                          <p className="font-semibold text-midnight-blue">{Number(pct || 0).toFixed(0)}%</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {Array.isArray((complianceExplainability?.authoritative || complianceExplainability)?.top_next_actions) &&
                    (complianceExplainability?.authoritative || complianceExplainability).top_next_actions.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-midnight-blue mb-1">Suggested score impact (reference)</p>
                      <ul className="space-y-1 text-sm text-gray-700">
                        {(complianceExplainability?.authoritative || complianceExplainability).top_next_actions.slice(0, 5).map((a, idx) => (
                          <li key={`${a.requirement_code || 'req'}-${idx}`} className="flex items-center justify-between gap-2">
                            <span>• {a.action}</span>
                            <span className="text-xs text-gray-500">+{Number(a.impact_points || 0).toFixed(1)} pts</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <p className="text-xs text-gray-600">
            Requirements below are the source of truth. Use the{' '}
            <button type="button" className="text-electric-teal font-medium underline-offset-2 hover:underline" onClick={() => setActiveTab(TAB_EVIDENCE)}>
              Documents
            </button>{' '}
            tab to upload, renew, or confirm documents for each requirement.
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm text-gray-600 sr-only" htmlFor="compliance-obligation-search">
              Search requirements
            </label>
            <input
              id="compliance-obligation-search"
              type="search"
              placeholder="Search by requirement name or code…"
              value={complianceSearchQuery}
              onChange={(e) => setComplianceSearchQuery(e.target.value)}
              className="max-w-md min-w-[200px] flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
            />
            {complianceSearchQuery.trim() ? (
              <Button type="button" variant="ghost" size="sm" className="text-gray-600" onClick={() => setComplianceSearchQuery('')}>
                Clear search
              </Button>
            ) : null}
          </div>

          {/* C) Obligation Table / Cards */}
          {requirements.length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-12 text-center text-gray-600 space-y-3">
                <p className="font-medium text-midnight-blue">No requirements are listed for this property yet.</p>
                <p className="text-sm max-w-md mx-auto">When your portfolio is configured, requirements appear here. Refresh after updating property or jurisdiction settings.</p>
                <Button variant="outline" onClick={handleRefresh}>
                  Refresh property data
                </Button>
              </CardContent>
            </Card>
          ) : getFilteredRequirements().length === 0 ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-gray-600 space-y-3">
                <p className="font-medium text-midnight-blue">No requirements match what you are viewing.</p>
                <p className="text-sm">Try clearing search or showing all requirements again.</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  <Button type="button" variant="outline" size="sm" onClick={() => { setComplianceSearchQuery(''); setComplianceStatusFilter(''); }}>
                    Show all requirements
                  </Button>
                  {complianceSearchQuery.trim() ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => setComplianceSearchQuery('')}>
                      Clear search only
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {!requirements.some((r) => r.evidence_doc_id) && (
                <Card className="border-amber-200 bg-amber-50/30">
                  <CardContent className="py-6 text-center">
                    <p className="text-gray-700 mb-2">No documents have been uploaded for this property yet.</p>
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button className="bg-electric-teal text-white hover:bg-electric-teal/90 min-h-11" onClick={() => navigate(resolveDocumentsPath(propertyId))}>{PORTAL_COPY.uploadDocument}</Button>
                      <Button variant="outline" onClick={() => setActiveTab(TAB_EVIDENCE)}>View Documents tab</Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {urgentNeedsAttention.total > 0 && (
                <Card className="border-amber-200 bg-amber-50/30">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Needs attention now</CardTitle>
                    <CardDescription>
                      Operational triage (max {NEEDS_ATTENTION_CAP}) — statutory blockers first, then operational workflows, then supporting evidence. Same primary actions as the full matrix.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {urgentRequirementsCapped.map((r, i) => {
                      const complianceDomId = rowReqId(r) || `rc:${propertyId}:${normalizeRequirementCode(r.requirement_code || r.requirement_type || `u${i}`)}`;
                      const rid = String(complianceDomId);
                      const statusUi = getStatus(r);
                      const stdStatus = complianceObligationStatusLabel(r);
                      const taRow = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId }).cta;
                      const tierBadge = getLifecycleTierBadge(r);
                      const explainOpen = urgentExplainOpenId === rid;
                      const explainPayload = canonicalComplianceInlineNarrative(r);
                      const showNonUploadSecondary =
                        taRow.secondary_action?.route && !isRedundantUploadStyleSecondaryAction(taRow);
                      return (
                        <div key={rid} className={cn(getRequirementLifecycleCardShellClass(r), 'overflow-hidden')}>
                          <div className="flex flex-col gap-3 p-3">
                            <div className="min-w-0">
                              <p className="font-medium text-midnight-blue">{rowCompactTitle(r)}</p>
                              <p className="text-sm text-gray-600 mt-0.5">
                                <span className="font-medium text-midnight-blue">{stdStatus}</span>
                                <span className="text-gray-400"> · </span>
                                Risk: {complianceImpactLabel(r).label}
                              </p>
                              {tierBadge ? (
                                <span
                                  className={cn(
                                    'inline-flex mt-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border',
                                    tierBadge.className,
                                  )}
                                >
                                  {tierBadge.text}
                                </span>
                              ) : null}
                              {statusUi.subline ? <p className="text-xs text-gray-500 mt-1">{statusUi.subline}</p> : null}
                            </div>
                            <div className="flex w-full flex-col gap-2 sm:max-w-md">
                              <Button
                                size="sm"
                                className="min-h-11 w-full bg-electric-teal text-white hover:bg-electric-teal/90 sm:min-h-11"
                                data-testid={taRow.primary_action_handler === 'guided_evidence' ? `compliance-urgent-guided-${rowReqId(r)}` : undefined}
                                disabled={taRow.primary_action_handler === 'guided_evidence_error'}
                                title={
                                  taRow.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined
                                }
                                onClick={() => {
                                  if (taRow.primary_action_handler === 'guided_evidence_error') return;
                                  runCompliancePrimaryCta(r);
                                }}
                              >
                                {taRow.primary_action_label}
                              </Button>
                              {showNonUploadSecondary ? (
                                <Button
                                  size="sm"
                                  type="button"
                                  variant="outline"
                                  className="min-h-10 w-full border-gray-300 text-gray-800 text-sm font-normal"
                                  onClick={() =>
                                    taRow.secondary_action.external
                                      ? window.open(taRow.secondary_action.route, '_blank', 'noopener,noreferrer')
                                      : navigate(taRow.secondary_action.route)
                                  }
                                >
                                  {taRow.secondary_action.label}
                                </Button>
                              ) : null}
                              {rowReqId(r) ? (
                                <button
                                  type="button"
                                  className="text-left text-xs font-normal text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline py-0.5"
                                  onClick={() => openComplianceRequirementIntel(r)}
                                >
                                  Requirement details
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="inline-flex items-center gap-1 text-left text-xs text-gray-500 hover:text-gray-700"
                                onClick={() => {
                                  if (explainOpen) {
                                    setUrgentExplainOpenId(null);
                                    return;
                                  }
                                  setUrgentExplainOpenId(rid);
                                }}
                              >
                                <Info className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
                                <span className="underline decoration-gray-300 underline-offset-2 hover:decoration-gray-500">
                                  Why this matters
                                </span>
                                {explainOpen ? (
                                  <ChevronUp className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
                                ) : (
                                  <ChevronDown className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
                                )}
                              </button>
                            </div>
                          </div>
                          {explainOpen && explainPayload ? (
                            <div className="px-3 pb-3 pt-0 border-t border-amber-100 bg-amber-50/30 space-y-2">
                              <div>
                                <p className="text-xs font-semibold text-midnight-blue uppercase tracking-wide mt-2">Why this matters</p>
                                <p className="text-sm text-gray-700 mt-1" data-testid="compliance-inline-why-short">
                                  {explainPayload.why_it_matters}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-midnight-blue uppercase tracking-wide">What changed</p>
                                <p className="text-sm text-gray-700 mt-1">{complianceWhatChangedLine(r)}</p>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Recommended action</p>
                                <p className="text-sm font-medium text-midnight-blue mt-1">{explainPayload.recommended_action_text}</p>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                    {urgentRequirementsOverflow > 0 ? (
                      <p className="text-sm text-gray-700 pt-1">
                        {urgentRequirementsOverflow} more requirements need review.{' '}
                        <button
                          type="button"
                          className="text-electric-teal font-medium hover:underline"
                          onClick={() => {
                            setComplianceStatusFilter('');
                            const el = document.querySelector('[data-testid="property-compliance-panel"]');
                            el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                          }}
                        >
                          View full compliance matrix.
                        </button>
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              )}

          {getFilteredRequirements().length > 0 && (
            <>
              <div className="hidden md:block rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 font-medium text-midnight-blue">Requirements</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-left text-gray-600">
                        <th className="p-3">Requirement</th>
                        <th className="p-3">Category</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Due date</th>
                        <th className="p-3">Documents</th>
                        <th className="p-3">Risk</th>
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
                        const stdStatus = complianceObligationStatusLabel(r);
                        const taRow = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId }).cta;
                        const complianceDomId = rowReqId(r) || `rc:${propertyId}:${normalizeRequirementCode(r.requirement_code || r.requirement_type || `t${idx}`)}`;
                        const isMissing = isRequirementMissingDocument(r);
                        const explainPayload = canonicalComplianceInlineNarrative(r);
                        const showComplianceMatrixSecondary =
                          taRow.secondary_action?.route && !isRedundantUploadStyleSecondaryAction(taRow);
                        const tierBadge = getLifecycleTierBadge(r);
                        return (
                          <React.Fragment key={rowReqId(r) || r.requirement_code || idx}>
                            <tr
                              className={cn(
                                'border-b border-gray-100 hover:bg-gray-50/90 cursor-pointer',
                                getRequirementLifecycleRowSurfaceClass(r),
                              )}
                              data-compliance-req-id={complianceDomId}
                              onClick={() => setComplianceExpandedReqId(complianceExpandedReqId === (rowReqId(r) || r.requirement_code) ? null : (rowReqId(r) || r.requirement_code))}
                              data-req-code={r.requirement_code || r.requirement_type || ''}
                            >
                              <td className="p-3 font-medium text-midnight-blue">{rowTitle(r)}</td>
                              <td className="p-3 text-gray-600">
                                {r.requirement_display?.category_label || r.category || '—'}
                              </td>
                              <td className="p-3">
                                <div>
                                  <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs ${status.className}`}>
                                    <Icon className="w-3.5 h-3.5" />
                                    {stdStatus}
                                  </span>
                                  {tierBadge ? (
                                    <span
                                      className={cn(
                                        'inline-flex items-center ml-2 px-2 py-0.5 rounded-full text-xs font-semibold border align-middle',
                                        tierBadge.className,
                                      )}
                                    >
                                      {tierBadge.text}
                                    </span>
                                  ) : null}
                                  {status.subline ? (
                                    <p className="text-xs text-gray-500 mt-1 max-w-xs">{status.subline}</p>
                                  ) : null}
                                </div>
                              </td>
                              <td className="p-3 text-gray-600">{formatDate(rowExpiry(r))}</td>
                              <td className="p-3 text-gray-600">{hasEvidence ? 'Linked' : '—'}</td>
                              <td className="p-3">
                                <span className={`inline-flex px-2 py-1 rounded border text-xs ${impact.className}`}>{impact.label}</span>
                              </td>
                              <td className="p-3" onClick={(e) => e.stopPropagation()}>
                                <div className="flex flex-col gap-1.5 items-start">
                                  <div className="flex flex-wrap gap-1 items-center">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="text-electric-teal border-electric-teal min-h-9"
                                      data-testid={`compliance-matrix-action-${rowReqId(r)}`}
                                      disabled={taRow.primary_action_handler === 'guided_evidence_error'}
                                      title={
                                        taRow.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined
                                      }
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (taRow.primary_action_handler === 'guided_evidence_error') return;
                                        runCompliancePrimaryCta(r);
                                      }}
                                    >
                                      {taRow.primary_intent === 'upload_evidence' && taRow.primary_action_handler === 'navigate' ? (
                                        <Upload className="w-3.5 h-3.5 mr-1 shrink-0" />
                                      ) : null}
                                      {taRow.actionType === 'JOB' ? <RefreshCw className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                                      {taRow.actionType === 'OBLIGATION' ? <Eye className="w-3.5 h-3.5 mr-1 shrink-0" /> : null}
                                      {taRow.primary_action_label}
                                    </Button>
                                    {showComplianceMatrixSecondary ? (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="min-h-9 border-gray-300 text-gray-800"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          if (taRow.secondary_action.external) {
                                            window.open(taRow.secondary_action.route, '_blank', 'noopener,noreferrer');
                                          } else {
                                            navigate(taRow.secondary_action.route);
                                          }
                                        }}
                                      >
                                        {taRow.secondary_action.label}
                                      </Button>
                                    ) : null}
                                  </div>
                                  <div className="flex flex-wrap gap-x-2 gap-y-0.5 items-center">
                                    {isMissing &&
                                      !suppressMarkNotApplicableCta(r) &&
                                      (r.requirement_code || r.requirement_type) && (
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-auto min-h-0 py-0.5 px-1 text-xs font-normal text-gray-500 hover:text-gray-700"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setNotApplicableModal({
                                            requirement_code: r.requirement_code || r.requirement_type,
                                            title: rowTitle(r),
                                          });
                                          setNotApplicablePreset('not_applicable');
                                          setNotApplicableAuditText('');
                                        }}
                                        data-testid="mark-not-applicable"
                                      >
                                        <MinusCircle className="w-3 h-3 mr-1 shrink-0" aria-hidden />
                                        Not applicable
                                      </Button>
                                    )}
                                    {rowReqId(r) ? (
                                      <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-auto min-h-0 py-0.5 px-1 text-xs font-normal text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          openComplianceRequirementIntel(r);
                                        }}
                                        data-testid={`property-compliance-requirement-intel-${rowReqId(r)}`}
                                      >
                                        Requirement details
                                      </Button>
                                    ) : null}
                                  </div>
                                </div>
                              </td>
                            </tr>
                            {complianceExpandedReqId === (rowReqId(r) || r.requirement_code) && (
                              <tr className="bg-gray-50 border-b border-gray-200">
                                <td colSpan={7} className="p-4">
                                  <div className="text-sm space-y-3 max-w-3xl">
                                    <p><span className="font-semibold text-midnight-blue">Requirement:</span> {rowTitle(r)}</p>
                                    <div>
                                      <p className="font-semibold text-midnight-blue">Why this matters</p>
                                      <p className="text-gray-700 mt-1" data-testid="compliance-inline-why-short">
                                        {explainPayload.why_it_matters}
                                      </p>
                                    </div>
                                    <div>
                                      <p className="font-semibold text-midnight-blue">What changed</p>
                                      <p className="text-gray-700 mt-1">{complianceWhatChangedLine(r)}</p>
                                    </div>
                                    <p>
                                      <span className="font-semibold text-midnight-blue">Status:</span> {stdStatus}
                                      {status.subline ? ` — ${status.subline}` : ''}
                                    </p>
                                    <p>
                                      <span className="font-semibold text-midnight-blue">Due date:</span> {formatDate(rowExpiry(r))}
                                      {days != null ? (days < 0 ? ` (${Math.abs(days)} days overdue)` : ` (${days} days left)`) : ''}
                                    </p>
                                    <p><span className="font-semibold text-midnight-blue">Document on file:</span> {hasEvidence ? 'Yes' : 'No'}</p>
                                    <p><span className="font-semibold text-midnight-blue">Risk if not met:</span> {impact.label}</p>
                                    <p><span className="font-semibold text-midnight-blue">Recommended action:</span> {explainPayload.recommended_action_text}</p>
                                    <div className="flex flex-wrap gap-2 pt-1">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={taRow.primary_action_handler === 'guided_evidence_error'}
                                        title={
                                          taRow.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined
                                        }
                                        onClick={() => {
                                          if (taRow.primary_action_handler === 'guided_evidence_error') return;
                                          runCompliancePrimaryCta(r);
                                        }}
                                      >
                                        {taRow.primary_action_label}
                                      </Button>
                                      {rowReqId(r) ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={() => {
                                            setComplianceExpandedReqId(null);
                                            openComplianceRequirementIntel(r);
                                          }}
                                        >
                                          Requirement details
                                        </Button>
                                      ) : null}
                                      <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_EVIDENCE)}>Open Documents tab</Button>
                                      <Button size="sm" variant="outline" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'COMPLIANCE' })); }}>View timeline</Button>
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
                  const isMissing = isRequirementMissingDocument(r);
                  const stdStatus = complianceObligationStatusLabel(r);
                  const taRow = projectResolvedRequirementSemantics(r, { pagePropertyId: propertyId }).cta;
                  const complianceDomId = rowReqId(r) || `rc:${propertyId}:${normalizeRequirementCode(r.requirement_code || r.requirement_type || `m${idx}`)}`;
                  const showComplianceMobileSecondary =
                    taRow.secondary_action?.route && !isRedundantUploadStyleSecondaryAction(taRow);
                  const tierBadge = getLifecycleTierBadge(r);
                  return (
                    <Card key={rowReqId(r) || idx} className={cn(getRequirementLifecycleCardShellClass(r), 'p-3')} data-compliance-req-id={complianceDomId}>
                      <div className="font-medium text-midnight-blue">{rowTitle(r)}</div>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs ${status.className}`}><Icon className="w-3 h-3" />{stdStatus}</span>
                        {tierBadge ? (
                          <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border', tierBadge.className)}>
                            {tierBadge.text}
                          </span>
                        ) : null}
                        <span className={`inline-flex px-2 py-0.5 rounded border text-xs ${impact.className}`}>Risk: {impact.label}</span>
                      </div>
                      {status.subline ? <p className="text-xs text-gray-500 mt-1">{status.subline}</p> : null}
                      <div className="text-xs text-gray-500 mt-1">{formatDate(rowExpiry(r))} · {hasEvidence ? 'Document linked' : 'No document'}</div>
                      <div className="mt-2 flex flex-col gap-1.5">
                        <div className="flex flex-wrap gap-1 items-center">
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-electric-teal border-electric-teal min-h-9"
                            disabled={taRow.primary_action_handler === 'guided_evidence_error'}
                            title={
                              taRow.primary_action_handler === 'guided_evidence_error' ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined
                            }
                            onClick={() => {
                              if (taRow.primary_action_handler === 'guided_evidence_error') return;
                              runCompliancePrimaryCta(r);
                            }}
                          >
                            {taRow.primary_action_label}
                          </Button>
                          {showComplianceMobileSecondary ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="min-h-9 border-gray-300 text-gray-800"
                              onClick={() =>
                                taRow.secondary_action.external
                                  ? window.open(taRow.secondary_action.route, '_blank', 'noopener,noreferrer')
                                  : navigate(taRow.secondary_action.route)
                              }
                            >
                              {taRow.secondary_action.label}
                            </Button>
                          ) : null}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="min-h-9"
                            onClick={() =>
                              setComplianceExpandedReqId(
                                complianceExpandedReqId === (rowReqId(r) || r.requirement_code)
                                  ? null
                                  : rowReqId(r) || r.requirement_code,
                              )
                            }
                          >
                            Details
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-x-2 gap-y-0.5 items-center">
                          {rowReqId(r) ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-auto min-h-0 py-0.5 px-1 text-xs font-normal text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline"
                              onClick={() => openComplianceRequirementIntel(r)}
                            >
                              Requirement details
                            </Button>
                          ) : null}
                          {isMissing &&
                          !suppressMarkNotApplicableCta(r) &&
                          (r.requirement_code || r.requirement_type) ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-auto min-h-0 py-0.5 px-1 text-xs font-normal text-gray-500 hover:text-gray-700"
                              onClick={() => {
                                setNotApplicableModal({ requirement_code: r.requirement_code || r.requirement_type, title: rowTitle(r) });
                                setNotApplicablePreset('not_applicable');
                                setNotApplicableAuditText('');
                              }}
                            >
                              <MinusCircle className="w-3 h-3 mr-1 shrink-0" aria-hidden />
                              Not applicable
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
            </div>
          )}

          {/* E) Compliance notes strip */}
          <p className="text-xs text-gray-500">Status based on portal records. Informational indicator only. Not legal advice.</p>
        </div>
        </>
      )}

      {/* Tab: Jobs & issues (maintenance issues + work orders, including compliance jobs) */}
      {activeTab === TAB_MAINTENANCE && !hasFeature('maintenance_workflows') && (
        <DiscoverabilityHint
          title={`${getFeatureDisplayInfo('maintenance_workflows').featureName} — portfolio-scale`}
          body="Create and manage issues, repair jobs, and compliance-led jobs when you add portfolio-scale automation. Evidence uploads and requirements stay available on your current plan."
          onCta={() =>
            navigate(
              buildSafeQueryPath('/settings/billing', {
                upgrade_to: getFeatureDisplayInfo('maintenance_workflows').requiredPlan,
              }),
            )
          }
        />
      )}
      {activeTab === TAB_MAINTENANCE && hasFeature('maintenance_workflows') && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-midnight-blue">Jobs & issues</h2>
              <p className="text-sm text-gray-600 mt-1 max-w-2xl">
                Operational queue for this property: triaged issues, repairs, and jobs raised from compliance (for requirement status and documents, use the Compliance tab).
              </p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="min-h-11" onClick={() => setCreateIssueOpen(true)}>
                <FileText className="w-4 h-4 mr-2" />
                {PORTAL_COPY.reportIssue}
              </Button>
              <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90 min-h-11" onClick={() => setCreateWoOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                {PORTAL_COPY.addWorkOrder}
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
              <CardTitle className="text-base">{PORTAL_COPY.maintenanceIssues}</CardTitle>
              <PortalFilterStack className="mt-2">
                <select value={maintenanceIssueFilter.status} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, status: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-2 text-sm min-h-11 w-full md:w-auto">
                  <option value="">All statuses</option><option value="new">New</option><option value="triaged">Triaged</option><option value="ready_for_work_order">{issueStatusLabel('ready_for_work_order')}</option><option value="closed">Closed</option>
                </select>
                <select value={maintenanceIssueFilter.severity} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, severity: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-2 text-sm min-h-11 w-full md:w-auto">
                  <option value="">All severities</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
                </select>
                <select value={maintenanceIssueFilter.category} onChange={(e) => setMaintenanceIssueFilter((f) => ({ ...f, category: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-2 text-sm min-h-11 w-full md:w-auto">
                  <option value="">All categories</option><option value="general">General</option><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="heating">Heating</option>
                </select>
                <Button size="sm" variant="ghost" className="min-h-11 w-full md:w-auto" onClick={loadMaintenanceIssues}>Refresh</Button>
              </PortalFilterStack>
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
                <>
                  <div className="md:hidden space-y-3">
                    {maintenanceIssues.map((iss) => (
                      <Card key={iss.issue_id} className="border border-gray-200 p-3">
                        <p className="font-medium text-midnight-blue text-sm">{iss.description || '—'}</p>
                        <p className="text-xs text-gray-600 mt-1">
                          {operationalLabelForToken(iss.category, { emptyLabel: '—' })} · {iss.severity || '—'} · {issueStatusLabel(iss.status)}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {iss.created_at ? formatDate(iss.created_at) : '—'} · {assetLabel(iss.asset_id)}
                        </p>
                        <div className="flex flex-col gap-2 mt-3">
                          <Button size="sm" variant="outline" className="min-h-11 w-full" onClick={() => setIssueDetailDrawer(iss.issue_id)}>{PORTAL_COPY.viewDetails}</Button>
                          {iss.status !== 'ready_for_work_order' && iss.status !== 'closed' && (
                            <Button size="sm" className="min-h-11 w-full bg-electric-teal hover:bg-electric-teal/90" onClick={() => handleCreateWoFromIssue(iss.issue_id)}>{PORTAL_COPY.addWorkOrder}</Button>
                          )}
                        </div>
                      </Card>
                    ))}
                  </div>
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead><tr className="border-b text-left text-gray-600"><th className="p-2">Summary</th><th className="p-2">Category</th><th className="p-2">Severity</th><th className="p-2">Priority</th><th className="p-2">Asset</th><th className="p-2">Source</th><th className="p-2">Status</th><th className="p-2">Created</th><th className="p-2 text-right">Actions</th></tr></thead>
                      <tbody>
                        {maintenanceIssues.map((iss) => (
                          <tr key={iss.issue_id} className="border-b hover:bg-gray-50">
                            <td className="p-2 font-medium max-w-[180px] truncate" title={iss.description}>{iss.description || '—'}</td>
                            <td className="p-2 text-gray-600">{operationalLabelForToken(iss.category, { emptyLabel: '—' })}</td>
                            <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${(iss.severity || '').toLowerCase() === 'urgent' ? 'bg-red-100 text-red-800' : (iss.severity || '').toLowerCase() === 'high' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'}`}>{iss.severity || '—'}</span></td>
                            <td className="p-2">{iss.priority_score != null ? iss.priority_score : '—'}</td>
                            <td className="p-2 text-gray-600">{assetLabel(iss.asset_id)}</td>
                            <td className="p-2 text-gray-600">{iss.source || '—'}</td>
                            <td className="p-2">{issueStatusLabel(iss.status)}</td>
                            <td className="p-2 text-gray-600">{iss.created_at ? formatDate(iss.created_at) : '—'}</td>
                            <td className="p-2 text-right">
                              <Button size="sm" variant="ghost" onClick={() => setIssueDetailDrawer(iss.issue_id)}>View</Button>
                              {iss.status !== 'ready_for_work_order' && iss.status !== 'closed' && (
                                <Button size="sm" variant="outline" className="ml-1" onClick={() => handleCreateWoFromIssue(iss.issue_id)}>Start maintenance job</Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Jobs queue: compliance vs repairs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{PORTAL_COPY.workOrders}</CardTitle>
              <CardDescription>Compliance-led jobs (inspections, renewals) and repair jobs are listed separately.</CardDescription>
              <PortalFilterStack className="mt-2">
                <select value={maintenanceWoFilter.status} onChange={(e) => setMaintenanceWoFilter((f) => ({ ...f, status: e.target.value }))} className="border border-gray-200 rounded-md px-2 py-2 text-sm min-h-11 w-full md:w-auto">
                  <option value="">All statuses</option><option value="OPEN">Open</option><option value="ASSIGNED">Assigned</option><option value="IN_PROGRESS">In progress</option><option value="COMPLETED">Completed</option><option value="CANCELLED">Cancelled</option>
                </select>
                <Button size="sm" variant="ghost" className="min-h-11 w-full md:w-auto" onClick={loadWorkOrders}>Refresh</Button>
              </PortalFilterStack>
            </CardHeader>
            <CardContent>
              {workOrdersLoading && workOrders.length === 0 ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : filteredWorkOrders.length === 0 ? (
                <div className="py-8 text-center text-gray-500">
                  <p className="font-medium">No jobs on this property yet.</p>
                  <div className="flex flex-wrap gap-2 justify-center mt-3">
                    <Button size="sm" variant="outline" onClick={() => setCreateWoOpen(true)}>Start maintenance job</Button>
                    {hasFeature('contractor_network') && <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_CONTRACTORS)}>Contractors</Button>}
                  </div>
                </div>
              ) : (
                <div className="space-y-8">
                  <section aria-labelledby="property-compliance-jobs-heading">
                    <h3 id="property-compliance-jobs-heading" className="text-sm font-semibold text-midnight-blue">Compliance jobs</h3>
                    <p className="text-xs text-gray-500 mt-0.5 mb-3">Inspections and certificate-led work. Requirement status lives under Compliance.</p>
                    {complianceWorkOrdersFiltered.length === 0 ? (
                      <p className="text-sm text-gray-500 py-2">No compliance jobs match these filters.</p>
                    ) : (
                      <>
                        <div className="md:hidden space-y-3">
                          {complianceWorkOrdersFiltered.map((wo) => (
                            <Card key={wo.work_order_id} className="border border-gray-200 p-3">
                              <div className="flex flex-wrap items-start gap-2">
                                <p className="font-medium text-midnight-blue text-sm flex-1 min-w-0">{wo.description || '—'}</p>
                                <span className={cn('shrink-0 inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                              </div>
                              <p className="text-xs text-gray-600 mt-1">
                                {workOrderStatusLabel(wo.status)} · {wo.severity || '—'}
                                {wo.sla_complete_by ? ` · SLA ${formatDate(wo.sla_complete_by)}` : ''}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                {wo.updated_at ? formatRelativeTime(wo.updated_at) : '—'} · {assetLabel(wo.asset_id)}
                                {wo.issue_id ? (
                                  <>
                                    {' · '}
                                    <button type="button" className="text-electric-teal hover:underline" onClick={() => setIssueDetailDrawer(wo.issue_id)}>{PORTAL_COPY.maintenanceIssue}</button>
                                  </>
                                ) : null}
                              </p>
                              <Button size="sm" variant="outline" className="min-h-11 w-full mt-3" onClick={() => setWoDetailDrawer(wo.work_order_id)}>Preview</Button>
                            </Card>
                          ))}
                        </div>
                        <div className="hidden md:block overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead><tr className="border-b text-left text-gray-600"><th className="p-2">Description</th><th className="p-2">Job type</th><th className="p-2">Linked issue</th><th className="p-2">Asset</th><th className="p-2">Severity</th><th className="p-2">Status</th><th className="p-2">SLA due</th><th className="p-2">Updated</th><th className="p-2 text-right">Actions</th></tr></thead>
                            <tbody>
                              {complianceWorkOrdersFiltered.map((wo) => (
                                <tr key={wo.work_order_id} className="border-b hover:bg-gray-50">
                                  <td className="p-2 font-medium max-w-[180px] truncate" title={wo.description}>{wo.description || '—'}</td>
                                  <td className="p-2 whitespace-nowrap">
                                    <span className={cn('inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                                  </td>
                                  <td className="p-2 text-gray-600">{wo.issue_id ? <button type="button" className="text-electric-teal hover:underline" onClick={() => setIssueDetailDrawer(wo.issue_id)}>View issue</button> : '—'}</td>
                                  <td className="p-2 text-gray-600">{assetLabel(wo.asset_id)}</td>
                                  <td className="p-2"><span className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{wo.severity || '—'}</span></td>
                                  <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${wo.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : wo.status === 'CANCELLED' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800'}`}>{workOrderStatusLabel(wo.status)}</span></td>
                                  <td className="p-2 text-gray-600">{wo.sla_complete_by ? formatDate(wo.sla_complete_by) : '—'}</td>
                                  <td className="p-2 text-gray-600">{wo.updated_at ? formatRelativeTime(wo.updated_at) : '—'}</td>
                                  <td className="p-2 text-right"><Button size="sm" variant="ghost" onClick={() => setWoDetailDrawer(wo.work_order_id)}>Preview</Button></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </section>
                  <section aria-labelledby="property-repair-jobs-heading">
                    <h3 id="property-repair-jobs-heading" className="text-sm font-semibold text-midnight-blue">Repairs & maintenance</h3>
                    <p className="text-xs text-gray-500 mt-0.5 mb-3">Reactive and planned repair jobs.</p>
                    {repairWorkOrdersFiltered.length === 0 ? (
                      <p className="text-sm text-gray-500 py-2">No repair jobs match these filters.</p>
                    ) : (
                      <>
                        <div className="md:hidden space-y-3">
                          {repairWorkOrdersFiltered.map((wo) => (
                            <Card key={wo.work_order_id} className="border border-gray-200 p-3">
                              <div className="flex flex-wrap items-start gap-2">
                                <p className="font-medium text-midnight-blue text-sm flex-1 min-w-0">{wo.description || '—'}</p>
                                <span className={cn('shrink-0 inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                              </div>
                              <p className="text-xs text-gray-600 mt-1">
                                {workOrderStatusLabel(wo.status)} · {wo.severity || '—'}
                                {wo.sla_complete_by ? ` · SLA ${formatDate(wo.sla_complete_by)}` : ''}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                {wo.updated_at ? formatRelativeTime(wo.updated_at) : '—'} · {assetLabel(wo.asset_id)}
                                {wo.issue_id ? (
                                  <>
                                    {' · '}
                                    <button type="button" className="text-electric-teal hover:underline" onClick={() => setIssueDetailDrawer(wo.issue_id)}>{PORTAL_COPY.maintenanceIssue}</button>
                                  </>
                                ) : null}
                              </p>
                              <Button size="sm" variant="outline" className="min-h-11 w-full mt-3" onClick={() => setWoDetailDrawer(wo.work_order_id)}>Preview</Button>
                            </Card>
                          ))}
                        </div>
                        <div className="hidden md:block overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead><tr className="border-b text-left text-gray-600"><th className="p-2">Description</th><th className="p-2">Job type</th><th className="p-2">Linked issue</th><th className="p-2">Asset</th><th className="p-2">Severity</th><th className="p-2">Status</th><th className="p-2">SLA due</th><th className="p-2">Updated</th><th className="p-2 text-right">Actions</th></tr></thead>
                            <tbody>
                              {repairWorkOrdersFiltered.map((wo) => (
                                <tr key={wo.work_order_id} className="border-b hover:bg-gray-50">
                                  <td className="p-2 font-medium max-w-[180px] truncate" title={wo.description}>{wo.description || '—'}</td>
                                  <td className="p-2 whitespace-nowrap">
                                    <span className={cn('inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                                  </td>
                                  <td className="p-2 text-gray-600">{wo.issue_id ? <button type="button" className="text-electric-teal hover:underline" onClick={() => setIssueDetailDrawer(wo.issue_id)}>View issue</button> : '—'}</td>
                                  <td className="p-2 text-gray-600">{assetLabel(wo.asset_id)}</td>
                                  <td className="p-2"><span className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{wo.severity || '—'}</span></td>
                                  <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${wo.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : wo.status === 'CANCELLED' ? 'bg-gray-100 text-gray-600' : 'bg-amber-100 text-amber-800'}`}>{workOrderStatusLabel(wo.status)}</span></td>
                                  <td className="p-2 text-gray-600">{wo.sla_complete_by ? formatDate(wo.sla_complete_by) : '—'}</td>
                                  <td className="p-2 text-gray-600">{wo.updated_at ? formatRelativeTime(wo.updated_at) : '—'}</td>
                                  <td className="p-2 text-right"><Button size="sm" variant="ghost" onClick={() => setWoDetailDrawer(wo.work_order_id)}>Preview</Button></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </section>
                </div>
              )}
            </CardContent>
          </Card>

          {/* SLA panel */}
          {slaAtRiskOrBreached.length > 0 && (
            <Card className="border-amber-200 bg-amber-50/30">
              <CardHeader><CardTitle className="text-base">SLA deadlines at risk or missed</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {slaAtRiskOrBreached.slice(0, 10).map((wo) => (
                    <li key={wo.work_order_id} className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-white border border-amber-100">
                      <span className="font-medium truncate max-w-[200px] flex flex-wrap items-center gap-2 min-w-0">
                        <span className="truncate">{wo.description || wo.work_order_id}</span>
                        <span className={cn('shrink-0 inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border', workOrderKindBadgeClassName(wo))}>{workOrderKindClientLabel(wo)}</span>
                      </span>
                      <span className="text-xs text-gray-600">{wo.sla_complete_by ? formatDate(wo.sla_complete_by) : '—'}</span>
                      {wo.sla_breached_at ? (
                        <span className="text-xs text-red-600 font-medium">Deadline missed</span>
                      ) : (
                        <span className="text-xs text-amber-600">Near deadline</span>
                      )}
                      <Button size="sm" variant="outline" onClick={() => setWoDetailDrawer(wo.work_order_id)}>Preview</Button>
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
                <span className="text-sm text-gray-600">Recurring issues and repair history feed into open issues.</span>
                <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_RISK_SIGNALS)}>View issues</Button>
              </CardContent>
            </Card>
          )}

          {createWoOpen && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setCreateWoOpen(false)}>
              <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[min(90dvh,90vh)] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Add job</h2>
                <form onSubmit={handleCreateWorkOrder} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
                    <textarea value={createWoForm.description} onChange={(e) => setCreateWoForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={3} placeholder="Describe the issue..." required />
                  </div>
                  <div className="flex items-start gap-2 rounded-md border border-gray-200 bg-gray-50/80 p-3">
                    <input
                      id="create-wo-inspection-required"
                      type="checkbox"
                      className="mt-1"
                      checked={!!createWoForm.inspection_required}
                      onChange={(e) => setCreateWoForm((f) => ({ ...f, inspection_required: e.target.checked }))}
                    />
                    <label htmlFor="create-wo-inspection-required" className="text-sm text-gray-700 cursor-pointer">
                      <span className="font-medium">Inspection before quote</span>
                      <span className="block text-xs text-gray-600 mt-0.5">
                        Contractor inspects first; repair price is agreed only after they submit a quote and you approve it in the
                        portal.
                      </span>
                    </label>
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
              <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[min(90dvh,90vh)] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
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
          <div className={cn(portalDrawerPanelClass, 'max-w-lg')} onClick={(e) => e.stopPropagation()}>
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
                    <dt className="text-gray-500">Category</dt><dd>{operationalLabelForToken(issueDetailData.category, { emptyLabel: '—' })}</dd>
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
                    <p className="text-sm text-gray-600 mb-4">
                      Recommended contractor:{' '}
                      {operationalLabelForToken(issueDetailData.triage.recommended_contractor_type, { emptyLabel: '—' })}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2 pt-2">
                    {issueDetailData.status !== 'ready_for_work_order' && issueDetailData.status !== 'closed' && (
                      <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => handleCreateWoFromIssue(issueDetailData.issue_id)}>Start maintenance job</Button>
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

      {/* Job preview drawer — read-only; decision copy matches `GET /jobs/:id` next_actions (full job page) */}
      {woDetailDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setWoDetailDrawer(null)}>
          <div className={cn(portalDrawerPanelClass, 'max-w-lg')} onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <div className="min-w-0 pr-2">
                <h3 className="font-semibold text-midnight-blue">Job preview</h3>
                <p className="text-xs text-gray-500 mt-0.5">Read-only — preview and navigation only.</p>
              </div>
              <button type="button" onClick={() => setWoDetailDrawer(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4">
              {woDetailLoading ? (
                <div className="flex gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
              ) : (() => {
                const wf = woPreviewPayload?.source === 'workflow' ? woPreviewPayload.job : null;
                const mw = woPreviewPayload?.source === 'maintenance' ? woPreviewPayload.wo : null;
                const basis = wf || mw;
                if (!basis) {
                  return <p className="text-gray-500 py-4">Could not load this job.</p>;
                }
                const workId = basis.work_order_id || woDetailDrawer;
                const current = clientCurrentUpdateSummary(wf || basis);
                const slaDue = basis.sla_complete_by ? formatDate(basis.sla_complete_by) : '—';
                let slaUrgency = slaDue;
                if (basis.sla_breached_at) slaUrgency = `${slaDue} · SLA deadline missed`;
                else if (basis.sla_breach_risk_at) slaUrgency = `${slaDue} · Near SLA deadline`;
                const cid = String(basis.contractor_id || '').trim();
                const cname = String(basis.contractor_name || '').trim();
                const contractorSummary = cid ? (cname && cname !== cid ? `${cname} · ${cid}` : cid) : 'Unassigned';
                const ss = String(basis.schedule_status || '').toLowerCase();
                const sched = basis.scheduled_at;
                let visitSummary = '—';
                if (sched) {
                  const when = formatJobPreviewDateTime(sched);
                  if (ss === 'confirmed') visitSummary = `${when} · Confirmed`;
                  else if (ss === 'proposed') visitSummary = `${when} · Proposed (confirm on full job page)`;
                  else visitSummary = `${when}${ss ? ` · ${operationalLabelForToken(ss, { emptyLabel: '' })}` : ''}`;
                } else if (ss) {
                  visitSummary = operationalLabelForToken(ss, { emptyLabel: '—' });
                }
                const pr = basis.pricing;
                let quoteSummary = null;
                if (pr?.pricing_workflow) {
                  const bits = [operationalLabelForToken(pr.price_status, { emptyLabel: '—' })];
                  if (pr.quoted_price != null && pr.quoted_price !== '') {
                    bits.push(`£${Number(pr.quoted_price).toFixed(2)}${pr.price_currency ? ` ${pr.price_currency}` : ''}`);
                  }
                  quoteSummary = bits.join(' · ');
                }
                const reqId = wf?.linked_property_requirement_id || mw?.linked_property_requirement_id;
                const reqCode = basis.requirement_code;
                const reqHref =
                  reqId && propertyId
                    ? buildEntityRoute({ requirement_id: reqId, property_id: propertyId, mode: 'requirement' }, '')
                    : '';
                const { nextStep, cta } = wf
                  ? { nextStep: jobPreviewNextStepLine(wf), cta: jobPreviewManageJobCtaLabel(wf) }
                  : maintenanceWorkOrderPreviewDecision(mw);
                return (
                  <>
                    <div className="mb-3">
                      <p className="text-xs font-mono text-gray-500 truncate" title={workId}>{workId}</p>
                      <p className="font-medium text-gray-900 mt-1">{basis.description || '—'}</p>
                    </div>
                    <dl className="grid grid-cols-[7.5rem_1fr] gap-x-2 gap-y-2 text-sm text-gray-800 mb-4">
                      <dt className="text-gray-500">Job type</dt>
                      <dd>
                        <span className={cn('inline-flex px-1.5 py-0.5 rounded text-xs font-medium border', workOrderKindBadgeClassName(basis))}>{workOrderKindClientLabel(basis)}</span>
                      </dd>
                      <dt className="text-gray-500">Status</dt>
                      <dd>
                        <span
                          className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${basis.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : basis.status === 'CANCELLED' ? 'bg-gray-100 text-gray-700' : 'bg-amber-100 text-amber-800'}`}
                          title={basis.status ? operationalLabelForToken(basis.status) : undefined}
                        >
                          {workOrderStatusLabel(basis.status)}
                        </span>
                        {current.headline ? <span className="block text-xs text-gray-500 mt-0.5">{current.headline}</span> : null}
                      </dd>
                      <dt className="text-gray-500">SLA / urgency</dt>
                      <dd className="text-sm">
                        <span className="block">{slaUrgency}</span>
                        {current.lines?.length > 0 ? (
                          <ul className="mt-1 text-xs text-gray-600 list-disc list-inside space-y-0.5">
                            {current.lines.map((line, i) => (
                              <li key={i}>{line}</li>
                            ))}
                          </ul>
                        ) : null}
                      </dd>
                      <dt className="text-gray-500">Contractor</dt>
                      <dd className="text-sm break-words">{contractorSummary}</dd>
                      <dt className="text-gray-500">Visit</dt>
                      <dd className="text-sm">{visitSummary}</dd>
                      {quoteSummary ? (
                        <>
                          <dt className="text-gray-500">Quote</dt>
                          <dd className="text-sm">{quoteSummary}</dd>
                        </>
                      ) : null}
                      <dt className="text-gray-500">Linked issue</dt>
                      <dd>
                        {basis.issue_id ? (
                          <button type="button" className="text-electric-teal hover:underline text-sm" onClick={() => { setIssueDetailDrawer(basis.issue_id); setWoDetailDrawer(null); }}>
                            Open linked issue
                          </button>
                        ) : (
                          '—'
                        )}
                      </dd>
                      <dt className="text-gray-500">Requirement</dt>
                      <dd className="text-sm">
                        {reqHref ? (
                          <Link to={reqHref} className="text-electric-teal hover:underline" onClick={() => setWoDetailDrawer(null)}>
                            {reqCode ? requirementLabel(reqCode) : 'Open requirement'}
                          </Link>
                        ) : reqCode ? (
                          requirementLabel(reqCode)
                        ) : (
                          '—'
                        )}
                      </dd>
                    </dl>
                    {basis.resolution_outcome ? (
                      <p className="text-xs text-gray-600 mb-3">
                        Outcome: {operationalLabelForToken(basis.resolution_outcome, { emptyLabel: '—' })}
                      </p>
                    ) : null}
                    {!quoteSummary && basis.cost_estimate_min != null && basis.cost_estimate_max != null ? (
                      <p className="text-xs text-gray-600 mb-3">Cost estimate: £{basis.cost_estimate_min} – £{basis.cost_estimate_max}</p>
                    ) : null}
                    <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3 mb-4">
                      <p className="text-sm font-medium text-midnight-blue mt-1.5 leading-snug">{nextStep}</p>
                      <p className="text-xs text-gray-500 mt-2">Continue on the full job page.</p>
                    </div>
                    <div className="flex flex-col gap-2">
                      <Button
                        size="sm"
                        className="w-full min-h-11 bg-electric-teal hover:bg-electric-teal/90 text-white"
                        onClick={() => {
                          if (!workId) return;
                          navigate(resolveClientPortalPath(`/operations/jobs/${encodeURIComponent(workId)}`, '/operations/work-orders'));
                          setWoDetailDrawer(null);
                        }}
                      >
                        {cta}
                      </Button>
                      {hasFeature('contractor_network') && (
                        <Button size="sm" variant="outline" className="w-full min-h-11" onClick={() => { setActiveTab(TAB_CONTRACTORS); setWoDetailDrawer(null); }}>
                          Browse contractors
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" className="w-full min-h-11 text-gray-600" onClick={() => setWoDetailDrawer(null)}>
                        Close
                      </Button>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Documents (internal id evidence) — files provided for this property */}
      {activeTab === TAB_EVIDENCE && (
        <div className="space-y-6" id="property-documents-panel">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-midnight-blue">Documents for this property</h2>
              <p className="text-xs text-gray-500 mt-1">What you have uploaded and linked. Requirements and status stay on the Compliance tab.</p>
            </div>
            <Button
              className="bg-electric-teal text-white hover:bg-electric-teal/90 min-h-11 shrink-0"
              onClick={() => navigate(resolveDocumentsPath(propertyId))}
            >
              <Upload className="w-4 h-4 mr-2" />
              {PORTAL_COPY.uploadDocument}
            </Button>
          </div>
          <p className="text-sm text-gray-500">
            <Link to="/help?article=uploading-evidence" className="text-electric-teal hover:underline">Uploading documents</Link>
            {' · Requirement status: '}
            <button
              type="button"
              className="text-electric-teal hover:underline p-0 border-0 bg-transparent text-sm font-inherit cursor-pointer"
              onClick={() => setActiveTab(TAB_COMPLIANCE)}
            >
              Compliance tab
            </button>
            .
          </p>

          {evidenceLoading ? (
            <PortalLoadingPanel message="Loading documents…" />
          ) : !evidenceData ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-gray-500 space-y-3">
                <p>Unable to load documents for this property.</p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    loadEvidence();
                    handleRefresh();
                  }}
                >
                  Try again
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* A) Summary */}
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
                  <span>
                    <strong className="text-midnight-blue">Total documents:</strong> {evidenceData.summary?.totalDocuments ?? 0}
                  </span>
                  <span>
                    <strong className="text-midnight-blue">Linked:</strong> {evidenceData.summary?.linked ?? 0}
                  </span>
                  <span>
                    <strong className="text-midnight-blue">Awaiting verification:</strong> {evidenceData.summary?.pendingConfirmation ?? 0}
                  </span>
                  {(evidenceData.summary?.missingCriticalEvidence ?? 0) > 0 ? (
                    <button
                      type="button"
                      className="text-left text-sm border-0 bg-transparent p-0 cursor-pointer hover:underline text-midnight-blue font-inherit"
                      onClick={() => {
                        setComplianceStatusFilter('MISSING');
                        setActiveTab(TAB_COMPLIANCE);
                      }}
                    >
                      <strong className="text-midnight-blue">Missing critical documents:</strong>{' '}
                      {evidenceData.summary?.missingCriticalEvidence ?? 0}
                      <span className="text-xs text-gray-500 font-normal"> — view in Compliance</span>
                    </button>
                  ) : (
                    <span>
                      <strong className="text-midnight-blue">Missing critical documents:</strong> {evidenceData.summary?.missingCriticalEvidence ?? 0}
                    </span>
                  )}
                  <span>
                    <strong className="text-midnight-blue">Last uploaded:</strong>{' '}
                    {evidenceData.summary?.lastUploadedAt ? formatRelativeTime(evidenceData.summary.lastUploadedAt) : '—'}
                  </span>
                </div>
              </div>

              {(evidenceData.summary?.missingCriticalEvidence ?? 0) > 0 && (
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardContent className="py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <span className="text-sm text-amber-800">
                      Some requirements still need documents. Uploads are opened for this property; pick the requirement when you upload.
                    </span>
                    <div className="flex flex-col sm:flex-row gap-2 shrink-0 w-full sm:w-auto">
                      <Button
                        size="sm"
                        className="bg-electric-teal text-white hover:bg-electric-teal/90 min-h-11"
                        onClick={() => navigate(resolveDocumentsPath(propertyId))}
                      >
                        {PORTAL_COPY.uploadDocument}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="min-h-11 border-amber-300 text-amber-900"
                        onClick={() => {
                          setComplianceStatusFilter('MISSING');
                          setActiveTab(TAB_COMPLIANCE);
                        }}
                      >
                        View full missing list in Compliance
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {requirementsMissingDocuments.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-1">Requirements still needing documents</h3>
                  <p className="text-xs text-gray-500 mb-3">
                    Same filter and order as Compliance → Missing documents (critical items first).
                  </p>
                  <PropertyDocumentsMissingRequirementList
                    items={requirementsMissingDocuments}
                    propertyId={propertyId}
                    navigate={navigate}
                    rowTitle={rowTitle}
                    rowReqId={rowReqId}
                    maxItems={12}
                    onSubmitted={fetchData}
                    openGuidedEvidenceModal={(p) =>
                      openGuidedEvidence({
                        propertyId,
                        requirement: p.requirement,
                        onSubmitted: p.onSubmitted || fetchData,
                        initialEvidenceMode: p.initialEvidenceMode,
                      })
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-2 text-electric-teal min-h-9 px-0"
                    onClick={() => {
                      setComplianceStatusFilter('MISSING');
                      setActiveTab(TAB_COMPLIANCE);
                    }}
                  >
                    View full missing list in Compliance
                  </Button>
                </div>
              )}

              {/* All uploaded files */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">All documents</h3>
                {(evidenceData.documents?.length ?? 0) === 0 ? (
                  <Card className="border border-gray-200">
                    <CardContent className="py-6 px-4 sm:px-6 text-center text-sm text-gray-600 space-y-4">
                      {requirementsMissingDocuments.length > 0 ? (
                        <>
                          <p>No files uploaded for this property yet. Use the list above to upload for a specific requirement, or add a file without picking one.</p>
                          <Button
                            type="button"
                            className="bg-electric-teal text-white hover:bg-electric-teal/90 min-h-11"
                            onClick={() => navigate(resolveDocumentsPath(propertyId))}
                          >
                            {PORTAL_COPY.uploadDocument}
                          </Button>
                        </>
                      ) : requirements.length === 0 ? (
                        <>
                          <p>No compliance requirements are configured for this property yet.</p>
                          <Button type="button" variant="outline" onClick={() => setActiveTab(TAB_COMPLIANCE)}>
                            Open Compliance
                          </Button>
                        </>
                      ) : (
                        <>
                          <p>No files uploaded for this property yet.</p>
                          <Button
                            type="button"
                            className="bg-electric-teal text-white hover:bg-electric-teal/90 min-h-11"
                            onClick={() => navigate(resolveDocumentsPath(propertyId))}
                          >
                            {PORTAL_COPY.uploadDocument}
                          </Button>
                          <div>
                            <Button type="button" variant="outline" size="sm" onClick={() => setActiveTab(TAB_COMPLIANCE)}>
                              Review requirements in Compliance
                            </Button>
                          </div>
                        </>
                      )}
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
                            {evidenceData.documents.map((doc) => {
                              const evidencePrimary = evidenceDocStatusLabel(doc);
                              const showVerificationSubline = !clientVerificationLabelRedundantWithPrimary(doc, evidencePrimary);
                              const reqLabel = linkedRequirementLabelForDocument(doc, requirements, rowTitle);
                              const upLabel = formatEvidenceUploaderLabel(doc.uploaded_by, portalUserId);
                              const workspaceHref = resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id });
                              return (
                              <tr key={doc.document_id} className="border-b border-gray-100 hover:bg-gray-50">
                                <td className="p-3 font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</td>
                                <td className="p-3 text-gray-600">{doc.document_type ? documentTypeLabel(doc.document_type) : '—'}</td>
                                <td className="p-3 text-gray-600">{reqLabel}</td>
                                <td className="p-3">
                                  <div className="flex flex-col gap-1">
                                    <span className="inline-flex px-2 py-1 rounded border text-xs bg-gray-100 text-gray-700 border-gray-200">{evidencePrimary}</span>
                                    {showVerificationSubline ? (
                                      <span className="text-[11px] text-gray-500">{clientFacingVerificationLabel(doc)}</span>
                                    ) : null}
                                  </div>
                                </td>
                                <td className="p-3 text-gray-600">{upLabel}</td>
                                <td className="p-3 text-gray-600">{doc.uploaded_at ? formatDate(doc.uploaded_at) : '—'}</td>
                                <td className="p-3">
                                  <div className="flex flex-wrap gap-1">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="text-electric-teal border-electric-teal"
                                      onClick={() => setPropertyDocumentPreview(doc)}
                                      data-testid={`property-doc-preview-open-${doc.document_id}`}
                                    >
                                      <Eye className="w-3 h-3 mr-1" /> View
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={() => handleEvidenceDocumentDownload(doc)}><Download className="w-3 h-3 mr-1" /> Download</Button>
                                    {isPendingConfirmation(doc) && (
                                      <Button variant="outline" size="sm" className="border-amber-300 text-amber-700" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>Confirm details</Button>
                                    )}
                                    <Button variant="ghost" size="sm" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'EVIDENCE' })); }}><History className="w-3 h-3 mr-1" /> History</Button>
                                  </div>
                                  <button
                                    type="button"
                                    className="mt-1.5 block text-left text-xs text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline"
                                    onClick={() => navigate(workspaceHref)}
                                  >
                                    Open in Documents workspace
                                  </button>
                                </td>
                              </tr>
                            );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <div className="md:hidden space-y-2">
                      {evidenceData.documents.map((doc) => {
                        const evidencePrimary = evidenceDocStatusLabel(doc);
                        const verificationSub = clientVerificationLabelRedundantWithPrimary(doc, evidencePrimary)
                          ? null
                          : clientFacingVerificationLabel(doc);
                        const reqLabel = linkedRequirementLabelForDocument(doc, requirements, rowTitle);
                        const upLabel = formatEvidenceUploaderLabel(doc.uploaded_by, portalUserId);
                        const metaBits = [
                          doc.document_type ? documentTypeLabel(doc.document_type) : '—',
                          evidencePrimary,
                          verificationSub,
                          reqLabel !== '—' ? `Requirement: ${reqLabel}` : null,
                          upLabel !== '—' ? `Uploaded by: ${upLabel}` : null,
                          doc.uploaded_at ? formatDate(doc.uploaded_at) : null,
                        ].filter(Boolean);
                        const workspaceHref = resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id });
                        return (
                        <Card key={doc.document_id} className="border border-gray-200 p-3">
                          <div className="font-medium text-midnight-blue">{doc.file_name || doc.original_filename || doc.document_id}</div>
                          <div className="text-xs text-gray-600 mt-1">{metaBits.join(' · ')}</div>
                          <div className="flex flex-wrap gap-1 mt-2">
                            <Button variant="outline" size="sm" onClick={() => setPropertyDocumentPreview(doc)}>View</Button>
                            <Button variant="outline" size="sm" onClick={() => handleEvidenceDocumentDownload(doc)}>Download</Button>
                            {isPendingConfirmation(doc) && <Button variant="outline" size="sm" onClick={() => navigate(resolveDocumentsPath(propertyId, { requirement_id: doc.requirement_id }))}>Confirm</Button>}
                            <Button variant="ghost" size="sm" onClick={() => { setActiveTab(TAB_TIMELINE); setTimelineFilters((f) => ({ ...f, category: 'EVIDENCE' })); }}>History</Button>
                          </div>
                          <button
                            type="button"
                            className="mt-2 text-left text-xs text-gray-600 hover:text-midnight-blue underline-offset-2 hover:underline w-full"
                            onClick={() => navigate(workspaceHref)}
                          >
                            Open in Documents workspace
                          </button>
                        </Card>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>

              <ClientDocumentPreviewModal
                open={Boolean(propertyDocumentPreview)}
                onOpenChange={(next) => {
                  if (!next) setPropertyDocumentPreview(null);
                }}
                api={apiClient}
                doc={propertyDocumentPreview}
                documentsWorkspacePath={
                  propertyDocumentPreview
                    ? resolveDocumentsPath(propertyId, {
                        ...(propertyDocumentPreview.requirement_id
                          ? { requirement_id: propertyDocumentPreview.requirement_id }
                          : {}),
                      })
                    : ''
                }
                requirementLabel={
                  propertyDocumentPreview
                    ? linkedRequirementLabelForDocument(propertyDocumentPreview, requirements, rowTitle)
                    : ''
                }
                uploaderLabel={
                  propertyDocumentPreview
                    ? formatEvidenceUploaderLabel(propertyDocumentPreview.uploaded_by, portalUserId)
                    : ''
                }
              />

              {/* D) Pending Confirmations */}
              {(() => {
                const pending = (evidenceData.documents || []).filter(isPendingConfirmation);
                if (pending.length === 0) return null;
                return (
                  <Card className="border-amber-200 bg-amber-50/30">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Awaiting verification</CardTitle>
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

              {/* C) Recent document-related activity (full audit on Timeline) */}
              {(evidenceData.recentEvents?.length ?? 0) > 0 && (
                <Card className="border border-gray-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Recent document activity</CardTitle>
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
        <DiscoverabilityHint
          title={`${getFeatureDisplayInfo('contractor_network').featureName} — portfolio coordination`}
          body="Contractor directory and routing fit larger operations with delegated maintenance. Optional when your workflow grows."
          onCta={() =>
            navigate(
              buildSafeQueryPath('/settings/billing', {
                upgrade_to: getFeatureDisplayInfo('contractor_network').requiredPlan,
              }),
            )
          }
        />
      )}
      {activeTab === TAB_CONTRACTORS && hasFeature('contractor_network') && (
        <div className="space-y-4">
          <Card className="border border-gray-200">
            <CardHeader>
              <CardTitle className="text-lg">Contractors on this property</CardTitle>
              <CardDescription>
                Anyone assigned to jobs here shows below. Your full contractor directory and onboarding live under Operations.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {hasFeature('maintenance_workflows') && workOrdersLoading && workOrders.length === 0 ? (
                <div className="flex gap-2 text-gray-500 py-6"><Loader2 className="w-5 h-5 animate-spin" /> Loading job history…</div>
              ) : contractorsTabRows.length > 0 ? (
                <>
                  <div className="hidden md:block overflow-x-auto rounded-lg border border-gray-100">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-gray-600 bg-gray-50">
                          <th className="p-3">Contractor</th>
                          <th className="p-3">Job mix</th>
                          <th className="p-3">Last activity</th>
                          <th className="p-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {contractorsTabRows.map((row) => (
                          <tr key={row.rowKey} className="border-b border-gray-100">
                            <td className="p-3 font-medium text-midnight-blue">{row.displayLabel}</td>
                            <td className="p-3 text-gray-700">
                              <span className="font-medium">{row.jobCount}</span>
                              <span className="block text-xs text-gray-500 mt-0.5">
                                {row.complianceJobCount > 0 ? `${row.complianceJobCount} compliance` : null}
                                {row.complianceJobCount > 0 && row.repairJobCount > 0 ? ' · ' : null}
                                {row.repairJobCount > 0 ? `${row.repairJobCount} repair` : null}
                                {row.complianceJobCount === 0 && row.repairJobCount === 0 ? '—' : null}
                              </span>
                            </td>
                            <td className="p-3 text-gray-600">{row.lastActivity ? formatRelativeTime(row.lastActivity) : '—'}</td>
                            <td className="p-3 text-right">
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-electric-teal border-electric-teal"
                                onClick={() => setActiveTab(TAB_MAINTENANCE)}
                              >
                                View jobs & issues
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <ul className="md:hidden space-y-2">
                    {contractorsTabRows.map((row) => (
                      <li key={row.rowKey} className="rounded-lg border border-gray-200 p-3">
                        <p className="font-medium text-midnight-blue">{row.displayLabel}</p>
                        <p className="text-xs text-gray-600 mt-1">
                          {row.jobCount} job{row.jobCount === 1 ? '' : 's'}
                          {row.complianceJobCount > 0 || row.repairJobCount > 0 ? (
                            <span className="text-gray-500">
                              {' '}
                              (
                              {row.complianceJobCount > 0 ? `${row.complianceJobCount} compliance` : null}
                              {row.complianceJobCount > 0 && row.repairJobCount > 0 ? ', ' : null}
                              {row.repairJobCount > 0 ? `${row.repairJobCount} repair` : null}
                              )
                            </span>
                          ) : null}
                          {' · '}
                          {row.lastActivity ? formatRelativeTime(row.lastActivity) : '—'}
                        </p>
                        <Button size="sm" variant="outline" className="mt-2 w-full text-electric-teal border-electric-teal" onClick={() => setActiveTab(TAB_MAINTENANCE)}>
                          View jobs & issues
                        </Button>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center">
                  <Users className="w-10 h-10 mx-auto text-gray-400 mb-2" />
                  <p className="font-medium text-midnight-blue">No contractor assignments on this property yet</p>
                  <p className="text-sm text-gray-600 mt-1 max-w-md mx-auto">
                    When you assign someone to a job, they will appear here. Open Jobs to assign a contractor, or browse your network in Operations.
                  </p>
                </div>
              )}
              <div className="flex flex-wrap gap-2 mt-6">
                <Button variant="outline" className="text-electric-teal border-electric-teal" onClick={() => navigate('/operations/contractors')}>
                  View all contractors
                </Button>
                {hasFeature('maintenance_workflows') && (
                  <>
                    <Button variant="outline" onClick={() => setActiveTab(TAB_MAINTENANCE)}>
                      Jobs & issues
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => navigate(buildSafeQueryPath('/operations/work-orders', { property_id: propertyId }))}
                    >
                      Portfolio jobs (this property)
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab: Timeline */}
      {activeTab === TAB_TIMELINE && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-midnight-blue">Timeline</h2>
              <p className="text-sm text-gray-600 mt-1">Property activity history — what changed, when, and who was involved.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={timelineFilters.category}
                onChange={(e) => setTimelineFilters((f) => ({ ...f, category: e.target.value }))}
                className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-electric-teal"
                aria-label="Event type"
              >
                <option value="">All events</option>
                <option value="EVIDENCE">Documents</option>
                <option value="COMPLIANCE">Compliance</option>
                <option value="MAINTENANCE">Jobs & repairs</option>
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
                <p className="text-sm text-gray-500 mt-1 mb-4">Upload documents, report an issue, or complete property setup to see events here.</p>
                <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-2">
                  <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal min-h-11" onClick={() => navigate(resolveDocumentsPath(propertyId))}>
                    <Upload className="w-4 h-4 mr-2" />
                    {PORTAL_COPY.uploadDocument}
                  </Button>
                  {hasFeature('maintenance_workflows') && (
                    <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90 min-h-11" onClick={() => { setActiveTab(TAB_MAINTENANCE); setCreateWoOpen(true); }}>
                      <Plus className="w-4 h-4 mr-2" />
                      {PORTAL_COPY.addWorkOrder}
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setActiveTab(TAB_OPERATING)}>
                    Property operating view
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {timelineItems.map((item) => {
                const presented = presentPropertyTimelineItem(item);
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
                        <p className="font-medium text-midnight-blue">{presented.title}</p>
                        {presented.description && <p className="text-sm text-gray-600 mt-0.5">{presented.description}</p>}
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
                            View {actionTab === TAB_EVIDENCE ? 'Documents' : actionTab === TAB_COMPLIANCE ? 'Compliance' : actionTab === TAB_MAINTENANCE ? 'Jobs & issues' : 'Risk signals'}
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
        <DiscoverabilityHint
          title={`${getFeatureDisplayInfo('predictive_maintenance').featureName} — operational insight`}
          body="Predictive signals and asset-linked insight are included on portfolio-scale plans. Resolving a signal does not by itself restore compliance."
          onCta={() =>
            navigate(
              buildSafeQueryPath('/settings/billing', {
                upgrade_to: getFeatureDisplayInfo('predictive_maintenance').requiredPlan,
              }),
            )
          }
        />
      )}
      {activeTab === TAB_RISK_SIGNALS && hasFeature('predictive_maintenance') && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-midnight-blue">Risk signals</h2>
          {riskSignalsLoading ? (
            <div className="flex items-center gap-2 text-gray-500 py-8"><Loader2 className="w-5 h-5 animate-spin" /> Loading…</div>
          ) : !(riskSignalsData?.signals?.length) ? (
            <Card className="border border-gray-200">
              <CardContent className="py-8 text-center text-gray-500">
                No active risk signals for this property. Signals refresh when property data changes or on the scheduled update.
              </CardContent>
            </Card>
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
              <ul className="space-y-3">
                {riskSignalsData.signals.map((s) => {
                  const hasMaint = hasFeature('maintenance_workflows');
                  const hasComp = hasFeature('compliance_engine');
                  const { key: primaryKey, label: primaryLabel } = resolveRiskSignalPrimaryKey(s, hasMaint, hasComp);

                  const onCreateWo = async () => {
                    if (hasMaint) {
                      try {
                        await clientAPI.createWorkOrderFromRiskSignal(s.signal_id, {});
                        toast.success('Job started');
                        loadRiskSignals();
                        setActiveTab(TAB_MAINTENANCE);
                      } catch (e) {
                        if (openPlanRestrictedJobGate(e, setPlanJobGate, { propertyId })) return;
                        toast.error(e?.response?.data?.detail || 'Failed');
                      }
                    } else {
                      setActiveTab(TAB_MAINTENANCE);
                      setCreateWoOpen(true);
                      setCreateWoForm((f) => ({ ...f, description: s.recommended_action }));
                    }
                  };

                  const primaryBtnClass = 'w-full lg:w-auto min-h-9 bg-electric-teal hover:bg-electric-teal/90 text-white';

                  const runPrimary = async () => {
                    if (primaryKey === 'compliance_inspection') {
                      openBookInspectionFromRisk(s.signal_id);
                      return;
                    }
                    if (primaryKey === 'log_inspection_issue') {
                      try {
                        await clientAPI.logInspectionIssueFromRiskSignal(s.signal_id, {});
                        toast.success('Logged for follow-up');
                        loadRiskSignals();
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || 'Failed');
                      }
                      return;
                    }
                    if (primaryKey === 'maintenance_job') {
                      await onCreateWo();
                      return;
                    }
                    if (primaryKey === 'maintenance_issue') {
                      try {
                        await clientAPI.createIssueFromRiskSignal(s.signal_id, {});
                        toast.success('Logged for follow-up');
                        loadRiskSignals();
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || 'Failed');
                      }
                      return;
                    }
                    setActiveTab(TAB_RISK_SIGNALS);
                  };

                  let primary = (
                    <Button size="sm" className={cn(primaryBtnClass, primaryKey === 'maintenance_job' ? 'inline-flex items-center justify-center' : '')} onClick={runPrimary}>
                      {primaryKey === 'maintenance_job' ? <Wrench className="w-4 h-4 mr-1 shrink-0" /> : null}
                      {primaryLabel}
                    </Button>
                  );
                  if (primaryKey === 'review') {
                    primary = (
                      <Button size="sm" variant="outline" className="w-full lg:w-auto min-h-9 border-electric-teal text-electric-teal" onClick={runPrimary}>
                        {primaryLabel}
                      </Button>
                    );
                  }

                  return (
                    <li key={s.signal_id} className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-gray-900">{humanRiskType(s)}</p>
                        <p className="text-sm text-gray-700 mt-0.5">{humanAction(s.recommended_action, s)}</p>
                        {Array.isArray(s.reasons) && s.reasons.length > 0 && (
                          <ul className="mt-1 text-xs text-gray-600 list-disc list-inside space-y-0.5">
                            {s.reasons.map((r, i) => (
                              <li key={i}>{humanizeRiskReasonBullet(r)}</li>
                            ))}
                          </ul>
                        )}
                        <span className={`inline-block mt-2 text-xs px-1.5 py-0.5 rounded ${['high', 'critical'].includes((s.risk_level || '').toLowerCase()) ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}`}>{humanSeverity(s.risk_level)}</span>
                        {s.status && s.status !== 'active' && (
                          <span className="ml-2 text-xs text-gray-500">{predictiveIssueStatusLabel(s.status)}</span>
                        )}
                      </div>
                      <div className="flex flex-col gap-2 shrink-0 w-full lg:w-auto lg:max-w-xs">
                        {primary}
                        {s.status === 'active' && (
                          <div className="pt-1 border-t border-gray-200/80">
                            <button
                              type="button"
                              className="text-xs text-gray-500 hover:text-midnight-blue underline"
                              onClick={async () => {
                                try {
                                  await clientAPI.updateRiskSignalStatus(s.signal_id, 'acknowledged');
                                  loadRiskSignals();
                                } catch (_) {}
                              }}
                            >
                              Acknowledge (informational)
                            </button>
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}

      {/* Tab: Assets */}
      {activeTab === TAB_ASSETS && !hasFeature('maintenance_workflows') && !hasFeature('predictive_maintenance') && (
        <DiscoverabilityHint
          title="Property assets — portfolio-scale tooling"
          body="Track equipment and link assets to maintenance when jobs and risk tooling are enabled. Your core compliance views stay unchanged."
          onCta={() => navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: 'PLAN_2_PORTFOLIO' }))}
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
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Recent jobs</p>
                    <p className="text-lg font-semibold text-midnight-blue">{assetsSummary.recent_work_orders ?? 0}</p>
                  </div>
                  <div className="p-3 rounded-lg border border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Compliance linked</p>
                    <p className="text-lg font-semibold text-midnight-blue">{assetsSummary.with_compliance_linkage ?? 0}</p>
                  </div>
                </div>
              )}
              {/* B) Asset Table */}
              <div className="hidden md:block rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 text-left text-gray-600 bg-gray-50">
                        <th className="p-3">Asset</th>
                        <th className="p-3">Type & status</th>
                        <th className="p-3 min-w-[200px]">Activity</th>
                        <th className="p-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assets.map((a) => {
                        const per = assetsSummary?.per_asset?.[a.asset_id] || {};
                        const status = (a.status || 'active').toLowerCase();
                        const statusLabel = status === 'active' ? 'Active' : status === 'inactive' ? 'Inactive' : status === 'replaced' ? 'Replaced' : status === 'removed' ? 'Removed' : 'Active';
                        const typeLabel = operationalLabelForToken(a.asset_type, { emptyLabel: '—' });
                        return (
                          <tr key={a.asset_id} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="p-3 font-medium text-midnight-blue">{a.name || typeLabel}</td>
                            <td className="p-3 text-gray-600">
                              <div>{typeLabel}</div>
                              <div className="text-xs text-gray-500 mt-0.5">{statusLabel}</div>
                            </td>
                            <td className="p-3 text-sm text-gray-700 leading-snug">{assetActivitySummary(a, per)}</td>
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
                                <Button variant="ghost" size="sm" className="text-gray-700 h-8 text-xs" onClick={() => setActiveTab(TAB_MAINTENANCE)}>
                                  Jobs & issues
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
                      <div className="font-medium text-midnight-blue">
                        {a.name || operationalLabelForToken(a.asset_type, { emptyLabel: '—' })}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {operationalLabelForToken(a.asset_type, { emptyLabel: '—' })} · {statusLabel}
                      </div>
                      <p className="text-sm text-gray-700 mt-2 leading-snug">{assetActivitySummary(a, per)}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal" onClick={() => { setAssetDetailDrawer(a.asset_id); setAssetDetailData(null); setAssetDetailLoading(true); clientAPI.getPropertyAsset(propertyId, a.asset_id).then((res) => setAssetDetailData(res.data)).catch(() => setAssetDetailData(null)).finally(() => setAssetDetailLoading(false)); }}>View</Button>
                        <Button variant="ghost" size="sm" className="h-8 text-xs text-gray-700" onClick={() => { setEditAssetModal(a); setEditAssetForm({ name: a.name ?? '', status: a.status ?? 'active', last_service_date: a.last_service_date ?? '', make: a.make ?? '', model: a.model ?? '' }); }}>Edit</Button>
                        <Button variant="ghost" size="sm" className="h-8 text-xs text-gray-700" onClick={() => setActiveTab(TAB_MAINTENANCE)}>Jobs & issues</Button>
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
          <div className={cn(portalDrawerPanelClass, 'max-w-md')} onClick={(e) => e.stopPropagation()}>
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
                    <div>
                      <dt className="text-gray-500">Type</dt>
                      <dd>{operationalLabelForToken(assetDetailData.asset.asset_type, { emptyLabel: '—' })}</dd>
                    </div>
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
                      <p className="text-sm text-gray-500">View risk signals on the Risk signals tab.</p>
                    </>
                  )}
                  <div className="mt-4 flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => { const a = assets.find((x) => x.asset_id === assetDetailDrawer); if (a) { setEditAssetModal(a); setEditAssetForm({ name: a.name ?? '', status: a.status ?? 'active', last_service_date: a.last_service_date ?? '', make: a.make ?? '', model: a.model ?? '' }); } setAssetDetailDrawer(null); }}>Edit asset</Button>
                    <Button size="sm" variant="outline" onClick={() => setActiveTab(TAB_MAINTENANCE)}>Jobs & issues</Button>
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
              <h3 className="font-semibold text-midnight-blue text-lg">Start inspection job</h3>
              <button type="button" onClick={() => !bookInspectionSaving && setBookInspectionOpen(false)} className="p-1 rounded hover:bg-gray-100" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Select the requirement this inspection satisfies. You will continue in Jobs to assign a contractor and complete the visit.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Requirement on this property</label>
            <select
              value={bookInspectionReqPick}
              onChange={(e) => setBookInspectionReqPick(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4 text-sm"
              disabled={bookInspectionSaving}
            >
              <option value="">— Select —</option>
              {getTrackedRequirementsForProperty(propertyId, requirements).map((r) => {
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
                {bookInspectionSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Start inspection job'}
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
            <div className="p-4 overflow-auto max-h-[60vh] max-w-full min-w-0">
              {scoreHistoryLoading ? (
                <p className="text-gray-500">Loading…</p>
              ) : scoreHistoryEntries.length === 0 ? (
                <p className="text-gray-500">No score change history yet.</p>
              ) : (
                <div className="overflow-x-auto -mx-1 px-1">
                <table className="w-full text-sm min-w-[480px]">
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
                    {scoreHistoryEntries.map((e, i) => {
                      const reasonPresented = e.reason_label
                        ? { title: e.reason_label, description: e.reason_detail || '' }
                        : presentScoreChangeReason(e.reason);
                      return (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="p-2">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                        <td className="p-2">{e.previous_score ?? '—'}</td>
                        <td className="p-2">{e.new_score ?? '—'}</td>
                        <td className={`p-2 font-medium ${e.delta > 0 ? 'text-green-600' : e.delta < 0 ? 'text-red-600' : ''}`}>{e.delta != null ? (e.delta > 0 ? '+' : '') + e.delta : '—'}</td>
                        <td className="p-2 text-gray-600">
                          <span className="font-medium text-gray-800">{reasonPresented.title}</span>
                          {reasonPresented.description ? (
                            <span className="block text-xs text-gray-500 mt-0.5">{reasonPresented.description}</span>
                          ) : null}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <RequirementIntelligenceModal
        open={!!requirementIntelRow && !!rowReqId(requirementIntelRow)}
        requirementId={requirementIntelRow ? String(rowReqId(requirementIntelRow)) : null}
        seedRequirement={requirementIntelRow}
        initialFocusSubmission={requirementIntelFocusSubmission}
        propertyLabel={property?.nickname || property?.address_line_1 || null}
        onClose={() => {
          setRequirementIntelRow(null);
          setRequirementIntelFocusSubmission(false);
        }}
        onNavigate={(path) => {
          setRequirementIntelRow(null);
          navigate(path);
        }}
        addressForMailto={address}
        onMarkNotApplicable={(m) => {
          setRequirementIntelRow(null);
          setNotApplicableModal({
            requirement_code: m.requirement_code || m.requirement_type,
            title: rowTitle(m),
          });
          setNotApplicablePreset('not_applicable');
          setNotApplicableAuditText('');
        }}
      />
      <PlanRestrictedJobModal gate={planJobGate} onDismiss={() => setPlanJobGate(null)} />

      {notApplicableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !notApplicableSubmitting && setNotApplicableModal(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full m-4 p-4 max-h-[min(90dvh,90vh)] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-midnight-blue mb-2">Record as not applicable</h3>
            <NotApplicableGovernedNotice />
            <p className="text-sm text-gray-700 mt-3 mb-2">
              <span className="font-medium text-gray-800">&ldquo;{notApplicableModal.title}&rdquo;</span>
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select
              value={notApplicablePreset}
              onChange={(e) => setNotApplicablePreset(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-3"
              data-testid="not-applicable-preset"
            >
              {NOT_REQUIRED_REASONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <label className="block text-sm font-medium text-gray-700 mb-1">Audit note (required, min. 10 characters)</label>
            <textarea
              value={notApplicableAuditText}
              onChange={(e) => setNotApplicableAuditText(e.target.value)}
              rows={4}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4 text-sm"
              placeholder="Briefly explain why this obligation does not apply, for audit and support review."
              data-testid="not-applicable-audit-reason"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setNotApplicableModal(null)} disabled={notApplicableSubmitting}>Cancel</Button>
              <Button
                onClick={async () => {
                  const audit = notApplicableAuditText.trim();
                  if (audit.length < 10) {
                    toast.error('Please add an audit note of at least 10 characters.');
                    return;
                  }
                  setNotApplicableSubmitting(true);
                  try {
                    await clientAPI.markRequirementNotApplicable(propertyId, {
                      requirement_code: notApplicableModal.requirement_code,
                      not_required_reason: notApplicablePreset,
                      reason: audit,
                    });
                    toast.success(
                      'Recorded as not applicable. Score and lists may update after recalculation completes.',
                    );
                    setNotApplicableModal(null);
                    fetchData();
                    if (typeof window !== 'undefined' && propertyId) {
                      window.dispatchEvent(
                        new CustomEvent('compliance-outcome', { detail: { property_id: propertyId } }),
                      );
                    }
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
