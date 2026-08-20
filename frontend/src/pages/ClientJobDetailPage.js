/**
 * Canonical client job detail: one workflow surface for compliance and maintenance jobs.
 * Data: GET /api/jobs/{id} (next_actions drives lifecycle CTAs).
 *
 * ACTION GATING (execution / scheduling / assignment / evidence):
 * Lifecycle buttons (request_booking, propose_schedule, confirm_visit, mark_no_access,
 * mark_reschedule_required, start, awaiting_parts, complete, verify, resume_after_parts, link_document,
 * assign) render only when `job.next_actions` contains a matching `id`. Assign contractor opens a modal:
 * GET /api/jobs/{id}/assignable-contractors; add-new (inline in this modal only) uses POST /api/contractors then
 * POST .../assign-contractor, with client-side soft duplicate hints against the assignable list.
 * Exception canonical states from the server (NO_ACCESS, RESCHEDULE_REQUIRED, FOLLOW_UP_REQUIRED,
 * AWAITING_PARTS) intentionally omit start/complete/verify/link_document; see
 * tests/test_compliance_workflow_maintenance_canonical.py and _maintenance_next_job_actions.
 * Cancel whole-job is gated on `next_actions` containing `cancel` (lifecycle section) — not raw status alone.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { clientAPI, parseApiError, contractorEvidenceFilenameFromKey, isContractorFileEvidenceKey, openBlobApiResponse } from '../api/client';
import { OperationalCapabilityProtectedRoute } from '../utils/CapabilityProtectedRoute';
import {
  useOperationalExecutionCapabilities,
} from '../utils/operationalCapabilityAccess';
import { jobLifecycleSuccessMessage, JOB_DETAIL_CONFIDENCE_LINE } from '../utils/confidenceUxCopy';
import { operationalLabelForToken } from '../utils/presentationLanguage';
import { resolveClientPortalPath, resolvePropertyPath } from '../utils/clientPortalNavigation';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Loader2,
  ArrowLeft,
  Wrench,
  Calendar,
  User,
  ClipboardList,
  FileText,
  History,
  LifeBuoy,
  ListChecks,
  Lock,
  Receipt,
  MessageSquareText,
} from 'lucide-react';
import { ContractorNetworkLockedModal } from '../components/client/ContractorNetworkLockedModal';
import { toast } from '@/utils/portalNotifications';
import { operationalExceptionLabel } from '../domain/presentDomain';
import {
  clientCurrentUpdateSummary,
  clientHeroOversightAction,
  clientJobProgressFromJob,
  prioritizedClientJobNextAction,
} from '../utils/jobWorkflowUi';
import NextActionHero from '../components/operational/NextActionHero';
import {
  canExecuteAssignContractor,
  canShowCancelJob,
  executeJobDetailPrimaryIntent,
  handleAssignContractorClick,
  isAssignContractorEntitlementBlocked,
  resolveHeroPrimaryExecution,
} from '../utils/jobDetailPrimaryAction';
import {
  assignDropdownEmptyMessage,
  groupedExclusionSamples,
} from '../utils/assignContractorRecovery';
import {
  earlyNetworkSupportText,
  ELIGIBILITY_EMPTY_SUMMARY,
  EARLY_NETWORK_GUIDANCE,
  EARLY_NETWORK_PRIMARY_CTA,
  EARLY_NETWORK_SECONDARY_HEADER,
  isEarlyNetworkMode,
  NETWORK_MATURITY_BANNER,
  networkCoverageLevel,
} from '../utils/assignContractorEarlyNetwork';
import { resolveAssignModalFocusTarget } from '../utils/assignContractorModalFocus';

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(iso);
  }
}

/** Trade / service tags for filter + add-contractor form (aligns with contractor trade_types vocabulary). */
const TRADE_SERVICE_OPTIONS = [
  { value: 'general', label: 'General / handyman' },
  { value: 'heating', label: 'Heating / gas' },
  { value: 'plumbing', label: 'Plumbing' },
  { value: 'electrical', label: 'Electrical' },
  { value: 'epc', label: 'EPC / energy assessor' },
  { value: 'fire', label: 'Fire / alarms' },
  { value: 'legionella', label: 'Legionella / water hygiene' },
  { value: 'damp', label: 'Damp / inspection' },
];

const TRADE_FILTER_OPTIONS = [{ value: 'all', label: 'All trades (no filter)' }, ...TRADE_SERVICE_OPTIONS];

/** UK portfolio labels aligned with backend contractor.service_regions / job jurisdiction. */
const UK_SERVICE_REGION_OPTIONS = [
  { value: 'Scotland', label: 'Scotland' },
  { value: 'England', label: 'England' },
  { value: 'Wales', label: 'Wales' },
  { value: 'Northern Ireland', label: 'Northern Ireland' },
];

function defaultTradeForJob(job) {
  if (!job) return 'general';
  const cat = (job.category || '').toLowerCase().trim();
  if (cat) {
    if (cat.includes('plumb')) return 'plumbing';
    if (cat.includes('electr')) return 'electrical';
    if (cat.includes('gas') || cat.includes('heat') || cat.includes('boiler')) return 'heating';
    return 'general';
  }
  const rc = (job.requirement_code || '').toLowerCase().replace(/-/g, '_');
  const map = {
    gas_safety: 'heating',
    eicr: 'electrical',
    epc: 'epc',
    fire_detection: 'fire',
    fire_risk_assessment: 'fire',
    portable_appliance_test: 'electrical',
    smoke_alarms: 'fire',
    co_alarms: 'fire',
    legionella: 'legionella',
  };
  return map[rc] || 'general';
}

function contractorMatchesTradeFilter(contractor, filterVal) {
  if (!filterVal || filterVal === 'all') return true;
  const fv = filterVal.toLowerCase();
  const trades = (contractor.trade_types || []).map((t) => String(t).toLowerCase());
  return trades.some((t) => t === fv || t.includes(fv) || fv.includes(t));
}

function digitsOnly(s) {
  return String(s || '').replace(/\D/g, '');
}

function normEmail(s) {
  return String(s || '').trim().toLowerCase();
}

/**
 * Soft duplicate hints against the full assignable list (not trade-filtered) so users see possible matches
 * even when the current trade filter hides a row.
 */
function findSoftDuplicateContractors(contractors, { company_name, email, phone }) {
  const em = normEmail(email);
  const ph = digitsOnly(phone);
  const nm = String(company_name || '').trim().toLowerCase();
  if (!em && ph.length < 6 && nm.length < 2) return [];
  const seen = new Set();
  const out = [];
  for (const c of contractors || []) {
    const id = c.contractor_id;
    if (!id || seen.has(id)) continue;
    const reasons = [];
    if (em) {
      const ce = normEmail(c.email);
      if (ce && ce === em) reasons.push('same email');
    }
    if (ph.length >= 6) {
      const cp = digitsOnly(c.phone);
      if (cp.length >= 6 && (cp === ph || cp.endsWith(ph) || ph.endsWith(cp))) reasons.push('similar phone');
    }
    if (nm.length >= 2) {
      const cn = String(c.company_name || '').trim().toLowerCase();
      const nname = String(c.name || '').trim().toLowerCase();
      const fields = [cn, nname].filter(Boolean);
      for (const f of fields) {
        if (f === nm || (nm.length >= 3 && (f.includes(nm) || nm.includes(f)))) {
          reasons.push('similar name');
          break;
        }
      }
    }
    if (reasons.length) {
      seen.add(id);
      out.push({ contractor: c, reasons: [...new Set(reasons)] });
    }
  }
  return out;
}

function contractorOptionLabel(c) {
  const primary = c.name || c.company_name || 'Contractor';
  const bits = [primary];
  if (c.company_name && c.name && c.company_name !== c.name) bits.push(c.company_name);
  if (c.email) bits.push(c.email);
  if (Array.isArray(c.service_regions) && c.service_regions.length > 0) {
    bits.push(`Regions: ${c.service_regions.join(', ')}`);
  }
  const onboarding = (c.onboarding_state || '').toLowerCase();
  if (onboarding && !['active'].includes(onboarding)) {
    const label = c.onboarding_state_label || 'Portal activation required';
    bits.push(label);
  }
  return bits.join(' · ');
}

/** Canonical job_status / execution states that need an explicit operational explanation in the UI. */
const EXCEPTION_STATE_PLAYBOOK = {
  NO_ACCESS: {
    label: 'No access',
    explanation:
      'The job is on hold because the property could not be accessed or the visit could not proceed. No further work should be assumed until this is resolved.',
  },
  RESCHEDULE_REQUIRED: {
    label: 'Reschedule required',
    explanation:
      'A new visit window is needed before work can continue. Agree a time with your contractor or operations, then confirm the schedule.',
  },
  FOLLOW_UP_REQUIRED: {
    label: 'Follow-up required',
    explanation:
      'Additional coordination or a return visit is needed before the job can move forward. Clear this hold when the follow-up is complete.',
  },
  AWAITING_PARTS: {
    label: 'Awaiting parts',
    explanation:
      'Work is paused until parts or materials arrive. When everything is on site, resume the job so the contractor can continue.',
  },
};

function recoveryLineFromNextActions(job) {
  const a = prioritizedClientJobNextAction(job);
  if (!a) return null;
  const tail = a.hint ? ` — ${a.hint}` : '';
  return `When you're ready: ${a.label}${tail}`;
}

function exceptionStateBanner(job) {
  const key = (job?.job_status || '').toUpperCase();
  const pb = EXCEPTION_STATE_PLAYBOOK[key];
  if (!pb) return null;
  const recovery = recoveryLineFromNextActions(job);
  return { key, ...pb, recovery };
}

function SectionCard({ title, icon: Icon, children }) {
  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          {Icon ? <Icon className="w-4 h-4 text-gray-500" /> : null}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-3 text-sm">{children}</CardContent>
    </Card>
  );
}

function ClientJobDetailInner() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const {
    canUseOpsContractors,
    canWriteOpsContractors,
    canUseOpsApprovals,
    canWriteOpsApprovals,
    canUseOpsComplianceReview,
    canWriteOpsMaintenance,
  } = useOperationalExecutionCapabilities();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionBusy, setActionBusy] = useState(null);
  const [assignableContractors, setAssignableContractors] = useState([]);
  /** Effective job jurisdiction from assignable-contractors API (for filtering + UX). */
  const [assignableJobJurisdiction, setAssignableJobJurisdiction] = useState(null);
  /** Server pipeline counts: who appears in directory vs excluded at each gate (mutually exclusive buckets). */
  const [assignableFilterDiagnostics, setAssignableFilterDiagnostics] = useState(null);
  const [assignableRecoveryGuidance, setAssignableRecoveryGuidance] = useState(null);
  const [assignableExclusionSamples, setAssignableExclusionSamples] = useState(null);
  const [assignablePropertyPostcode, setAssignablePropertyPostcode] = useState(null);
  const [showExcludedContractors, setShowExcludedContractors] = useState(false);
  const [showEligibilityDiagnostics, setShowEligibilityDiagnostics] = useState(false);
  const [assignableLoading, setAssignableLoading] = useState(false);
  const [contractorFilter, setContractorFilter] = useState('');
  const [tradeTypeFilter, setTradeTypeFilter] = useState('all');
  const [assignContractorId, setAssignContractorId] = useState('');
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignModalError, setAssignModalError] = useState('');
  const [bookingGuardOpen, setBookingGuardOpen] = useState(false);
  const [showAddContractorForm, setShowAddContractorForm] = useState(false);
  /** After soft-duplicate warning, user explicitly chooses to create a new record anyway. */
  const [allowCreateDespiteDuplicates, setAllowCreateDespiteDuplicates] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    datetimeLocal: '',
    timezone: typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/London' : 'Europe/London',
    notes: '',
  });
  const [newContractor, setNewContractor] = useState({
    company_name: '',
    tradeType: 'general',
    phone: '',
    email: '',
    contact_name: '',
    region: '',
    accreditation: '',
    notes: '',
    areas_served: '',
    /** @type {string[]} */
    service_regions: [],
  });
  const [linkDocId, setLinkDocId] = useState('');
  const [exceptionChoice, setExceptionChoice] = useState('');
  const [decisionNote, setDecisionNote] = useState('');
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);
  const [quoteRevisionOpen, setQuoteRevisionOpen] = useState(false);
  const [quoteRevisionReasonCode, setQuoteRevisionReasonCode] = useState('price_too_high');
  const [quoteRevisionMessage, setQuoteRevisionMessage] = useState('');
  const [quoteRevisionTargetBudget, setQuoteRevisionTargetBudget] = useState('');
  const [quoteRejectFinalOpen, setQuoteRejectFinalOpen] = useState(false);
  const [quoteRejectFinalReason, setQuoteRejectFinalReason] = useState('');

  const QUOTE_REVISION_REASONS = [
    { code: 'price_too_high', label: 'Price too high' },
    { code: 'scope_unclear', label: 'Scope unclear' },
    { code: 'missing_breakdown', label: 'Missing breakdown' },
    { code: 'wrong_work_proposed', label: 'Wrong work proposed' },
    { code: 'incomplete_quote', label: 'Incomplete quote' },
    { code: 'timeline_unsuitable', label: 'Timeline unsuitable' },
    { code: 'other', label: 'Other' },
  ];
  const visitSectionRef = useRef(null);
  const assignModalBodyRef = useRef(null);
  const assignContractorSelectRef = useRef(null);
  const earlyNetworkCtaRef = useRef(null);
  const addContractorNameRef = useRef(null);
  const [contractorNetworkLockedOpen, setContractorNetworkLockedOpen] = useState(false);
  const openContractorNetworkLocked = useCallback(() => setContractorNetworkLockedOpen(true), []);

  const clientProgress = useMemo(
    () => (job ? clientJobProgressFromJob(job) : { steps: [], currentIndex: -1, completedFlags: [] }),
    [job],
  );
  const currentUpdate = useMemo(
    () => (job ? clientCurrentUpdateSummary(job) : { headline: '', lines: [], canonical: '' }),
    [job],
  );
  const heroOversightAction = useMemo(
    () => (job ? clientHeroOversightAction(job.next_actions) : null),
    [job],
  );
  const heroExecution = useMemo(
    () => (job ? resolveHeroPrimaryExecution(job, canUseOpsContractors) : null),
    [job, canUseOpsContractors],
  );
  const showCancelJob = useMemo(() => (job ? canShowCancelJob(job) : false), [job]);
  const cancelJobAction = useMemo(
    () => (job?.next_actions || []).find((a) => a?.id === 'cancel') || null,
    [job],
  );

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError('');
    try {
      const res = await clientAPI.getComplianceWorkflowJob(jobId);
      setJob(res.data || null);
    } catch (err) {
      setJob(null);
      setError(parseApiError(err, 'Could not load job'));
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setAllowCreateDespiteDuplicates(false);
  }, [newContractor.company_name, newContractor.email, newContractor.phone]);

  const serverEligibleCountForFocus = assignableFilterDiagnostics?.eligible ?? assignableContractors.length;

  useEffect(() => {
    if (!assignModalOpen || assignableLoading) return undefined;
    const frame = window.requestAnimationFrame(() => {
      assignModalBodyRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      const target = resolveAssignModalFocusTarget({
        showAddContractorForm,
        eligibleCount: serverEligibleCountForFocus,
      });
      if (target === 'add_name') {
        addContractorNameRef.current?.focus();
        return;
      }
      if (target === 'select') {
        assignContractorSelectRef.current?.focus();
        return;
      }
      earlyNetworkCtaRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [assignModalOpen, assignableLoading, showAddContractorForm, serverEligibleCountForFocus]);

  const loadAssignableContractors = useCallback(async () => {
    if (!jobId || !canUseOpsContractors) return;
    setAssignableLoading(true);
    try {
      const r = await clientAPI.getJobAssignableContractors(jobId, { limit: 200 });
      setAssignableContractors(r.data?.contractors || []);
      setAssignableFilterDiagnostics(r.data?.filter_diagnostics ?? null);
      setAssignableRecoveryGuidance(r.data?.recovery_guidance ?? null);
      setAssignableExclusionSamples(r.data?.exclusion_samples ?? null);
      setAssignablePropertyPostcode(r.data?.property_postcode ?? null);
      const jj = r.data?.job_jurisdiction ?? null;
      setAssignableJobJurisdiction(jj);
      return r.data;
    } catch {
      setAssignableContractors([]);
      setAssignableJobJurisdiction(null);
      setAssignableRecoveryGuidance(null);
      setAssignableExclusionSamples(null);
      toast.error('Could not load assignable contractors');
      return null;
    } finally {
      setAssignableLoading(false);
    }
  }, [jobId, canUseOpsContractors]);

  const openAssignModal = useCallback(
    async (opts = {}) => {
      const { focusAdd = false } = opts;
      if (!jobId || !canUseOpsContractors) return;
      setAssignModalOpen(true);
      setShowAddContractorForm(!!focusAdd);
      setShowExcludedContractors(false);
      setShowEligibilityDiagnostics(false);
      const suggested = defaultTradeForJob(job);
      setTradeTypeFilter(suggested);
      setNewContractor((prev) => ({ ...prev, tradeType: suggested }));
      const data = await loadAssignableContractors();
      const jj = data?.job_jurisdiction ?? null;
      setNewContractor((prev) => ({
        ...prev,
        tradeType: suggested,
        service_regions:
          (job?.work_order_kind || '').toUpperCase() === 'COMPLIANCE' && jj ? [jj] : [],
      }));
    },
    [jobId, job, canUseOpsContractors, loadAssignableContractors]
  );

  const kindLabel = useMemo(() => {
    const k = (job?.work_order_kind || '').toUpperCase();
    if (k === 'COMPLIANCE') return 'Compliance job';
    return 'Maintenance job';
  }, [job]);

  const nextBySection = useMemo(() => {
    const list = job?.next_actions || [];
    const m = { summary: [], assignment: [], scheduling: [], execution: [], evidence: [], timeline: [], billing: [] };
    for (const a of list) {
      const sec = (a.section || 'execution').toLowerCase();
      if (m[sec]) m[sec].push(a);
      else m.execution.push(a);
    }
    return m;
  }, [job]);

  const runAction = async (key, fn, { successToast } = {}) => {
    if (!jobId) return;
    setActionBusy(key);
    try {
      const data = await fn();
      if (data && typeof data === 'object' && (data.job_id || data.work_order_id)) setJob(data);
      else await load();
      const msg = typeof successToast === 'string' ? successToast : jobLifecycleSuccessMessage(key);
      toast.success(msg);
      const prop =
        data && typeof data === 'object' && data.property_id
          ? data.property_id
          : job?.property_id;
      if (prop && typeof window !== 'undefined') {
        const milestoneKeys = new Set(['complete', 'verify', 'close_job']);
        const detail = { property_id: prop };
        if (milestoneKeys.has(String(key))) detail.job_execution_milestone = true;
        window.dispatchEvent(new CustomEvent('compliance-outcome', { detail }));
      }
    } catch (err) {
      const msg = parseApiError(err, 'Action failed');
      toast.error(msg);
      if (key === 'assign' || key === 'create_contractor_assign') {
        setAssignModalError(msg);
      }
    } finally {
      setActionBusy(null);
    }
  };

  const schedulePayload = () => ({
    scheduled_at: new Date(scheduleForm.datetimeLocal).toISOString(),
    timezone: scheduleForm.timezone,
    notes: scheduleForm.notes || undefined,
  });

  const scheduleTimeActions = ['request_booking', 'propose_schedule', 'reschedule_booking'];

  const handleLifecycleClick = (actionId) => {
    if (!jobId) return;
    if (actionId === 'request_quote_revision') {
      setQuoteRevisionOpen(true);
      return;
    }
    if (actionId === 'request_visit_reschedule') {
      const reason = window.prompt('Optional note for the contractor (why you need another date)') ?? '';
      runAction('request_visit_reschedule', () =>
        clientAPI.complianceJobRequestVisitReschedule(jobId, { reason: reason.trim() || undefined }).then((r) => r.data),
      );
      return;
    }
    if (
      scheduleTimeActions.includes(actionId) &&
      !(job?.contractor_id || '').toString().trim()
    ) {
      setBookingGuardOpen(true);
      return;
    }
    const map = {
      request_booking: () => clientAPI.complianceJobRequestBooking(jobId, schedulePayload()).then((r) => r.data),
      propose_schedule: () => clientAPI.complianceJobRequestBooking(jobId, schedulePayload()).then((r) => r.data),
      reschedule_booking: () => clientAPI.complianceJobReschedule(jobId, schedulePayload()).then((r) => r.data),
      confirm_visit: () => clientAPI.complianceJobConfirmBooking(jobId).then((r) => r.data),
      cancel_booking: () => clientAPI.complianceJobCancelBooking(jobId).then((r) => r.data),
      mark_no_access: () => clientAPI.complianceJobMarkNoAccess(jobId, {}).then((r) => r.data),
      mark_reschedule_required: () =>
        clientAPI.complianceJobMarkRescheduleRequired(jobId).then((r) => r.data),
      start: () => clientAPI.complianceJobStart(jobId).then((r) => r.data),
      awaiting_parts: () => clientAPI.complianceJobAwaitingParts(jobId).then((r) => r.data),
      complete: () => clientAPI.complianceJobComplete(jobId).then((r) => r.data),
      verify: () => clientAPI.complianceJobVerify(jobId).then((r) => r.data),
      close_job: () => clientAPI.complianceJobClose(jobId).then((r) => r.data),
      cancel: () => clientAPI.complianceJobCancel(jobId).then((r) => r.data),
      resume_after_parts: () => clientAPI.complianceJobResumeAfterParts(jobId).then((r) => r.data),
      clear_operational_exception: () =>
        clientAPI.complianceJobSetOperationalException(jobId, '').then((r) => r.data),
      approve_quote: () => clientAPI.complianceJobApproveQuote(jobId).then((r) => r.data),
      accept_completion: () => clientAPI.complianceJobAcceptCompletion(jobId).then((r) => r.data),
      request_proof_clarification: () => {
        const note = window.prompt('What should the contractor clarify or replace on the proof?') ?? '';
        return clientAPI
          .complianceJobRequestProofClarification(jobId, { note: note.trim() || undefined })
          .then((r) => r.data);
      },
      reject_completion: () => {
        const note = window.prompt('Why are you rejecting this completion?') ?? '';
        return clientAPI.complianceJobRejectCompletion(jobId, { note: note.trim() || undefined }).then((r) => r.data);
      },
      link_document: () => clientAPI.complianceJobLinkDocument(jobId, { document_id: linkDocId.trim() }).then((r) => r.data),
      attach_completion_proof: () =>
        clientAPI.complianceJobAttachCompletionProof(jobId, { document_id: linkDocId.trim() }).then((r) => r.data),
    };
    const fn = map[actionId];
    if (!fn) {
      toast.message('Use the controls in this section for this step.');
      return;
    }
    if (scheduleTimeActions.includes(actionId) && !scheduleForm.datetimeLocal) {
      toast.error('Choose a date and time for the visit.');
      return;
    }
    if ((actionId === 'link_document' || actionId === 'attach_completion_proof') && !linkDocId.trim()) {
      toast.error('Enter a document ID from your vault.');
      return;
    }
    runAction(actionId, fn);
  };

  const handleAssign = () => {
    if (!assignContractorId.trim()) {
      toast.error('Select a contractor');
      return;
    }
    runAction(
      'assign',
      () =>
        clientAPI.complianceJobAssignContractor(jobId, { contractor_id: assignContractorId.trim() }).then((r) => {
          setAssignModalOpen(false);
          return r.data;
        }),
      {
        successToast: assignSelectedNeedsActivation
          ? 'Contractor assigned. They will receive job and portal activation emails — portal activation is required before they can respond.'
          : 'Contractor assigned. They will receive an email with a secure link to view the job.',
      },
    );
  };

  const softDuplicateMatches = useMemo(
    () =>
      showAddContractorForm
        ? findSoftDuplicateContractors(assignableContractors, {
            company_name: newContractor.company_name,
            email: newContractor.email,
            phone: newContractor.phone,
          })
        : [],
    [
      showAddContractorForm,
      assignableContractors,
      newContractor.company_name,
      newContractor.email,
      newContractor.phone,
    ]
  );

  const handleCreateAndAssign = () => {
    if (!newContractor.company_name.trim()) {
      toast.error('Name is required');
      return;
    }
    if (!newContractor.tradeType) {
      toast.error('Select a trade / service type');
      return;
    }
    if (!newContractor.phone.trim() && !newContractor.email.trim()) {
      toast.error('Add at least one contact method.');
      return;
    }
    if (softDuplicateMatches.length > 0 && !allowCreateDespiteDuplicates) {
      toast.error('Select a listed contractor—Create new if none match.');
      return;
    }
    runAction(
      'create_contractor_assign',
      async () => {
        const body = {
          company_name: newContractor.company_name.trim(),
          trade_types: [newContractor.tradeType],
          phone: newContractor.phone.trim() || undefined,
          email: newContractor.email.trim() || undefined,
          contact_name: newContractor.contact_name.trim() || undefined,
          region: newContractor.region.trim() || undefined,
          areas_served: newContractor.areas_served.trim()
            ? newContractor.areas_served.split(',').map((s) => s.trim()).filter(Boolean)
            : undefined,
          accreditation_certification: newContractor.accreditation.trim() || undefined,
          notes: newContractor.notes.trim() || undefined,
          work_order_id: jobId,
          service_regions:
            Array.isArray(newContractor.service_regions) && newContractor.service_regions.length > 0
              ? newContractor.service_regions
              : undefined,
        };
        const cr = await clientAPI.createWorkflowContractor(body);
        const cid = cr.data?.contractor_id;
        if (!cid) throw new Error('Contractor was not created');
        const ar = await clientAPI.complianceJobAssignContractor(jobId, { contractor_id: cid });
        setAssignModalOpen(false);
        setShowAddContractorForm(false);
        setAllowCreateDespiteDuplicates(false);
        return ar.data;
      },
      {
        successToast:
          'Contractor saved and assigned. They will receive job and portal activation emails — they must activate their portal before they can view the job, submit a quote, or update progress.',
      }
    );
  };

  const handleUseDuplicateMatch = (contractorId) => {
    setAssignContractorId(contractorId);
    setShowAddContractorForm(false);
    setAllowCreateDespiteDuplicates(false);
    toast.message('Existing contractor selected — tap Assign selected to confirm.');
  };

  const handleSetException = () => {
    runAction('op_ex', () =>
      clientAPI.complianceJobSetOperationalException(jobId, exceptionChoice).then((r) => r.data)
    );
  };

  const filteredAssignableContractors = useMemo(() => {
    let list = assignableContractors.filter((c) => contractorMatchesTradeFilter(c, tradeTypeFilter));
    const q = (contractorFilter || '').toLowerCase().trim();
    if (!q) return list;
    return list.filter(
      (c) =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.company_name || '').toLowerCase().includes(q) ||
        (c.email || '').toLowerCase().includes(q) ||
        (c.contractor_id || '').toLowerCase().includes(q)
    );
  }, [assignableContractors, contractorFilter, tradeTypeFilter]);

  const selectedAssignContractor = useMemo(
    () => filteredAssignableContractors.find((c) => c.contractor_id === assignContractorId) || null,
    [filteredAssignableContractors, assignContractorId],
  );

  const assignSelectedNeedsActivation = useMemo(() => {
    const st = (selectedAssignContractor?.onboarding_state || '').toLowerCase();
    return !!st && !['active', 'disabled', 'unavailable'].includes(st);
  }, [selectedAssignContractor]);

  const assignableClientFilterStats = useMemo(() => {
    const total = assignableContractors.length;
    const afterTrade = assignableContractors.filter((c) => contractorMatchesTradeFilter(c, tradeTypeFilter));
    const hiddenByTrade =
      tradeTypeFilter && tradeTypeFilter !== 'all' ? Math.max(0, total - afterTrade.length) : 0;
    const q = (contractorFilter || '').toLowerCase().trim();
    const hiddenBySearch = q ? Math.max(0, afterTrade.length - filteredAssignableContractors.length) : 0;
    return { total, hiddenByTrade, hiddenBySearch, afterTradeCount: afterTrade.length };
  }, [assignableContractors, tradeTypeFilter, contractorFilter, filteredAssignableContractors]);

  const assignDropdownEmpty = useMemo(
    () =>
      assignDropdownEmptyMessage({
        filteredCount: filteredAssignableContractors.length,
        eligibleTotal: assignableContractors.length,
        filterStats: assignableClientFilterStats,
        diagnostics: assignableFilterDiagnostics,
        tradeTypeFilter,
        contractorFilter,
      }),
    [
      filteredAssignableContractors.length,
      assignableContractors.length,
      assignableClientFilterStats,
      assignableFilterDiagnostics,
      tradeTypeFilter,
      contractorFilter,
    ]
  );

  const excludedContractorGroups = useMemo(
    () => groupedExclusionSamples(assignableExclusionSamples),
    [assignableExclusionSamples]
  );

  const serverEligibleCount = assignableFilterDiagnostics?.eligible ?? assignableContractors.length;

  const earlyNetworkMode = useMemo(
    () =>
      isEarlyNetworkMode({
        diagnostics: assignableFilterDiagnostics,
        eligibleCount: serverEligibleCount,
      }),
    [assignableFilterDiagnostics, serverEligibleCount]
  );

  const coverageLevel = useMemo(
    () => networkCoverageLevel(assignableFilterDiagnostics),
    [assignableFilterDiagnostics]
  );

  const assignedContractorDisplay = useMemo(() => {
    const named = String(job?.contractor_name || '').trim();
    if (named) return named;
    const cid = String(job?.contractor_id || '').trim();
    if (!cid) return '';
    const match = (assignableContractors || []).find(
      (c) => String(c.contractor_id || c.id || '') === cid,
    );
    if (!match) return '';
    return String(match.company_name || match.name || '').trim();
  }, [job?.contractor_name, job?.contractor_id, assignableContractors]);

  const earlyNetworkSupport = useMemo(
    () =>
      earlyNetworkSupportText({
        jobJurisdiction: assignableJobJurisdiction,
        propertyPostcode: assignablePropertyPostcode,
      }),
    [assignableJobJurisdiction, assignablePropertyPostcode]
  );

  const handleRecoveryAction = (action) => {
    if (!action) return;
    if (action.action === 'focus_add_form') {
      setShowAddContractorForm(true);
      return;
    }
    if (action.href && typeof window !== 'undefined') {
      window.open(action.href, '_self');
    }
  };

  const openEvidenceFile = async (key) => {
    if (!jobId || !key || key.startsWith('document:')) return;
    try {
      const res = await clientAPI.getMaintenanceWorkOrderContractorEvidenceFile(jobId, key, false);
      openBlobApiResponse(res, { download: false, fallbackFilename: contractorEvidenceFilenameFromKey(key) });
    } catch (e) {
      toast.error(parseApiError(e, 'Could not open file'));
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="w-10 h-10 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Button variant="ghost" className="mb-4" onClick={() => navigate(-1)}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Alert variant="destructive">
          <AlertDescription>{error || 'Job not found'}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const isCompliance = (job.work_order_kind || '').toUpperCase() === 'COMPLIANCE';
  const na = job.next_actions || [];
  const certificateLinked = (job.evidence_keys || []).some((k) => String(k).startsWith('document:'));

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" variant="ghost" size="sm" onClick={() => navigate(resolveClientPortalPath('/operations/work-orders', '/operations/work-orders'))}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            All jobs
          </Button>
          <Badge variant="outline">{kindLabel}</Badge>
          {job.jurisdiction ? (
            <Badge variant="outline" title="Portfolio jurisdiction for this job">
              {job.jurisdiction}
            </Badge>
          ) : null}
          <Badge>{currentUpdate.headline}</Badge>
          {job.operational_exception ? (
            <Badge variant="secondary">Hold: {operationalExceptionLabel(job.operational_exception)}</Badge>
          ) : null}
        </div>
        <div>
          <p className="text-xs font-mono text-gray-500">{job.work_order_id}</p>
          <h1 className="text-lg font-semibold text-midnight-blue leading-snug">{job.description || 'Job'}</h1>
          <p className="text-sm text-gray-600 mt-2 max-w-prose">{JOB_DETAIL_CONFIDENCE_LINE}</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-gray-600">
          {job.property_id ? (
            <p>
              Property:{' '}
              <Link to={resolvePropertyPath(job.property_id)} className="text-electric-teal hover:underline">
                {job.property_id}
              </Link>
            </p>
          ) : null}
          {isCompliance && job.linked_property_requirement_id ? (
            <p>
              Requirement:{' '}
              <Link
                to={resolveClientPortalPath(`/requirements?view_requirement=${encodeURIComponent(job.linked_property_requirement_id)}`, '/requirements')}
                className="text-electric-teal hover:underline"
              >
                View requirement
              </Link>
            </p>
          ) : null}
          {job.issue_id ? (
            <p>
              Issue:{' '}
              <Link to={`/operations/issues/${job.issue_id}`} className="text-electric-teal hover:underline">
                Open issue
              </Link>
            </p>
          ) : null}
          {job.requirement_code ? <p>Code: {job.requirement_code}</p> : null}
          {job.resolution_outcome ? (
            <p className="sm:col-span-2 text-gray-700">
              Outcome:{' '}
              <span className="font-medium">{operationalLabelForToken(job.resolution_outcome, { emptyLabel: '—' })}</span>
            </p>
          ) : null}
          {job.issue_resolution_hint ? <p className="sm:col-span-2 text-gray-600">{job.issue_resolution_hint}</p> : null}
        </div>
      </header>

      {isAssignContractorEntitlementBlocked(job, canUseOpsContractors) ? (
        <Alert className="mb-6 border-slate-200 bg-slate-50 text-slate-900">
          <AlertDescription className="text-sm space-y-2">
            <p className="font-semibold text-midnight-blue">Contractor assignment is included on Professional</p>
            <p className="text-slate-700">
              Your plan includes maintenance jobs, but assigning contractors from the portal requires the contractor network
              on the Professional plan. Use the locked action above to view upgrade options or contact support.
            </p>
            <Link to={resolveClientPortalPath('/help', '/help')} className="text-electric-teal hover:underline text-sm font-medium inline-flex items-center gap-1">
              <LifeBuoy className="w-3.5 h-3.5" />
              Contact support
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      <NextActionHero
        entity={job}
        primaryLocked={Boolean(heroExecution?.lockedUpsell)}
        primaryDisabled={heroExecution ? !heroExecution.executable && !heroExecution.lockedUpsell : false}
        onPrimaryClick={() => {
          if (heroExecution?.lockedUpsell) {
            openContractorNetworkLocked();
            return;
          }
          if (!heroExecution?.executable) {
            if (heroExecution?.blockedMessage) toast.message(heroExecution.blockedMessage);
            return;
          }
          executeJobDetailPrimaryIntent(heroExecution.intent, {
            job,
            openAssignModal,
            scrollToVisit: () =>
              visitSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
            navigate: (url) => navigate(url),
          });
        }}
      />

      {(() => {
        const banner = exceptionStateBanner(job);
        if (!banner) return null;
        return (
          <Alert className="border-amber-200 bg-amber-50/90 text-amber-950">
            <AlertDescription className="space-y-1 text-sm">
              <p className="font-semibold text-amber-950">{banner.label}</p>
              <p className="text-amber-900/90">{banner.explanation}</p>
              {banner.recovery ? <p className="text-amber-950 font-medium pt-1">{banner.recovery}</p> : null}
            </AlertDescription>
          </Alert>
        );
      })()}

      {job.pricing?.pricing_workflow &&
      String(job.pricing.pricing_mode || '').toUpperCase() === 'MAINTENANCE_INSPECTION_REQUIRED' ? (
        <Alert className="border-sky-200 bg-sky-50/90 text-sky-950">
          <AlertDescription className="text-sm space-y-1">
            <p className="font-semibold text-sky-950">Inspection before final price</p>
            <p className="text-sky-900/90">
              Your contractor can attend for an inspection visit before you approve a repair quote. Repair work itself should not
              proceed until you have approved their quoted price in Pleerity — then they can schedule completion and invoice up to
              that agreed amount.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      {job.pricing?.pricing_workflow &&
      String(job.work_order_kind || '').toUpperCase() === 'COMPLIANCE' &&
      String(job.pricing.pricing_mode || '').toUpperCase() === 'COMPLIANCE_FIXED_QUOTE' ? (
        <Alert className="border-slate-200 bg-slate-50 text-slate-900">
          <AlertDescription className="text-sm">
            <span className="font-semibold">Quote approval required: </span>
            The contractor must submit a price for your approval before work is marked in progress or invoiced.
          </AlertDescription>
        </Alert>
      ) : null}

      <SectionCard title="Current update" icon={Wrench}>
        <p className="text-sm font-medium text-midnight-blue">{currentUpdate.headline}</p>
        {currentUpdate.lines?.length ? (
          <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
            {currentUpdate.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        ) : null}
        <p className="text-xs text-gray-600 pt-1">
          Details for booking, field work, and proof live in the sections below — this line is your oversight snapshot only.
        </p>
        {heroOversightAction ? (
          <div className="pt-3 border-t border-gray-100">
            <Button
              type="button"
              size="sm"
              className="bg-midnight-blue hover:bg-midnight-blue/90"
              onClick={() => visitSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              {heroOversightAction.label}
            </Button>
          </div>
        ) : null}
        <div className="pt-3 border-t border-gray-100 flex flex-wrap gap-x-4 gap-y-2 text-xs">
          {canUseOpsApprovals ? (
            <Link to={resolveClientPortalPath('/operations/approvals', '/operations/approvals')} className="text-electric-teal hover:underline inline-flex items-center gap-1 font-medium">
              Review invoice
            </Link>
          ) : null}
          <Link to={resolveClientPortalPath('/help', '/help')} className="text-electric-teal hover:underline inline-flex items-center gap-1 font-medium">
            <LifeBuoy className="w-3.5 h-3.5" />
            Contact support
          </Link>
        </div>
      </SectionCard>

      <SectionCard title="Progress" icon={ListChecks}>
        <div className="flex flex-wrap items-center gap-1 text-[10px] sm:text-xs">
          {clientProgress.steps.map((label, idx) => {
            const cancelled = clientProgress.currentIndex < 0;
            const active = !cancelled && clientProgress.currentIndex === idx;
            const done = !cancelled && clientProgress.currentIndex > idx;
            return (
              <span key={label} className="flex items-center gap-1">
                {idx > 0 ? <span className="text-gray-300">→</span> : null}
                <span
                  className={`px-2 py-1 rounded font-medium ${
                    cancelled
                      ? 'bg-gray-100 text-gray-400'
                      : active
                        ? 'bg-electric-teal text-white'
                        : done
                          ? 'bg-emerald-100 text-emerald-900'
                          : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {label}
                </span>
              </span>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="Contractor" icon={User}>
        <p className="text-xs text-gray-600">
          Use an assigned contractor before requesting a booking. Add new contractors only from this job — not from requirement
          cards or Today.
        </p>
        {job.contractor_id ? (
          <div className="text-sm space-y-1">
            <p>
              Assigned contractor:{' '}
              <span className="font-medium text-midnight-blue">
                {assignedContractorDisplay || 'Name unavailable'}
              </span>
            </p>
            <p className="text-xs text-gray-500">
              Reference ID: <span className="font-mono">{job.contractor_id}</span>
            </p>
          </div>
        ) : (
          <p className="text-sm text-amber-800">No contractor assigned yet.</p>
        )}
        {isAssignContractorEntitlementBlocked(job, canUseOpsContractors) ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-2 border-slate-300"
            data-testid="open-assign-contractor-locked"
            onClick={openContractorNetworkLocked}
          >
            Assign contractor
            <Lock className="w-3.5 h-3.5 ml-2 shrink-0" aria-hidden />
          </Button>
        ) : canExecuteAssignContractor(job, canWriteOpsContractors) ? (
          <Button
            type="button"
            size="sm"
            className="mt-2 bg-midnight-blue hover:bg-midnight-blue/90"
            data-testid="open-assign-contractor-modal"
            onClick={() => {
              if (!canUseOpsContractors) {
                openContractorNetworkLocked();
                return;
              }
              handleAssignContractorClick(job, canWriteOpsContractors, openAssignModal, {
                onLocked: openContractorNetworkLocked,
              });
            }}
          >
            Assign contractor
          </Button>
        ) : null}
      </SectionCard>

      <div ref={visitSectionRef} id="client-job-visit" className="scroll-mt-24">
        <SectionCard title="Visit" icon={Calendar}>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <dt className="text-gray-500">Schedule status</dt>
          <dd>{job.scheduling?.visit_status_label || job.schedule_status || '—'}</dd>
          {job.scheduling?.workflow_mode_label ? (
            <>
              <dt className="text-gray-500">Workflow mode</dt>
              <dd>{job.scheduling.workflow_mode_label}</dd>
            </>
          ) : null}
          <dt className="text-gray-500">Proposed / confirmed at</dt>
          <dd>{formatWhen(job.scheduled_at)}</dd>
          <dt className="text-gray-500">Timezone</dt>
          <dd>{job.scheduled_timezone || '—'}</dd>
        </dl>
        {(job.scheduling?.visit_negotiation_history || []).length > 0 ? (
          <div className="mt-2 border-t border-gray-100 pt-2 text-xs">
            <p className="font-semibold text-gray-700 mb-1">Visit history</p>
            <ul className="space-y-1 text-gray-600">
              {(job.scheduling.visit_negotiation_history || []).map((row, idx) => (
                <li key={`${row.at}-${row.event}-${idx}`}>
                  {String(row.event || '').replace(/_/g, ' ')}
                  {row.scheduled_at ? ` · ${formatWhen(row.scheduled_at)}` : ''}
                  {row.at ? ` · ${formatWhen(row.at)}` : ''}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {nextBySection.scheduling.length > 0 ? (
          <div className="space-y-2 border-t border-gray-100 pt-3">
            {na.some((a) => scheduleTimeActions.includes(a.id)) ? (
              <>
                <p className="text-xs text-gray-600">
                  Booking happens on this job after assignment: pick a slot, confirm when agreed, then continue with execution.
                </p>
                <label className="block text-xs text-gray-600">Visit date and time (local)</label>
                <input
                  type="datetime-local"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={scheduleForm.datetimeLocal}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, datetimeLocal: e.target.value }))}
                />
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  placeholder="IANA timezone"
                  value={scheduleForm.timezone}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, timezone: e.target.value }))}
                />
                <textarea
                  className="w-full border rounded-lg px-3 py-2 text-sm min-h-[60px]"
                  placeholder="Notes (optional)"
                  value={scheduleForm.notes}
                  onChange={(e) => setScheduleForm((f) => ({ ...f, notes: e.target.value }))}
                />
                <Button
                  type="button"
                  size="sm"
                  disabled={!!actionBusy}
                  onClick={() => {
                    const id = na.some((a) => a.id === 'reschedule_booking')
                      ? 'reschedule_booking'
                      : na.some((a) => a.id === 'request_booking')
                        ? 'request_booking'
                        : 'propose_schedule';
                    handleLifecycleClick(id);
                  }}
                >
                  {['request_booking', 'propose_schedule', 'reschedule_booking'].includes(actionBusy) ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : na.some((a) => a.id === 'reschedule_booking') ? (
                    'Propose new visit time'
                  ) : na.some((a) => a.id === 'request_booking') ? (
                    'Request booking'
                  ) : (
                    'Propose visit'
                  )}
                </Button>
              </>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {na.some((a) => a.id === 'confirm_visit') ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={!!actionBusy}
                  onClick={() => handleLifecycleClick('confirm_visit')}
                >
                  {actionBusy === 'confirm_visit' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Confirm visit'}
                </Button>
              ) : null}
              {na.some((a) => a.id === 'request_visit_reschedule') ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!!actionBusy}
                  onClick={() => handleLifecycleClick('request_visit_reschedule')}
                >
                  {actionBusy === 'request_visit_reschedule' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Request another date'
                  )}
                </Button>
              ) : null}
              {na.some((a) => a.id === 'cancel_booking') ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!!actionBusy}
                  onClick={() => handleLifecycleClick('cancel_booking')}
                >
                  {actionBusy === 'cancel_booking' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Cancel booking'}
                </Button>
              ) : null}
              {na.some((a) => a.id === 'mark_no_access') ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!!actionBusy}
                  onClick={() => handleLifecycleClick('mark_no_access')}
                >
                  {actionBusy === 'mark_no_access' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Mark no access'}
                </Button>
              ) : null}
              {na.some((a) => a.id === 'mark_reschedule_required') ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!!actionBusy}
                  onClick={() => handleLifecycleClick('mark_reschedule_required')}
                >
                  {actionBusy === 'mark_reschedule_required' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Mark reschedule required'
                  )}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
        </SectionCard>
      </div>

      <SectionCard title="During / after the visit" icon={ClipboardList}>
        <div className="flex flex-wrap gap-2">
          {na.some((a) => a.id === 'start') ? (
            <Button type="button" size="sm" disabled={!!actionBusy} onClick={() => handleLifecycleClick('start')}>
              {actionBusy === 'start' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Mark in progress'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'awaiting_parts') ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('awaiting_parts')}
            >
              {actionBusy === 'awaiting_parts' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Mark awaiting parts'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'complete') ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('complete')}
            >
              {actionBusy === 'complete' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Mark work complete'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'verify') ? (
            <Button
              type="button"
              size="sm"
              className="bg-teal-700 hover:bg-teal-800"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('verify')}
            >
              {actionBusy === 'verify' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify & close'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'close_job') ? (
            <Button
              type="button"
              size="sm"
              className="bg-teal-700 hover:bg-teal-800"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('close_job')}
            >
              {actionBusy === 'close_job' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Close job'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'accept_completion') ? (
            <Button
              type="button"
              size="sm"
              className="bg-teal-700 hover:bg-teal-800"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('accept_completion')}
            >
              {actionBusy === 'accept_completion' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Accept completion'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'request_proof_clarification') ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('request_proof_clarification')}
            >
              {actionBusy === 'request_proof_clarification' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                'Request clarification'
              )}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'reject_completion') ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="text-red-700 border-red-200 hover:bg-red-50"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('reject_completion')}
            >
              {actionBusy === 'reject_completion' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Reject completion'}
            </Button>
          ) : null}
          {na.some((a) => a.id === 'resume_after_parts') ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!!actionBusy}
              onClick={() => handleLifecycleClick('resume_after_parts')}
            >
              {actionBusy === 'resume_after_parts' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Resume after parts'}
            </Button>
          ) : null}
        </div>
        {(na.some((a) => a.id === 'set_operational_exception') || na.some((a) => a.id === 'clear_operational_exception')) && (
          <div className="border border-gray-100 rounded-lg p-3 space-y-2 mt-3">
            <p className="text-xs font-medium text-gray-700">Operational hold (no access / reschedule / follow-up)</p>
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={exceptionChoice}
              onChange={(e) => setExceptionChoice(e.target.value)}
            >
              <option value="">Clear hold</option>
              <option value="NO_ACCESS">No access</option>
              <option value="RESCHEDULE_REQUIRED">Reschedule required</option>
              <option value="FOLLOW_UP_REQUIRED">Follow-up required</option>
            </select>
            <Button type="button" size="sm" variant="outline" disabled={!!actionBusy} onClick={handleSetException}>
              {actionBusy === 'op_ex' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Apply hold / clear'}
            </Button>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Proof / outcome" icon={FileText}>
        {!isCompliance ? (
          <p className="text-xs text-gray-600">Link vault documents when the visit or repair is complete.</p>
        ) : (
          <p className="text-xs text-gray-600">Attach the compliance certificate from your vault before verification.</p>
        )}
        {isCompliance ? (
          <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3 space-y-1 text-xs text-gray-800">
            <p className="font-semibold text-midnight-blue">Compliance status</p>
            <p>
              Certificate uploaded:{' '}
              <span className="font-medium">{certificateLinked ? 'Yes' : 'Not yet'}</span>
            </p>
            {job.compliance_proof_status != null && String(job.compliance_proof_status).trim() !== '' ? (
              <p>
                Validation:{' '}
                <span className="font-medium">{operationalLabelForToken(job.compliance_proof_status, { emptyLabel: '—' })}</span>
              </p>
            ) : (
              <p className="text-gray-600">Validation: pending or not yet recorded for this job.</p>
            )}
            <p className="text-gray-600">
              Requirement compliance is tracked on the requirement record —{' '}
              {job.linked_property_requirement_id ? (
                <Link
                  to={resolveClientPortalPath(`/requirements?view_requirement=${encodeURIComponent(job.linked_property_requirement_id)}`, '/requirements')}
                  className="text-electric-teal hover:underline font-medium"
                >
                  open requirement
                </Link>
              ) : (
                'link this job to a requirement where applicable.'
              )}
            </p>
          </div>
        ) : null}
        <ul className="space-y-1 text-xs font-mono break-all">
          {(job.evidence_keys || []).length === 0 ? <li className="text-gray-500">No linked documents yet.</li> : null}
          {(job.evidence_keys || []).map((k) => (
            <li key={k} className="flex flex-wrap items-center gap-2">
              <span>{k.startsWith('document:') ? `Document ${k.replace('document:', '')}` : k}</span>
              {!k.startsWith('document:') && isContractorFileEvidenceKey(k) ? (
                <button type="button" className="text-electric-teal hover:underline text-xs" onClick={() => openEvidenceFile(k)}>
                  Open
                </button>
              ) : null}
            </li>
          ))}
        </ul>
        {isCompliance && canUseOpsComplianceReview && na.some((a) => a.id === 'link_document') ? (
          <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-gray-100">
            <input
              className="flex-1 border rounded-lg px-3 py-2 text-sm"
              placeholder="Document ID to link"
              value={linkDocId}
              onChange={(e) => setLinkDocId(e.target.value)}
            />
            <Button type="button" size="sm" disabled={!!actionBusy} onClick={() => handleLifecycleClick('link_document')}>
              {actionBusy === 'link_document' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Link document'}
            </Button>
          </div>
        ) : null}
        {!isCompliance && na.some((a) => a.id === 'attach_completion_proof') ? (
          <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-gray-100">
            <input
              className="flex-1 border rounded-lg px-3 py-2 text-sm"
              placeholder="Document ID from vault"
              value={linkDocId}
              onChange={(e) => setLinkDocId(e.target.value)}
            />
            <Button type="button" size="sm" disabled={!!actionBusy} onClick={() => handleLifecycleClick('attach_completion_proof')}>
              {actionBusy === 'attach_completion_proof' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Attach proof'}
            </Button>
          </div>
        ) : null}
        <Link to={resolveClientPortalPath('/documents', '/documents')} className="text-xs text-electric-teal hover:underline inline-block mt-2">
          Open documents vault
        </Link>
      </SectionCard>

      {canUseOpsApprovals ? (
        <SectionCard title="Billing / approvals" icon={Receipt}>
          {job.pricing?.pricing_workflow ? (
            <div className="rounded-lg border border-gray-100 bg-gray-50/80 p-3 text-xs text-gray-800 space-y-1 mb-3">
              <p className="font-semibold text-midnight-blue">Quote status</p>
              <p>
                <span className="text-gray-500">Status:</span>{' '}
                <span className="font-medium">{operationalLabelForToken(job.pricing.price_status, { emptyLabel: '—' })}</span>
              </p>
              {job.pricing.quoted_price != null && job.pricing.quoted_price !== '' ? (
                <p>
                  <span className="text-gray-500">Quoted:</span>{' '}
                  <span className="font-medium">
                    £{Number(job.pricing.quoted_price).toFixed(2)} {job.pricing.price_currency || 'GBP'}
                  </span>
                </p>
              ) : null}
              {job.pricing.quote_notes ? (
                <p className="text-gray-700 whitespace-pre-wrap break-words">Contractor notes: {job.pricing.quote_notes}</p>
              ) : null}
              {job.pricing.revision_active || job.pricing.quote_revision_reason_code ? (
                <div className="mt-2 rounded border border-amber-200 bg-amber-50/90 p-2 text-amber-950">
                  <p className="font-semibold">Changes requested</p>
                  {job.pricing.quote_revision_reason_code ? (
                    <p>
                      Reason:{' '}
                      {QUOTE_REVISION_REASONS.find((r) => r.code === job.pricing.quote_revision_reason_code)?.label ||
                        job.pricing.quote_revision_reason_code}
                    </p>
                  ) : null}
                  {job.pricing.quote_revision_message ? (
                    <p className="whitespace-pre-wrap break-words">{job.pricing.quote_revision_message}</p>
                  ) : null}
                  {job.pricing.quote_revision_target_budget != null ? (
                    <p>Target budget: £{Number(job.pricing.quote_revision_target_budget).toFixed(2)}</p>
                  ) : null}
                </div>
              ) : null}
              {(job.pricing.quote_negotiation_history || []).length > 0 ? (
                <div className="mt-2 border-t border-gray-200 pt-2">
                  <p className="font-semibold text-gray-700 mb-1">Quote history</p>
                  <ul className="space-y-1">
                    {(job.pricing.quote_negotiation_history || []).map((row, idx) => (
                      <li key={`${row.at}-${row.event}-${idx}`} className="text-gray-600">
                        v{row.version || '—'} · {String(row.event || '').replace(/_/g, ' ')}
                        {row.amount != null ? ` · £${Number(row.amount).toFixed(2)}` : ''}
                        {row.at ? ` · ${formatWhen(row.at)}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2 mb-3">
            {na.some((a) => a.id === 'approve_quote') ? (
              <Button
                type="button"
                size="sm"
                className="bg-teal-700 hover:bg-teal-800"
                disabled={!!actionBusy}
                onClick={() => handleLifecycleClick('approve_quote')}
              >
                {actionBusy === 'approve_quote' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Approve and authorise work'}
              </Button>
            ) : null}
            {na.some((a) => a.id === 'request_quote_revision') ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!!actionBusy}
                onClick={() => handleLifecycleClick('request_quote_revision')}
              >
                Request changes
              </Button>
            ) : null}
            {na.some((a) => a.id === 'reject_quote_final') ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="text-red-700 border-red-200 hover:bg-red-50"
                disabled={!!actionBusy}
                onClick={() => handleLifecycleClick('reject_quote_final')}
              >
                Decline quote (final)
              </Button>
            ) : null}
          </div>
          <p className="text-xs text-gray-600 mb-2">
            Requesting quote changes does not cancel the job or remove the contractor. To assign a different contractor or close
            without proceeding, use Assign contractor or Cancel job below.
          </p>
          <p className="text-sm text-gray-700">
            When your contractor submits an invoice for this job, it appears under Approvals for review (approve, reject, or
            request more information). Your team reference on the invoice is the Pleerity invoice number where one has been issued.
          </p>
          <div className="mt-2 rounded-lg border border-sky-200 bg-sky-50/80 p-3 text-xs text-sky-900">
            <p className="font-medium mb-1">Payment responsibility</p>
            <p>
              You pay the contractor directly for the agreed or final amount. Pleerity records completion and payment status
              where supported; it does not process contractor payouts or send funds to the contractor.
            </p>
          </div>
          <Button size="sm" variant="secondary" className="mt-2" asChild>
            <Link to={resolveClientPortalPath('/operations/approvals', '/operations/approvals')}>Open Approvals</Link>
          </Button>
        </SectionCard>
      ) : null}

      <SectionCard title="Timeline" icon={History}>
        {(job.timeline_events || []).length > 0 ? (
          <ul className="text-xs text-gray-600 space-y-1">
            {job.timeline_events.map((ev, idx) => (
              <li key={`${ev.label}-${ev.at}-${idx}`}>
                <span className="font-medium text-gray-700">{ev.label}:</span> {formatWhen(ev.at)}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="text-xs text-gray-600 space-y-1">
            <li>Created: {formatWhen(job.created_at)}</li>
            <li>Updated: {formatWhen(job.updated_at)}</li>
            <li>Completed: {formatWhen(job.completed_at)}</li>
          </ul>
        )}
      </SectionCard>

      <SectionCard title="Decision log" icon={MessageSquareText}>
        <p className="text-xs text-gray-600 mb-3">
          Short notes on what was decided or agreed (no chat thread). Visible on this job for your team.
        </p>
        {(job.decision_log || []).length > 0 ? (
          <ul className="space-y-3 mb-4 text-sm border border-gray-100 rounded-lg p-3 bg-gray-50/50">
            {job.decision_log.map((row, idx) => (
              <li key={`${row.timestamp}-${idx}`} className="border-b border-gray-100 last:border-0 last:pb-0 pb-3">
                <p className="text-gray-900 whitespace-pre-wrap break-words">{row.message}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {String(row.actor || 'unknown').replace(/^./, (c) => c.toUpperCase())} · {formatWhen(row.timestamp)}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-gray-500 mb-3">No entries yet.</p>
        )}
        <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
          <textarea
            className="flex-1 min-h-[72px] border rounded-lg px-3 py-2 text-sm"
            placeholder="Add a decision or note…"
            value={decisionNote}
            maxLength={2000}
            onChange={(e) => setDecisionNote(e.target.value)}
            disabled={decisionSubmitting}
          />
          <Button
            type="button"
            size="sm"
            className="shrink-0 bg-midnight-blue hover:bg-midnight-blue/90"
            disabled={decisionSubmitting || !decisionNote.trim()}
            onClick={async () => {
              if (!jobId || !decisionNote.trim()) return;
              setDecisionSubmitting(true);
              try {
                const res = await clientAPI.postJobDecisionLog(jobId, { message: decisionNote.trim() });
                if (res.data && typeof res.data === 'object' && (res.data.job_id || res.data.work_order_id)) {
                  setJob(res.data);
                } else {
                  await load();
                }
                setDecisionNote('');
                toast.success(
                  'Decision note saved. It appears on the job timeline so coordinators see why the job moved.',
                );
              } catch (err) {
                toast.error(parseApiError(err, 'Could not save note'));
              } finally {
                setDecisionSubmitting(false);
              }
            }}
          >
            {decisionSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add entry'}
          </Button>
        </div>
      </SectionCard>

      <SectionCard title="Support / notes" icon={LifeBuoy}>
        <p className="text-sm text-gray-700">
          If something looks wrong or you need help coordinating this job, reach your usual support channel or open Help in the
          app.
        </p>
        <Link to={resolveClientPortalPath('/help', '/help')} className="text-sm text-electric-teal hover:underline inline-block mt-2 font-medium">
          Open Help
        </Link>
      </SectionCard>

      {showCancelJob ? (
        <SectionCard title="Job options" icon={ClipboardList}>
          <p className="text-xs text-gray-600 mb-2">
            {cancelJobAction?.hint ||
              'Stop the whole job. This is separate from cancelling a visit booking.'}
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-red-200 text-red-800 hover:bg-red-50"
            disabled={!!actionBusy}
            data-testid="cancel-job-lifecycle"
            onClick={() => handleLifecycleClick('cancel')}
          >
            {actionBusy === 'cancel' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              cancelJobAction?.label || 'Cancel job'
            )}
          </Button>
        </SectionCard>
      ) : null}

      <Dialog
        open={quoteRevisionOpen}
        onOpenChange={(open) => {
          setQuoteRevisionOpen(open);
          if (!open) {
            setQuoteRevisionMessage('');
            setQuoteRevisionTargetBudget('');
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Request quote changes</DialogTitle>
            <DialogDescription>
              The contractor stays assigned and can submit a revised quote. This does not cancel the job or reject the contractor.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Reason</span>
              <select
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                value={quoteRevisionReasonCode}
                onChange={(e) => setQuoteRevisionReasonCode(e.target.value)}
              >
                {QUOTE_REVISION_REASONS.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <textarea
              className="w-full border rounded-lg px-3 py-2 text-sm min-h-[72px]"
              placeholder="Message to contractor (optional)"
              value={quoteRevisionMessage}
              onChange={(e) => setQuoteRevisionMessage(e.target.value)}
            />
            <label className="block text-sm">
              <span className="text-gray-700 font-medium">Target budget (optional)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="e.g. 250"
                value={quoteRevisionTargetBudget}
                onChange={(e) => setQuoteRevisionTargetBudget(e.target.value)}
              />
            </label>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button type="button" variant="outline" onClick={() => setQuoteRevisionOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!!actionBusy}
              onClick={async () => {
                setActionBusy('request_quote_revision');
                try {
                  const body = {
                    reason_code: quoteRevisionReasonCode,
                    message: quoteRevisionMessage.trim() || undefined,
                  };
                  const tb = parseFloat(String(quoteRevisionTargetBudget).replace(/,/g, ''));
                  if (!Number.isNaN(tb) && tb > 0) body.target_budget = tb;
                  const r = await clientAPI.complianceJobRequestQuoteRevision(jobId, body);
                  if (r.data && typeof r.data === 'object' && (r.data.job_id || r.data.work_order_id)) setJob(r.data);
                  else await load();
                  setQuoteRevisionOpen(false);
                  setQuoteRevisionMessage('');
                  setQuoteRevisionTargetBudget('');
                  toast.success(
                    'Changes requested — the contractor can submit a revised quote. The job and assignment remain active.',
                  );
                } catch (err) {
                  toast.error(parseApiError(err, 'Could not request quote changes'));
                } finally {
                  setActionBusy(null);
                }
              }}
            >
              {actionBusy === 'request_quote_revision' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Request changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={quoteRejectFinalOpen}
        onOpenChange={(open) => {
          setQuoteRejectFinalOpen(open);
          if (!open) setQuoteRejectFinalReason('');
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Decline quote (final)?</DialogTitle>
            <DialogDescription>
              Marks this quote as finally declined. The job stays open — reassign a contractor or cancel the job separately if needed.
            </DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full border rounded-lg px-3 py-2 text-sm min-h-[72px]"
            placeholder="Reason (optional)"
            value={quoteRejectFinalReason}
            onChange={(e) => setQuoteRejectFinalReason(e.target.value)}
          />
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button type="button" variant="outline" onClick={() => setQuoteRejectFinalOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={!!actionBusy}
              onClick={async () => {
                setActionBusy('reject_quote_final');
                try {
                  const r = await clientAPI.complianceJobRejectQuoteFinal(jobId, {
                    reason: quoteRejectFinalReason.trim() || undefined,
                  });
                  if (r.data && typeof r.data === 'object' && (r.data.job_id || r.data.work_order_id)) setJob(r.data);
                  else await load();
                  setQuoteRejectFinalOpen(false);
                  setQuoteRejectFinalReason('');
                  toast.success('Quote declined (final). Reassign or close the job if you will not proceed with this contractor.');
                } catch (err) {
                  toast.error(parseApiError(err, 'Could not decline quote'));
                } finally {
                  setActionBusy(null);
                }
              }}
            >
              {actionBusy === 'reject_quote_final' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Decline quote (final)'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={bookingGuardOpen} onOpenChange={setBookingGuardOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Assign a contractor first</DialogTitle>
            <DialogDescription>
              A contractor must be assigned before booking can be requested.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              type="button"
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => {
                setBookingGuardOpen(false);
                if (!canUseOpsContractors) {
                  openContractorNetworkLocked();
                  return;
                }
                if (!canWriteOpsContractors) return;
                openAssignModal();
              }}
            >
              Assign contractor
            </Button>
            <Button
              type="button"
              className="w-full sm:w-auto bg-midnight-blue hover:bg-midnight-blue/90"
              onClick={() => {
                setBookingGuardOpen(false);
                if (!canUseOpsContractors) {
                  openContractorNetworkLocked();
                  return;
                }
                if (!canWriteOpsContractors) return;
                openAssignModal({ focusAdd: true });
              }}
            >
              Add and assign contractor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={assignModalOpen}
        onOpenChange={(open) => {
          setAssignModalOpen(open);
          if (!open) {
            setShowAddContractorForm(false);
            setAllowCreateDespiteDuplicates(false);
            setAssignableFilterDiagnostics(null);
            setAssignableRecoveryGuidance(null);
            setAssignableExclusionSamples(null);
            setShowExcludedContractors(false);
            setShowEligibilityDiagnostics(false);
            setAssignablePropertyPostcode(null);
            setAssignModalError('');
          } else {
            setAssignModalError('');
          }
        }}
      >
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Assign contractor</DialogTitle>
            <DialogDescription>
              Match contractors to this job by trade and coverage, or add someone new for this property area.
            </DialogDescription>
          </DialogHeader>
          <div
            ref={assignModalBodyRef}
            className="space-y-3 text-sm"
            data-testid="assign-contractor-modal"
            data-early-network-mode={earlyNetworkMode ? 'true' : 'false'}
            data-coverage-level={coverageLevel}
          >
            {!assignableLoading && serverEligibleCount === 0 ? (
              <Alert className="border-slate-200 bg-slate-50 text-slate-800 py-2" data-testid="assign-contractor-network-banner">
                <AlertDescription className="text-xs leading-relaxed">{NETWORK_MATURITY_BANNER}</AlertDescription>
              </Alert>
            ) : (
              <Alert className="border-teal-200 bg-teal-50/80 text-teal-950 py-2">
                <AlertDescription className="text-xs">
                  When you assign a contractor, they will receive an email. They must activate their contractor portal
                  before they can view the job, submit a quote, or update progress.
                </AlertDescription>
              </Alert>
            )}
            {assignSelectedNeedsActivation ? (
              <Alert className="border-amber-200 bg-amber-50/90 text-amber-950 py-2">
                <AlertDescription className="text-xs">
                  Portal activation required before this contractor can respond to the assignment.
                </AlertDescription>
              </Alert>
            ) : null}
            {assignModalError ? (
              <Alert className="border-red-200 bg-red-50 text-red-900 py-2" data-testid="assign-contractor-error">
                <AlertDescription className="text-sm leading-relaxed">{assignModalError}</AlertDescription>
              </Alert>
            ) : null}
            {!assignableLoading && serverEligibleCount === 0 ? (
              <div
                className="rounded-lg border-2 border-teal-600 bg-teal-50/90 px-4 py-3 space-y-2"
                data-testid="assign-contractor-primary-cta"
              >
                <p className="text-sm text-gray-800">{earlyNetworkSupport}</p>
                <Button
                  ref={earlyNetworkCtaRef}
                  type="button"
                  className="w-full bg-midnight-blue hover:bg-midnight-blue/90"
                  onClick={() => setShowAddContractorForm(true)}
                >
                  {EARLY_NETWORK_PRIMARY_CTA}
                </Button>
                <p className="text-xs text-gray-600">{EARLY_NETWORK_GUIDANCE}</p>
              </div>
            ) : null}
            {!assignableLoading && serverEligibleCount === 0 && assignableFilterDiagnostics ? (
              <div className="text-xs text-gray-800" data-testid="assign-contractor-eligibility-summary">
                <p>
                  {ELIGIBILITY_EMPTY_SUMMARY}{' '}
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    className="h-auto p-0 text-teal-800 align-baseline"
                    onClick={() => setShowEligibilityDiagnostics((v) => !v)}
                  >
                    {showEligibilityDiagnostics ? 'Hide details' : 'Why?'}
                  </Button>
                </p>
              </div>
            ) : null}
            {!assignableLoading && serverEligibleCount > 0 && assignableFilterDiagnostics ? (
              <p className="text-xs text-teal-900 font-medium">
                {serverEligibleCount} contractor{serverEligibleCount === 1 ? '' : 's'} ready to assign on this job.
              </p>
            ) : null}
            {!assignableLoading && showEligibilityDiagnostics && assignableFilterDiagnostics ? (
              <div
                className="rounded-lg border border-gray-200 bg-gray-50/90 px-3 py-2 text-xs text-gray-800 space-y-1.5"
                data-testid="assign-contractor-funnel"
              >
                <p className="font-semibold text-gray-900">Who can appear on this list</p>
                <ul className="space-y-0.5 list-none">
                  <li>
                    In your contractor directory:{' '}
                    <strong>{assignableFilterDiagnostics.visible_in_directory}</strong>
                  </li>
                  <li className="text-gray-600">
                    Excluded — not assignment-ready (email, vetting, portal activation, status, or marked unavailable):{' '}
                    <strong>{assignableFilterDiagnostics.excluded_not_assignment_ready}</strong>
                  </li>
                  <li className="text-gray-600">
                    Excluded — property / location rules:{' '}
                    <strong>
                      {assignableFilterDiagnostics.excluded_property_scope +
                        assignableFilterDiagnostics.excluded_location_postcode}
                    </strong>{' '}
                    <span className="text-gray-500">
                      (property scope: {assignableFilterDiagnostics.excluded_property_scope}, postcode / coverage:{' '}
                      {assignableFilterDiagnostics.excluded_location_postcode})
                    </span>
                  </li>
                  <li className="text-gray-600">
                    Excluded — job capability (e.g. verified compliance for this requirement):{' '}
                    <strong>{assignableFilterDiagnostics.excluded_execution_capability}</strong>
                  </li>
                  <li className="text-gray-600">
                    Excluded — service region does not include this jurisdiction:{' '}
                    <strong>{assignableFilterDiagnostics.excluded_service_region_jurisdiction}</strong>
                  </li>
                  <li className="text-gray-600">
                    Excluded — maintenance trade vs job category:{' '}
                    <strong>{assignableFilterDiagnostics.excluded_maintenance_trade}</strong>
                  </li>
                  <li className="text-gray-600">
                    Excluded — other client scope:{' '}
                    <strong>{assignableFilterDiagnostics.excluded_wrong_client_scope}</strong>
                  </li>
                  <li>
                    <span className="text-teal-800 font-medium">Ready to assign on this job: </span>
                    <strong>{assignableFilterDiagnostics.eligible}</strong>
                  </li>
                </ul>
                <p className="text-[11px] text-gray-500 border-t border-gray-200 pt-1.5">
                  Each contractor is counted once at the first rule that blocked them. Trade and search filters below
                  can hide additional rows from the dropdown.
                </p>
              </div>
            ) : null}
            {!assignableLoading &&
            showEligibilityDiagnostics &&
            serverEligibleCount === 0 &&
            assignableRecoveryGuidance?.recovery_actions?.length ? (
              <div
                className="rounded-lg border border-teal-100 bg-teal-50/60 px-3 py-2 text-xs space-y-2"
                data-testid="assign-contractor-recovery"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-teal-950">What you can do next</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="text-[11px] h-7"
                    disabled={assignableLoading}
                    onClick={() => loadAssignableContractors()}
                  >
                    Refresh list
                  </Button>
                </div>
                <ul className="space-y-2 list-none">
                  {assignableRecoveryGuidance.recovery_actions.map((action) => (
                    <li key={action.key} className="rounded-md border border-teal-100 bg-white/80 px-2.5 py-2">
                      <p className="font-medium text-gray-900">{action.headline}</p>
                      {action.detail ? <p className="text-gray-600 mt-0.5">{action.detail}</p> : null}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-1.5 text-[11px] h-7"
                        onClick={() => handleRecoveryAction(action)}
                      >
                        {action.cta_label}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {!assignableLoading && showEligibilityDiagnostics && excludedContractorGroups.length > 0 ? (
              <div className="text-xs" data-testid="assign-contractor-excluded-review">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-0 text-teal-800 hover:text-teal-900"
                  onClick={() => setShowExcludedContractors((v) => !v)}
                >
                  {showExcludedContractors ? 'Hide excluded contractors' : 'Review excluded contractors'}
                </Button>
                {showExcludedContractors ? (
                  <div className="mt-1 space-y-2 rounded-lg border border-gray-200 bg-white px-3 py-2">
                    {excludedContractorGroups.map((group) => (
                      <div key={group.reasonKey}>
                        <p className="font-medium text-gray-800">{group.label}</p>
                        <ul className="mt-1 space-y-0.5 text-gray-600 list-disc pl-4">
                          {group.contractors.map((c) => (
                            <li key={c.contractor_id}>
                              {c.name || 'Unnamed contractor'}
                              {c.trade_types?.length ? ` · ${c.trade_types.join(', ')}` : ''}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                    <Link to="/contractors" className="inline-block text-teal-800 underline mt-1">
                      Open contractor directory to update coverage or readiness
                    </Link>
                  </div>
                ) : null}
              </div>
            ) : null}
            {!assignableLoading && serverEligibleCount === 0 ? (
              <div className="border-t border-gray-100 pt-3">
                <p className="text-xs font-semibold text-gray-800 mb-2">{EARLY_NETWORK_SECONDARY_HEADER}</p>
              </div>
            ) : null}
            {(tradeTypeFilter && tradeTypeFilter !== 'all') || (contractorFilter || '').trim() ? (
              <div className="flex flex-wrap gap-2">
                {tradeTypeFilter && tradeTypeFilter !== 'all' ? (
                  <Button type="button" variant="outline" size="sm" className="text-xs h-8" onClick={() => setTradeTypeFilter('all')}>
                    Show all trades
                  </Button>
                ) : null}
                {(contractorFilter || '').trim() ? (
                  <Button type="button" variant="outline" size="sm" className="text-xs h-8" onClick={() => setContractorFilter('')}>
                    Clear search
                  </Button>
                ) : null}
              </div>
            ) : null}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Filter by trade / service</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={tradeTypeFilter}
                onChange={(e) => setTradeTypeFilter(e.target.value)}
              >
                {TRADE_FILTER_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-gray-500 mt-1">Default matches this job; choose &quot;All trades&quot; to widen the list.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Search</label>
              <input
                type="text"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder="Name, company, email, or ID"
                value={contractorFilter}
                onChange={(e) => setContractorFilter(e.target.value)}
              />
            </div>
            {assignableLoading ? (
              <div className="flex justify-center py-6">
                <Loader2 className="w-8 h-8 animate-spin text-electric-teal" />
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Select contractor</label>
                  <select
                    ref={assignContractorSelectRef}
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={assignContractorId}
                    onChange={(e) => setAssignContractorId(e.target.value)}
                    data-testid="assign-contractor-select"
                  >
                    <option value="">Choose…</option>
                    {filteredAssignableContractors.map((c) => (
                      <option key={c.contractor_id} value={c.contractor_id}>
                        {contractorOptionLabel(c)}
                      </option>
                    ))}
                  </select>
                  {!filteredAssignableContractors.length && assignDropdownEmpty ? (
                    <div className="text-xs text-amber-800 mt-1 space-y-1">
                      <p>{assignDropdownEmpty.headline}</p>
                      <p>{assignDropdownEmpty.detail}</p>
                    </div>
                  ) : null}
                </div>
                <Button
                  type="button"
                  size="sm"
                  disabled={!!actionBusy || !assignContractorId.trim() || !filteredAssignableContractors.length}
                  onClick={handleAssign}
                >
                  {actionBusy === 'assign' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Assign selected'}
                </Button>
              </>
            )}
            {serverEligibleCount > 0 || showAddContractorForm ? (
              <div className="border-t border-gray-100 pt-3 space-y-2">
                {serverEligibleCount > 0 ? (
                  <p className="text-xs text-gray-600">No suitable match in the list?</p>
                ) : null}
                <Button
                  type="button"
                  variant={serverEligibleCount > 0 ? 'outline' : 'ghost'}
                  size="sm"
                  className={serverEligibleCount > 0 ? 'w-full' : 'w-full text-teal-800'}
                  onClick={() => setShowAddContractorForm((v) => !v)}
                >
                  {showAddContractorForm ? 'Hide add contractor form' : EARLY_NETWORK_PRIMARY_CTA}
                </Button>
              </div>
            ) : null}
            {showAddContractorForm ? (
              <div className="space-y-2 border border-dashed border-gray-200 rounded-lg p-3 bg-gray-50/80">
                <p className="text-xs text-gray-700 rounded-md border border-teal-100 bg-teal-50/70 px-2.5 py-2">
                  This contractor will receive an email when assigned. They must activate their portal before they can
                  view the job, submit a quote, or update progress.
                </p>
                <label className="block text-xs font-medium text-gray-700">Name *</label>
                <input
                  ref={addContractorNameRef}
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Business or contact name"
                  value={newContractor.company_name}
                  onChange={(e) => setNewContractor((f) => ({ ...f, company_name: e.target.value }))}
                  autoComplete="organization"
                  data-testid="assign-contractor-add-name"
                />
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Trade / service type *</label>
                  <select
                    className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                    value={newContractor.tradeType}
                    onChange={(e) => setNewContractor((f) => ({ ...f, tradeType: e.target.value }))}
                  >
                    {TRADE_SERVICE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Phone (required if no email)"
                  value={newContractor.phone}
                  onChange={(e) => setNewContractor((f) => ({ ...f, phone: e.target.value }))}
                />
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Email (required if no phone)"
                  value={newContractor.email}
                  onChange={(e) => setNewContractor((f) => ({ ...f, email: e.target.value }))}
                />
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Contact person (optional)"
                  value={newContractor.contact_name}
                  onChange={(e) => setNewContractor((f) => ({ ...f, contact_name: e.target.value }))}
                  autoComplete="name"
                />
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Coverage area (optional)"
                  value={newContractor.region}
                  onChange={(e) => setNewContractor((f) => ({ ...f, region: e.target.value }))}
                />
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-1">Service regions (UK)</p>
                  <p className="text-[11px] text-gray-500 mb-2">
                    For compliance work, regions default to this job&apos;s jurisdiction; adjust if the contractor covers more
                    than one.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {UK_SERVICE_REGION_OPTIONS.map((o) => {
                      const checked = (newContractor.service_regions || []).includes(o.value);
                      return (
                        <label
                          key={o.value}
                          className="inline-flex items-center gap-1.5 text-xs border rounded-md px-2 py-1 bg-white cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              setNewContractor((f) => {
                                const cur = f.service_regions || [];
                                const next = checked ? cur.filter((x) => x !== o.value) : [...cur, o.value];
                                return { ...f, service_regions: next };
                              });
                            }}
                          />
                          {o.label}
                        </label>
                      );
                    })}
                  </div>
                </div>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Areas served — comma-separated (optional)"
                  value={newContractor.areas_served}
                  onChange={(e) => setNewContractor((f) => ({ ...f, areas_served: e.target.value }))}
                />
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
                  placeholder="Accreditation / certification (optional)"
                  value={newContractor.accreditation}
                  onChange={(e) => setNewContractor((f) => ({ ...f, accreditation: e.target.value }))}
                />
                <textarea
                  className="w-full border rounded-lg px-3 py-2 text-sm min-h-[56px] bg-white"
                  placeholder="Notes (optional)"
                  value={newContractor.notes}
                  onChange={(e) => setNewContractor((f) => ({ ...f, notes: e.target.value }))}
                />
                {softDuplicateMatches.length > 0 ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50/90 p-3 space-y-2 text-xs text-amber-950">
                    <p className="font-medium">Possible matches already on your list</p>
                    <p className="text-amber-900/90">
                      We matched name, email, or phone to existing contractors for this job. Use one of them, or create a new
                      record if you are sure it is different.
                    </p>
                    <ul className="space-y-2">
                      {softDuplicateMatches.map(({ contractor: c, reasons }) => (
                        <li key={c.contractor_id} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                          <span>
                            <span className="font-medium">{contractorOptionLabel(c)}</span>
                            <span className="text-amber-800"> ({reasons.join(', ')})</span>
                          </span>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            className="shrink-0"
                            onClick={() => handleUseDuplicateMatch(c.contractor_id)}
                          >
                            Use this contractor
                          </Button>
                        </li>
                      ))}
                    </ul>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="w-full border-amber-300"
                      onClick={() => setAllowCreateDespiteDuplicates(true)}
                    >
                      Create new anyway
                    </Button>
                    {allowCreateDespiteDuplicates ? (
                      <p className="text-amber-900 font-medium">Creating a new directory entry — tap Save and assign to continue.</p>
                    ) : null}
                  </div>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  className="w-full bg-electric-teal text-midnight-blue font-semibold hover:bg-electric-teal/90"
                  disabled={
                    !!actionBusy ||
                    (softDuplicateMatches.length > 0 && !allowCreateDespiteDuplicates)
                  }
                  onClick={handleCreateAndAssign}
                >
                  {actionBusy === 'create_contractor_assign' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Save and assign'
                  )}
                </Button>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      <ContractorNetworkLockedModal open={contractorNetworkLockedOpen} onOpenChange={setContractorNetworkLockedOpen} />
    </div>
  );
}

export default function ClientJobDetailPage() {
  return (
    <OperationalCapabilityProtectedRoute requiredFeature="maintenance_workflows">
      <ClientJobDetailInner />
    </OperationalCapabilityProtectedRoute>
  );
}
