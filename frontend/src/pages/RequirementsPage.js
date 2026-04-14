import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import api from '../api/client';
import { toast } from 'sonner';
import { useEntitlements } from '../contexts/EntitlementsContext';
import {
  FileCheck,
  Calendar,
  Building2,
  ArrowLeft,
  Search,
  RefreshCw,
  FileText,
  ChevronRight,
  AlertCircle,
  Loader2,
  Eye,
  Ban,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { buildSafeQueryPath, resolveDocumentsPath } from '../utils/clientPortalNavigation';
import { getEvidenceStatus } from '../utils/evidenceStatus';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import { Alert, AlertDescription } from '../components/ui/alert';
import EmptyState from '../components/EmptyState';
import { requirementLabel } from '../domain/presentDomain';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import { PortalLoadingPanel } from '../components/client/ClientPortalPatterns';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';
import { REQUIREMENTS_PAGE_CONFIDENCE_LINE } from '../utils/confidenceUxCopy';
import { isRequirementIncludedInAttentionViews } from '../utils/portalRequirementAttention';
import { isRequirementMissingDocument } from '../utils/propertyDocumentsMatrix';

const NOT_REQUIRED_REASONS = [
  { value: 'no_gas_supply', label: 'No gas supply' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'not_applicable', label: 'Not applicable' },
  { value: 'other', label: 'Other' },
];

const RequirementsPage = () => {
  const navigate = useNavigate();
  const { hasFeature } = useEntitlements();
  const [searchParams] = useSearchParams();
  const highlightParam = searchParams.get('highlight');
  const [flashRequirementId, setFlashRequirementId] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [clientData, setClientData] = useState(null);
  const [groupBy, setGroupBy] = useState('property'); // 'property' | 'requirement'
  const [editModal, setEditModal] = useState(null); // { requirement, property } or null
  const [editSaving, setEditSaving] = useState(false);
  const [editForm, setEditForm] = useState({ confirmed_expiry_date: '', applicability: '', not_required_reason: '' });
  const [documentCountByRequirementId, setDocumentCountByRequirementId] = useState({});
  const [requirementsPresentation, setRequirementsPresentation] = useState(null);
  const [notApplicableModal, setNotApplicableModal] = useState(null);
  const [notApplicableReason, setNotApplicableReason] = useState('');
  const [notApplicableCode, setNotApplicableCode] = useState('other');
  const [notApplicableSaving, setNotApplicableSaving] = useState(false);
  const [notApplicableCloseActiveJob, setNotApplicableCloseActiveJob] = useState(false);
  const [notApplicableActiveJobId, setNotApplicableActiveJobId] = useState(null);
  const [viewRequirementModal, setViewRequirementModal] = useState(null);
  const [viewRequirementLoading, setViewRequirementLoading] = useState(false);
  const [viewRequirementData, setViewRequirementData] = useState(null);
  const [planJobGate, setPlanJobGate] = useState(null);

  // Get filter from URL params
  const statusFilter = searchParams.get('status') || 'all';
  const windowDays = searchParams.get('window');

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (!highlightParam || loading) return undefined;
    const scrollT = window.setTimeout(() => {
      document
        .querySelector(`[data-testid="requirement-row-${CSS.escape(highlightParam)}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 150);
    setFlashRequirementId(highlightParam);
    const clearT = window.setTimeout(() => setFlashRequirementId(null), 2200);
    return () => {
      window.clearTimeout(scrollT);
      window.clearTimeout(clearT);
    };
  }, [highlightParam, loading, requirements.length]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [dashboardRes, requirementsRes, documentsRes] = await Promise.all([
        clientAPI.getDashboard().then((r) => r.data),
        clientAPI.getRequirements().then((r) => r.data),
        clientAPI.getDocuments().then((r) => r.data).catch(() => ({ documents: [] }))
      ]);
      setClientData(dashboardRes);
      setProperties(dashboardRes?.properties || []);
      setRequirements(requirementsRes?.requirements || []);
      setRequirementsPresentation(requirementsRes?.presentation || null);
      const docs = documentsRes?.documents || [];
      const countBy = {};
      docs.forEach((d) => {
        const rid = d.requirement_id;
        if (rid) countBy[rid] = (countBy[rid] || 0) + 1;
      });
      setDocumentCountByRequirementId(countBy);
    } catch (error) {
      toast.error('Failed to load requirements');
    } finally {
      setLoading(false);
    }
  };

  const getPropertyById = (propertyId) => {
    return properties.find(p => p.property_id === propertyId) || {};
  };

  /** Use full requirement row so evidence state (e.g. linked doc + pending) matches Property surfaces; no inferred fields. */
  const getStatusConfig = (req) => {
    const config = getEvidenceStatus(req.status, req);
    const color = config.className.includes('green') ? 'green' : config.className.includes('amber') ? 'amber' : config.className.includes('red') ? 'red' : config.className.includes('blue') ? 'blue' : 'gray';
    return { ...config, color };
  };

  const getDaysUntilDue = (dueDate) => {
    if (!dueDate) return null;
    const due = new Date(dueDate);
    const now = new Date();
    const diffTime = due - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Not set';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  const hasUnknownApplicability = requirements.some(r => (r.applicability || 'UNKNOWN') === 'UNKNOWN');

  const openEditModal = (req) => {
    const due = req.confirmed_expiry_date || req.extracted_expiry_date || req.due_date;
    const dateStr = due ? (typeof due === 'string' ? due : new Date(due).toISOString()).slice(0, 10) : '';
    setEditForm({
      confirmed_expiry_date: dateStr,
      applicability: req.applicability || 'UNKNOWN',
      not_required_reason: req.not_required_reason || '',
    });
    setEditModal({ requirement: req, property: getPropertyById(req.property_id) });
  };

  const openViewRequirementModal = (req) => {
    setViewRequirementModal({ requirement: req });
    setViewRequirementData(null);
    setViewRequirementLoading(true);
    clientAPI
      .getRequirementWorkflow(req.requirement_id)
      .then((r) => setViewRequirementData(r.data))
      .catch((err) => {
        toast.error(err.response?.data?.detail || 'Could not load requirement');
        setViewRequirementModal(null);
      })
      .finally(() => setViewRequirementLoading(false));
  };

  const submitNotApplicable = async () => {
    if (!notApplicableModal) return;
    const text = notApplicableReason.trim();
    if (text.length < 10) {
      toast.error('Please enter a reason (at least 10 characters) for the audit trail.');
      return;
    }
    setNotApplicableSaving(true);
    const propIdForOutcome = notApplicableModal.requirement?.property_id;
    try {
      await clientAPI.markRequirementNotApplicableById(notApplicableModal.requirement.requirement_id, {
        reason: text,
        reason_code: notApplicableCode || undefined,
        confirm_close_active_job: notApplicableCloseActiveJob,
      });
      toast.success(
        'Recorded as not applicable with audit reason. This requirement stops counting as overdue for that property.',
      );
      setNotApplicableModal(null);
      setNotApplicableReason('');
      setNotApplicableCode('other');
      setNotApplicableCloseActiveJob(false);
      setNotApplicableActiveJobId(null);
      fetchData();
      if (propIdForOutcome && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: { property_id: propIdForOutcome } }));
      }
    } catch (error) {
      const st = error.response?.status;
      const det = error.response?.data?.detail;
      if (st === 409 && det && typeof det === 'object' && det.code === 'ACTIVE_COMPLIANCE_JOB_EXISTS') {
        setNotApplicableActiveJobId(det.work_order_id || null);
        toast.error(det.message || 'An open compliance job must be cancelled to mark this not applicable.');
      } else {
        toast.error(typeof det === 'string' ? det : det?.message || 'Could not update requirement');
      }
    } finally {
      setNotApplicableSaving(false);
    }
  };

  const handleEditSubmit = async () => {
    if (!editModal) return;
    const { requirement } = editModal;
    setEditSaving(true);
    try {
      const payload = {};
      if (editForm.confirmed_expiry_date.trim()) payload.confirmed_expiry_date = editForm.confirmed_expiry_date.trim();
      if (editForm.applicability) payload.applicability = editForm.applicability;
      if (editForm.applicability === 'NOT_REQUIRED' && editForm.not_required_reason) payload.not_required_reason = editForm.not_required_reason;
      if (Object.keys(payload).length === 0) {
        setEditModal(null);
        return;
      }
      await api.patch(
        `/properties/${requirement.property_id}/requirements/${requirement.requirement_id}`,
        payload
      );
      toast.success(
        'Dates and applicability saved. Compliance scoring and overdue views refresh on the next recalculation for this property.',
        { description: 'Requirement row will reflect the change after recalculation.' },
      );
      setFlashRequirementId(requirement.requirement_id);
      window.setTimeout(() => setFlashRequirementId(null), 2200);
      setEditModal(null);
      fetchData();
      if (requirement.property_id && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: { property_id: requirement.property_id } }));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update requirement');
    } finally {
      setEditSaving(false);
    }
  };

  const attentionScopedOnly =
    statusFilter === 'DUE_SOON' || statusFilter === 'OVERDUE_OR_MISSING' || Boolean(windowDays);

  // Apply filters
  const filteredRequirements = requirements.filter(req => {
    if (req.client_surface_visible === false) return false;
    if (attentionScopedOnly && !isRequirementIncludedInAttentionViews(req)) return false;
    // Search filter
    const property = getPropertyById(req.property_id);
    const reqLabel = requirementLabel(req.requirement_type || req.requirement_code || '');
    const matchesSearch = searchTerm === '' ||
      req.requirement_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reqLabel.toLowerCase().includes(searchTerm.toLowerCase()) ||
      req.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      property.nickname?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      property.address_line_1?.toLowerCase().includes(searchTerm.toLowerCase());
    
    if (!matchesSearch) return false;

    // Status filter
    if (statusFilter === 'DUE_SOON') {
      return req.status === 'EXPIRING_SOON';
    } else if (statusFilter === 'OVERDUE_OR_MISSING') {
      return req.status === 'OVERDUE' || req.status === 'PENDING';
    } else if (statusFilter !== 'all') {
      return req.status === statusFilter;
    }

    // Window filter (for "Expiring Soon" tile)
    if (windowDays) {
      const days = getDaysUntilDue(req.due_date);
      return days !== null && days >= 0 && days <= parseInt(windowDays);
    }

    return true;
  }).sort((a, b) => {
    // Sort by urgency: OVERDUE first, then EXPIRING_SOON, then by due_date
    const priorityOrder = { 'OVERDUE': 0, 'EXPIRING_SOON': 1, 'PENDING': 2, 'COMPLIANT': 3 };
    const priorityDiff = (priorityOrder[a.status] || 4) - (priorityOrder[b.status] || 4);
    if (priorityDiff !== 0) return priorityDiff;
    
    // Then sort by due date
    const dateA = a.due_date ? new Date(a.due_date) : new Date('9999-12-31');
    const dateB = b.due_date ? new Date(b.due_date) : new Date('9999-12-31');
    return dateA - dateB;
  });

  const renderRequirementRow = (req) => {
    const property = getPropertyById(req.property_id);
    const statusConfig = getStatusConfig(req);
    const StatusIcon = statusConfig.icon;
    const daysUntil = getDaysUntilDue(req.due_date);
    const docCount = documentCountByRequirementId[req.requirement_id] || 0;
    const hasDocs = docCount > 0;
    const reqCode = String(req.requirement_code || req.requirement_type || '').trim();
    const docQuery = { requirement_id: req.requirement_id, ...(reqCode ? { requirement_code: reqCode } : {}) };
    const docsPath = resolveDocumentsPath(req.property_id, docQuery);
    const uploadPath = resolveDocumentsPath(req.property_id, { ...docQuery, focus: 'upload' });
    const reqClass = String(req.compliance_requirement_class || req.requirement_class || '').toUpperCase();
    const informational =
      reqClass === 'OBLIGATION' ||
      reqClass === 'SYSTEM' ||
      req.engine_informational === true ||
      String(req.engine_client_visibility || req.client_visibility || '').toLowerCase() === 'informational';
    const fulfillment =
      reqClass === 'JOB'
        ? 'job'
        : reqClass === 'DOCUMENT'
          ? 'document'
          : String(req.engine_fulfillment_mode || req.fulfillment_mode || 'document').toLowerCase();
    const needsDocEvidence = req.engine_requires_document_evidence !== false;
    const mayBookJob = req.engine_creates_compliance_job === true || reqClass === 'JOB';

    const requirementPreActionLine = (() => {
      if (informational) {
        return 'This is a tenancy or legal obligation to keep on record; it does not create an urgent task in Today.';
      }
      const st = String(req.status || '').toUpperCase();
      if (st === 'OVERDUE') return 'This requirement is overdue and affects compliance status for this property.';
      if (st === 'PENDING_VERIFICATION' || st === 'AWAITING_VERIFICATION')
        return 'Document received—confirming dates moves this requirement toward verified compliance.';
      if (st === 'PENDING' || st === 'MISSING')
        return 'This document is required to keep this property compliant.';
      if (st === 'EXPIRING_SOON') return 'Renewing before expiry keeps this property inside compliance windows.';
      if (st === 'COMPLIANT') return 'Keeping this row current preserves a clear audit trail for this property.';
      return 'Actions here update how this property appears in portfolio compliance views.';
    })();
    return (
      <div
        key={req.requirement_id}
        className={`p-4 hover:bg-gray-50 transition-colors ${
          flashRequirementId === req.requirement_id ? 'ring-2 ring-electric-teal/70 bg-teal-50/40 rounded-lg' : ''
        }`}
        data-testid={`requirement-row-${req.requirement_id}`}
      >
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="flex items-start gap-4 flex-1 min-w-0">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${statusConfig.color === 'green' ? 'bg-green-100' : statusConfig.color === 'amber' ? 'bg-amber-100' : statusConfig.color === 'red' ? 'bg-red-100' : statusConfig.color === 'blue' ? 'bg-blue-100' : 'bg-gray-100'}`}>
              <StatusIcon className={`w-5 h-5 ${statusConfig.color === 'green' ? 'text-green-600' : statusConfig.color === 'amber' ? 'text-amber-600' : statusConfig.color === 'red' ? 'text-red-600' : statusConfig.color === 'blue' ? 'text-blue-600' : 'text-gray-600'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-midnight-blue">{req.display_label || requirementLabel(req.requirement_type || req.requirement_code) || 'Requirement'}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusConfig.className}`}>{statusConfig.text}</span>
                {req.evidence_badge_label && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-50 text-slate-700 border border-slate-200" data-testid={`evidence-badge-${req.requirement_id}`}>
                    Document: {req.evidence_badge_label}
                  </span>
                )}
                {docCount > 0 && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200" data-testid={`doc-count-${req.requirement_id}`}>
                    <FileText className="w-3.5 h-3.5" />
                    {docCount} document{docCount !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {statusConfig.subline ? (
                <p className="text-xs text-gray-500 mt-1 max-w-prose">{statusConfig.subline}</p>
              ) : null}
              <p className="text-sm text-gray-600 mt-1 line-clamp-2">{req.description || 'No description available'}</p>
              <div className="flex flex-col gap-1 mt-2 text-sm text-gray-500">
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" />{property.nickname || property.address_line_1 || 'Unknown Property'}</span>
                  <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" />{req.date_label || `Due: ${formatDate(req.due_date)}`}</span>
                </div>
                {req.date_explanation_helper && (
                  <p className="text-xs text-gray-500 max-w-2xl">{req.date_explanation_helper}</p>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-3 w-full lg:w-auto lg:max-w-xs shrink-0 border-t border-gray-100 pt-4 lg:border-t-0 lg:pt-0">
            <p className="text-xs text-gray-600 leading-snug">{requirementPreActionLine}</p>
            {daysUntil !== null && (
              <div className={`flex lg:flex-col items-center lg:items-end justify-between lg:justify-start gap-2 ${daysUntil < 0 ? 'text-red-600' : daysUntil <= 14 ? 'text-amber-600' : daysUntil <= 30 ? 'text-yellow-600' : 'text-gray-600'}`}>
                <p className="text-lg font-bold tabular-nums">{daysUntil < 0 ? Math.abs(daysUntil) : daysUntil}</p>
                <p className="text-xs">{daysUntil < 0 ? 'days overdue' : 'days left'}</p>
              </div>
            )}
            {(() => {
              const needsDoc = isRequirementMissingDocument(req);
              const fixPath = !hasDocs || needsDoc ? uploadPath : docsPath;
              let primaryLabel = PORTAL_COPY.fixComplianceIssue;
              let onPrimary = () => navigate(fixPath);
              if (informational || fulfillment === 'obligation') {
                primaryLabel = 'Review obligation';
                onPrimary = () => openViewRequirementModal(req);
              } else if (fulfillment === 'job' && mayBookJob) {
                primaryLabel = 'Book inspection';
                const hash = reqCode ? `#req=${encodeURIComponent(reqCode)}` : '';
                onPrimary = () => navigate(`/properties/${req.property_id}${hash}`);
              } else if (fulfillment === 'document' && needsDocEvidence) {
                onPrimary = () => navigate(fixPath);
              } else {
                primaryLabel = 'View details';
                onPrimary = () => openViewRequirementModal(req);
              }
              return (
                <Button
                  className="w-full min-h-11 justify-center bg-electric-teal hover:bg-electric-teal/90 text-midnight-blue font-semibold"
                  onClick={onPrimary}
                  data-testid={`fix-compliance-${req.requirement_id}`}
                >
                  {primaryLabel}
                  <ChevronRight className="w-4 h-4 ml-1 shrink-0" />
                </Button>
              );
            })()}
            <div className="flex flex-col gap-2">
              <button
                type="button"
                className="text-sm text-electric-teal hover:underline text-left min-h-10"
                onClick={() => openViewRequirementModal(req)}
                data-testid={`compliance-view-requirement-${req.requirement_id}`}
              >
                View details
              </button>
              <button
                type="button"
                className="text-xs text-gray-500 hover:text-midnight-blue text-left underline"
                onClick={() => openEditModal(req)}
                data-testid={`edit-requirement-${req.requirement_id}`}
              >
                Edit dates and applicability
              </button>
              <button
                type="button"
                className="text-xs text-gray-500 hover:text-midnight-blue text-left underline"
                onClick={() => {
                  setNotApplicableReason('');
                  setNotApplicableCode('other');
                  setNotApplicableModal({ requirement: req });
                  setNotApplicableCloseActiveJob(false);
                  setNotApplicableActiveJobId(null);
                }}
                data-testid={`compliance-not-applicable-${req.requirement_id}`}
              >
                Mark as not applicable
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Get page title based on filter
  const getPageTitle = () => {
    if (statusFilter === 'DUE_SOON') return 'Attention Needed';
    if (statusFilter === 'OVERDUE_OR_MISSING') return 'Attention needed';
    if (windowDays) return `Expiring in Next ${windowDays} Days`;
    return 'All Requirements';
  };

  const getPageDescription = () => {
    if (statusFilter === 'DUE_SOON') return 'Tracked items expiring soon that need attention';
    if (statusFilter === 'OVERDUE_OR_MISSING')
      return 'Overdue or missing items—upload on Documents to clear gaps; Command Center and Today reflect the result.';
    if (windowDays) return `Tracked items with deadlines within the next ${windowDays} days`;
    return 'Manage obligations here; documents and dates feed your compliance score and your Today inbox.';
  };

  // Stats
  const statsBase = requirements.filter(
    (r) => r.client_surface_visible !== false && isRequirementIncludedInAttentionViews(r)
  );
  const trackedAttentionCount = statsBase.length;
  const stats = {
    total: trackedAttentionCount,
    compliant: statsBase.filter((r) => r.status === 'COMPLIANT').length,
    expiringSoon: statsBase.filter((r) => r.status === 'EXPIRING_SOON').length,
    overdue: statsBase.filter((r) => r.status === 'OVERDUE').length,
    pending: statsBase.filter((r) => r.status === 'PENDING').length,
  };

  if (loading) {
    return <PortalLoadingPanel message={`Loading ${PORTAL_COPY.requirements.toLowerCase()}…`} />;
  }

  return (
    <div data-testid="requirements-page">
        {/* Back Button + Page Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
            className="text-gray-600 hover:text-midnight-blue mb-4"
            data-testid="back-to-dashboard"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
            <div className="min-w-0">
              <h2 className="text-xl sm:text-2xl font-bold text-midnight-blue">{getPageTitle()}</h2>
              <p className="text-gray-500 mt-1 text-sm sm:text-base">{getPageDescription()}</p>
              <p className="text-gray-600 mt-2 text-sm sm:text-base">{REQUIREMENTS_PAGE_CONFIDENCE_LINE}</p>
            </div>
            <div className="text-left sm:text-right shrink-0 rounded-xl border border-gray-200 bg-white px-4 py-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Showing</p>
              <p className="text-2xl font-bold text-midnight-blue tabular-nums">{filteredRequirements.length}</p>
              <p className="text-sm text-gray-500">
                {attentionScopedOnly ? PORTAL_COPY.trackedItems : `All ${PORTAL_COPY.requirements.toLowerCase()}`}
              </p>
            </div>
          </div>
        </div>

        {/* UNKNOWN applicability banner */}
        {requirementsPresentation?.show_compliance_estimates_notice && (
          <Alert className="mb-6 border-sky-200 bg-sky-50" data-testid="compliance-estimates-notice">
            <AlertCircle className="h-4 w-4 text-sky-700" />
            <AlertDescription className="text-sky-900">
              {requirementsPresentation.compliance_estimates_notice_text}
            </AlertDescription>
          </Alert>
        )}

        {hasUnknownApplicability && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="unknown-applicability-banner">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-800">Confirm your property details.</span>
              <span className="text-amber-700 ml-1">Some tracked items depend on your property settings. Update expiry dates or mark items as not applicable so we can show the right status.</span>
            </AlertDescription>
          </Alert>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${!statusFilter || statusFilter === 'all' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements')}
            data-testid="filter-all"
          >
            <p className="text-2xl font-bold text-midnight-blue">{stats.total}</p>
            <p className="text-sm text-gray-500">Total</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'COMPLIANT' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=COMPLIANT')}
            data-testid="filter-compliant"
          >
            <p className="text-2xl font-bold text-green-600">{stats.compliant}</p>
            <p className="text-sm text-gray-500">Valid</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'DUE_SOON' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=DUE_SOON')}
            data-testid="filter-due-soon"
          >
            <p className="text-2xl font-bold text-amber-600">{stats.expiringSoon}</p>
            <p className="text-sm text-gray-500">Expiring Soon</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'OVERDUE_OR_MISSING' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="filter-overdue"
          >
            <p className="text-2xl font-bold text-red-600">{stats.overdue + stats.pending}</p>
            <p className="text-sm text-gray-500">Attention needed</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${windowDays === '30' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?window=30&status=DUE_SOON')}
            data-testid="filter-30-days"
          >
            <p className="text-2xl font-bold text-blue-600">30</p>
            <p className="text-sm text-gray-500">Day Window</p>
          </button>
        </div>

        {/* Search Bar */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:gap-4">
            <div className="flex-1 relative min-w-0">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search requirement, property, or notes…"
                className="w-full min-h-11 pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                data-testid="search-input"
              />
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full lg:w-auto shrink-0">
            <Button
              variant="outline"
              onClick={fetchData}
              className="border-gray-200 w-full sm:w-auto min-h-11"
              data-testid="refresh-btn"
            >
              <RefreshCw className="w-4 h-4 mr-2 shrink-0" />
              Refresh
            </Button>
            <div className="flex flex-1 items-stretch gap-1 border border-gray-200 rounded-lg p-1 bg-gray-50 min-h-11">
              <button
                type="button"
                onClick={() => setGroupBy('property')}
                className={`flex-1 px-2 sm:px-3 py-2 text-xs sm:text-sm rounded-md min-h-[2.5rem] ${groupBy === 'property' ? 'bg-white shadow border border-gray-200 font-medium text-midnight-blue' : 'text-gray-600'}`}
                data-testid="group-by-property"
              >
                By property
              </button>
              <button
                type="button"
                onClick={() => setGroupBy('requirement')}
                className={`flex-1 px-2 sm:px-3 py-2 text-xs sm:text-sm rounded-md min-h-[2.5rem] ${groupBy === 'requirement' ? 'bg-white shadow border border-gray-200 font-medium text-midnight-blue' : 'text-gray-600'}`}
                data-testid="group-by-requirement"
              >
                By requirement
              </button>
            </div>
            </div>
          </div>
        </div>

        {/* Requirements: accordion by property or grouped by requirement */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {filteredRequirements.length === 0 ? (
            <EmptyState
              icon={FileCheck}
              title="No tracked items found"
              description={searchTerm ? 'Try adjusting your search criteria' : 'No tracked items match the current filter'}
              className="p-12"
            />
          ) : groupBy === 'property' ? (
            <Accordion type="multiple" className="w-full">
              {(() => {
                const byProperty = {};
                filteredRequirements.forEach((req) => {
                  const pid = req.property_id || 'unknown';
                  if (!byProperty[pid]) byProperty[pid] = [];
                  byProperty[pid].push(req);
                });
                return Object.entries(byProperty).map(([propertyId, reqs]) => {
                  const property = getPropertyById(propertyId);
                  const label = property?.nickname || property?.address_line_1 || `Property ${propertyId}`;
                  return (
                    <AccordionItem key={propertyId} value={propertyId} data-testid={`accordion-property-${propertyId}`}>
                      <AccordionTrigger className="px-4 py-3 hover:no-underline">
                        <span className="flex items-center gap-2">
                          <Building2 className="w-4 h-4 text-electric-teal" />
                          {label}
                        </span>
                        <span className="text-sm text-gray-500 font-normal ml-2">({reqs.length} tracked)</span>
                      </AccordionTrigger>
                      <AccordionContent className="px-4 pb-4">
                        <div className="divide-y divide-gray-100">
                          {reqs.map((req) => renderRequirementRow(req))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                });
              })()}
            </Accordion>
          ) : (
            <Accordion type="multiple" className="w-full">
              {(() => {
                const byReqType = {};
                filteredRequirements.forEach((req) => {
                  const type = req.requirement_type || req.requirement_code || 'Other';
                  if (!byReqType[type]) byReqType[type] = [];
                  byReqType[type].push(req);
                });
                return Object.entries(byReqType).map(([reqType, reqs]) => (
                  <AccordionItem key={reqType} value={reqType} data-testid={`accordion-requirement-${reqType}`}>
                    <AccordionTrigger className="px-4 py-3 hover:no-underline">
                      <span className="font-medium text-midnight-blue">{reqType === 'Other' ? 'Other' : requirementLabel(reqType)}</span>
                      <span className="text-sm text-gray-500 font-normal ml-2">({reqs.length})</span>
                    </AccordionTrigger>
                    <AccordionContent className="px-4 pb-4">
                      <div className="divide-y divide-gray-100">
                        {reqs.map((req) => renderRequirementRow(req))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ));
              })()}
            </Accordion>
          )}
        </div>

        {/* Footer count */}
        {filteredRequirements.length > 0 && (
          <div className="mt-4 text-center text-sm text-gray-500">
            Showing {filteredRequirements.length} of {trackedAttentionCount} tracked items
          </div>
        )}

        {notApplicableModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="not-applicable-modal">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6 portal-modal-scroll max-h-[min(90dvh,90vh)]">
              <h3 className="text-lg font-semibold text-midnight-blue mb-2">Mark as not applicable</h3>
              <p className="text-sm text-gray-600 mb-4">
                This is recorded for audit. The requirement is not deleted.
              </p>
              {notApplicableActiveJobId ? (
                <Alert className="mb-4 border-amber-200 bg-amber-50">
                  <AlertDescription className="text-sm text-amber-900">
                    An open compliance job is linked to this requirement (
                    <span className="font-mono">{notApplicableActiveJobId}</span>). To mark not applicable, confirm that
                    this job should be cancelled with audit trail.
                  </AlertDescription>
                </Alert>
              ) : null}
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category (optional)</label>
                  <select
                    value={notApplicableCode}
                    onChange={(e) => setNotApplicableCode(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    {NOT_REQUIRED_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Reason (required, min. 10 characters)</label>
                  <textarea
                    value={notApplicableReason}
                    onChange={(e) => setNotApplicableReason(e.target.value)}
                    rows={4}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="Explain why this requirement does not apply to this property."
                    data-testid="not-applicable-reason"
                  />
                </div>
                {notApplicableActiveJobId ? (
                  <label className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={notApplicableCloseActiveJob}
                      onChange={(e) => setNotApplicableCloseActiveJob(e.target.checked)}
                      data-testid="not-applicable-close-job"
                    />
                    <span>
                      Cancel the open compliance job and mark this requirement not applicable (one step).
                    </span>
                  </label>
                ) : null}
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setNotApplicableModal(null);
                    setNotApplicableReason('');
                    setNotApplicableCloseActiveJob(false);
                    setNotApplicableActiveJobId(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={submitNotApplicable}
                  disabled={notApplicableSaving || (notApplicableActiveJobId && !notApplicableCloseActiveJob)}
                  data-testid="not-applicable-submit"
                >
                  {notApplicableSaving ? 'Saving…' : 'Confirm'}
                </Button>
              </div>
            </div>
          </div>
        )}

        {viewRequirementModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="view-requirement-modal">
            <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6 portal-modal-scroll max-h-[min(90dvh,90vh)]">
              <h3 className="text-lg font-semibold text-midnight-blue mb-2">Requirement</h3>
              {viewRequirementLoading ? (
                <div className="flex items-center gap-2 text-gray-500 py-8">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Loading…
                </div>
              ) : viewRequirementData?.requirement ? (
                <div className="space-y-2 text-sm">
                  <p className="font-medium text-gray-900">
                    {viewRequirementData.requirement.display_label
                      || requirementLabel(viewRequirementData.requirement.requirement_type || viewRequirementData.requirement.requirement_code)}
                  </p>
                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    <dt className="text-gray-500">Workflow status</dt>
                    <dd>{viewRequirementData.requirement.workflow_status || '—'}</dd>
                    <dt className="text-gray-500">Compliance state</dt>
                    <dd>{viewRequirementData.requirement.compliance_state || '—'}</dd>
                    <dt className="text-gray-500">Property</dt>
                    <dd>{getPropertyById(viewRequirementData.requirement.property_id).nickname || getPropertyById(viewRequirementData.requirement.property_id).address_line_1 || '—'}</dd>
                  </dl>
                  {viewRequirementData.active_compliance_job?.job_id ? (
                    <div className="pt-2 border-t border-gray-100 mt-2">
                      <p className="text-xs text-gray-600 mb-1">Active compliance job</p>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="w-full min-h-10"
                        onClick={() => {
                          const jid = viewRequirementData.active_compliance_job.job_id;
                          setViewRequirementModal(null);
                          navigate(`/operations/jobs/${jid}`);
                        }}
                      >
                        Open job {viewRequirementData.active_compliance_job.job_id?.slice(0, 8)}…
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-gray-600">No data.</p>
              )}
              <div className="flex justify-end mt-6">
                <Button variant="outline" onClick={() => setViewRequirementModal(null)}>Close</Button>
              </div>
            </div>
          </div>
        )}

        {/* Edit requirement modal */}
        {editModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="edit-requirement-modal">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6 portal-modal-scroll max-h-[min(90dvh,90vh)]">
              <h3 className="text-lg font-semibold text-midnight-blue mb-4">Edit tracked item</h3>
              <p className="text-sm text-gray-600 mb-2">
                {editModal.requirement.requirement_type?.replace(/_/g, ' ')} — {editModal.property?.nickname || editModal.property?.address_line_1 || 'Property'}
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Expiry date</label>
                  <input
                    type="date"
                    value={editForm.confirmed_expiry_date}
                    onChange={(e) => setEditForm(f => ({ ...f, confirmed_expiry_date: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2"
                    data-testid="edit-expiry-date"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Applies to this property</label>
                  <select
                    value={editForm.applicability}
                    onChange={(e) => setEditForm(f => ({ ...f, applicability: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2"
                    data-testid="edit-applicability"
                  >
                    <option value="UNKNOWN">Unknown / not set</option>
                    <option value="REQUIRED">Yes, applies to this property</option>
                    <option value="NOT_REQUIRED">No, does not apply</option>
                  </select>
                </div>
                {editForm.applicability === 'NOT_REQUIRED' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                    <select
                      value={editForm.not_required_reason}
                      onChange={(e) => setEditForm(f => ({ ...f, not_required_reason: e.target.value }))}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2"
                      data-testid="edit-not-required-reason"
                    >
                      <option value="">Select reason</option>
                      {NOT_REQUIRED_REASONS.map((r) => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <Button variant="outline" onClick={() => setEditModal(null)}>Cancel</Button>
                <Button onClick={handleEditSubmit} disabled={editSaving} data-testid="edit-requirement-submit">
                  {editSaving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          </div>
        )}

      <PlanRestrictedJobModal gate={planJobGate} onDismiss={() => setPlanJobGate(null)} />
    </div>
  );
};

export default RequirementsPage;
