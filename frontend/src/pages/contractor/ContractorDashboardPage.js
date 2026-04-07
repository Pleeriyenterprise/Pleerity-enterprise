import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createContractorAPI,
  openBlobApiResponse,
  contractorEvidenceFilenameFromKey,
  isContractorFileEvidenceKey,
} from '../../api/client';
import { getContractorToken } from './ContractorLoginPage';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Alert, AlertDescription } from '../../components/ui/alert';
import {
  Wrench,
  LogOut,
  Loader2,
  X,
  FileText,
  Upload,
  AlertCircle,
  Info,
  ClipboardList,
  PoundSterling,
  ChevronRight,
  CalendarClock,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  buildInvoiceByWorkOrderId,
  formatMoneyGbp,
  getBlockOrCancelReason,
  getEvidenceGuidance,
  getJobTypeLabel,
  getJobValueDisplay,
  getNextStepMessage,
  isCompletedPipeline,
  isPendingScheduling,
  isSlaOverdue,
  parseIsoDate,
  sortWorkOrdersForDashboard,
  contractorNextStepLineFromNextActions,
  contractorJobStatusLabel,
  contractorDetailExecutionProgressFromWorkOrder,
  contractorPortalExecutableActions,
  contractorListPrimaryAction,
  CONTRACTOR_DETAIL_JOB_ACTION_IDS,
  contractorBillingPhaseForWorkOrder,
  contractorDetailTimelineSorted,
  contractorBillingActionButtonLabel,
  isContractorExecutionActive,
  isContractorInvoiceEligible,
  isContractorWaitingOnOthers,
  isScheduledTodayUtc,
  defaultInvoiceAmountFieldFromWorkOrder,
  formatContractorInvoiceStateLabel,
} from '../../utils/contractorWorkflow';
import { fireContractorWorkflowUsage } from '../../utils/contractorWorkflowUsage';

function contractorDebugLog(event, payload) {
  if (typeof window === 'undefined') return;
  if (process.env.NODE_ENV === 'production' && !window.__CVP_CONTRACTOR_DEBUG && !window.__CVP_DEBUG) return;
  console.info('[CVP][ContractorPortal]', event, payload);
}

function formatDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return String(s);
  }
}

function formatScheduleInstant(iso, tz) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return `${d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })} (${tz || 'UTC'})`;
  } catch {
    return String(iso);
  }
}

function scheduleLifecycleLabel(wo) {
  const st = (wo?.schedule_status || '').toLowerCase();
  if (st === 'proposed') return 'Proposed visit';
  if (st === 'confirmed') return 'Confirmed visit';
  if (st === 'reschedule_requested') return 'Reschedule requested';
  if (st === 'cancelled') return 'Visit cancelled';
  if (st === 'completed') return 'Visit completed (job closed)';
  if (wo?.scheduled_at) return 'Visit time on file';
  return 'No visit scheduled';
}

function scheduleProposedByLabel(by) {
  const b = (by || '').toLowerCase();
  if (b === 'client') return 'Client';
  if (b === 'contractor') return 'You / contractor';
  if (b === 'admin') return 'Operations';
  return by || '—';
}

export default function ContractorDashboardPage() {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [workOrders, setWorkOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [bootstrapLoading, setBootstrapLoading] = useState(true);
  const [workOrdersError, setWorkOrdersError] = useState(null);
  const [invoicesError, setInvoicesError] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [invoiceModal, setInvoiceModal] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [invoicesRefreshing, setInvoicesRefreshing] = useState(false);
  const [notesForm, setNotesForm] = useState({ contractor_notes: '', completion_notes: '' });
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [evidenceFileLoadingKey, setEvidenceFileLoadingKey] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({
    datetimeLocal: '',
    timezone: typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/London' : 'Europe/London',
    notes: '',
  });
  const [scheduleActionLoading, setScheduleActionLoading] = useState(false);
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [dashboardSummaryError, setDashboardSummaryError] = useState(null);
  const invoicesSectionRef = useRef(null);
  const completionProofInputRef = useRef(null);
  const lastJobOpenUsageRef = useRef(null);
  const scheduleSectionRef = useRef(null);
  const urgentSectionRef = useRef(null);
  const activeJobsSectionRef = useRef(null);
  const readyToInvoiceSectionRef = useRef(null);
  const waitingSectionRef = useRef(null);
  const completedMonthSectionRef = useRef(null);
  const [detailOpenFocus, setDetailOpenFocus] = useState(null);
  const [activeJobFilter, setActiveJobFilter] = useState('all');

  useEffect(() => {
    const t = getContractorToken();
    if (!t) {
      contractorDebugLog('bootstrap_no_token', { route: window.location?.pathname });
      navigate('/contractor/login', { replace: true });
      return;
    }
    setToken(t);
    contractorDebugLog('bootstrap_token_present', { route: window.location?.pathname });
    try {
      const u = localStorage.getItem('contractor_user');
      if (u) setUser(JSON.parse(u));
    } catch (_) {}
  }, [navigate]);

  // createContractorAPI() returns a new object every call — must memoize or bootstrap useEffect
  // (which depends on load* callbacks keyed by `api`) will re-run every render → request storm + stuck spinner.
  const api = useMemo(() => (token ? createContractorAPI(token) : null), [token]);

  const loadWorkOrders = useCallback(() => {
    if (!api) return Promise.resolve();
    setWorkOrdersError(null);
    return api
      .getWorkOrders({ limit: 100 })
      .then((res) => {
        setWorkOrders(res.data?.work_orders || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ||
          (typeof err?.response?.data?.detail === 'object' ? err.response.data.detail?.message : null) ||
          err?.message ||
          'Could not load work orders.';
        setWorkOrders([]);
        setTotal(0);
        setWorkOrdersError(typeof msg === 'string' ? msg : 'Could not load work orders.');
        contractorDebugLog('work_orders_failed', { status: err?.response?.status, msg });
      });
  }, [api]);

  const loadInvoices = useCallback(() => {
    if (!api) return Promise.resolve();
    setInvoicesError(null);
    return api
      .getInvoices({ limit: 50 })
      .then((res) => setInvoices(res.data?.invoices || []))
      .catch((err) => {
        setInvoices([]);
        const msg =
          err?.response?.data?.detail ||
          (typeof err?.response?.data?.detail === 'object' ? err.response.data.detail?.message : null) ||
          err?.message ||
          'Could not load invoices.';
        setInvoicesError(typeof msg === 'string' ? msg : 'Could not load invoices.');
        contractorDebugLog('invoices_failed', { status: err?.response?.status, msg });
      });
  }, [api]);

  const loadProfile = useCallback(() => {
    if (!api) return Promise.resolve();
    setProfileError(null);
    return api
      .getProfile()
      .then((res) => setProfile(res.data))
      .catch((err) => {
        setProfile(null);
        const msg =
          err?.response?.data?.detail ||
          (typeof err?.response?.data?.detail === 'object' ? err.response.data.detail?.message : null) ||
          err?.message ||
          'Could not load profile.';
        setProfileError(typeof msg === 'string' ? msg : 'Could not load profile.');
        contractorDebugLog('profile_failed', { status: err?.response?.status, msg });
      });
  }, [api]);

  const loadDashboardSummary = useCallback(() => {
    if (!api) return Promise.resolve();
    setDashboardSummaryError(null);
    return api
      .getDashboardSummary()
      .then((res) => setDashboardSummary(res.data))
      .catch((err) => {
        setDashboardSummary(null);
        const msg =
          err?.response?.data?.detail ||
          (typeof err?.response?.data?.detail === 'object' ? err.response.data.detail?.message : null) ||
          err?.message ||
          'Could not load dashboard summary.';
        setDashboardSummaryError(typeof msg === 'string' ? msg : 'Could not load dashboard summary.');
        contractorDebugLog('dashboard_summary_failed', { status: err?.response?.status, msg });
      });
  }, [api]);

  const invoiceByWorkOrderId = useMemo(() => buildInvoiceByWorkOrderId(invoices), [invoices]);

  const detailPortalActions = useMemo(() => contractorPortalExecutableActions(detail || {}), [detail]);

  const detailPrimaryAction = useMemo(() => (detail ? contractorListPrimaryAction(detail) : null), [detail]);

  const detailActionIds = useMemo(
    () => new Set(detailPortalActions.map((a) => a.id)),
    [detailPortalActions],
  );

  const sortedWorkOrders = useMemo(() => sortWorkOrdersForDashboard(workOrders), [workOrders]);

  const actionCounts = useMemo(() => {
    if (dashboardSummary?.work_orders) return dashboardSummary.work_orders;
    return {
      overdue: workOrders.filter((w) => isSlaOverdue(w)).length,
      pending_scheduling: workOrders.filter((w) => isPendingScheduling(w)).length,
      completed: workOrders.filter((w) => isCompletedPipeline(w)).length,
      total_assigned: workOrders.length,
    };
  }, [dashboardSummary, workOrders]);

  const earningsDisplay = useMemo(() => {
    if (dashboardSummary?.earnings_gbp) return dashboardSummary.earnings_gbp;
    let pendingApprovalTotal = 0;
    const now = new Date();
    const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    let paidThisMonthTotal = 0;
    (invoices || []).forEach((inv) => {
      const st = (inv.status || '').toLowerCase();
      const amt = Number(inv.submitted_amount);
      const a = Number.isNaN(amt) ? 0 : amt;
      if (st === 'pending' || st === 'needs_info') pendingApprovalTotal += a;
      if (st === 'paid' && inv.paid_at) {
        const pd = new Date(inv.paid_at);
        if (!Number.isNaN(pd.getTime()) && pd >= monthStart) paidThisMonthTotal += a;
      }
    });
    const invoicedWo = new Set((invoices || []).map((i) => i.work_order_id).filter(Boolean));
    let readyJobs = 0;
    let readyEst = 0;
    (workOrders || []).forEach((wo) => {
      const st = (wo.status || '').toUpperCase();
      if (!wo.work_order_id || invoicedWo.has(wo.work_order_id)) return;
      if (!['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st)) return;
      readyJobs += 1;
      const mx = wo.cost_estimate_max != null ? Number(wo.cost_estimate_max) : null;
      const mn = wo.cost_estimate_min != null ? Number(wo.cost_estimate_min) : null;
      if (mx != null && !Number.isNaN(mx)) readyEst += mx;
      else if (mn != null && !Number.isNaN(mn)) readyEst += mn;
    });
    return {
      pending_approval_total: Math.round(pendingApprovalTotal * 100) / 100,
      ready_to_invoice_jobs: readyJobs,
      ready_to_invoice_estimated_total: Math.round(readyEst * 100) / 100,
      paid_this_month_total: Math.round(paidThisMonthTotal * 100) / 100,
    };
  }, [dashboardSummary, invoices, workOrders]);

  const displayWorkflow = useMemo(() => {
    const w = dashboardSummary?.workflow;
    if (w) {
      return {
        action: w.action_needed,
        payments: w.payments,
        jobs: w.jobs,
        submitPrimary: !!w.submit_invoice_primary_cta,
      };
    }
    const action = {
      visit_confirmation: 0,
      proof_upload: 0,
      invoice_submission: 0,
      invoice_correction: 0,
    };
    (workOrders || []).forEach((wo) => {
      (wo.next_actions || []).forEach((a) => {
        if (!a?.id) return;
        if (a.id === 'confirm_visit') action.visit_confirmation += 1;
        if (a.id === 'upload_completion_proof') action.proof_upload += 1;
        if (a.id === 'submit_invoice') action.invoice_submission += 1;
        if (a.id === 'edit_invoice') action.invoice_correction += 1;
      });
    });
    const submitPrimary = action.invoice_submission > 0;
    const now = new Date();
    let active = 0;
    let scheduledToday = 0;
    (workOrders || []).forEach((wo) => {
      const s = (wo.status || '').toUpperCase();
      if (['OPEN', 'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'AWAITING_PARTS'].includes(s)) active += 1;
      if (s !== 'CANCELLED' && wo.scheduled_at) {
        try {
          const d = new Date(wo.scheduled_at);
          if (
            d.getUTCFullYear() === now.getUTCFullYear() &&
            d.getUTCMonth() === now.getUTCMonth() &&
            d.getUTCDate() === now.getUTCDate()
          ) {
            scheduledToday += 1;
          }
        } catch (_) {
          /* ignore */
        }
      }
    });
    const awaitingApprovalJobs = new Set(
      (invoices || [])
        .filter((i) => ['pending', 'needs_info'].includes((i.status || '').toLowerCase()))
        .map((i) => i.work_order_id)
        .filter(Boolean),
    ).size;
    return {
      action,
      payments: {
        ready_to_invoice_jobs: earningsDisplay.ready_to_invoice_jobs,
        awaiting_approval_jobs: awaitingApprovalJobs,
        paid_this_month_total: earningsDisplay.paid_this_month_total,
      },
      jobs: {
        active,
        scheduled_today: scheduledToday,
        overdue_at_risk: (workOrders || []).filter((w) => isSlaOverdue(w)).length,
      },
      submitPrimary,
    };
  }, [dashboardSummary, workOrders, invoices, earningsDisplay]);

  const profileAwaitingApproval = useMemo(() => {
    const s = (profile?.account_status || '').toLowerCase();
    const pa = (profile?.portal_access || '').toLowerCase();
    return ['pending_review', 'pending_approval', 'invited'].includes(s) || pa === 'invite_pending';
  }, [profile]);

  const URGENT_ACTION_IDS = useMemo(
    () =>
      new Set(['accept_assignment', 'confirm_visit', 'upload_completion_proof', 'submit_invoice', 'edit_invoice']),
    [],
  );

  const urgentItems = useMemo(() => {
    const out = [];
    sortedWorkOrders.forEach((wo) => {
      const hit = contractorPortalExecutableActions(wo).find((a) => URGENT_ACTION_IDS.has(a.id));
      if (hit) out.push({ wo, action: hit });
    });
    return out;
  }, [sortedWorkOrders, URGENT_ACTION_IDS]);

  const performanceMetrics = useMemo(() => {
    const now = new Date();
    const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    let completedMonth = 0;
    const closeDays = [];
    let holds = 0;
    (workOrders || []).forEach((wo) => {
      if ((wo.operational_exception || '').trim()) holds += 1;
      const st = (wo.status || '').toUpperCase();
      const comp = parseIsoDate(wo.completed_at);
      if (comp && comp >= monthStart && ['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st)) completedMonth += 1;
      const created = parseIsoDate(wo.created_at);
      if (created && comp && ['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st)) {
        closeDays.push((comp.getTime() - created.getTime()) / 86400000);
      }
    });
    const avgClose =
      closeDays.length > 0
        ? Math.round((closeDays.reduce((a, b) => a + b, 0) / closeDays.length) * 10) / 10
        : null;
    return { completedMonth, avgCloseDays: avgClose, holds };
  }, [workOrders]);

  const workOrderById = useMemo(() => {
    const m = {};
    (workOrders || []).forEach((w) => {
      if (w.work_order_id) m[w.work_order_id] = w;
    });
    return m;
  }, [workOrders]);

  const activeJobsFiltered = useMemo(() => {
    let list = sortedWorkOrders.filter((w) => isContractorExecutionActive(w) && !isContractorWaitingOnOthers(w));
    if (activeJobFilter === 'scheduled_today') list = list.filter((w) => isScheduledTodayUtc(w));
    if (activeJobFilter === 'at_risk') list = list.filter((w) => isSlaOverdue(w));
    return list;
  }, [sortedWorkOrders, activeJobFilter]);

  const executionActiveCount = useMemo(
    () => sortedWorkOrders.filter((w) => isContractorExecutionActive(w) && !isContractorWaitingOnOthers(w)).length,
    [sortedWorkOrders],
  );
  const scheduledTodayActiveCount = useMemo(
    () =>
      sortedWorkOrders.filter(
        (w) => isContractorExecutionActive(w) && !isContractorWaitingOnOthers(w) && isScheduledTodayUtc(w),
      ).length,
    [sortedWorkOrders],
  );
  const atRiskActiveCount = useMemo(
    () =>
      sortedWorkOrders.filter((w) => isContractorExecutionActive(w) && !isContractorWaitingOnOthers(w) && isSlaOverdue(w))
        .length,
    [sortedWorkOrders],
  );

  const readyToInvoiceJobs = useMemo(
    () => sortedWorkOrders.filter((w) => isContractorInvoiceEligible(w)),
    [sortedWorkOrders],
  );

  const waitingJobs = useMemo(() => sortedWorkOrders.filter((w) => isContractorWaitingOnOthers(w)), [sortedWorkOrders]);

  const completedMonthJobs = useMemo(() => {
    const now = new Date();
    const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    return sortedWorkOrders.filter((w) => {
      const comp = parseIsoDate(w.completed_at);
      const st = (w.status || '').toUpperCase();
      return comp && comp >= monthStart && ['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st);
    });
  }, [sortedWorkOrders]);

  const paymentTableRows = useMemo(() => {
    const rows = [...(invoices || [])];
    rows.sort((a, b) => {
      const pa = a.paid_at ? new Date(a.paid_at).getTime() : 0;
      const pb = b.paid_at ? new Date(b.paid_at).getTime() : 0;
      if (pb !== pa) return pb - pa;
      const sa = a.submitted_at ? new Date(a.submitted_at).getTime() : 0;
      const sb = b.submitted_at ? new Date(b.submitted_at).getTime() : 0;
      return sb - sa;
    });
    return rows;
  }, [invoices]);

  const detailNextIdleMessage = useMemo(() => {
    if (!detail) return null;
    if (contractorPortalExecutableActions(detail).length > 0) return null;
    const st = (detail.status || '').toUpperCase();
    if (st === 'CANCELLED') return 'This job was cancelled. No further action.';
    if (['COMPLETED', 'VERIFIED', 'CLOSED'].includes(st)) return 'This job is complete. No further action required.';
    return 'No action available right now.';
  }, [detail]);

  const detailJobPanelActions = useMemo(() => {
    const pid = detailPrimaryAction?.id;
    return detailPortalActions.filter((a) => CONTRACTOR_DETAIL_JOB_ACTION_IDS.has(a.id) && a.id !== pid);
  }, [detailPortalActions, detailPrimaryAction]);

  const detailBillingPanelActions = useMemo(() => {
    const pid = detailPrimaryAction?.id;
    return detailPortalActions.filter((a) => a.section === 'billing' && a.id !== pid);
  }, [detailPortalActions, detailPrimaryAction]);

  const detailBillingPhase = useMemo(
    () => (detail ? contractorBillingPhaseForWorkOrder(detail, invoiceByWorkOrderId) : null),
    [detail, invoiceByWorkOrderId],
  );

  const detailTimelineSorted = useMemo(
    () => (detail?.timeline_events?.length ? contractorDetailTimelineSorted(detail.timeline_events) : []),
    [detail?.timeline_events],
  );

  const scrollToRef = (r) => {
    requestAnimationFrame(() => r?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  useEffect(() => {
    if (!api) {
      setBootstrapLoading(false);
      return undefined;
    }
    let cancelled = false;
    setBootstrapLoading(true);
    setWorkOrdersError(null);
    setInvoicesError(null);
    setProfileError(null);
    contractorDebugLog('bootstrap_api_calls_start', {});
    Promise.all([loadWorkOrders(), loadInvoices(), loadProfile(), loadDashboardSummary()]).finally(() => {
      if (!cancelled) {
        setBootstrapLoading(false);
        contractorDebugLog('bootstrap_api_calls_done', {});
      }
    });
    return () => {
      cancelled = true;
    };
  }, [api, loadWorkOrders, loadInvoices, loadProfile, loadDashboardSummary]);

  useEffect(() => {
    if (!api || !detailId) return;
    setDetailLoading(true);
    api.getWorkOrder(detailId)
      .then((res) => setDetail(res.data))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [api, detailId]);

  useEffect(() => {
    if (!detailId) lastJobOpenUsageRef.current = null;
  }, [detailId]);

  useEffect(() => {
    if (!detailId || !api || detailLoading) return;
    if (!detail?.work_order_id || detail.work_order_id !== detailId) return;
    const wid = detail.work_order_id;
    if (lastJobOpenUsageRef.current === wid) return;
    lastJobOpenUsageRef.current = wid;
    fireContractorWorkflowUsage(api.postWorkflowUsage, { event_type: 'job_opened', work_order_id: wid });
  }, [api, detailId, detail, detailLoading]);

  useEffect(() => {
    if (detail) {
      setNotesForm({
        contractor_notes: detail.contractor_notes || '',
        completion_notes: detail.completion_notes || '',
      });
    }
  }, [detail]);

  useEffect(() => {
    if (!detail || !detailOpenFocus) return undefined;
    if (detailOpenFocus === 'proof') {
      const t = setTimeout(() => {
        completionProofInputRef.current?.click?.();
        setDetailOpenFocus(null);
      }, 200);
      return () => clearTimeout(t);
    }
    if (detailOpenFocus === 'schedule') {
      const t = setTimeout(() => {
        scheduleSectionRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
        setDetailOpenFocus(null);
      }, 200);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [detail, detailOpenFocus]);

  const handleLogout = () => {
    localStorage.removeItem('contractor_token');
    localStorage.removeItem('contractor_user');
    navigate('/contractor/login', { replace: true });
  };

  const handleSaveNotes = () => {
    if (!detail || !api) return;
    setActionLoading(detail.work_order_id);
    api
      .updateWorkOrder(detail.work_order_id, {
        contractor_notes: notesForm.contractor_notes || undefined,
        completion_notes: notesForm.completion_notes || undefined,
      })
      .then((r) => {
        toast.success('Notes saved');
        setDetail(r.data);
        loadWorkOrders();
        loadDashboardSummary();
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const refreshContractorDetail = (id) => {
    if (!api || !id) return Promise.resolve();
    return api.getWorkOrder(id).then((r) => setDetail(r.data));
  };

  const executeContractorAction = useCallback(
    async (wo, action, ev) => {
      ev?.stopPropagation?.();
      if (!api || !wo?.work_order_id || !action?.id) return;
      const wid = wo.work_order_id;
      const aid = action.id;
      const refreshListAndDetail = async () => {
        await loadWorkOrders();
        await loadDashboardSummary();
        if (detailId === wid) {
          const r = await api.getWorkOrder(wid);
          setDetail(r.data);
        }
      };
      const logActionTaken = () =>
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'action_taken',
          work_order_id: wid,
          action_id: aid,
        });
      if (aid === 'complete_job' && wo.completion_proof_required && !wo.completion_proof_satisfied) {
        toast.error('Upload completion proof before completing this job');
        return;
      }
      const needsConfirmBeforeUsage =
        aid === 'decline_assignment' || aid === 'cancel_scheduled_visit';
      if (!needsConfirmBeforeUsage) {
        logActionTaken();
      }
      try {
        if (aid === 'accept_assignment') {
          setActionLoading(wid);
          await api.acceptAssignment(wid);
          toast.success('Assignment accepted');
          setDetailId(null);
          await refreshListAndDetail();
        } else if (aid === 'decline_assignment') {
          if (!window.confirm('Decline this assignment? The work order will be unassigned.')) return;
          logActionTaken();
          setActionLoading(wid);
          await api.declineAssignment(wid);
        toast.success('Assignment declined');
        setDetailId(null);
          await refreshListAndDetail();
        } else if (aid === 'confirm_visit') {
          setScheduleActionLoading(true);
          await api.confirmSchedule(wid);
          toast.success('Visit confirmed');
          await refreshListAndDetail();
        } else if (aid === 'reschedule_visit') {
          const reason = window.prompt('Reason for reschedule request (optional)') ?? '';
          setScheduleActionLoading(true);
          await api.requestScheduleReschedule(wid, { reason: reason.trim() || undefined });
          toast.success('Reschedule request sent');
          await refreshListAndDetail();
        } else if (aid === 'propose_visit') {
          setDetailId(wid);
          setDetailOpenFocus('schedule');
        } else if (aid === 'start_job') {
          setActionLoading(wid);
          await api.updateWorkOrder(wid, { status: 'IN_PROGRESS' });
          toast.success('Job started');
          await refreshListAndDetail();
        } else if (aid === 'awaiting_parts') {
          setActionLoading(wid);
          await api.updateWorkOrder(wid, { status: 'AWAITING_PARTS' });
          toast.success('Marked awaiting parts');
          await refreshListAndDetail();
        } else if (aid === 'resume_job') {
          setActionLoading(wid);
          await api.updateWorkOrder(wid, { status: 'IN_PROGRESS' });
          toast.success('Job resumed');
          await refreshListAndDetail();
        } else if (aid === 'complete_job') {
          setActionLoading(wid);
          await api.updateWorkOrder(wid, { status: 'COMPLETED' });
          fireContractorWorkflowUsage(api.postWorkflowUsage, { event_type: 'job_completed', work_order_id: wid });
          toast.success('Job marked complete');
          await refreshListAndDetail();
        } else if (aid === 'submit_invoice') {
          setDetailId(wid);
          setInvoiceForm({
            reference: '',
            description: '',
            submitted_amount: defaultInvoiceAmountFieldFromWorkOrder(wo),
          });
          setInvoiceModal({ mode: 'create', workOrder: wo, invoice: null });
        } else if (aid === 'view_invoice' || aid === 'edit_invoice') {
          setDetailId(wid);
          const inv = wo.linked_invoice || invoiceByWorkOrderId[wid];
          setInvoiceForm({
            reference: inv?.reference || '',
            description: inv?.description || '',
            submitted_amount: inv?.submitted_amount != null ? String(inv.submitted_amount) : '',
          });
          setInvoiceModal({
            mode: aid === 'edit_invoice' ? 'edit' : 'view',
            workOrder: wo,
            invoice: inv || null,
          });
        } else if (aid === 'upload_completion_proof') {
          setDetailId(wid);
          setDetailOpenFocus('proof');
        } else if (aid === 'open_job_detail') {
          setDetailId(wid);
        } else if (aid === 'mark_no_access') {
          const notes = window.prompt('Optional note for your client (e.g. why access was not possible)') ?? '';
          setActionLoading(wid);
          await api.markNoAccess(wid, { notes: notes.trim() || undefined });
          toast.success('No access recorded. Your client can reschedule or clear the hold.');
          await refreshListAndDetail();
        } else if (aid === 'cancel_scheduled_visit') {
          if (!window.confirm('Cancel this scheduled visit? The booking will be cleared.')) return;
          logActionTaken();
          setScheduleActionLoading(true);
          await api.cancelSchedule(wid);
          toast.success('Visit cancelled');
          await refreshListAndDetail();
        }
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Action failed');
      } finally {
        setActionLoading(null);
        setScheduleActionLoading(false);
      }
    },
    [api, loadWorkOrders, loadDashboardSummary, detailId, invoiceByWorkOrderId],
  );

  const handleProposeVisitSchedule = () => {
    if (!detail || !api) return;
    if (!scheduleForm.datetimeLocal) {
      toast.error('Choose a visit date and time');
      return;
    }
    const raw = scheduleForm.datetimeLocal.length === 16 ? `${scheduleForm.datetimeLocal}:00` : scheduleForm.datetimeLocal;
    setScheduleActionLoading(true);
    api
      .proposeSchedule(detail.work_order_id, {
        scheduled_at: raw,
        timezone: scheduleForm.timezone,
        notes: scheduleForm.notes?.trim() || undefined,
      })
      .then(() => {
        toast.success('Visit time proposed');
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'action_taken',
          work_order_id: detail.work_order_id,
          action_id: 'propose_visit',
        });
        return refreshContractorDetail(detail.work_order_id);
      })
      .then(() => loadWorkOrders())
      .then(() => loadDashboardSummary())
      .catch((e) => toast.error(e.response?.data?.detail || 'Could not propose visit time'))
      .finally(() => setScheduleActionLoading(false));
  };

  const handleConfirmVisitSchedule = () => {
    if (!detail || !api) return;
    setScheduleActionLoading(true);
    api
      .confirmSchedule(detail.work_order_id)
      .then(() => {
        toast.success('Visit confirmed');
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'action_taken',
          work_order_id: detail.work_order_id,
          action_id: 'confirm_visit',
        });
        return refreshContractorDetail(detail.work_order_id);
      })
      .then(() => loadWorkOrders())
      .then(() => loadDashboardSummary())
      .catch((e) => toast.error(e.response?.data?.detail || 'Could not confirm'))
      .finally(() => setScheduleActionLoading(false));
  };

  const handleRequestVisitReschedule = () => {
    if (!detail || !api) return;
    const reason = window.prompt('Reason for reschedule request (optional)') ?? '';
    setScheduleActionLoading(true);
    api
      .requestScheduleReschedule(detail.work_order_id, { reason: reason.trim() || undefined })
      .then(() => {
        toast.success('Reschedule request sent');
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'action_taken',
          work_order_id: detail.work_order_id,
          action_id: 'reschedule_visit',
        });
        return refreshContractorDetail(detail.work_order_id);
      })
      .then(() => loadWorkOrders())
      .then(() => loadDashboardSummary())
      .catch((e) => toast.error(e.response?.data?.detail || 'Request failed'))
      .finally(() => setScheduleActionLoading(false));
  };

  const onEvidenceSelected = (e) => {
    const file = e.target.files?.[0];
    if (!file || !detail || !api) return;
    setEvidenceUploading(true);
    api
      .uploadWorkOrderEvidence(detail.work_order_id, file)
      .then((res) => {
        toast.success('Evidence uploaded');
        setDetail(res.data.work_order);
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'proof_uploaded',
          work_order_id: detail.work_order_id,
        });
        loadWorkOrders();
        loadDashboardSummary();
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Upload failed'))
      .finally(() => {
        setEvidenceUploading(false);
        e.target.value = '';
      });
  };

  const handleEvidenceFileOpen = (storageKey, download) => {
    if (!detail || !api) return;
    setEvidenceFileLoadingKey(storageKey);
    api
      .downloadWorkOrderEvidenceFile(detail.work_order_id, storageKey, download)
      .then((res) =>
        openBlobApiResponse(res, {
          download,
          fallbackFilename: contractorEvidenceFilenameFromKey(storageKey),
        }),
      )
      .catch((err) => {
        const d = err?.response?.data?.detail;
        toast.error(typeof d === 'string' ? d : 'Could not open file');
      })
      .finally(() => setEvidenceFileLoadingKey(null));
  };

  const handleSubmitInvoice = (e) => {
    e.preventDefault();
    if (!invoiceModal || !api) return;
    if (invoiceModal.mode === 'view') return;
    const ref = (invoiceForm.reference || '').trim();
    if (!ref) {
      toast.error('Invoice reference is required');
      return;
    }
    const amt = parseFloat(String(invoiceForm.submitted_amount).replace(/,/g, ''));
    if (Number.isNaN(amt) || amt <= 0) {
      toast.error('Enter a valid invoice amount greater than zero');
      return;
    }
    const wo = invoiceModal.workOrder;
    if (!wo?.work_order_id) return;
    setInvoiceSaving(true);
    const body = {
      reference: ref,
      description: (invoiceForm.description || '').trim() || undefined,
      submitted_amount: amt,
    };
    const finishOk = () => {
      toast.success(
        invoiceModal.mode === 'edit' ? 'Invoice updated and resubmitted for approval.' : 'Invoice submitted for approval.',
      );
        setInvoiceModal(null);
        setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
      setInvoicesRefreshing(true);
      Promise.all([loadInvoices(), loadWorkOrders(), loadDashboardSummary()]).finally(() => setInvoicesRefreshing(false));
    };
    const req =
      invoiceModal.mode === 'edit' && invoiceModal.invoice?.invoice_id
        ? api.resubmitInvoice(invoiceModal.invoice.invoice_id, body)
        : api.submitInvoice({ work_order_id: wo.work_order_id, ...body });
    req.then(finishOk).catch((err) => toast.error(err.response?.data?.detail || 'Failed')).finally(() => setInvoiceSaving(false));
  };

  if (!token) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wrench className="w-6 h-6 text-electric-teal" />
          <span className="font-semibold text-midnight-blue">Contractor Portal</span>
          {(profile?.name || profile?.company_name) && (
            <span className="text-sm text-gray-600">{profile.name || profile.company_name}</span>
          )}
          {user?.email && <span className="text-sm text-gray-500">({user.email})</span>}
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="w-4 h-4 mr-1" /> Sign out
        </Button>
      </header>

      <main className="max-w-6xl mx-auto p-4 md:p-6">
        {profileError && (
          <Alert variant="destructive" className="mb-4" data-testid="contractor-profile-error">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>Profile: {profileError}</AlertDescription>
          </Alert>
        )}

        {bootstrapLoading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-gray-600">
            <Loader2 className="w-10 h-10 animate-spin text-electric-teal" />
            <p className="text-sm">Loading your portal…</p>
          </div>
        ) : (
          <>
            {!workOrdersError &&
              !invoicesError &&
              !profileError &&
              workOrders.length === 0 &&
              invoices.length === 0 &&
              !profileAwaitingApproval && (
                <Alert className="mb-6 border-electric-teal/30 bg-teal-50/80">
                  <Info className="h-4 w-4 text-electric-teal" />
                  <AlertDescription>
                    <span className="font-medium text-midnight-blue">Your account is active.</span>
                    <span className="block mt-1 text-gray-700">
                      When a client assigns work to you, it will appear below. You can also open secure job links from assignment
                      emails without signing in.
                    </span>
                  </AlertDescription>
                </Alert>
              )}

            {profileAwaitingApproval ? (
              <Alert className="mb-6 border-amber-300 bg-amber-50">
                <AlertCircle className="h-4 w-4 text-amber-700" />
                <AlertDescription className="text-amber-950">
                  <span className="font-medium">Your account is awaiting approval.</span>
                  <span className="block mt-1 text-sm">You will be able to use the full portal once your client or administrator activates your profile.</span>
                </AlertDescription>
              </Alert>
            ) : null}

            {dashboardSummaryError ? (
              <Alert className="mb-4 border-amber-200 bg-amber-50">
                <AlertCircle className="h-4 w-4 text-amber-700" />
                <AlertDescription className="text-amber-900 text-sm">{dashboardSummaryError}</AlertDescription>
              </Alert>
            ) : null}

            <section ref={urgentSectionRef} className="mb-8 scroll-mt-24" aria-label="Urgent actions">
              <h2 className="text-sm font-bold text-midnight-blue tracking-tight mb-3 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                Urgent actions
              </h2>
              {urgentItems.length === 0 ? (
                <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600">
                  You&apos;re up to date. No urgent contractor actions right now.
                </div>
              ) : (
                <ul className="space-y-2">
                  {urgentItems.map(({ wo, action }) => (
                    <li
                      key={`${wo.work_order_id}-${action.id}`}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 rounded-lg border border-gray-200 bg-white p-3 shadow-sm"
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-midnight-blue truncate">{wo.description || wo.work_order_id}</p>
                        <p className="text-xs text-gray-500">
                          {action.label} · {wo.property_address || wo.property_id}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        className="shrink-0 bg-electric-teal hover:bg-electric-teal/90 text-white"
                        disabled={!!actionLoading && actionLoading === wo.work_order_id}
                        onClick={(e) => executeContractorAction(wo, action, e)}
                      >
                        {actionLoading === wo.work_order_id ? <Loader2 className="w-4 h-4 animate-spin" /> : action.label}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mb-10" aria-label="Primary metrics">
              <h2 className="text-sm font-bold text-midnight-blue tracking-tight mb-3 flex items-center gap-2">
                <PoundSterling className="w-4 h-4 text-electric-teal" />
                Primary metrics
              </h2>
              <p className="text-xs text-gray-500 mb-4">Tap a tile to jump to the matching list or section.</p>
              <div className="grid lg:grid-cols-3 gap-6">
                  <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">A. Jobs</h3>
                  <div className="grid gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setActiveJobFilter('all');
                        scrollToRef(activeJobsSectionRef);
                      }}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-electric-teal/50 hover:bg-teal-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Active jobs</p>
                      <p className="text-2xl font-bold text-midnight-blue">{executionActiveCount}</p>
                      <p className="text-[10px] text-gray-400 mt-1">Show active execution list</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveJobFilter('scheduled_today');
                        scrollToRef(activeJobsSectionRef);
                      }}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-sky-300 hover:bg-sky-50/50 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Scheduled today (UTC)</p>
                      <p className="text-2xl font-bold text-midnight-blue">{scheduledTodayActiveCount}</p>
                      <p className="text-[10px] text-gray-400 mt-1">Filter active list</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveJobFilter('at_risk');
                        scrollToRef(activeJobsSectionRef);
                      }}
                      className="text-left rounded-lg border border-red-100 bg-white p-3 hover:border-red-300 hover:bg-red-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">At risk (SLA)</p>
                      <p className="text-2xl font-bold text-red-700">{atRiskActiveCount}</p>
                      <p className="text-[10px] text-gray-400 mt-1">Filter overdue active jobs</p>
                    </button>
                  </div>
                  </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">B. Billing</h3>
                  <div className="grid gap-2">
                    <button
                      type="button"
                      onClick={() => scrollToRef(readyToInvoiceSectionRef)}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-electric-teal/50 hover:bg-teal-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Ready to invoice</p>
                      <p className="text-2xl font-bold text-midnight-blue">{displayWorkflow.payments.ready_to_invoice_jobs ?? 0}</p>
                      <p className="text-[10px] text-gray-400 mt-1">Jump to ready-to-invoice</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollToRef(waitingSectionRef)}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-violet-200 hover:bg-violet-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Awaiting approval</p>
                      <p className="text-2xl font-bold text-midnight-blue">{displayWorkflow.payments.awaiting_approval_jobs ?? 0}</p>
                      <p className="text-[10px] text-gray-400 mt-1">
                        {formatMoneyGbp(earningsDisplay.pending_approval_total) || '£0.00'} in review · see Waiting on others
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollToRef(invoicesSectionRef)}
                      className="text-left rounded-lg border border-emerald-100 bg-white p-3 hover:border-emerald-300 hover:bg-emerald-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Paid this month</p>
                      <p className="text-2xl font-bold text-emerald-800">
                        {formatMoneyGbp(displayWorkflow.payments.paid_this_month_total) || '£0.00'}
                      </p>
                      <p className="text-[10px] text-gray-400 mt-1">Jump to payment history</p>
                    </button>
                  </div>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">C. Performance</h3>
                  <div className="grid gap-2">
                    <button
                      type="button"
                      onClick={() => scrollToRef(completedMonthSectionRef)}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-gray-300 hover:bg-gray-50 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Completed this month (UTC)</p>
                      <p className="text-2xl font-bold text-midnight-blue">{performanceMetrics.completedMonth}</p>
                      <p className="text-[10px] text-gray-400 mt-1">Jump to list</p>
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        toast.message('Average close time', {
                          description:
                            performanceMetrics.avgCloseDays != null
                              ? `About ${performanceMetrics.avgCloseDays} days from job created to completed (jobs with both dates).`
                              : 'Not enough completed jobs with dates to calculate yet.',
                        })
                      }
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-gray-300 hover:bg-gray-50 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Avg. close time</p>
                      <p className="text-2xl font-bold text-midnight-blue">
                        {performanceMetrics.avgCloseDays != null ? `${performanceMetrics.avgCloseDays}d` : '—'}
                      </p>
                      <p className="text-[10px] text-gray-400 mt-1">Tap for detail</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => scrollToRef(waitingSectionRef)}
                      className="text-left rounded-lg border border-gray-200 bg-white p-3 hover:border-amber-200 hover:bg-amber-50/40 transition-colors"
                    >
                      <p className="text-xs text-gray-500">Operational holds</p>
                      <p className="text-2xl font-bold text-amber-900">{performanceMetrics.holds}</p>
                      <p className="text-[10px] text-gray-400 mt-1">No access / reschedule holds · Waiting on others</p>
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-4">
                Scheduling queue: {actionCounts.pending_scheduling ?? 0} · Completed (all time): {actionCounts.completed ?? 0}
              </p>
            </section>

            <section ref={activeJobsSectionRef} className="mb-10 scroll-mt-24" aria-label="Active jobs">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="text-lg font-bold text-midnight-blue flex items-center gap-2">
                  <CalendarClock className="w-5 h-5 text-electric-teal" />
                  Active jobs
                  {total > 0 ? <span className="text-sm font-normal text-gray-500">({total} assigned)</span> : null}
                </h2>
                {activeJobFilter !== 'all' ? (
                  <Button type="button" variant="ghost" size="sm" onClick={() => setActiveJobFilter('all')}>
                    Clear filter
                  </Button>
                ) : null}
              </div>
            {workOrdersError ? (
              <Alert variant="destructive" className="mb-4" data-testid="contractor-work-orders-error">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <span className="font-medium">Work orders</span>
                  <span className="block mt-1">{workOrdersError}</span>
                </AlertDescription>
              </Alert>
            ) : null}
            {workOrders.length === 0 && !workOrdersError ? (
              <Card className="mb-10">
                <CardContent className="py-10 text-center text-gray-600">
                  <p className="font-semibold text-midnight-blue text-lg">You have no active jobs yet.</p>
                  <p className="text-sm mt-2 text-gray-500">Jobs will appear here when assigned.</p>
                </CardContent>
              </Card>
            ) : null}
            {workOrders.length > 0 && !workOrdersError ? (
              activeJobsFiltered.length === 0 ? (
                <Card className="mb-10">
                  <CardContent className="py-8 text-center text-gray-600 text-sm">
                    No active jobs match this filter.{' '}
                    <button type="button" className="text-electric-teal underline font-medium" onClick={() => setActiveJobFilter('all')}>
                      Show all active jobs
                    </button>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-4 mb-10">
                  {activeJobsFiltered.map((wo) => {
                    const overdue = isSlaOverdue(wo);
                    const borderClass = overdue ? 'border-l-red-500' : isPendingScheduling(wo) ? 'border-l-amber-400' : 'border-l-teal-500';
                    const reason = getBlockOrCancelReason(wo);
                    const hasServerActions = Array.isArray(wo.next_actions);
                    const nextLine = hasServerActions
                      ? contractorNextStepLineFromNextActions(wo)
                      : getNextStepMessage(wo, invoiceByWorkOrderId);
                    const primaryAction = hasServerActions ? contractorListPrimaryAction(wo) : null;
                    const schedLabel = scheduleLifecycleLabel(wo);
                    const schedWhen =
                      wo.scheduled_at && (wo.schedule_status || '').toLowerCase() !== 'cancelled'
                        ? formatScheduleInstant(wo.scheduled_at, wo.scheduled_timezone)
                        : null;
                    return (
                      <Card
                        key={wo.work_order_id}
                        className={`border-l-4 ${borderClass} overflow-hidden shadow-sm`}
                      >
                        <CardContent className="py-4 px-4 md:px-5">
                          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                            <div className="min-w-0 flex-1 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-semibold px-2 py-0.5 rounded border bg-teal-50 text-teal-900 border-teal-200">
                                  {contractorJobStatusLabel(wo)}
                                </span>
                                {overdue ? (
                                  <span className="text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded">At risk (SLA)</span>
                                ) : null}
          </div>
                              <p className="text-xs font-medium text-electric-teal uppercase tracking-wide">{getJobTypeLabel(wo)}</p>
                              <p className="font-semibold text-midnight-blue leading-snug">{wo.description || wo.work_order_id}</p>
                              <p className="text-sm text-gray-700">{wo.property_address || wo.property_id}</p>
                              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
                                <span>
                                  <span className="text-gray-400">Visit:</span> {schedWhen || schedLabel}
                                </span>
                                <span>
                                  <span className="text-gray-400">SLA:</span> {formatDate(wo.sla_complete_by)}
                                </span>
                                <span>
                                  <span className="text-gray-400">Value:</span> {getJobValueDisplay(wo)}
                                </span>
                              </div>
                              {reason ? (
                                <p className="text-xs text-red-800 bg-red-50 border border-red-100 rounded px-2 py-1.5">{reason}</p>
                              ) : null}
                              <p className="text-sm text-gray-700 border-t border-gray-100 pt-2 mt-1">
                                <span className="font-medium text-midnight-blue">Next step:</span> {nextLine}
                              </p>
                            </div>
                            <div className="flex flex-col items-stretch md:items-end gap-2 shrink-0 min-w-[10rem]">
                              {primaryAction ? (
                                <Button
                                  size="sm"
                                  className="bg-electric-teal hover:bg-electric-teal/90 text-white"
                                  disabled={!!actionLoading && actionLoading === wo.work_order_id}
                                  onClick={(e) => executeContractorAction(wo, primaryAction, e)}
                                >
                                  {actionLoading === wo.work_order_id ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                  ) : (
                                    <>
                                      {primaryAction.label}
                                      <ChevronRight className="w-4 h-4 ml-1" />
                                    </>
                                  )}
                                </Button>
                              ) : (
                                <p className="text-xs text-gray-500 md:text-right">No primary action — open job for details.</p>
                              )}
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="border-gray-300"
                                onClick={() => setDetailId(wo.work_order_id)}
                              >
                                Open job
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )
            ) : null}
            </section>

            <section ref={readyToInvoiceSectionRef} className="mb-10 scroll-mt-24" aria-label="Ready to invoice">
              <h2 className="text-lg font-bold text-midnight-blue mb-2 flex items-center gap-2">
                <FileText className="w-5 h-5 text-electric-teal" />
                Ready to invoice
              </h2>
              {readyToInvoiceJobs.length === 0 ? (
                <p className="text-sm text-gray-600 border border-dashed border-gray-200 rounded-lg px-4 py-6 bg-white text-center">
                  No jobs are ready to invoice yet.
                </p>
              ) : (
                <div className="space-y-3">
                  {readyToInvoiceJobs.map((wo) => {
                    const proofLine = wo.completion_proof_required
                      ? wo.completion_proof_satisfied
                        ? 'Completion proof on file'
                        : 'Proof still required — open the job to upload'
                      : 'Proof not required for this job type';
                    return (
                      <Card key={wo.work_order_id} className="border-l-4 border-l-violet-500 shadow-sm">
                        <CardContent className="py-4 px-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-semibold text-midnight-blue">{wo.description || wo.work_order_id}</p>
                            <p className="text-sm text-gray-600">{wo.property_address || wo.property_id}</p>
                            <p className="text-xs text-gray-500 mt-1">{proofLine}</p>
                            <p className="text-xs text-gray-500">Estimate: {getJobValueDisplay(wo)}</p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            className="shrink-0 bg-electric-teal hover:bg-electric-teal/90 text-white"
                            disabled={!isContractorInvoiceEligible(wo)}
                            onClick={(e) =>
                              executeContractorAction(wo, { id: 'submit_invoice', label: 'Submit invoice', section: 'billing' }, e)
                            }
                          >
                            Submit invoice
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </section>

            <section ref={waitingSectionRef} className="mb-10 scroll-mt-24" aria-label="Waiting on others">
              <h2 className="text-lg font-bold text-midnight-blue mb-2">Waiting on others</h2>
              <p className="text-xs text-gray-500 mb-4">
                Invoice review, client confirmation, payment processing, or holds — nothing for you to push until the client or system
                moves forward.
              </p>
              {waitingJobs.length === 0 ? (
                <p className="text-sm text-gray-600 border border-dashed border-gray-200 rounded-lg px-4 py-6 bg-white text-center">
                  Nothing in this queue. When a client is reviewing an invoice or confirming a visit, it will show here.
                </p>
              ) : (
                <div className="space-y-3">
                  {waitingJobs.map((wo) => {
                    const nextLine = contractorNextStepLineFromNextActions(wo);
                    const inv = wo.linked_invoice || invoiceByWorkOrderId[wo.work_order_id];
                    return (
                      <Card key={wo.work_order_id} className="border border-gray-200 bg-gray-50/60">
                        <CardContent className="py-4 px-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium text-midnight-blue">{wo.description || wo.work_order_id}</p>
                            <p className="text-sm text-gray-600">{wo.property_address || wo.property_id}</p>
                            <p className="text-sm text-gray-700 mt-2">{nextLine}</p>
                            {inv ? (
                              <p className="text-xs text-gray-500 mt-1">Invoice: {formatContractorInvoiceStateLabel(inv)}</p>
                            ) : null}
                            {(wo.operational_exception || '').trim() ? (
                              <p className="text-xs text-amber-900 mt-1">Hold: {(wo.operational_exception || '').replace(/_/g, ' ')}</p>
                            ) : null}
                          </div>
                          <Button type="button" size="sm" variant="outline" className="shrink-0" onClick={() => setDetailId(wo.work_order_id)}>
                            Open job
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </section>

            <section ref={completedMonthSectionRef} className="mb-10 scroll-mt-24" aria-label="Completed this month">
              <h2 className="text-base font-bold text-midnight-blue mb-3">Completed this month (UTC)</h2>
              {completedMonthJobs.length === 0 ? (
                <p className="text-sm text-gray-600">No jobs marked complete in the current UTC month yet.</p>
              ) : (
                <ul className="space-y-2 text-sm border border-gray-200 rounded-lg bg-white divide-y divide-gray-100">
                  {completedMonthJobs.map((wo) => (
                    <li key={wo.work_order_id} className="px-4 py-2 flex justify-between gap-2">
                      <span className="font-medium text-midnight-blue truncate">{wo.description || wo.work_order_id}</span>
                      <button
                        type="button"
                        className="text-electric-teal text-xs shrink-0 underline"
                        onClick={() => setDetailId(wo.work_order_id)}
                      >
                        Open
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="mt-6 scroll-mt-24" ref={invoicesSectionRef}>
              <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-electric-teal" />
                Payment history
              </h2>
              {invoicesError ? (
                <Alert variant="destructive" className="mb-4" data-testid="contractor-invoices-error">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    <span className="font-medium">Invoices</span>
                    <span className="block mt-1">{invoicesError}</span>
                  </AlertDescription>
                </Alert>
              ) : null}
              {invoicesRefreshing ? (
                <div className="flex gap-2 text-gray-500 py-4"><Loader2 className="w-5 h-5 animate-spin" /> Refreshing invoices…</div>
              ) : invoices.length === 0 && !invoicesError ? (
            <Card>
                  <CardContent className="py-6 text-center text-gray-600">
                    <p className="font-medium text-midnight-blue">No invoices submitted yet</p>
                    <p className="text-sm mt-2 text-gray-500">After you complete a job, you can submit an invoice from the work order details.</p>
                  </CardContent>
                </Card>
              ) : invoices.length > 0 ? (
                <Card>
                  <CardContent className="p-0 overflow-x-auto">
                    <table className="w-full text-sm min-w-[640px]">
                  <thead>
                    <tr className="border-b bg-gray-50">
                          <th className="text-left p-3 font-medium">Date paid</th>
                          <th className="text-left p-3 font-medium">Invoice</th>
                          <th className="text-left p-3 font-medium">Job</th>
                          <th className="text-left p-3 font-medium">Property</th>
                      <th className="text-right p-3 font-medium">Amount</th>
                          <th className="text-left p-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                        {paymentTableRows.map((inv) => {
                          const wo = workOrderById[inv.work_order_id];
                          return (
                      <tr key={inv.invoice_id} className="border-b last:border-0">
                              <td className="p-3 whitespace-nowrap">{formatDate(inv.paid_at) || '—'}</td>
                        <td className="p-3">{inv.reference || inv.invoice_id}</td>
                              <td className="p-3 max-w-[200px] truncate" title={wo?.description || inv.work_order_id}>
                                {wo?.description || inv.work_order_id || '—'}
                              </td>
                              <td className="p-3 max-w-[180px] truncate">{wo?.property_address || wo?.property_id || '—'}</td>
                              <td className="p-3 text-right whitespace-nowrap">
                                {inv.submitted_amount != null ? `£${Number(inv.submitted_amount).toFixed(2)}` : '—'}
                              </td>
                              <td className="p-3">
                                <span
                                  className={`px-1.5 py-0.5 rounded inline-block ${
                                    inv.status === 'approved' || inv.status === 'paid'
                                      ? 'bg-green-100 text-green-800'
                                      : inv.status === 'rejected'
                                        ? 'bg-red-100 text-red-800'
                                        : 'bg-amber-100 text-amber-800'
                                  }`}
                                >
                                  {formatContractorInvoiceStateLabel(inv)}
                                </span>
                              </td>
                      </tr>
                          );
                        })}
                  </tbody>
                </table>
              </CardContent>
            </Card>
              ) : null}
        </div>
          </>
        )}

        {/* Detail drawer */}
        {detailId && (
          <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={() => setDetailId(null)}>
            <div className="w-full max-w-3xl bg-white shadow-2xl overflow-y-auto border-l border-gray-200" onClick={(e) => e.stopPropagation()}>
              <div className="sticky top-0 z-10 flex items-start justify-between gap-3 p-4 border-b bg-white/95 backdrop-blur">
                <div className="min-w-0 pr-2">
                  <h2 className="font-semibold text-midnight-blue leading-snug">
                    {detailLoading ? 'Loading…' : detail?.description || detail?.work_order_id || 'Job'}
                  </h2>
                  {!detailLoading && detail ? (
                    <p className="text-xs text-gray-500 mt-1">
                      {getJobTypeLabel(detail)} · {detail.property_address || detail.property_id}
                    </p>
                  ) : null}
              </div>
                <button type="button" onClick={() => setDetailId(null)} className="p-1 rounded hover:bg-gray-100 shrink-0" aria-label="Close">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 md:p-6 space-y-8">
                {detailLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-electric-teal" />
                ) : detail ? (
                  <>
                    {(() => {
                      const primary = detailPrimaryAction;
                      return (
                        <section
                          className="rounded-xl border-2 border-electric-teal/80 bg-gradient-to-b from-teal-50 via-white to-white shadow-md p-5 md:p-6"
                          aria-label="Next action"
                        >
                          <p className="text-[11px] font-bold text-electric-teal uppercase tracking-[0.12em] mb-3">Next action</p>
                          {detailNextIdleMessage ? (
                            <p className="text-base text-midnight-blue font-medium leading-relaxed">{detailNextIdleMessage}</p>
                          ) : primary ? (
                            <>
                              {primary.hint ? (
                                <p className="text-base text-gray-800 leading-relaxed mb-5">{primary.hint}</p>
                              ) : null}
                              {detail.completion_proof_required &&
                              !detail.completion_proof_satisfied &&
                              ['IN_PROGRESS', 'AWAITING_PARTS'].includes((detail.status || '').toUpperCase()) ? (
                                <p className="text-sm font-medium text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 mb-4">
                                  Upload completion proof before completing this job
                                </p>
                              ) : null}
                              <Button
                                type="button"
                                size="lg"
                                className="w-full sm:w-auto min-h-[48px] px-8 text-base font-semibold bg-electric-teal hover:bg-electric-teal/90 text-white shadow-sm"
                                disabled={
                                  (!!actionLoading && actionLoading === detail.work_order_id) ||
                                  (primary.id === 'complete_job' &&
                                    detail.completion_proof_required &&
                                    !detail.completion_proof_satisfied)
                                }
                                onClick={(e) => executeContractorAction(detail, primary, e)}
                              >
                                {actionLoading === detail.work_order_id ? (
                                  <Loader2 className="w-5 h-5 animate-spin" />
                                ) : (
                                  primary.label
                                )}
                        </Button>
                            </>
                          ) : (
                            <p className="text-base text-gray-700">No action available right now.</p>
                          )}
                          <div className="mt-4 pt-4 border-t border-teal-100/80 flex flex-wrap gap-2 items-center">
                            <span className="text-xs text-gray-600 px-2 py-1 bg-white/90 rounded border border-gray-200">
                              Job status: {contractorJobStatusLabel(detail)} ({detail.status})
                            </span>
                          </div>
                        </section>
                      );
                    })()}

                    {(() => {
                      const progress = contractorDetailExecutionProgressFromWorkOrder(detail);
                      return (
                        <section className="rounded-xl border border-gray-200 bg-white p-4" aria-label="Progress indicator">
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Progress indicator</p>
                          <p className="text-[11px] text-gray-500 mb-2">Assigned → Scheduled → In progress → Proof uploaded → Completed → Closed</p>
                          <div className="flex flex-wrap items-center gap-1 text-[10px] sm:text-xs">
                            {progress.steps.map((label, idx) => {
                              const cancelled = progress.currentIndex < 0;
                              const active = !cancelled && progress.currentIndex === idx;
                              const done = !cancelled && progress.currentIndex > idx;
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
                        </section>
                      );
                    })()}

                    <section ref={scheduleSectionRef} aria-label="Visit and scheduling">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">Visit / scheduling</h3>
                      {getBlockOrCancelReason(detail) ? (
                        <p className="text-sm text-red-800 bg-red-50 border border-red-100 rounded-md p-3 mb-3">{getBlockOrCancelReason(detail)}</p>
                      ) : null}
                      {(() => {
                        const st = (detail.status || '').toUpperCase();
                        const woTerminal = ['CANCELLED', 'COMPLETED', 'CLOSED', 'VERIFIED'].includes(st);
                        const canUseSchedule = !woTerminal;
                        const hasVisit =
                          detail.scheduled_at && (detail.schedule_status || '').toLowerCase() !== 'cancelled';
                        const showProposeForm = detailActionIds.has('propose_visit') && canUseSchedule;
                        const markNoAccessAction = detailPortalActions.find((a) => a.id === 'mark_no_access');
                        const proposeVisitAction = detailPortalActions.find((a) => a.id === 'propose_visit');
                        return (
                          <div className="rounded-lg border border-gray-200 bg-white p-3 mb-2 text-sm">
                            {!hasVisit ? (
                              <>
                                <p className="font-medium text-midnight-blue mb-2">No visit scheduled</p>
                                {canUseSchedule && proposeVisitAction && detailPrimaryAction?.id !== 'propose_visit' ? (
                                  <div className="mb-3">
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      onClick={(e) => executeContractorAction(detail, proposeVisitAction, e)}
                                    >
                                      Propose time
                        </Button>
                      </div>
                                ) : null}
                              </>
                            ) : (
                              <>
                                <p className="font-medium text-midnight-blue mb-1">{scheduleLifecycleLabel(detail)}</p>
                                <p className="text-gray-700 text-sm mb-1">
                                  {formatScheduleInstant(detail.scheduled_at, detail.scheduled_timezone)}
                                </p>
                                {detail.scheduled_by ? (
                                  <p className="text-gray-600 text-xs mb-2">Set by: {scheduleProposedByLabel(detail.scheduled_by)}</p>
                                ) : null}
                              </>
                            )}
                            {canUseSchedule ? (
                              <div className="space-y-2 mt-2">
                                {showProposeForm ? (
                                  <div className="space-y-2 border-t border-gray-200 pt-2">
                                    <p className="text-xs font-medium text-gray-700">Propose time</p>
                                    <input
                                      type="datetime-local"
                                      className="border border-gray-200 rounded-md px-2 py-1.5 text-xs w-full max-w-xs"
                                      value={scheduleForm.datetimeLocal}
                                      onChange={(e) => setScheduleForm((f) => ({ ...f, datetimeLocal: e.target.value }))}
                                    />
                                    <input
                                      type="text"
                                      className="border border-gray-200 rounded-md px-2 py-1.5 text-xs w-full max-w-xs"
                                      placeholder="IANA timezone (e.g. Europe/London)"
                                      value={scheduleForm.timezone}
                                      onChange={(e) => setScheduleForm((f) => ({ ...f, timezone: e.target.value }))}
                                    />
                                    <input
                                      type="text"
                                      className="border border-gray-200 rounded-md px-2 py-1.5 text-xs w-full"
                                      placeholder="Notes (optional)"
                                      value={scheduleForm.notes}
                                      onChange={(e) => setScheduleForm((f) => ({ ...f, notes: e.target.value }))}
                                    />
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="secondary"
                                      disabled={scheduleActionLoading}
                                      onClick={handleProposeVisitSchedule}
                                    >
                                      Propose time
                                    </Button>
                                  </div>
                                ) : null}
                                <div className="flex flex-wrap gap-2">
                                  {detailActionIds.has('confirm_visit') ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="secondary"
                                      disabled={scheduleActionLoading}
                                      onClick={handleConfirmVisitSchedule}
                                    >
                                      Confirm visit
                                    </Button>
                                  ) : null}
                                  {detailActionIds.has('reschedule_visit') ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      disabled={scheduleActionLoading}
                                      onClick={handleRequestVisitReschedule}
                                    >
                                      Reschedule
                                    </Button>
                                  ) : null}
                                  {markNoAccessAction ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      disabled={!!actionLoading && actionLoading === detail.work_order_id}
                                      onClick={(e) => executeContractorAction(detail, markNoAccessAction, e)}
                                    >
                                      Mark no access
                                    </Button>
                                  ) : null}
                                  {detailActionIds.has('cancel_scheduled_visit') ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      className="text-amber-900 border-amber-200"
                                      disabled={scheduleActionLoading}
                                      onClick={(e) =>
                                        executeContractorAction(
                                          detail,
                                          { id: 'cancel_scheduled_visit', label: 'Cancel visit' },
                                          e,
                                        )
                                      }
                                    >
                                      Cancel visit
                                    </Button>
                                  ) : null}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })()}
                    </section>

                    <section aria-label="Completion proof">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">Completion proof</h3>
                      <p className="text-sm text-gray-700 mb-3 leading-relaxed">{getEvidenceGuidance(detail)}</p>
                      {detail.completion_proof_required ? (
                        <p className="text-xs font-medium text-amber-900 bg-amber-50 border border-amber-100 rounded px-2 py-1.5 mb-2">
                          {detail.completion_proof_satisfied
                            ? 'Completion proof on file — you can complete the job when ready.'
                            : 'Upload completion proof before completing this job'}
                        </p>
                      ) : null}
                      <p className="text-xs text-gray-500 mb-2">PDF, images, or Word — max 20MB. Accept the assignment first if the upload is disabled.</p>
                      {(detail.evidence_keys || []).length > 0 && (
                        <ul className="text-sm text-gray-700 mb-2 space-y-2 max-h-40 overflow-y-auto">
                          {(detail.evidence_keys || []).map((k) => {
                            const keyStr = typeof k === 'string' ? k : String(k);
                            const fileKey = isContractorFileEvidenceKey(keyStr);
                            return (
                              <li key={keyStr} className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2 last:border-0">
                                <span className="break-all text-xs">{contractorEvidenceFilenameFromKey(keyStr)}</span>
                                {fileKey ? (
                                  <span className="flex gap-1 shrink-0">
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      className="h-7 text-xs px-2"
                                      disabled={evidenceFileLoadingKey === keyStr}
                                      onClick={() => handleEvidenceFileOpen(keyStr, false)}
                                    >
                                      View
                                    </Button>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="ghost"
                                      className="h-7 text-xs px-2"
                                      disabled={evidenceFileLoadingKey === keyStr}
                                      onClick={() => handleEvidenceFileOpen(keyStr, true)}
                                    >
                                      Download
                                    </Button>
                                  </span>
                                ) : (
                                  <span className="text-xs text-gray-400 shrink-0">Linked ref</span>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      <label className="inline-flex items-center gap-2 text-sm font-medium text-midnight-blue cursor-pointer rounded-lg border border-electric-teal/40 bg-teal-50/50 px-4 py-2.5 hover:bg-teal-50">
                        <Upload className="w-4 h-4 shrink-0 text-electric-teal" />
                        <span>{evidenceUploading ? 'Uploading…' : 'Upload completion proof'}</span>
                        <input
                          ref={completionProofInputRef}
                          type="file"
                          className="sr-only"
                          accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,application/pdf"
                          disabled={evidenceUploading || detail.status === 'OPEN' || detail.status === 'ASSIGNED'}
                          onChange={onEvidenceSelected}
                        />
                      </label>
                    </section>

                    <section aria-label="Job actions">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">Job actions</h3>
                      <p className="text-xs text-gray-600 mb-2">
                        Only actions your client workflow currently allows (same list as the server). The primary step stays in Next
                        action above.
                      </p>
                      {detailJobPanelActions.length > 0 ? (
                        <div className="flex flex-wrap gap-2 mb-4">
                          {detailJobPanelActions.map((a) => (
                            <Button
                              key={a.id}
                              type="button"
                              size="sm"
                              variant="outline"
                              className="border-gray-300"
                              disabled={
                                (!!actionLoading && actionLoading === detail.work_order_id) ||
                                (a.id === 'complete_job' &&
                                  detail.completion_proof_required &&
                                  !detail.completion_proof_satisfied)
                              }
                              onClick={(e) => executeContractorAction(detail, a, e)}
                            >
                              {a.label}
                            </Button>
                          ))}
                      </div>
                      ) : (
                        <p className="text-sm text-gray-500 mb-2">No extra job actions right now — use Next action if shown.</p>
                      )}
                      {['CANCELLED'].includes((detail.status || '').toUpperCase()) ? (
                        <p className="text-sm text-gray-600">This job is cancelled — no further actions.</p>
                      ) : null}
                      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-gray-600 mt-3">
                        <div>
                          <dt className="text-gray-400">Work order ID</dt>
                          <dd className="font-mono break-all">{detail.work_order_id}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-400">Job value</dt>
                          <dd>{getJobValueDisplay(detail)}</dd>
                        </div>
                      </dl>
                    </section>

                    <section className="rounded-xl border border-violet-100 bg-violet-50/40 p-4" aria-label="Billing">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b border-violet-100 pb-2">
                        Billing
                      </h3>
                      {detailBillingPhase ? (
                        <p className="text-sm text-gray-800 mb-1">
                          <span className="font-medium text-gray-600">Invoice state: </span>
                          <span className="font-semibold text-midnight-blue">{detailBillingPhase.label}</span>
                        </p>
                      ) : null}
                      {detail.linked_invoice || invoiceByWorkOrderId[detail.work_order_id] ? (
                        <p className="text-xs text-gray-600 mb-3">
                          Detail:{' '}
                          {formatContractorInvoiceStateLabel(
                            detail.linked_invoice || invoiceByWorkOrderId[detail.work_order_id],
                          )}
                        </p>
                      ) : (
                        <p className="text-xs text-gray-600 mb-3">No invoice on file for this job yet.</p>
                      )}
                      {detailBillingPanelActions.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {detailBillingPanelActions.map((a) => (
                            <Button
                              key={a.id}
                              type="button"
                              size="sm"
                              variant={a.id === 'view_invoice' ? 'outline' : 'default'}
                              className={
                                a.id === 'submit_invoice' || a.id === 'edit_invoice'
                                  ? 'bg-electric-teal hover:bg-electric-teal/90 text-white border-0'
                                  : ''
                              }
                              disabled={!!actionLoading && actionLoading === detail.work_order_id}
                              onClick={(e) => executeContractorAction(detail, a, e)}
                            >
                              {contractorBillingActionButtonLabel(a, detail, invoiceByWorkOrderId)}
                      </Button>
                          ))}
                        </div>
                      ) : null}
                    </section>

                    <section aria-label="Timeline">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">Timeline</h3>
                      <p className="text-xs text-gray-500 mb-2">Chronological milestones (read-only).</p>
                      {detailTimelineSorted.length > 0 ? (
                        <ul className="text-xs text-gray-700 space-y-1.5 border border-gray-100 rounded-md p-3 bg-gray-50/80 max-h-48 overflow-y-auto">
                          {detailTimelineSorted.map((ev, idx) => (
                            <li
                              key={`${ev.label}-${ev.at}-${idx}`}
                              className="flex flex-col sm:flex-row sm:justify-between sm:gap-2 border-b border-gray-100/80 pb-1.5 last:border-0 last:pb-0"
                            >
                              <span className="font-medium text-midnight-blue">{ev.label}</span>
                              <span className="text-gray-600 tabular-nums">{formatScheduleInstant(ev.at, null)}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-500">No timeline events yet.</p>
                      )}
                    </section>

                    <section aria-label="Notes">
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">Notes</h3>
                      <div className="space-y-2">
                        <Input
                          placeholder="On-site / internal notes (optional)"
                          value={notesForm.contractor_notes}
                          onChange={(ev) => setNotesForm((f) => ({ ...f, contractor_notes: ev.target.value }))}
                          className="mb-1"
                        />
                        <Input
                          placeholder="Completion summary for the client (optional)"
                          value={notesForm.completion_notes}
                          onChange={(ev) => setNotesForm((f) => ({ ...f, completion_notes: ev.target.value }))}
                          className="mb-1"
                        />
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={handleSaveNotes}
                          disabled={!!actionLoading || evidenceUploading}
                        >
                          Save notes
                        </Button>
                      </div>
                    </section>
                  </>
                ) : (
                  <p className="text-gray-500">Could not load details.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Invoice modal */}
        {invoiceModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModal(null)}>
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <h3 className="text-lg font-semibold mb-4">
                {invoiceModal.mode === 'view'
                  ? 'View invoice'
                  : invoiceModal.mode === 'edit'
                    ? 'Edit and resubmit invoice'
                    : 'Submit invoice'}
              </h3>
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4">
                Pleerity coordinates work orders and invoice approval. Payment responsibility lies with the client. Pleerity does
                not process contractor payments. Follow up with the client for payment.
              </p>
              {invoiceModal.workOrder ? (
                <dl className="text-xs text-gray-600 space-y-1 mb-4 border border-gray-100 rounded-md p-3 bg-gray-50/80">
                  <div>
                    <dt className="inline text-gray-500">Job: </dt>
                    <dd className="inline font-medium text-midnight-blue">
                      {invoiceModal.workOrder.description || invoiceModal.workOrder.work_order_id}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-gray-500">Property: </dt>
                    <dd className="inline">{invoiceModal.workOrder.property_address || invoiceModal.workOrder.property_id}</dd>
                  </div>
                  <div>
                    <dt className="inline text-gray-500">Job ID: </dt>
                    <dd className="inline font-mono break-all">{invoiceModal.workOrder.work_order_id}</dd>
                  </div>
                  <div>
                    <dt className="inline text-gray-500">Visit / completion: </dt>
                    <dd className="inline">
                      {invoiceModal.workOrder.completed_at
                        ? formatScheduleInstant(invoiceModal.workOrder.completed_at, invoiceModal.workOrder.scheduled_timezone)
                        : invoiceModal.workOrder.scheduled_at
                          ? formatScheduleInstant(
                              invoiceModal.workOrder.scheduled_at,
                              invoiceModal.workOrder.scheduled_timezone,
                            )
                          : '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline text-gray-500">Estimate: </dt>
                    <dd className="inline">{getJobValueDisplay(invoiceModal.workOrder)}</dd>
                  </div>
                </dl>
              ) : null}
              <form onSubmit={handleSubmitInvoice} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Invoice reference{invoiceModal.mode === 'view' ? '' : ' *'}
                  </label>
                  <input
                    type="text"
                    readOnly={invoiceModal.mode === 'view'}
                    value={invoiceForm.reference}
                    onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))}
                    className="border border-gray-300 rounded-md px-3 py-2 w-full read-only:bg-gray-50"
                    placeholder="INV-001"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                  <textarea
                    readOnly={invoiceModal.mode === 'view'}
                    value={invoiceForm.description}
                    onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))}
                    className="border border-gray-300 rounded-md px-3 py-2 w-full read-only:bg-gray-50"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Amount £{invoiceModal.mode === 'view' ? '' : ' *'}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    readOnly={invoiceModal.mode === 'view'}
                    value={invoiceForm.submitted_amount}
                    onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))}
                    className="border border-gray-300 rounded-md px-3 py-2 w-full read-only:bg-gray-50"
                    placeholder="0.00"
                  />
                </div>
                <div className="flex gap-2">
                  {invoiceModal.mode !== 'view' ? (
                  <Button type="submit" disabled={invoiceSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                      {invoiceSaving ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : invoiceModal.mode === 'edit' ? (
                        'Resubmit invoice'
                      ) : (
                        'Submit invoice'
                      )}
                  </Button>
                  ) : null}
                  <Button type="button" variant="outline" onClick={() => setInvoiceModal(null)}>
                    {invoiceModal.mode === 'view' ? 'Close' : 'Cancel'}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
