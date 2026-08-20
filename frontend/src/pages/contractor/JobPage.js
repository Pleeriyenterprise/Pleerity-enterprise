/**
 * Secure job link page: contractor interacts with a single job via token (no login).
 * Token is in URL ?token=... from assignment email.
 * Optimised for fast first paint: preconnect to API host, layout shell while loading, next action first.
 */
import React, { useState, useEffect, useLayoutEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  createJobLinkAPI,
  openBlobApiResponse,
  contractorEvidenceFilenameFromKey,
  isContractorFileEvidenceKey,
  parseApiError,
  parseJobLinkError,
} from '../../api/client';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Wrench, Loader2, FileText, CheckCircle, XCircle, AlertCircle, Upload, Zap } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import {
  contractorPortalExecutableActions,
  contractorListPrimaryAction,
  contractorDrawerPrimaryPresentation,
  contractorNextStepLineFromNextActions,
  defaultInvoiceAmountFieldFromWorkOrder,
  formatContractorInvoiceStateLabel,
} from '../../utils/contractorWorkflow';
import { fireContractorWorkflowUsage } from '../../utils/contractorWorkflowUsage';
import { invoiceDisplayLabel } from '../../utils/invoiceDisplay';
import { operationalLabelForToken } from '../../utils/presentationLanguage';

const QUOTE_REVISION_REASON_LABELS = {
  price_too_high: 'Price too high',
  scope_unclear: 'Scope unclear',
  missing_breakdown: 'Missing breakdown',
  wrong_work_proposed: 'Wrong work proposed',
  incomplete_quote: 'Incomplete quote',
  timeline_unsuitable: 'Timeline unsuitable',
  other: 'Other',
};

function formatDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString(undefined, { dateStyle: 'short' });
  } catch {
    return String(s);
  }
}

function evidenceUploadErrorMessage(err) {
  const base = parseApiError(err, 'Upload failed');
  if (/Unsupported file type/i.test(base || '')) {
    return 'Unsupported file type. Upload PDF, JPG/JPEG, PNG, DOC, or DOCX (max 20MB). Upload does not auto-verify evidence.';
  }
  return base;
}

const STATUS_OPTIONS = [
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'AWAITING_PARTS', label: 'Awaiting parts' },
  { value: 'COMPLETED', label: 'Completed' },
];

const SCHEDULE_TZ_OPTIONS = [
  { value: 'Europe/London', label: 'UK (London)' },
  { value: 'Europe/Dublin', label: 'Ireland (Dublin)' },
  { value: 'UTC', label: 'UTC' },
];

export default function JobPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [workOrder, setWorkOrder] = useState(null);
  const [linkContext, setLinkContext] = useState(null);
  const [loading, setLoading] = useState(() => !!token);
  const [loadError, setLoadError] = useState(null);
  const [activationResendMessage, setActivationResendMessage] = useState('');
  const [activationResending, setActivationResending] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [invoiceModal, setInvoiceModal] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState({ reference: '', description: '', submitted_amount: '' });
  const [invoiceSaving, setInvoiceSaving] = useState(false);
  const [quoteOpen, setQuoteOpen] = useState(false);
  const [quoteForm, setQuoteForm] = useState({ amount: '', notes: '' });
  const [quoteSaving, setQuoteSaving] = useState(false);
  const [notesForm, setNotesForm] = useState({ contractor_notes: '', completion_notes: '' });
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [evidenceFileLoadingKey, setEvidenceFileLoadingKey] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({ datetimeLocal: '', timezone: 'Europe/London' });

  const evidenceSectionRef = useRef(null);
  const evidenceFileInputRef = useRef(null);
  const nextActionRef = useRef(null);
  const jobLinkOpenUsageWidRef = useRef(null);
  const loadErrorToastKeyRef = useRef(null);

  const api = useMemo(() => (token ? createJobLinkAPI(token) : null), [token]);

  const loadWorkOrder = useCallback(() => {
    if (!api) return Promise.resolve();
    setLoading(true);
    setLoadError(null);
    return api
      .getWorkOrder()
      .then((res) => {
        setWorkOrder(res.data);
        setLoadError(null);
        loadErrorToastKeyRef.current = null;
        const wid = res.data?.work_order_id;
        if (wid && jobLinkOpenUsageWidRef.current !== wid) {
          jobLinkOpenUsageWidRef.current = wid;
          fireContractorWorkflowUsage(api.postWorkflowUsage, { event_type: 'job_opened', work_order_id: wid });
        }
      })
      .catch((err) => {
        const parsed = parseJobLinkError(err);
        if (parsed.errorCode === 'ACTIVATION_REQUIRED') {
          setLinkContext((prev) =>
            prev
              ? { ...prev, activation_required: true, message: parsed.message }
              : {
                  activation_required: true,
                  message: parsed.message,
                  return_job_path: `/job?token=${token}`,
                },
          );
          setWorkOrder(null);
          setLoadError(null);
          return;
        }
        setLoadError(parsed);
        setWorkOrder(null);
        const toastKey = parsed.errorCode || parsed.message;
        if (loadErrorToastKeyRef.current !== toastKey) {
          loadErrorToastKeyRef.current = toastKey;
          toast.error(parsed.message);
        }
      })
      .finally(() => setLoading(false));
  }, [api, token]);

  const loadJobEntry = useCallback(() => {
    if (!api) return Promise.resolve();
    setLoading(true);
    setLoadError(null);
    setActivationResendMessage('');
    return api
      .getLinkContext()
      .then((res) => {
        const ctx = res.data || {};
        setLinkContext(ctx);
        if (ctx.activation_required) {
          setWorkOrder(null);
          setLoadError(null);
          setLoading(false);
          return;
        }
        return loadWorkOrder();
      })
      .catch((err) => {
        const parsed = parseJobLinkError(err);
        setLoadError(parsed);
        setWorkOrder(null);
        setLoading(false);
        const toastKey = parsed.errorCode || parsed.message;
        if (loadErrorToastKeyRef.current !== toastKey) {
          loadErrorToastKeyRef.current = toastKey;
          toast.error(parsed.message);
        }
      });
  }, [api, loadWorkOrder]);

  const handleRequestPortalActivation = useCallback(() => {
    if (!api) return;
    setActivationResending(true);
    setActivationResendMessage('');
    api
      .requestPortalActivation()
      .then((res) => {
        setActivationResendMessage(res.data?.message || 'Check your email for the portal activation link.');
      })
      .catch((err) => {
        setActivationResendMessage(parseApiError(err, 'Could not send activation email. Contact the client.'));
      })
      .finally(() => setActivationResending(false));
  }, [api]);

  const handleRetryAfterActivation = useCallback(() => {
    if (!api) return;
    setLinkContext(null);
    loadJobEntry();
  }, [api, loadJobEntry]);

  /**
   * Start the work-order fetch on layout (before paint) so the request begins marginally earlier than useEffect.
   * Keep this only where the extra paint cycle is justified; do not copy blindly to other screens.
   */
  useLayoutEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    loadJobEntry();
  }, [token, loadJobEntry]);

  /** Preconnect to API origin when backend URL is absolute (cuts first-request latency). */
  useEffect(() => {
    if (!token || typeof document === 'undefined') return;
    const raw = (process.env.REACT_APP_BACKEND_URL || '').trim();
    if (!raw) return;
    try {
      const u = new URL(raw);
      const href = `${u.protocol}//${u.host}`;
      const id = 'cvp-job-link-preconnect';
      if (document.getElementById(id)) return;
      const link = document.createElement('link');
      link.id = id;
      link.rel = 'preconnect';
      link.href = href;
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
      return () => {
        const el = document.getElementById(id);
        if (el && el.parentNode) el.parentNode.removeChild(el);
      };
    } catch {
      return undefined;
    }
  }, [token]);

  useEffect(() => {
    if (workOrder) {
      setNotesForm({
        contractor_notes: workOrder.contractor_notes || '',
        completion_notes: workOrder.completion_notes || '',
      });
    }
  }, [workOrder]);

  const primaryAction = useMemo(
    () => (workOrder ? contractorListPrimaryAction(workOrder) : null),
    [workOrder],
  );
  const primaryPresentation = useMemo(
    () => (workOrder ? contractorDrawerPrimaryPresentation(workOrder) : { mode: 'none' }),
    [workOrder],
  );
  const nextStepLine = useMemo(
    () => (workOrder ? contractorNextStepLineFromNextActions(workOrder) : ''),
    [workOrder],
  );

  const scrollToEvidence = useCallback(() => {
    evidenceSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => evidenceFileInputRef.current?.focus?.(), 400);
  }, []);

  const handleAccept = useCallback(() => {
    if (!api || !workOrder?.work_order_id) return;
    fireContractorWorkflowUsage(api.postWorkflowUsage, {
      event_type: 'action_taken',
      work_order_id: workOrder.work_order_id,
      action_id: 'accept_assignment',
    });
    setActionLoading(true);
    api
      .acceptAssignment()
      .then(() => {
        toast.success('Assignment accepted');
        return loadWorkOrder();
      })
      .catch((e) => toast.error(parseApiError(e, 'Could not accept assignment')))
      .finally(() => setActionLoading(false));
  }, [api, loadWorkOrder, workOrder?.work_order_id]);

  const handleDecline = useCallback(() => {
    if (!api || !workOrder?.work_order_id) return;
    if (!window.confirm('Decline this assignment? The job will be unassigned.')) return;
    const wid = workOrder.work_order_id;
    fireContractorWorkflowUsage(api.postWorkflowUsage, {
      event_type: 'action_taken',
      work_order_id: wid,
      action_id: 'decline_assignment',
    });
    setActionLoading(true);
    api
      .declineAssignment()
      .then(() => {
        toast.success('Assignment declined');
        setWorkOrder(null);
        setLoadError({
          title: 'Assignment declined',
          message: 'You have declined this assignment. You can close this page.',
        });
      })
      .catch((e) => toast.error(parseApiError(e, 'Could not decline assignment')))
      .finally(() => setActionLoading(false));
  }, [api, workOrder?.work_order_id]);

  const handleStatusChange = useCallback(
    (status) => {
      if (!api || !workOrder?.work_order_id) return;
      const wid = workOrder.work_order_id;
      setActionLoading(true);
      api
        .updateWorkOrder({ status })
        .then((res) => {
          const completed = (status || '').toUpperCase() === 'COMPLETED';
          if (completed) {
            const id = res?.data?.work_order_id || wid;
            fireContractorWorkflowUsage(api.postWorkflowUsage, { event_type: 'job_completed', work_order_id: id });
          }
          toast.success('Status updated');
          return loadWorkOrder();
        })
        .catch((e) => toast.error(parseApiError(e, 'Could not update status')))
        .finally(() => setActionLoading(false));
    },
    [api, loadWorkOrder, workOrder?.work_order_id],
  );

  const handleSaveNotes = useCallback(() => {
    if (!api) return;
    setActionLoading(true);
    api
      .updateWorkOrder({
        contractor_notes: notesForm.contractor_notes || undefined,
        completion_notes: notesForm.completion_notes || undefined,
      })
      .then(() => {
        toast.success('Notes saved');
        return loadWorkOrder();
      })
      .catch((e) => toast.error(parseApiError(e, 'Could not save notes')))
      .finally(() => setActionLoading(false));
  }, [api, notesForm, loadWorkOrder]);

  const onEvidenceSelected = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file || !api || !workOrder?.work_order_id) return;
      const wid = workOrder.work_order_id;
      setEvidenceUploading(true);
      api
        .uploadWorkOrderEvidence(file)
        .then(() => {
          toast.success('Evidence uploaded. It still needs landlord/admin review before it counts as verified.');
          fireContractorWorkflowUsage(api.postWorkflowUsage, { event_type: 'proof_uploaded', work_order_id: wid });
          return loadWorkOrder();
        })
        .catch((err) => toast.error(evidenceUploadErrorMessage(err)))
        .finally(() => {
          setEvidenceUploading(false);
          e.target.value = '';
        });
    },
    [api, loadWorkOrder, workOrder?.work_order_id],
  );

  const handleEvidenceFileOpen = useCallback(
    (storageKey, download) => {
      if (!api) return;
      setEvidenceFileLoadingKey(storageKey);
      api
        .downloadWorkOrderEvidenceFile(storageKey, download)
        .then((res) =>
          openBlobApiResponse(res, {
            download,
            fallbackFilename: contractorEvidenceFilenameFromKey(storageKey),
          }),
        )
        .catch((err) => {
          toast.error(parseApiError(err, 'Could not open file'));
        })
        .finally(() => setEvidenceFileLoadingKey(null));
    },
    [api],
  );

  const openInvoiceModal = useCallback(() => {
    if (!workOrder) return;
    const billingAction = contractorPortalExecutableActions(workOrder).find((a) =>
      ['submit_invoice', 'view_invoice', 'edit_invoice'].includes(a.id),
    );
    if (!billingAction) return;
    const li = workOrder.linked_invoice;
    if (billingAction.id === 'submit_invoice') {
      setInvoiceForm({
        reference: '',
        description: '',
        submitted_amount: defaultInvoiceAmountFieldFromWorkOrder(workOrder),
      });
      setInvoiceModal({ mode: 'create' });
      return;
    }
    setInvoiceForm({
      reference: li?.contractor_reference || li?.reference || '',
      description: li?.description || '',
      submitted_amount: li?.submitted_amount != null ? String(li.submitted_amount) : '',
    });
    setInvoiceModal({ mode: billingAction.id === 'edit_invoice' ? 'edit' : 'view' });
  }, [workOrder]);

  const openQuoteDialog = useCallback(() => {
    if (!workOrder) return;
    setQuoteForm({
      amount: defaultInvoiceAmountFieldFromWorkOrder(workOrder),
      notes: '',
    });
    setQuoteOpen(true);
  }, [workOrder]);

  const handleSubmitQuote = useCallback(
    (e) => {
      e.preventDefault();
      if (!api) return;
      const amt = parseFloat(String(quoteForm.amount).replace(/,/g, ''));
      if (Number.isNaN(amt) || amt <= 0) {
        toast.error('Enter a valid quote amount greater than zero');
        return;
      }
      setQuoteSaving(true);
      api
        .submitQuote({
          amount: amt,
          notes: (quoteForm.notes || '').trim() || undefined,
        })
        .then(() => {
          toast.success(
            workOrder?.pricing?.revision_active
              ? 'Revised quote submitted for client approval'
              : 'Quote submitted for client approval',
          );
          setQuoteOpen(false);
          setQuoteForm({ amount: '', notes: '' });
          return loadWorkOrder();
        })
        .catch((err) => toast.error(parseApiError(err, 'Could not submit quote')))
        .finally(() => setQuoteSaving(false));
    },
    [api, quoteForm, loadWorkOrder, workOrder?.pricing?.revision_active],
  );

  const handleSubmitInvoice = useCallback(
    (e) => {
      e.preventDefault();
      if (!api || !invoiceModal) return;
      if (invoiceModal.mode === 'view') return;
      const ref = (invoiceForm.reference || '').trim();
      const amt = parseFloat(String(invoiceForm.submitted_amount).replace(/,/g, ''));
      if (Number.isNaN(amt) || amt <= 0) {
        toast.error('Enter a valid invoice amount greater than zero');
        return;
      }
      setInvoiceSaving(true);
      api
        .submitInvoice({
          ...(ref ? { contractor_reference: ref } : {}),
          description: (invoiceForm.description || '').trim() || undefined,
          submitted_amount: amt,
        })
        .then(() => {
          toast.success(
            invoiceModal.mode === 'edit'
              ? 'Invoice updated and resubmitted for approval.'
              : 'Invoice submitted for approval.',
          );
          setInvoiceModal(null);
          setInvoiceForm({ reference: '', description: '', submitted_amount: '' });
          return loadWorkOrder();
        })
        .catch((err) => toast.error(parseApiError(err, 'Could not submit invoice')))
        .finally(() => setInvoiceSaving(false));
    },
    [api, invoiceModal, invoiceForm, loadWorkOrder],
  );

  const handleProposeSchedule = useCallback(() => {
    if (!api) return;
    if (!scheduleForm.datetimeLocal) {
      toast.error('Choose a visit date and time');
      return;
    }
    const raw =
      scheduleForm.datetimeLocal.length === 16 ? `${scheduleForm.datetimeLocal}:00` : scheduleForm.datetimeLocal;
    setActionLoading(true);
    api
      .proposeSchedule({
        scheduled_at: raw,
        timezone: scheduleForm.timezone,
      })
      .then(() => {
        toast.success('Visit time proposed');
        if (workOrder?.work_order_id) {
          fireContractorWorkflowUsage(api.postWorkflowUsage, {
            event_type: 'action_taken',
            work_order_id: workOrder.work_order_id,
            action_id: 'propose_visit',
          });
        }
        return loadWorkOrder();
      })
      .catch((e) => toast.error(parseApiError(e, 'Could not propose visit time')))
      .finally(() => setActionLoading(false));
  }, [api, scheduleForm, loadWorkOrder, workOrder?.work_order_id]);

  const handlePrimaryOrNextAction = useCallback(
    (action) => {
      if (!action?.id || !workOrder || !api) return;
      const aid = action.id;
      const wid = workOrder.work_order_id;
      const logActionTaken = () =>
        fireContractorWorkflowUsage(api.postWorkflowUsage, {
          event_type: 'action_taken',
          work_order_id: wid,
          action_id: aid,
        });
      if (aid === 'open_job_detail') {
        nextActionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      if (aid === 'accept_assignment') {
        handleAccept();
        return;
      }
      if (aid === 'decline_assignment') {
        handleDecline();
        return;
      }
      if (aid === 'upload_completion_proof') {
        logActionTaken();
        scrollToEvidence();
        toast.message('Upload your file in the Evidence section below.');
        return;
      }
      if (aid === 'start_job') {
        logActionTaken();
        handleStatusChange('IN_PROGRESS');
        return;
      }
      if (aid === 'awaiting_parts') {
        logActionTaken();
        handleStatusChange('AWAITING_PARTS');
        return;
      }
      if (aid === 'resume_job') {
        logActionTaken();
        handleStatusChange('IN_PROGRESS');
        return;
      }
      if (aid === 'complete_job') {
        if (workOrder.completion_proof_required && !workOrder.completion_proof_satisfied) {
          toast.error('Upload completion proof before completing this job');
          scrollToEvidence();
          return;
        }
        logActionTaken();
        handleStatusChange('COMPLETED');
        return;
      }
      if (aid === 'submit_quote') {
        logActionTaken();
        openQuoteDialog();
        return;
      }
      if (aid === 'mark_inspection_complete') {
        logActionTaken();
        setActionLoading(true);
        api
          .markInspectionComplete()
          .then(() => {
            toast.success('Inspection marked complete');
            return loadWorkOrder();
          })
          .catch((e) => toast.error(parseApiError(e, 'Could not update inspection')))
          .finally(() => setActionLoading(false));
        return;
      }
      if (aid === 'submit_invoice' || aid === 'view_invoice' || aid === 'edit_invoice') {
        logActionTaken();
        openInvoiceModal();
        return;
      }
      if (aid === 'propose_visit') {
        logActionTaken();
        nextActionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        toast.message('Choose date, time, and timezone, then tap Propose visit time.');
        return;
      }
      if (aid === 'confirm_visit') {
        logActionTaken();
        setActionLoading(true);
        api
          .confirmSchedule()
          .then(() => {
            toast.success('Visit confirmed');
            return loadWorkOrder();
          })
          .catch((e) => toast.error(parseApiError(e, 'Could not confirm')))
          .finally(() => setActionLoading(false));
        return;
      }
      if (aid === 'reschedule_visit') {
        const reason = window.prompt('Reason for reschedule request (optional)') ?? '';
        logActionTaken();
        setActionLoading(true);
        api
          .requestScheduleReschedule({ reason: reason.trim() || undefined })
          .then(() => {
            toast.success('Reschedule request sent');
            return loadWorkOrder();
          })
          .catch((e) => toast.error(parseApiError(e, 'Request failed')))
          .finally(() => setActionLoading(false));
        return;
      }
      if (aid === 'cancel_scheduled_visit') {
        if (!window.confirm('Cancel this scheduled visit? The booking will be cleared.')) return;
        logActionTaken();
        setActionLoading(true);
        api
          .cancelSchedule()
          .then(() => {
            toast.success('Visit cancelled');
            return loadWorkOrder();
          })
          .catch((e) => toast.error(parseApiError(e, 'Could not cancel')))
          .finally(() => setActionLoading(false));
        return;
      }
      if (aid === 'mark_no_access') {
        const notes = window.prompt('Optional note for your client (e.g. why access was not possible)') ?? '';
        logActionTaken();
        setActionLoading(true);
        api
          .markNoAccess({ notes: notes.trim() || undefined })
          .then(() => {
            toast.success('No access recorded.');
            return loadWorkOrder();
          })
          .catch((e) => toast.error(parseApiError(e, 'Could not record no access')))
          .finally(() => setActionLoading(false));
      }
    },
    [
      workOrder,
      api,
      handleAccept,
      handleDecline,
      handleStatusChange,
      scrollToEvidence,
      openInvoiceModal,
      openQuoteDialog,
      loadWorkOrder,
    ],
  );

  const billingAction = useMemo(() => {
    if (!workOrder) return null;
    const actions = contractorPortalExecutableActions(workOrder);
    const order = ['submit_quote', 'submit_invoice', 'view_invoice', 'edit_invoice'];
    for (const id of order) {
      const a = actions.find((x) => x.id === id);
      if (a) return a;
    }
    return null;
  }, [workOrder]);

  const primaryDisabled =
    !!actionLoading ||
    (primaryAction?.id === 'complete_job' &&
      workOrder?.completion_proof_required &&
      !workOrder?.completion_proof_satisfied);

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
            <h1 className="text-lg font-semibold text-gray-900">Invalid link</h1>
            <p className="text-gray-600 mt-2">Use the link from your job assignment email.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading && !workOrder) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-2">
          <Wrench className="w-6 h-6 text-electric-teal" />
          <span className="font-semibold text-midnight-blue">Job</span>
        </header>
        <main className="max-w-2xl mx-auto p-4">
          <a href="#job-next-action" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-3 focus:py-2 focus:rounded-md focus:shadow">
            Skip to next action
          </a>
          <div
            id="job-next-action"
            ref={nextActionRef}
            className="rounded-xl border-2 border-electric-teal/60 bg-gradient-to-b from-teal-50 to-white p-5 mb-4 animate-pulse"
            aria-busy="true"
            aria-label="Loading next action"
          >
            <div className="h-3 w-28 bg-teal-200/80 rounded mb-4" />
            <div className="h-4 w-full bg-gray-200 rounded mb-3" />
            <div className="h-11 w-48 bg-electric-teal/30 rounded-lg" />
          </div>
          <p className="text-sm text-gray-600 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-electric-teal shrink-0" />
            Loading your job…
          </p>
        </main>
      </div>
    );
  }

  if (linkContext?.activation_required && !workOrder) {
    const returnPath = linkContext.return_job_path || `/job?token=${token}`;
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-lg w-full">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <Wrench className="w-6 h-6 text-electric-teal" />
              <h1 className="text-lg font-semibold text-gray-900">Activate your contractor portal</h1>
            </div>
            <p className="text-gray-700">
              {linkContext.message ||
                'Activate your contractor portal to view this job and submit your quote.'}
            </p>
            <p className="text-sm text-gray-600 mt-3">
              Open the <strong>portal setup email</strong> we sent when you were assigned, set your password, then return
              here to open the job.
            </p>
            {activationResendMessage ? (
              <p className="text-sm text-teal-800 mt-3 rounded-md border border-teal-200 bg-teal-50 px-3 py-2">
                {activationResendMessage}
              </p>
            ) : null}
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                className="bg-electric-teal hover:bg-electric-teal/90"
                disabled={activationResending}
                onClick={handleRequestPortalActivation}
              >
                {activationResending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Resend activation email'}
              </Button>
              <Button type="button" variant="outline" onClick={handleRetryAfterActivation}>
                I&apos;ve activated — open job
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-4">
              After setting your password you will be returned to this job automatically when you use the link from your
              activation email with return path{' '}
              <span className="font-mono break-all">{returnPath}</span>.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loadError && !workOrder) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center">
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
            <h1 className="text-lg font-semibold text-gray-900">{loadError.title}</h1>
            <p className="text-gray-600 mt-2 text-left">{loadError.message}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const detail = workOrder;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-2">
        <Wrench className="w-6 h-6 text-electric-teal" />
        <span className="font-semibold text-midnight-blue">Job</span>
      </header>

      <main className="max-w-2xl mx-auto p-4">
        <a href="#job-next-action" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-3 focus:py-2 focus:rounded-md focus:shadow">
          Skip to next action
        </a>

        <section
          id="job-next-action"
          ref={nextActionRef}
          className="rounded-xl border-2 border-electric-teal/80 bg-gradient-to-b from-teal-50 via-white to-white shadow-md p-5 mb-4 scroll-mt-4"
          aria-label="Next action"
        >
          <p className="text-[11px] font-bold text-electric-teal uppercase tracking-[0.12em] mb-2 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" aria-hidden />
            Next action
          </p>
          {primaryPresentation.mode === 'waiting' ? (
            <p className="text-base text-midnight-blue font-medium leading-relaxed">{primaryPresentation.message}</p>
          ) : primaryAction ? (
            <>
              {primaryAction.hint ? (
                <p className="text-base text-gray-800 leading-relaxed mb-4">{primaryAction.hint}</p>
              ) : null}
              <Button
                type="button"
                size="lg"
                className="w-full sm:w-auto min-h-[48px] px-8 text-base font-semibold bg-electric-teal hover:bg-electric-teal/90 text-white shadow-sm"
                disabled={primaryDisabled}
                onClick={() => handlePrimaryOrNextAction(primaryAction)}
              >
                {actionLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : primaryAction.label}
              </Button>
            </>
          ) : (
            <p className="text-base text-midnight-blue font-medium leading-relaxed">{nextStepLine || 'No action required right now.'}</p>
          )}

          {contractorPortalExecutableActions(detail).some((a) => a.id === 'propose_visit') ? (
            <div className="mt-5 pt-4 border-t border-teal-100 space-y-3">
              <p className="text-xs font-semibold text-gray-600">Propose a visit time</p>
              <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
                <div className="flex-1 min-w-0">
                  <label className="block text-xs text-gray-500 mb-1">Date and time</label>
                  <Input
                    type="datetime-local"
                    value={scheduleForm.datetimeLocal}
                    onChange={(e) => setScheduleForm((f) => ({ ...f, datetimeLocal: e.target.value }))}
                    className="w-full"
                  />
                </div>
                <div className="w-full sm:w-44">
                  <label className="block text-xs text-gray-500 mb-1">Timezone</label>
                  <select
                    className="border border-gray-200 rounded-md px-3 py-2 text-sm w-full h-10 bg-white"
                    value={scheduleForm.timezone}
                    onChange={(e) => setScheduleForm((f) => ({ ...f, timezone: e.target.value }))}
                  >
                    {SCHEDULE_TZ_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  type="button"
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white shrink-0"
                  disabled={actionLoading}
                  onClick={handleProposeSchedule}
                >
                  Propose visit time
                </Button>
              </div>
            </div>
          ) : null}
        </section>

        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-900">
          <span className="font-medium">Payment: </span>
          Pleerity does not pay contractors—invoice the client after approval, then follow up with them directly.
        </div>

        {String(detail.pricing_mode || '').toUpperCase() === 'MAINTENANCE_INSPECTION_REQUIRED' &&
        !detail.inspection_completed_at ? (
          <div
            className="mb-4 rounded-lg border border-teal-200 bg-teal-50/90 p-3 text-xs text-midnight-blue"
            role="status"
          >
            <span className="font-medium">Inspection first: </span>
            Inspect-then-quote flow—finish the inspection visit, mark inspection complete, then submit your repair quote. Pause billable
            repair until the client approves the quote here.
          </div>
        ) : null}

        {workOrder?.pricing?.pricing_workflow ? (
          <div
            className={`mb-4 rounded-lg border p-3 text-xs ${
              workOrder.pricing.revision_active
                ? 'border-amber-300 bg-amber-50/90 text-amber-950'
                : 'border-gray-200 bg-gray-50/80 text-gray-800'
            }`}
            role="status"
          >
            <p className="font-semibold">
              Quote status:{' '}
              {workOrder.pricing.quote_presentation?.label ||
                workOrder.pricing.negotiation_status_label ||
                operationalLabelForToken(workOrder.pricing.price_status, { emptyLabel: '—' })}
            </p>
            {workOrder.pricing.revision_active ? (
              <p className="mt-1 font-medium">Quote changes requested — your assignment is still active.</p>
            ) : null}
            {workOrder.pricing.quote_revision_reason_code ? (
              <p className="mt-1">
                Reason:{' '}
                {QUOTE_REVISION_REASON_LABELS[workOrder.pricing.quote_revision_reason_code] ||
                  workOrder.pricing.quote_revision_reason_code}
              </p>
            ) : null}
            {workOrder.pricing.quote_revision_message ? (
              <p className="mt-1 whitespace-pre-wrap break-words">{workOrder.pricing.quote_revision_message}</p>
            ) : null}
            {workOrder.pricing.quote_revision_target_budget != null ? (
              <p className="mt-1">Target budget: £{Number(workOrder.pricing.quote_revision_target_budget).toFixed(2)}</p>
            ) : null}
            {(workOrder.pricing.quote_negotiation_history || []).length > 0 ? (
              <ul className="mt-2 space-y-0.5 border-t border-current/10 pt-2">
                {(workOrder.pricing.quote_negotiation_history || []).map((row, idx) => (
                  <li key={`${row.at}-${row.event}-${idx}`}>
                    v{row.version || '—'} · {String(row.event || '').replace(/_/g, ' ')}
                    {row.amount != null ? ` · £${Number(row.amount).toFixed(2)}` : ''}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {workOrder?.scheduling ? (
          <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50/80 p-3 text-xs text-gray-800" role="status">
            <p className="font-semibold">
              Visit: {workOrder.scheduling.visit_status_label || workOrder.schedule_status || '—'}
            </p>
            {workOrder.scheduling.scheduled_at ? (
              <p className="mt-1">Scheduled: {formatDate(workOrder.scheduling.scheduled_at)}</p>
            ) : null}
            {workOrder.scheduling.schedule_reschedule_reason ? (
              <p className="mt-1">Client requested another date: {workOrder.scheduling.schedule_reschedule_reason}</p>
            ) : null}
            {(workOrder.scheduling.visit_negotiation_history || []).length > 0 ? (
              <ul className="mt-2 space-y-0.5 border-t border-gray-200 pt-2">
                {(workOrder.scheduling.visit_negotiation_history || []).map((row, idx) => (
                  <li key={`${row.at}-${row.event}-${idx}`}>
                    {String(row.event || '').replace(/_/g, ' ')}
                    {row.scheduled_at ? ` · ${formatDate(row.scheduled_at)}` : ''}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {(detail.status || '').toUpperCase() === 'CANCELLED' ? (
          <div
            className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800"
            role="status"
          >
            <p className="font-semibold text-slate-900">This job was cancelled</p>
            <p className="text-slate-600 mt-1">
              You do not need to take any further action on this job. Contact the client if that does not match what you
              expected.
            </p>
          </div>
        ) : null}

        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="font-medium text-gray-900">{detail.description || detail.work_order_id}</p>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">Status</dt>
              <dd>
                <span className="px-1.5 py-0.5 rounded bg-gray-100">{detail.status}</span>
              </dd>
              <dt className="text-gray-500">Property</dt>
              <dd>{detail.property_address || detail.property_id}</dd>
              <dt className="text-gray-500">SLA complete by</dt>
              <dd>{formatDate(detail.sla_complete_by)}</dd>
            </dl>

            {(detail.status === 'ASSIGNED' || detail.status === 'OPEN') && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={handleAccept} disabled={!!actionLoading}>
                  {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-1" />}
                  Accept
                </Button>
                <Button size="sm" variant="outline" onClick={handleDecline} disabled={!!actionLoading}>
                  <XCircle className="w-4 h-4 mr-1" /> Decline
                </Button>
              </div>
            )}

            {!['OPEN', 'ASSIGNED'].includes(detail.status) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Update status</label>
                {detail.completion_proof_required && !detail.completion_proof_satisfied ? (
                  <p className="text-xs font-medium text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-2 py-1.5 mb-2">
                    Upload completion proof before completing this job
                  </p>
                ) : null}
                <select
                  value={detail.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  disabled={!!actionLoading}
                  className="border border-gray-200 rounded-md px-3 py-2 text-sm w-full"
                >
                  {STATUS_OPTIONS.filter((o) => {
                    if (o.value !== 'COMPLETED') return true;
                    if ((detail.status || '').toUpperCase() === 'COMPLETED') return true;
                    if (detail.completion_proof_required && !detail.completion_proof_satisfied) return false;
                    return true;
                  }).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your notes</label>
              <Input
                placeholder="Contractor notes"
                value={notesForm.contractor_notes}
                onChange={(e) => setNotesForm((f) => ({ ...f, contractor_notes: e.target.value }))}
                className="mb-2"
              />
              <Input
                placeholder="Completion notes"
                value={notesForm.completion_notes}
                onChange={(e) => setNotesForm((f) => ({ ...f, completion_notes: e.target.value }))}
                className="mb-2"
              />
              <Button size="sm" variant="outline" onClick={handleSaveNotes} disabled={!!actionLoading || evidenceUploading}>
                Save notes
              </Button>
            </div>

            <div ref={evidenceSectionRef}>
              <label className="block text-sm font-medium text-gray-700 mb-1">Evidence</label>
              <p className="text-xs text-gray-500 mb-2">
                PDF, images, Word—max 20MB. Uploads are visible for review and do not auto-verify compliance.
              </p>
              {(detail.evidence_keys || []).length > 0 && (
                <ul className="text-sm text-gray-700 mb-2 space-y-2 max-h-40 overflow-y-auto">
                  {(detail.evidence_keys || []).map((k) => {
                    const keyStr = typeof k === 'string' ? k : String(k);
                    const fileKey = isContractorFileEvidenceKey(keyStr);
                    return (
                      <li
                        key={keyStr}
                        className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2 last:border-0"
                      >
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
                              onClick={() => handleEvidenceFileOpen(keyStr, true)}
                              disabled={evidenceFileLoadingKey === keyStr}
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
              <label className="inline-flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <Upload className="w-4 h-4 shrink-0 text-electric-teal" />
                <span>{evidenceUploading ? 'Uploading…' : 'Choose file'}</span>
                <input
                  ref={evidenceFileInputRef}
                  type="file"
                  className="sr-only"
                  accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,application/pdf"
                  disabled={evidenceUploading || detail.status === 'OPEN' || detail.status === 'ASSIGNED'}
                  onChange={onEvidenceSelected}
                />
              </label>
            </div>

            {billingAction ? (
              <Button
                size="sm"
                variant={billingAction.id === 'submit_invoice' || billingAction.id === 'submit_quote' ? 'default' : 'outline'}
                className={
                  billingAction.id === 'submit_invoice' || billingAction.id === 'submit_quote'
                    ? 'bg-electric-teal hover:bg-electric-teal/90'
                    : 'border-electric-teal text-midnight-blue'
                }
                onClick={() =>
                  billingAction.id === 'submit_quote'
                    ? openQuoteDialog()
                    : openInvoiceModal()
                }
              >
                <FileText className="w-4 h-4 mr-1" /> {billingAction.label}
              </Button>
            ) : null}
            {workOrder?.linked_invoice && (
              <p className="text-sm text-gray-600">
                Invoice{' '}
                <span className="font-medium">{invoiceDisplayLabel(workOrder.linked_invoice)}</span>
                {' — '}
                <span className="font-medium">{formatContractorInvoiceStateLabel(workOrder.linked_invoice)}</span>
              </p>
            )}
          </CardContent>
        </Card>
      </main>

      {invoiceModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setInvoiceModal(null)}>
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-4">
              {invoiceModal.mode === 'view'
                ? 'View invoice'
                : invoiceModal.mode === 'edit'
                  ? 'Edit and resubmit invoice'
                  : 'Submit invoice'}
            </h3>
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-4">
              Pleerity coordinates jobs and invoice approval. Payment responsibility lies with the client. Pleerity does not
              process contractor payments. Follow up with the client for payment.
            </p>
            {workOrder ? (
              <dl className="text-xs text-gray-600 space-y-1 mb-4 border border-gray-100 rounded-md p-3 bg-gray-50/80">
                <div>
                  <dt className="inline text-gray-500">Job: </dt>
                  <dd className="inline font-medium text-gray-900">{workOrder.description || workOrder.work_order_id}</dd>
                </div>
                <div>
                  <dt className="inline text-gray-500">Property: </dt>
                  <dd className="inline">{workOrder.property_address || workOrder.property_id}</dd>
                </div>
                <div>
                  <dt className="inline text-gray-500">Job ID: </dt>
                  <dd className="inline font-mono break-all text-[11px]">{workOrder.work_order_id}</dd>
                </div>
                <div>
                  <dt className="inline text-gray-500">Visit / completion: </dt>
                  <dd className="inline">
                    {workOrder.completed_at
                      ? formatDate(workOrder.completed_at)
                      : workOrder.scheduled_at
                        ? formatDate(workOrder.scheduled_at)
                        : '—'}
                  </dd>
                </div>
              </dl>
            ) : null}
            {invoiceModal.mode !== 'create' && workOrder?.linked_invoice ? (
              <p className="text-sm text-gray-700 mb-3">
                <span className="text-gray-500">Invoice number: </span>
                <span className="font-medium text-gray-900">{invoiceDisplayLabel(workOrder.linked_invoice)}</span>
              </p>
            ) : null}
            <form onSubmit={handleSubmitInvoice} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Your invoice reference{invoiceModal.mode === 'view' ? '' : ' (optional)'}
                </label>
                <Input
                  readOnly={invoiceModal.mode === 'view'}
                  value={invoiceForm.reference}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, reference: e.target.value }))}
                  placeholder="INV-001"
                  className={invoiceModal.mode === 'view' ? 'bg-gray-50' : ''}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                <textarea
                  readOnly={invoiceModal.mode === 'view'}
                  value={invoiceForm.description}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, description: e.target.value }))}
                  className={`border border-gray-300 rounded-md px-3 py-2 w-full min-h-[80px] ${invoiceModal.mode === 'view' ? 'bg-gray-50' : ''}`}
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Amount £{invoiceModal.mode === 'view' ? '' : ' *'}
                </label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  readOnly={invoiceModal.mode === 'view'}
                  value={invoiceForm.submitted_amount}
                  onChange={(e) => setInvoiceForm((f) => ({ ...f, submitted_amount: e.target.value }))}
                  placeholder="0.00"
                  className={invoiceModal.mode === 'view' ? 'bg-gray-50' : ''}
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

      {quoteOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4" onClick={() => setQuoteOpen(false)}>
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-4">
              {workOrder?.pricing?.revision_active ? 'Submit revised quote' : 'Submit quote'}
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              {workOrder?.pricing?.revision_active
                ? 'Address the client feedback and submit an updated price for approval.'
                : 'Propose a fixed price for client approval before further billable repair work.'}
            </p>
            {workOrder ? (
              <dl className="text-xs text-gray-600 space-y-1 mb-4 border border-gray-100 rounded-md p-3 bg-gray-50/80">
                <div>
                  <dt className="inline text-gray-500">Job: </dt>
                  <dd className="inline font-medium text-gray-900">{workOrder.description || workOrder.work_order_id}</dd>
                </div>
                <div>
                  <dt className="inline text-gray-500">Property: </dt>
                  <dd className="inline">{workOrder.property_address || workOrder.property_id}</dd>
                </div>
              </dl>
            ) : null}
            <form onSubmit={handleSubmitQuote} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quote amount £ *</label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={quoteForm.amount}
                  onChange={(e) => setQuoteForm((f) => ({ ...f, amount: e.target.value }))}
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                <textarea
                  value={quoteForm.notes}
                  onChange={(e) => setQuoteForm((f) => ({ ...f, notes: e.target.value }))}
                  className="border border-gray-300 rounded-md px-3 py-2 w-full min-h-[80px]"
                  rows={3}
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={quoteSaving} className="bg-electric-teal hover:bg-electric-teal/90">
                  {quoteSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit quote'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setQuoteOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
