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
  CheckCircle,
  XCircle,
  Upload,
  AlertCircle,
  Info,
  ClipboardList,
  PoundSterling,
  ChevronRight,
  CalendarClock,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  buildInvoiceByWorkOrderId,
  formatMoneyGbp,
  getAllowedNextStatuses,
  getBlockOrCancelReason,
  getEvidenceGuidance,
  getJobTypeLabel,
  getJobValueDisplay,
  getLifecycleBadge,
  getLifecycleStage,
  getNextStepMessage,
  isCompletedPipeline,
  isPendingScheduling,
  isSlaOverdue,
  sortWorkOrdersForDashboard,
  statusValueToLabel,
  toneToClasses,
} from '../../utils/contractorWorkflow';

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

function contractorMayConfirmSchedule(wo) {
  if ((wo?.schedule_status || '').toLowerCase() !== 'proposed') return false;
  const sb = (wo?.scheduled_by || '').toLowerCase();
  return sb === 'client' || sb === 'admin';
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
    if (detail) {
      setNotesForm({
        contractor_notes: detail.contractor_notes || '',
        completion_notes: detail.completion_notes || '',
      });
    }
  }, [detail]);

  const handleLogout = () => {
    localStorage.removeItem('contractor_token');
    localStorage.removeItem('contractor_user');
    navigate('/contractor/login', { replace: true });
  };

  const handleAccept = (id) => {
    setActionLoading(id);
    api.acceptAssignment(id)
      .then(() => {
        toast.success('Assignment accepted');
        loadWorkOrders();
        loadDashboardSummary();
        setDetailId(null);
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const handleDecline = (id) => {
    if (!confirm('Decline this assignment? The work order will be unassigned.')) return;
    setActionLoading(id);
    api.declineAssignment(id)
      .then(() => {
        toast.success('Assignment declined');
        loadWorkOrders();
        loadDashboardSummary();
        setDetailId(null);
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
  };

  const handleStatusChange = (id, status) => {
    setActionLoading(id);
    api.updateWorkOrder(id, { status })
      .then(() => {
        toast.success('Status updated');
        loadWorkOrders();
        loadDashboardSummary();
        if (detailId === id) api.getWorkOrder(id).then((r) => setDetail(r.data));
      })
      .catch((e) => toast.error(e.response?.data?.detail || 'Failed'))
      .finally(() => setActionLoading(null));
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
        return refreshContractorDetail(detail.work_order_id);
      })
      .then(() => loadWorkOrders())
      .then(() => loadDashboardSummary())
      .catch((e) => toast.error(e.response?.data?.detail || 'Request failed'))
      .finally(() => setScheduleActionLoading(false));
  };

  const handleCancelVisitSchedule = () => {
    if (!detail || !api) return;
    if (!window.confirm('Cancel this scheduled visit?')) return;
    setScheduleActionLoading(true);
    api
      .cancelSchedule(detail.work_order_id)
      .then(() => {
        toast.success('Visit cancelled');
        return refreshContractorDetail(detail.work_order_id);
      })
      .then(() => loadWorkOrders())
      .then(() => loadDashboardSummary())
      .catch((e) => toast.error(e.response?.data?.detail || 'Could not cancel'))
      .finally(() => setScheduleActionLoading(false));
  };

  const handleDownloadScheduleIcs = () => {
    if (!detail || !api) return;
    api
      .getScheduleIcs(detail.work_order_id)
      .then((res) => openBlobApiResponse(res, `visit-${detail.work_order_id}.ics`))
      .catch((e) => toast.error(e.response?.data?.detail || 'Download failed'));
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
    setInvoiceSaving(true);
    api.submitInvoice({
      work_order_id: invoiceModal.work_order_id,
      reference: invoiceForm.reference || undefined,
      description: invoiceForm.description || undefined,
      submitted_amount: invoiceForm.submitted_amount ? parseFloat(invoiceForm.submitted_amount) : undefined,
    })
      .then(() => {
        toast.success('Invoice submitted. It will appear in the client’s Approvals.');
        setInvoiceModal(null);
        setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
        setInvoicesRefreshing(true);
        loadInvoices()
          .then(() => loadDashboardSummary())
          .finally(() => setInvoicesRefreshing(false));
      })
      .catch((err) => toast.error(err.response?.data?.detail || 'Failed'))
      .finally(() => setInvoiceSaving(false));
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
            {!workOrdersError && !invoicesError && !profileError && workOrders.length === 0 && invoices.length === 0 && (
              <Alert className="mb-6 border-electric-teal/30 bg-teal-50/80">
                <Info className="h-4 w-4 text-electric-teal" />
                <AlertDescription>
                  <span className="font-medium text-midnight-blue">Your account is active.</span>
                  <span className="block mt-1 text-gray-700">
                    When a client assigns work to you, it will appear below. You can also open secure job links from assignment emails without signing in.
                  </span>
                </AlertDescription>
              </Alert>
            )}

            {dashboardSummaryError ? (
              <Alert className="mb-4 border-amber-200 bg-amber-50">
                <AlertCircle className="h-4 w-4 text-amber-700" />
                <AlertDescription className="text-amber-900 text-sm">{dashboardSummaryError}</AlertDescription>
              </Alert>
            ) : null}

            <section className="mb-8" aria-label="Action required summary">
              <h1 className="text-lg font-bold text-midnight-blue tracking-tight mb-3">Action required</h1>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Card className={`border-l-4 ${actionCounts.overdue > 0 ? 'border-l-red-500 shadow-sm' : 'border-l-red-200'}`}>
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-red-800">Overdue SLA</p>
                    <p className="text-3xl font-bold text-red-700 mt-1">{actionCounts.overdue ?? 0}</p>
                    <p className="text-xs text-gray-600 mt-1">Past agreed complete-by date — act today.</p>
                  </CardContent>
                </Card>
                <Card className={`border-l-4 ${actionCounts.pending_scheduling > 0 ? 'border-l-amber-500 shadow-sm' : 'border-l-amber-200'}`}>
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">Pending scheduling</p>
                    <p className="text-3xl font-bold text-amber-800 mt-1">{actionCounts.pending_scheduling ?? 0}</p>
                    <p className="text-xs text-gray-600 mt-1">Needs a confirmed visit time.</p>
                  </CardContent>
                </Card>
                <Card className="border-l-4 border-l-emerald-500">
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-900">Completed</p>
                    <p className="text-3xl font-bold text-emerald-800 mt-1">{actionCounts.completed ?? 0}</p>
                    <p className="text-xs text-gray-600 mt-1">Finished jobs (awaiting invoice if needed).</p>
                  </CardContent>
                </Card>
              </div>
            </section>

            <section className="mb-8" aria-label="Earnings and invoices">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <h2 className="text-lg font-bold text-midnight-blue flex items-center gap-2">
                  <PoundSterling className="w-5 h-5 text-electric-teal" />
                  Earnings &amp; invoices
                </h2>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="border-electric-teal text-midnight-blue"
                    onClick={() => {
                      const first = sortedWorkOrders.find(
                        (w) =>
                          ['COMPLETED', 'VERIFIED', 'CLOSED'].includes((w.status || '').toUpperCase()) &&
                          !invoiceByWorkOrderId[w.work_order_id],
                      );
                      if (first) {
                        setDetailId(first.work_order_id);
                        setTimeout(() => setInvoiceModal(first), 300);
                      } else {
                        toast.message('No completed jobs waiting for an invoice', {
                          description: 'Open a completed job from the list below to submit an invoice.',
                        });
                      }
                    }}
                  >
                    <FileText className="w-4 h-4 mr-1" />
                    Submit invoice
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => invoicesSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                  >
                    <ClipboardList className="w-4 h-4 mr-1" />
                    View payment history
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Card className="border border-gray-200 shadow-sm">
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-medium text-gray-500 uppercase">Pending approval</p>
                    <p className="text-2xl font-bold text-midnight-blue mt-1">
                      {formatMoneyGbp(earningsDisplay.pending_approval_total) || '£0.00'}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">With client for review.</p>
                  </CardContent>
                </Card>
                <Card className="border border-gray-200 shadow-sm">
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-medium text-gray-500 uppercase">Ready to invoice</p>
                    <p className="text-2xl font-bold text-midnight-blue mt-1">
                      {earningsDisplay.ready_to_invoice_jobs ?? 0}{' '}
                      <span className="text-sm font-normal text-gray-500">jobs</span>
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      Est. value {formatMoneyGbp(earningsDisplay.ready_to_invoice_estimated_total) || '£0.00'} (from job estimates)
                    </p>
                  </CardContent>
                </Card>
                <Card className="border border-gray-200 shadow-sm">
                  <CardContent className="pt-4 pb-4">
                    <p className="text-xs font-medium text-gray-500 uppercase">Paid this month</p>
                    <p className="text-2xl font-bold text-emerald-800 mt-1">
                      {formatMoneyGbp(earningsDisplay.paid_this_month_total) || '£0.00'}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">Recorded on invoices (UTC month).</p>
                  </CardContent>
                </Card>
              </div>
            </section>

            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <CalendarClock className="w-5 h-5 text-electric-teal" />
              My work orders
              {total > 0 ? <span className="text-sm font-normal text-gray-500">({total})</span> : null}
            </h2>
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
              <Card>
                <CardContent className="py-8 text-center text-gray-600">
                  <p className="font-medium text-midnight-blue">No work orders assigned yet</p>
                  <p className="text-sm mt-2 text-gray-500">Check your email for job links, or wait for your client to assign you.</p>
                </CardContent>
              </Card>
            ) : workOrders.length > 0 ? (
              <div className="space-y-4">
                {sortedWorkOrders.map((wo) => {
                  const stage = getLifecycleStage(wo, invoiceByWorkOrderId);
                  const badge = getLifecycleBadge(stage);
                  const overdue = isSlaOverdue(wo);
                  const borderClass = overdue ? 'border-l-red-500' : isPendingScheduling(wo) ? 'border-l-amber-400' : 'border-l-teal-500';
                  const reason = getBlockOrCancelReason(wo);
                  const nextLine = getNextStepMessage(wo, invoiceByWorkOrderId);
                  return (
                    <Card
                      key={wo.work_order_id}
                      className={`cursor-pointer hover:shadow-md transition-shadow border-l-4 ${borderClass} overflow-hidden`}
                      onClick={() => setDetailId(wo.work_order_id)}
                    >
                      <CardContent className="py-4 px-4 md:px-5">
                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                          <div className="min-w-0 flex-1 space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${toneToClasses(badge.tone)}`}>
                                {badge.label}
                              </span>
                              {overdue ? (
                                <span className="text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded">SLA overdue</span>
                              ) : null}
                            </div>
                            <p className="text-xs font-medium text-electric-teal uppercase tracking-wide">{getJobTypeLabel(wo)}</p>
                            <p className="font-semibold text-midnight-blue leading-snug">{wo.description || wo.work_order_id}</p>
                            <p className="text-sm text-gray-700">{wo.property_address || wo.property_id}</p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
                              <span>
                                <span className="text-gray-400">SLA / due:</span> {formatDate(wo.sla_complete_by)}
                              </span>
                              <span>
                                <span className="text-gray-400">Job value:</span> {getJobValueDisplay(wo)}
                              </span>
                            </div>
                            {reason ? (
                              <p className="text-xs text-red-800 bg-red-50 border border-red-100 rounded px-2 py-1.5">{reason}</p>
                            ) : null}
                            <p className="text-sm text-gray-700 border-t border-gray-100 pt-2 mt-1">
                              <span className="font-medium text-midnight-blue">Next step:</span> {nextLine}
                            </p>
                          </div>
                          <div className="flex md:flex-col items-center md:items-end gap-2 shrink-0">
                            <Button
                              size="sm"
                              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDetailId(wo.work_order_id);
                              }}
                            >
                              View details
                              <ChevronRight className="w-4 h-4 ml-1" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            ) : null}

            {/* My invoices */}
            <div className="mt-10 scroll-mt-24" ref={invoicesSectionRef}>
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Payment history</h2>
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
                  <CardContent className="p-0">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-gray-50">
                          <th className="text-left p-3 font-medium">Reference</th>
                          <th className="text-right p-3 font-medium">Amount</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Submitted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoices.map((inv) => (
                          <tr key={inv.invoice_id} className="border-b last:border-0">
                            <td className="p-3">{inv.reference || inv.invoice_id}</td>
                            <td className="p-3 text-right">{inv.submitted_amount != null ? `£${Number(inv.submitted_amount).toFixed(2)}` : '—'}</td>
                            <td className="p-3"><span className={`px-1.5 py-0.5 rounded ${inv.status === 'approved' || inv.status === 'paid' ? 'bg-green-100 text-green-800' : inv.status === 'rejected' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}`}>{inv.status || '—'}</span></td>
                            <td className="p-3">{formatDate(inv.submitted_at)}</td>
                          </tr>
                        ))}
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
            <div className="w-full max-w-2xl bg-white shadow-2xl overflow-y-auto border-l border-gray-200" onClick={(e) => e.stopPropagation()}>
              <div className="sticky top-0 z-10 flex items-center justify-between p-4 border-b bg-white/95 backdrop-blur">
                <h2 className="font-semibold text-midnight-blue">Job control</h2>
                <button type="button" onClick={() => setDetailId(null)} className="p-1 rounded hover:bg-gray-100"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-4 md:p-6 space-y-8">
                {detailLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-electric-teal" />
                ) : detail ? (
                  <>
                    {(() => {
                      const dStage = getLifecycleStage(detail, invoiceByWorkOrderId);
                      const dBadge = getLifecycleBadge(dStage);
                      const nextLine = getNextStepMessage(detail, invoiceByWorkOrderId);
                      return (
                        <section className="rounded-xl border border-gray-200 bg-slate-50/80 p-4">
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Next step</p>
                          <p className="text-sm text-midnight-blue leading-relaxed">{nextLine}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className={`text-xs font-semibold px-2 py-1 rounded border ${toneToClasses(dBadge.tone)}`}>{dBadge.label}</span>
                            <span className="text-xs text-gray-500 px-2 py-1 bg-white rounded border border-gray-200">
                              System status: {detail.status}
                            </span>
                          </div>
                        </section>
                      );
                    })()}

                    <section>
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">A. Job overview</h3>
                      <p className="font-semibold text-midnight-blue mb-1">{detail.description || detail.work_order_id}</p>
                      <p className="text-sm text-electric-teal font-medium mb-3">{getJobTypeLabel(detail)}</p>
                      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                        <div>
                          <dt className="text-gray-500">Property</dt>
                          <dd className="font-medium text-gray-900">{detail.property_address || detail.property_id}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">Job value (estimate)</dt>
                          <dd className="font-medium text-gray-900">{getJobValueDisplay(detail)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">SLA complete by</dt>
                          <dd className="font-medium text-gray-900">{formatDate(detail.sla_complete_by)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">Work order ID</dt>
                          <dd className="font-mono text-xs text-gray-700 break-all">{detail.work_order_id}</dd>
                        </div>
                      </dl>
                    </section>

                    <section>
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">B. Required actions</h3>
                      {getBlockOrCancelReason(detail) ? (
                        <p className="text-sm text-red-800 bg-red-50 border border-red-100 rounded-md p-3 mb-3">{getBlockOrCancelReason(detail)}</p>
                      ) : null}
                    {(detail.status === 'ASSIGNED' || detail.status === 'OPEN') && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        <Button size="sm" onClick={() => handleAccept(detail.work_order_id)} disabled={!!actionLoading}>
                          {actionLoading === detail.work_order_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                          Accept assignment
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleDecline(detail.work_order_id)} disabled={!!actionLoading}>
                          <XCircle className="w-4 h-4 mr-1" /> Decline
                        </Button>
                      </div>
                    )}
                    {(() => {
                      const st = (detail.status || '').toUpperCase();
                      const woTerminal = ['CANCELLED', 'COMPLETED', 'CLOSED', 'VERIFIED'].includes(st);
                      const ss = (detail.schedule_status || '').toLowerCase();
                      const canUseSchedule = !woTerminal;
                      const showPropose =
                        canUseSchedule &&
                        (!ss || ss === 'cancelled' || ss === 'reschedule_requested' || (!detail.scheduled_at && !ss));
                      const showReschedule =
                        canUseSchedule && detail.scheduled_at && (ss === 'proposed' || ss === 'confirmed');
                      const showCancel =
                        canUseSchedule &&
                        detail.scheduled_at &&
                        ss !== 'cancelled' &&
                        ss !== 'completed';
                      return (
                        <div className="rounded-lg border border-gray-200 bg-white p-3 mb-2 text-sm">
                          <p className="font-medium text-midnight-blue mb-2">Visit scheduling</p>
                          <p className="text-gray-800 mb-1">{scheduleLifecycleLabel(detail)}</p>
                          {detail.scheduled_at ? (
                            <p className="text-gray-700 text-xs mb-1">
                              {formatScheduleInstant(detail.scheduled_at, detail.scheduled_timezone)}
                            </p>
                          ) : null}
                          {detail.scheduled_by ? (
                            <p className="text-gray-600 text-xs mb-2">Set by: {scheduleProposedByLabel(detail.scheduled_by)}</p>
                          ) : (
                            <p className="text-gray-600 text-xs mb-2">&nbsp;</p>
                          )}
                          {canUseSchedule ? (
                            <div className="space-y-2 mt-2">
                              {showPropose ? (
                                <div className="space-y-2 border-t border-gray-200 pt-2">
                                  <p className="text-xs font-medium text-gray-700">Propose visit time</p>
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
                                    Propose visit time
                                  </Button>
                                </div>
                              ) : null}
                              <div className="flex flex-wrap gap-2">
                                {contractorMayConfirmSchedule(detail) ? (
                                  <Button type="button" size="sm" disabled={scheduleActionLoading} onClick={handleConfirmVisitSchedule}>
                                    Confirm visit
                                  </Button>
                                ) : null}
                                {showReschedule ? (
                                  <Button type="button" size="sm" variant="outline" disabled={scheduleActionLoading} onClick={handleRequestVisitReschedule}>
                                    Request change
                                  </Button>
                                ) : null}
                                {showCancel ? (
                                  <Button type="button" size="sm" variant="outline" disabled={scheduleActionLoading} onClick={handleCancelVisitSchedule}>
                                    Cancel visit
                                  </Button>
                                ) : null}
                                {detail.scheduled_at ? (
                                  <Button type="button" size="sm" variant="ghost" disabled={scheduleActionLoading} onClick={handleDownloadScheduleIcs}>
                                    Download .ics
                                  </Button>
                                ) : null}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      );
                    })()}
                    </section>

                    <section>
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">C. Evidence upload</h3>
                      <p className="text-sm text-gray-700 mb-3 leading-relaxed">{getEvidenceGuidance(detail)}</p>
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
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                        <Upload className="w-4 h-4 shrink-0 text-electric-teal" />
                        <span>{evidenceUploading ? 'Uploading…' : 'Choose file'}</span>
                        <input
                          type="file"
                          className="sr-only"
                          accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,application/pdf"
                          disabled={evidenceUploading || detail.status === 'OPEN' || detail.status === 'ASSIGNED'}
                          onChange={onEvidenceSelected}
                        />
                      </label>
                    </section>

                    <section>
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">D. Progress &amp; billing</h3>
                      <p className="text-xs text-gray-600 mb-2">
                        Current job status: <strong className="text-midnight-blue">{detail.status}</strong>. Progress is{' '}
                        <strong>one step at a time</strong> (for example, mark in progress before complete).
                      </p>
                      {!['OPEN', 'ASSIGNED'].includes((detail.status || '').toUpperCase()) &&
                      !['CANCELLED', 'COMPLETED', 'CLOSED', 'VERIFIED'].includes((detail.status || '').toUpperCase()) ? (
                        <div className="space-y-2 mb-4">
                          <p className="text-xs font-medium text-gray-600">Set status to:</p>
                          <div className="flex flex-wrap gap-2">
                            {getAllowedNextStatuses(detail).map((val) => (
                              <Button
                                key={val}
                                type="button"
                                size="sm"
                                variant={detail.status === val ? 'default' : 'outline'}
                                className={detail.status === val ? 'bg-electric-teal hover:bg-electric-teal/90' : ''}
                                disabled={!!actionLoading || detail.status === val}
                                onClick={() => handleStatusChange(detail.work_order_id, val)}
                              >
                                {statusValueToLabel(val)}
                              </Button>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {['CANCELLED'].includes((detail.status || '').toUpperCase()) ? (
                        <p className="text-sm text-gray-600">This job is closed — no status changes.</p>
                      ) : null}
                      {['COMPLETED', 'VERIFIED', 'CLOSED'].includes((detail.status || '').toUpperCase()) ? (
                        <div className="space-y-3">
                          <p className="text-sm text-gray-700">Work is marked complete. Submit an invoice for the client to approve and record payment.</p>
                          {!invoiceByWorkOrderId[detail.work_order_id] ? (
                            <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" onClick={() => setInvoiceModal(detail)}>
                              <FileText className="w-4 h-4 mr-1" /> Submit invoice
                            </Button>
                          ) : (
                            <p className="text-sm text-gray-600">
                              Invoice status:{' '}
                              <span className="font-medium">{invoiceByWorkOrderId[detail.work_order_id].status || '—'}</span>
                            </p>
                          )}
                        </div>
                      ) : null}
                    </section>

                    <section>
                      <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-2">E. Notes</h3>
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
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
              <h3 className="text-lg font-semibold mb-4">Submit invoice</h3>
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4">Pleerity coordinates work orders and invoice approval. Payment responsibility lies with the client. Pleerity does not process contractor payments. Follow up with the client for payment.</p>
              <form onSubmit={handleSubmitInvoice} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Reference (optional)</label>
                  <input type="text" value={invoiceForm.reference} onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" placeholder="INV-001" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                  <textarea value={invoiceForm.description} onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" rows={2} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Amount £ (optional)</label>
                  <input type="number" step="0.01" min="0" value={invoiceForm.submitted_amount} onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))} className="border border-gray-300 rounded-md px-3 py-2 w-full" placeholder="0.00" />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={invoiceSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                    {invoiceSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setInvoiceModal(null)}>Cancel</Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
