import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import api from '../api/client';
import { toast } from '@/utils/portalNotifications';
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
  Eye,
  Ban,
  ExternalLink,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { projectResolvedRequirementSemantics } from '../utils/resolvedRequirementViewModel';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import { Alert, AlertDescription } from '../components/ui/alert';
import EmptyState from '../components/EmptyState';
import { requirementDisplayTitle, requirementLabel } from '../domain/presentDomain';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import { PortalLoadingPanel } from '../components/client/ClientPortalPatterns';
import { PlanRestrictedJobModal, openPlanRestrictedJobGate } from '../components/client/PlanRestrictedActionModal';
import RequirementIntelligenceModal from '../components/client/RequirementIntelligenceModal';
import { getPropertyDisplayName } from '../utils/propertyDisplayName';
import { REQUIREMENTS_PAGE_CONFIDENCE_LINE } from '../utils/confidenceUxCopy';
import {
  WORKSPACE_REQUIREMENTS_DESCRIPTION_DEFAULT,
  WORKSPACE_REQUIREMENTS_DESCRIPTION_DUE_SOON,
  WORKSPACE_REQUIREMENTS_DESCRIPTION_OVERDUE_OR_MISSING,
  workspaceRequirementsDescriptionWindow,
  WORKSPACE_REQUIREMENTS_EMPTY_DESCRIPTION,
} from '../utils/workspaceOrientationCopy';
import { isRequirementIncludedInAttentionViews } from '../utils/portalRequirementAttention';
import { resolveClientRequirementLifecycle } from '../utils/clientRequirementLifecycle';
import {
  getLifecycleTierBadge,
  getRequirementLifecycleIconTone,
  getRequirementLifecycleRowSurfaceClass,
} from '../utils/requirementLifecyclePresentation';
import {
  executeRequirementPrimaryCta,
  GUIDED_CTA_UNAVAILABLE_TITLE,
} from '../utils/requirementCtaParity';
import { useGuidedEvidenceModal } from '../context/GuidedEvidenceModalContext';
import { isRequirementMissingDocument } from '../utils/propertyDocumentsMatrix';
import { NotApplicableGovernedNotice } from '../utils/notApplicableGovernedCopy';

const NOT_REQUIRED_REASONS = [
  { value: 'no_gas_supply', label: 'No gas supply' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'not_applicable', label: 'Not applicable' },
  { value: 'other', label: 'Other' },
];

const RequirementsPage = () => {
  const navigate = useNavigate();
  const { openGuidedEvidence } = useGuidedEvidenceModal();
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
  const [editForm, setEditForm] = useState({
    confirmed_expiry_date: '',
    applicability: '',
    not_required_reason: '',
    not_applicable_audit_reason: '',
  });
  const [documentCountByRequirementId, setDocumentCountByRequirementId] = useState({});
  const [requirementsPresentation, setRequirementsPresentation] = useState(null);
  const [notApplicableModal, setNotApplicableModal] = useState(null);
  const [notApplicableReason, setNotApplicableReason] = useState('');
  const [notApplicableCode, setNotApplicableCode] = useState('other');
  const [notApplicableSaving, setNotApplicableSaving] = useState(false);
  const [notApplicableCloseActiveJob, setNotApplicableCloseActiveJob] = useState(false);
  const [notApplicableActiveJobId, setNotApplicableActiveJobId] = useState(null);
  const [viewRequirementModal, setViewRequirementModal] = useState(null);
  const [planJobGate, setPlanJobGate] = useState(null);
  const [reopenSavingId, setReopenSavingId] = useState(null);

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
  const getStatusConfig = (req, semOpt) => {
    const sem = semOpt || projectResolvedRequirementSemantics(req, { pagePropertyId: null });
    const config = sem.evidenceStatusForStatus(req.status);
    const cn = String(config.className || '');
    const color = cn.includes('red') ? 'red' : cn.includes('amber') ? 'amber' : cn.includes('emerald') ? 'emerald' : cn.includes('green') ? 'green' : cn.includes('blue') ? 'blue' : 'gray';
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
      not_applicable_audit_reason:
        typeof req.not_applicable_audit_reason === 'string' ? req.not_applicable_audit_reason : '',
    });
    setEditModal({ requirement: req, property: getPropertyById(req.property_id) });
  };

  const openViewRequirementModal = (req) => {
    setViewRequirementModal({ requirement: req });
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
        'Recorded as not applicable with audit reason. Tracking and score views may update after recalculation completes.',
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
        toast.error(det.message || 'An open compliance job must be cancelled to record this as not applicable.');
      } else {
        toast.error(typeof det === 'string' ? det : det?.message || 'Could not update requirement');
      }
    } finally {
      setNotApplicableSaving(false);
    }
  };

  const handleReopenRequirement = async (req) => {
    setReopenSavingId(req.requirement_id);
    try {
      await clientAPI.reopenRequirementById(req.requirement_id);
      toast.success(
        'Restored to active tracking. Score and lists may update after recalculation completes.',
      );
      fetchData();
      if (req.property_id && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail: { property_id: req.property_id } }));
      }
    } catch (error) {
      const det = error.response?.data?.detail;
      toast.error(typeof det === 'string' ? det : det?.message || 'Could not restore requirement');
    } finally {
      setReopenSavingId(null);
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
      if (editForm.applicability === 'NOT_REQUIRED') {
        if (!editForm.not_required_reason) {
          toast.error('Select a category for why this does not apply.');
          setEditSaving(false);
          return;
        }
        const audit = editForm.not_applicable_audit_reason.trim();
        if (audit.length < 10) {
          toast.error('Add an audit note of at least 10 characters describing why this does not apply.');
          setEditSaving(false);
          return;
        }
        payload.not_required_reason = editForm.not_required_reason;
        payload.not_applicable_audit_reason = audit;
      }
      if (Object.keys(payload).length === 0) {
        setEditModal(null);
        setEditSaving(false);
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
    const reqLabel =
      requirementDisplayTitle(req.requirement_display, 'compact') ||
      requirementDisplayTitle(req.requirement_display, 'detail') ||
      requirementLabel(req.requirement_type || req.requirement_code || '');
    const propertyLabel = getPropertyDisplayName(property).toLowerCase();
    const matchesSearch = searchTerm === '' ||
      req.requirement_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reqLabel.toLowerCase().includes(searchTerm.toLowerCase()) ||
      req.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      propertyLabel.includes(searchTerm.toLowerCase());
    
    if (!matchesSearch) return false;

    // Status filter
    if (statusFilter === 'DUE_SOON') {
      return req.status === 'EXPIRING_SOON';
    } else if (statusFilter === 'OVERDUE_OR_MISSING') {
      const lc = resolveClientRequirementLifecycle(req).state;
      return (
        lc === 'ACTION_REQUIRED' ||
        req.status === 'OVERDUE' ||
        req.status === 'MISSING' ||
        req.status === 'MISSING_EVIDENCE'
      );
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
    const sem = projectResolvedRequirementSemantics(req, { pagePropertyId: null });
    const takeActionResolved = sem.cta;
    const statusConfig = getStatusConfig(req, sem);
    const StatusIcon = statusConfig.icon;
    const daysUntil = getDaysUntilDue(req.due_date);
    const docCount = documentCountByRequirementId[req.requirement_id] || 0;
    const hasDocs = docCount > 0;
    const reqClass = String(req.compliance_requirement_class || req.requirement_class || '').toUpperCase();
    const informational =
      reqClass === 'OBLIGATION' ||
      reqClass === 'SYSTEM' ||
      req.engine_informational === true ||
      String(req.engine_client_visibility || req.client_visibility || '').toLowerCase() === 'informational';

    const publishedWhy = String(req.why_it_matters_short || '').trim();
    const lcState = sem.lifecycle.state;
    const requirementPreActionFallback = () => {
      if (informational) {
        return 'This is a tenancy or legal obligation to keep on record; it does not create an urgent task in Today.';
      }
      if (lcState === 'PENDING_REVIEW') {
        return 'Your submission is in the review queue. We will tell you if anything else is required.';
      }
      if (lcState === 'SATISFIED_UNVERIFIED' || lcState === 'VERIFIED') {
        return 'Evidence is on file for this requirement. Keep renewal dates updated to stay in control.';
      }
      if (lcState === 'NOT_APPLICABLE') {
        return 'This item is not applicable for this property under current settings.';
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
    };
    const requirementPreActionLine = publishedWhy || requirementPreActionFallback();
    const runtimeSourceLabel = (() => {
      const s = String(req.source || '').toLowerCase();
      if (s === 'published') return 'Published guidance';
      if (s === 'both') return 'Published + core rules';
      if (s === 'baseline') return 'Core rules';
      return null;
    })();
    const tierBadge = getLifecycleTierBadge(req);
    const iconTone = getRequirementLifecycleIconTone(req);
    const iconWell =
      iconTone === 'red'
        ? { bg: 'bg-red-100', ic: 'text-red-600' }
        : iconTone === 'amber'
          ? { bg: 'bg-amber-100', ic: 'text-amber-700' }
          : iconTone === 'emerald'
            ? { bg: 'bg-emerald-100', ic: 'text-emerald-700' }
            : iconTone === 'green'
              ? { bg: 'bg-green-100', ic: 'text-green-700' }
              : iconTone === 'slate'
                ? { bg: 'bg-slate-100', ic: 'text-slate-600' }
                : { bg: 'bg-gray-100', ic: 'text-gray-600' };
    const rowSurface = getRequirementLifecycleRowSurfaceClass(req);
    return (
      <div
        key={req.requirement_id}
        className={`p-4 hover:bg-gray-50/80 transition-colors ${rowSurface} ${
          flashRequirementId === req.requirement_id ? 'ring-2 ring-electric-teal/70 bg-teal-50/40 rounded-lg' : ''
        }`}
        data-testid={`requirement-row-${req.requirement_id}`}
      >
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="flex items-start gap-4 flex-1 min-w-0">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${iconWell.bg}`}>
              <StatusIcon className={`w-5 h-5 ${iconWell.ic}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-midnight-blue">
                  {requirementDisplayTitle(req.requirement_display, 'compact') ||
                    requirementDisplayTitle(req.requirement_display, 'detail') ||
                    req.display_label ||
                    requirementLabel(req.requirement_type || req.requirement_code) ||
                    'Requirement'}
                </h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusConfig.className}`}>{statusConfig.text}</span>
                {tierBadge ? (
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${tierBadge.className}`}
                    data-testid={`lifecycle-tier-${req.requirement_id}`}
                  >
                    {tierBadge.text}
                  </span>
                ) : null}
                {req.evidence_completeness?.summary_label && req.evidence_completeness.summary_label !== 'Complete' ? (
                  <span
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-900 border border-amber-200"
                    data-testid={`evidence-completeness-${req.requirement_id}`}
                  >
                    {req.evidence_completeness.summary_label}
                  </span>
                ) : null}
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
              {req.why_it_matters_long ? (
                <p className="text-sm text-gray-600 mt-1 line-clamp-3" data-testid={`why-long-${req.requirement_id}`}>
                  {req.why_it_matters_long}
                </p>
              ) : (
                <p className="text-sm text-gray-600 mt-1 line-clamp-2">{req.description || 'No description available'}</p>
              )}
              <div className="flex flex-col gap-1 mt-2 text-sm text-gray-500">
                <div className="flex items-center gap-4 flex-wrap">
                  <span className="flex items-center gap-1 flex-wrap">
                    <Building2 className="w-3.5 h-3.5 shrink-0" />
                    {getPropertyDisplayName(property)}
                    {req.property_jurisdiction ? (
                      <span className="text-xs text-gray-500 border border-gray-200 rounded px-1.5 py-0.5" data-testid={`jurisdiction-${req.requirement_id}`}>
                        {req.property_jurisdiction}
                      </span>
                    ) : null}
                  </span>
                  <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" />{req.date_label || `Due: ${formatDate(req.due_date)}`}</span>
                  {runtimeSourceLabel ? (
                    <span className="text-[11px] text-gray-500 uppercase tracking-wide" data-testid={`runtime-source-${req.requirement_id}`}>
                      {runtimeSourceLabel}
                    </span>
                  ) : null}
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
              const ta = takeActionResolved;
              const primaryError = ta.primary_action_handler === 'guided_evidence_error';
              const onPrimary = () => {
                if (primaryError) return;
                const { handled } = executeRequirementPrimaryCta({
                  requirement: req,
                  pagePropertyId: null,
                  navigate,
                  openGuidedEvidence,
                });
                if (!handled && !ta.primary_route) {
                  openViewRequirementModal(req);
                }
              };
              return (
                <Button
                  className="w-full min-h-11 justify-center bg-electric-teal hover:bg-electric-teal/90 text-midnight-blue font-semibold"
                  onClick={onPrimary}
                  disabled={primaryError}
                  title={primaryError ? GUIDED_CTA_UNAVAILABLE_TITLE : undefined}
                  data-testid={
                    ta.primary_action_handler === 'guided_evidence'
                      ? `requirements-guided-open-${req.requirement_id}`
                      : `requirement-primary-cta-${req.requirement_id}`
                  }
                >
                  {ta.primary_action_label}
                  <ChevronRight className="w-4 h-4 ml-1 shrink-0" />
                </Button>
              );
            })()}
            <div className="flex flex-col gap-2">
              {(() => {
                const ta = takeActionResolved;
                if (ta.secondary_action?.route) {
                  const sec = ta.secondary_action;
                  return (
                    <button
                      type="button"
                      className="text-sm text-electric-teal hover:underline text-left min-h-10"
                      onClick={() => {
                        if (sec.external) window.open(sec.route, '_blank', 'noopener,noreferrer');
                        else navigate(sec.route);
                      }}
                      data-testid={`requirement-secondary-${req.requirement_id}`}
                    >
                      {sec.label}
                    </button>
                  );
                }
                return null;
              })()}
              {(() => {
                const links = Array.isArray(takeActionResolved.supporting_external_links)
                  ? takeActionResolved.supporting_external_links
                  : [];
                if (!links.length) return null;
                return (
                  <div className="flex flex-col gap-1 pt-1 border-t border-gray-100">
                    <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">External resources</p>
                    {links.map((lnk) => (
                      <button
                        key={lnk.key || lnk.url}
                        type="button"
                        className="text-xs text-electric-teal hover:underline text-left min-h-10 inline-flex items-start gap-1"
                        onClick={() => window.open(String(lnk.url || ''), '_blank', 'noopener,noreferrer')}
                        data-testid={`requirement-external-link-${req.requirement_id}-${lnk.key || 'link'}`}
                      >
                        <span className="break-words text-left">{lnk.label}</span>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0 mt-0.5 opacity-80" aria-hidden />
                      </button>
                    ))}
                  </div>
                );
              })()}
              <button
                type="button"
                className="text-sm text-gray-600 hover:underline text-left min-h-10"
                onClick={() => openViewRequirementModal(req)}
                data-testid={`compliance-view-requirement-${req.requirement_id}`}
              >
                Requirement details
              </button>
              <button
                type="button"
                className="text-xs text-gray-500 hover:text-midnight-blue text-left underline"
                onClick={() => openEditModal(req)}
                data-testid={`edit-requirement-${req.requirement_id}`}
              >
                Edit dates and applicability
              </button>
              {String(req.applicability || '').toUpperCase() === 'NOT_REQUIRED' ? (
                <button
                  type="button"
                  className="text-xs text-gray-500 hover:text-midnight-blue text-left underline disabled:opacity-50"
                  disabled={reopenSavingId === req.requirement_id}
                  onClick={() => handleReopenRequirement(req)}
                  data-testid={`compliance-reopen-${req.requirement_id}`}
                >
                  {reopenSavingId === req.requirement_id ? 'Restoring…' : 'Restore to active tracking'}
                </button>
              ) : (
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
                  Record as not applicable
                </button>
              )}
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
    if (statusFilter === 'DUE_SOON') return WORKSPACE_REQUIREMENTS_DESCRIPTION_DUE_SOON;
    if (statusFilter === 'OVERDUE_OR_MISSING') return WORKSPACE_REQUIREMENTS_DESCRIPTION_OVERDUE_OR_MISSING;
    if (windowDays) return workspaceRequirementsDescriptionWindow(windowDays);
    return WORKSPACE_REQUIREMENTS_DESCRIPTION_DEFAULT;
  };

  // Stats
  const statsBase = requirements.filter(
    (r) => r.client_surface_visible !== false && isRequirementIncludedInAttentionViews(r)
  );
  const trackedAttentionCount = statsBase.length;
  const stats = {
    total: trackedAttentionCount,
    compliant: statsBase.filter((r) => {
      const s = resolveClientRequirementLifecycle(r).state;
      return s === 'VERIFIED' || s === 'SATISFIED_UNVERIFIED';
    }).length,
    expiringSoon: statsBase.filter((r) => r.status === 'EXPIRING_SOON').length,
    attentionAction: statsBase.filter((r) => resolveClientRequirementLifecycle(r).state === 'ACTION_REQUIRED').length,
    pendingReview: statsBase.filter((r) => resolveClientRequirementLifecycle(r).state === 'PENDING_REVIEW').length,
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
            <p className="text-2xl font-bold text-red-600">{stats.attentionAction}</p>
            <p className="text-sm text-gray-500">Action required</p>
            {stats.pendingReview > 0 ? (
              <p className="text-xs text-amber-700 mt-1 tabular-nums" data-testid="requirements-pending-review-hint">
                {stats.pendingReview} awaiting review
              </p>
            ) : null}
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
              description={searchTerm ? 'Try adjusting your search criteria' : WORKSPACE_REQUIREMENTS_EMPTY_DESCRIPTION}
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
                  const label = getPropertyDisplayName(property) || `Property ${propertyId}`;
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
                      <span className="font-medium text-midnight-blue">
                        {reqType === 'Other'
                          ? 'Other'
                          : requirementDisplayTitle(reqs?.[0]?.requirement_display, 'compact') ||
                            requirementDisplayTitle(reqs?.[0]?.requirement_display, 'detail') ||
                            requirementLabel(reqType)}
                      </span>
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
              <h3 className="text-lg font-semibold text-midnight-blue mb-2">Record as not applicable</h3>
              <div className="mb-4">
                <NotApplicableGovernedNotice />
              </div>
              {notApplicableActiveJobId ? (
                <Alert className="mb-4 border-amber-200 bg-amber-50">
                  <AlertDescription className="text-sm text-amber-900">
                    An open compliance job is linked to this requirement (
                    <span className="font-mono">{notApplicableActiveJobId}</span>). To record this as not applicable, confirm that
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
                      Cancel the open compliance job and record this requirement as not applicable (one step).
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

        <RequirementIntelligenceModal
          open={!!viewRequirementModal}
          requirementId={viewRequirementModal?.requirement?.requirement_id || null}
          seedRequirement={viewRequirementModal?.requirement || null}
          propertyLabel={
            viewRequirementModal?.requirement?.property_id
              ? getPropertyById(viewRequirementModal.requirement.property_id).nickname
                || getPropertyById(viewRequirementModal.requirement.property_id).address_line_1
                || null
              : null
          }
          onClose={() => setViewRequirementModal(null)}
          onNavigate={(path) => {
            setViewRequirementModal(null);
            navigate(path);
          }}
          showEditDatesAndApplicability
          onEditDates={(merged) => {
            setViewRequirementModal(null);
            openEditModal(merged);
          }}
          onMarkNotApplicable={(merged) => {
            setViewRequirementModal(null);
            setNotApplicableModal({ requirement: merged });
            setNotApplicableReason('');
            setNotApplicableCode('other');
            setNotApplicableCloseActiveJob(false);
            setNotApplicableActiveJobId(null);
          }}
        />

        {/* Edit requirement modal */}
        {editModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" data-testid="edit-requirement-modal">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6 portal-modal-scroll max-h-[min(90dvh,90vh)]">
              <h3 className="text-lg font-semibold text-midnight-blue mb-4">Edit tracked item</h3>
              <p className="text-sm text-gray-600 mb-2">
                {requirementLabel(editModal.requirement.requirement_type || editModal.requirement.requirement_code)} —{' '}
                {getPropertyDisplayName(editModal.property)}
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
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                      <select
                        value={editForm.not_required_reason}
                        onChange={(e) => setEditForm(f => ({ ...f, not_required_reason: e.target.value }))}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2"
                        data-testid="edit-not-required-reason"
                      >
                        <option value="">Select category</option>
                        {NOT_REQUIRED_REASONS.map((r) => (
                          <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Audit note (required, min. 10 characters)</label>
                      <textarea
                        value={editForm.not_applicable_audit_reason}
                        onChange={(e) => setEditForm(f => ({ ...f, not_applicable_audit_reason: e.target.value }))}
                        rows={3}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                        placeholder="Explain why this does not apply, for audit and support review."
                        data-testid="edit-not-applicable-audit-reason"
                      />
                    </div>
                    <div className="rounded-md border border-gray-100 bg-gray-50/80 p-2">
                      <NotApplicableGovernedNotice variant="compact" />
                    </div>
                  </>
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
