import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Search, 
  RefreshCw, 
  ExternalLink, 
  Mail, 
  MessageSquare,
  Key,
  Play,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  CreditCard,
  Building2,
  User,
  Calendar,
  Copy,
  Send,
  Loader2,
  ChevronRight,
  ArrowLeft,
  FileText,
  Phone,
  Info,
  AlertCircle,
  Download
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from '@/utils/portalNotifications';
import api from '../api/client';
import AdminPendingPaymentsPage from './AdminPendingPaymentsPage';
import AdminBillingRecoveryPanel from '../components/admin/AdminBillingRecoveryPanel';
import AdminPaymentHistoryTable from '../components/admin/AdminPaymentHistoryTable';
import AdminClientSupportSearch from '../components/admin/AdminClientSupportSearch';
import {
  getAdminActionPolicy,
  getGovernanceConfirmationWording,
  getGovernanceEscalationGuidance,
  getGovernanceRiskBadgeClass,
  getGovernanceWarning,
} from '../utils/adminActionGovernance';
import { runGovernedAdminMutation } from '../utils/adminGovernedMutation';
import { useStepUpApi } from '../hooks/useStepUpApi';

const MIN_VALID_DATE_MS = 946684800000;

function formatAdminDate(isoOrDate) {
  if (isoOrDate == null || isoOrDate === '') return null;
  const t = new Date(isoOrDate).getTime();
  if (Number.isNaN(t) || t < MIN_VALID_DATE_MS) return null;
  return new Date(isoOrDate).toLocaleString('en-GB');
}

/** Mirrors tenant BillingPage labels; `sl` = API `subscription_lifecycle` object */
function humanLifecycleLabel(sl) {
  if (sl?.lifecycle_status_label) return sl.lifecycle_status_label;
  if (!sl?.has_subscription) return 'No active subscription';
  if (sl.cancel_at_period_end) return 'Cancelling at period end';
  const lc = (sl.billing_lifecycle_state || 'active').toLowerCase();
  if (lc === 'grace_period') return 'Payment retry (grace period)';
  if (lc === 'limited') return 'Restricted — payment overdue';
  if (lc === 'past_due') return 'Payment past due';
  if (lc === 'expired') return 'Subscription expired';
  if (lc === 'cancelled') return 'Subscription cancelled';
  if (lc === 'renewing') return 'Paid subscription — renewal date approaching';
  return 'Paid subscription active';
}

const AdminBillingPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'overview';
  
  // Selected client state (only when on overview tab)
  const [selectedClientId, setSelectedClientId] = useState(searchParams.get('client') || null);
  const [billingSnapshot, setBillingSnapshot] = useState(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  
  // Action states
  const [syncing, setSyncing] = useState(false);
  const [creatingPortal, setCreatingPortal] = useState(false);
  const [resendingSetup, setResendingSetup] = useState(false);
  const [provisioning, setProvisioning] = useState(false);
  const [portalLink, setPortalLink] = useState(null);
  const [changingPlan, setChangingPlan] = useState(false);
  const [changePlanCode, setChangePlanCode] = useState('PLAN_2_PORTFOLIO');
  const [applyAtPeriodEnd, setApplyAtPeriodEnd] = useState(true);
  
  // Message modal
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [messageChannels, setMessageChannels] = useState(['email']);
  const [messageTemplate, setMessageTemplate] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  
  // Statistics
  const [statistics, setStatistics] = useState(null);
  const [subscriptionOpsEvents, setSubscriptionOpsEvents] = useState([]);
  const [subscriptionOpsLoading, setSubscriptionOpsLoading] = useState(false);

  const [lifecycleJobRunning, setLifecycleJobRunning] = useState(false);
  const [lastLifecycleJobResult, setLastLifecycleJobResult] = useState(null);

  const getRequiredReason = useCallback((actionId, actionLabel) => {
    const reason = window.prompt(
      `${actionLabel}\n${getGovernanceConfirmationWording(actionId)}\n\nEnter support reason (minimum 10 characters):`,
      '',
    );
    if (reason == null) return null;
    const trimmed = reason.trim();
    if (trimmed.length < 10) {
      toast.error('Reason must be at least 10 characters');
      return null;
    }
    return trimmed;
  }, []);
  const [stripeReconcileRunning, setStripeReconcileRunning] = useState(false);
  const [paymentLedgerReconcileRunning, setPaymentLedgerReconcileRunning] = useState(false);
  const [showAdminCancelDialog, setShowAdminCancelDialog] = useState(false);
  const [adminCancelImmediate, setAdminCancelImmediate] = useState(false);
  const [adminCancelReason, setAdminCancelReason] = useState('');
  const [adminCancelling, setAdminCancelling] = useState(false);
  const adminCancelStepUp = useStepUpApi();

  // Receipts & invoices (canonical ledger + orders)
  const [receipts, setReceipts] = useState([]);
  const [receiptsLoading, setReceiptsLoading] = useState(false);
  const [receiptsError, setReceiptsError] = useState('');
  const [receiptsMeta, setReceiptsMeta] = useState({});
  const [receiptTypeFilter, setReceiptTypeFilter] = useState('all');
  const [receiptStatusFilter, setReceiptStatusFilter] = useState('');
  const [receiptDateFrom, setReceiptDateFrom] = useState('');
  const [receiptDateTo, setReceiptDateTo] = useState('');
  const [receiptActionKey, setReceiptActionKey] = useState(null);

  // Fetch statistics on mount
  useEffect(() => {
    fetchStatistics();
    fetchSubscriptionOpsEvents();
  }, []);

  const fetchSubscriptionOpsEvents = async () => {
    setSubscriptionOpsLoading(true);
    try {
      const response = await api.get('/admin/billing/subscription-operational-events', { params: { limit: 20 } });
      setSubscriptionOpsEvents(response.data?.events || []);
    } catch {
      setSubscriptionOpsEvents([]);
    } finally {
      setSubscriptionOpsLoading(false);
    }
  };

  // Fetch client details when selected
  useEffect(() => {
    if (selectedClientId) {
      fetchBillingSnapshot(selectedClientId);
      setSearchParams({ client: selectedClientId });
    }
  }, [selectedClientId, setSearchParams]);

  // Keep change-plan dropdown in sync with current plan when snapshot loads
  useEffect(() => {
    if (billingSnapshot?.plan_code && billingSnapshot?.stripe_subscription_id) {
      setChangePlanCode(billingSnapshot.plan_code);
    }
  }, [billingSnapshot?.plan_code, billingSnapshot?.stripe_subscription_id]);

  const fetchClientReceipts = useCallback(async (clientId) => {
    if (!clientId) {
      setReceipts([]);
      return;
    }
    setReceiptsLoading(true);
    setReceiptsError('');
    try {
      const params = new URLSearchParams();
      params.set('type', receiptTypeFilter || 'all');
      if (receiptStatusFilter.trim()) params.set('status', receiptStatusFilter.trim());
      if (receiptDateFrom.trim()) params.set('date_from', receiptDateFrom.trim());
      if (receiptDateTo.trim()) params.set('date_to', receiptDateTo.trim());
      const response = await api.get(`/admin/billing/clients/${clientId}/receipts?${params.toString()}`);
      setReceipts(response.data.receipts || []);
      setReceiptsMeta(response.data.meta || {});
    } catch (error) {
      console.error('Receipts fetch error:', error);
      const msg = error.response?.data?.detail || 'Failed to load payment history';
      setReceiptsError(typeof msg === 'string' ? msg : 'Failed to load payment history');
      toast.error(msg);
      setReceipts([]);
      setReceiptsMeta({});
    } finally {
      setReceiptsLoading(false);
    }
  }, [receiptTypeFilter, receiptStatusFilter, receiptDateFrom, receiptDateTo]);

  useEffect(() => {
    if (selectedClientId) {
      fetchClientReceipts(selectedClientId);
    } else {
      setReceipts([]);
      setReceiptsMeta({});
    }
  }, [selectedClientId, fetchClientReceipts]);

  const fetchStatistics = async () => {
    try {
      const response = await api.get('/admin/billing/statistics');
      setStatistics(response.data);
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const fetchBillingSnapshot = async (clientId) => {
    setLoadingSnapshot(true);
    try {
      const response = await api.get(`/admin/billing/clients/${clientId}`);
      setBillingSnapshot(response.data);
    } catch (error) {
      console.error('Fetch snapshot error:', error);
      toast.error('Failed to load billing details');
    } finally {
      setLoadingSnapshot(false);
    }
  };

  const handleSync = async () => {
    if (!selectedClientId) return;
    
    setSyncing(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/sync`);
      
      if (response.data.success) {
        const lc = response.data.lifecycle_sync;
        const lcOk = lc && !lc.error;
        toast.success('Billing synced', {
          description: response.data.changes_detected
            ? 'Changes detected and applied'
            : 'Already up to date',
        });
        if (lc && lc.error) {
          toast.warning('Lifecycle reconcile failed', { description: String(lc.error) });
        } else if (lcOk && lc.updated) {
          toast.info('Subscription lifecycle updated', {
            description: `State: ${lc.billing_lifecycle_state || '—'} · Entitlement: ${lc.entitlement_status || '—'}`,
          });
        }

        if (response.data.provisioning_triggered) {
          toast.info('Provisioning triggered', {
            description: 'Client provisioning has been started',
          });
        }
        
        // Refresh snapshot
        await fetchBillingSnapshot(selectedClientId);
        fetchStatistics();
      } else {
        toast.warning(response.data.message);
      }
    } catch (error) {
      console.error('Sync error:', error);
      toast.error(error.response?.data?.detail || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleRunStripeSubscriptionReconcile = async () => {
    const reason = getRequiredReason('run_stripe_reconcile_batch', 'Run Stripe reconcile batch');
    if (!reason) return;
    setStripeReconcileRunning(true);
    try {
      const response = await api.post('/admin/billing/jobs/stripe-subscription-reconcile', { reason });
      const d = response.data || {};
      toast.success('Stripe subscription reconcile finished', {
        description: `Reconciled: ${d.reconciled ?? '—'} · Errors: ${d.errors ?? '—'} · Attempted: ${d.attempted ?? '—'}`,
      });
      fetchStatistics();
      if (selectedClientId) {
        await fetchBillingSnapshot(selectedClientId);
      }
    } catch (error) {
      console.error('Stripe reconcile job error:', error);
      toast.error(error.response?.data?.detail || 'Stripe reconcile job failed');
    } finally {
      setStripeReconcileRunning(false);
    }
  };

  const handleReconcileSubscriptionPaymentLedger = async () => {
    if (!selectedClientId) return;
    const pol = getAdminActionPolicy('reconcile_subscription_payment_ledger');
    if (pol?.requires_confirmation) {
      const ok = window.confirm(
        `${getGovernanceConfirmationWording('reconcile_subscription_payment_ledger')}\n\n` +
          'Materialize paid Stripe invoices into the internal payment ledger (idempotent).',
      );
      if (!ok) return;
    }
    if (pol?.requires_reason) {
      const reason = getRequiredReason(
        'reconcile_subscription_payment_ledger',
        'Reconcile subscription payment ledger',
      );
      if (!reason) return;
    }
    setPaymentLedgerReconcileRunning(true);
    try {
      const response = await api.post(
        `/admin/billing/clients/${selectedClientId}/reconcile-payment-ledger`,
        { from_stripe_events: true, from_stripe_invoice_api_limit: 0 },
      );
      const d = response.data || {};
      toast.success('Payment ledger reconciliation finished', {
        description: `Upserted invoice rows: ${d.upsert_count ?? 0}. Last payment fields synced: ${d.client_billing_last_payment_synced ? 'yes' : 'no'}.`,
      });
      if (d.errors?.length) {
        toast.warning('Reconciliation completed with errors — see server logs / response payload.');
      }
      await fetchBillingSnapshot(selectedClientId);
      fetchClientReceipts(selectedClientId);
    } catch (error) {
      console.error('Payment ledger reconcile error:', error);
      toast.error(error.response?.data?.detail || 'Payment ledger reconciliation failed');
    } finally {
      setPaymentLedgerReconcileRunning(false);
    }
  };

  const handleRunSubscriptionLifecycleJob = async () => {
    const reason = getRequiredReason('run_subscription_lifecycle_batch', 'Run subscription lifecycle batch');
    if (!reason) return;
    setLifecycleJobRunning(true);
    setLastLifecycleJobResult(null);
    try {
      const response = await api.post('/admin/billing/jobs/subscription-lifecycle', { reason });
      const d = response.data || {};
      setLastLifecycleJobResult(d);
      const m = d.outcome_metrics || {};
      toast.success('Subscription lifecycle job finished', {
        description:
          d.message ||
          `Post-grace: ${m.post_grace_updates ?? '—'} · Grace nudges: ${m.grace_reminders ?? '—'} · 7d: ${m.renewal_7d ?? '—'} · 3d: ${m.renewal_3d ?? '—'}`,
      });
      fetchStatistics();
      if (selectedClientId) {
        await fetchBillingSnapshot(selectedClientId);
      }
    } catch (error) {
      console.error('Lifecycle job error:', error);
      toast.error(error.response?.data?.detail || 'Subscription lifecycle job failed');
    } finally {
      setLifecycleJobRunning(false);
    }
  };

  const handleCreatePortalLink = async () => {
    if (!selectedClientId) return;
    
    setCreatingPortal(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/portal-link`);
      
      if (response.data.success) {
        setPortalLink(response.data.portal_url);
        toast.success('Portal link created');
      }
    } catch (error) {
      console.error('Portal link error:', error);
      toast.error(error.response?.data?.detail || 'Failed to create portal link');
    } finally {
      setCreatingPortal(false);
    }
  };

  const handleResendSetup = async () => {
    if (!selectedClientId) return;
    
    setResendingSetup(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/resend-setup`);
      
      if (response.data.success) {
        toast.success('Setup email sent', {
          description: `Sent to ${response.data.email}`,
        });
      }
    } catch (error) {
      console.error('Resend setup error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send setup email');
    } finally {
      setResendingSetup(false);
    }
  };

  const handleChangePlan = async () => {
    if (!selectedClientId || !changePlanCode) return;
    if (changePlanCode === billingSnapshot?.plan_code) {
      toast.error('Select a different plan to change');
      return;
    }
    const reason = getRequiredReason('change_plan', 'Change plan');
    if (!reason) return;
    setChangingPlan(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/change-plan`, {
        plan_code: changePlanCode,
        apply_at_period_end: applyAtPeriodEnd,
        reason,
      });
      if (response.data.success) {
        toast.success('Plan change applied', {
          description: response.data.apply_at_period_end
            ? `New plan (${response.data.new_plan}) will apply at end of billing period.`
            : `Switched to ${response.data.new_plan}.`,
        });
        await fetchBillingSnapshot(selectedClientId);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to change plan');
    } finally {
      setChangingPlan(false);
    }
  };

  const adminSubscriptionStatusUpper = String(
    billingSnapshot?.subscription_status ||
      billingSnapshot?.stripe_subscription_status ||
      billingSnapshot?.subscription_lifecycle?.subscription_status ||
      '',
  ).toUpperCase();
  const adminAlreadyCancelled = ['CANCELED', 'CANCELLED'].includes(adminSubscriptionStatusUpper);
  const adminCancelScheduled = Boolean(billingSnapshot?.cancel_at_period_end);
  const adminCanCancelSubscription =
    Boolean(billingSnapshot?.stripe_subscription_id) && !adminAlreadyCancelled && !adminCancelScheduled;

  const handleAdminCancelSubscription = async () => {
    if (!selectedClientId) return;
    const trimmedReason = adminCancelReason.trim();
    if (trimmedReason.length < 10) {
      toast.error('Support reason must be at least 10 characters');
      return;
    }
    setAdminCancelling(true);
    try {
      await adminCancelStepUp.request(async (stepHeaders) => {
        await runGovernedAdminMutation({
          actionId: 'admin_cancel_subscription',
          reason: trimmedReason,
          resourceKey: selectedClientId,
          mutate: async (govHeaders) => {
            const response = await api.post(
              `/admin/billing/clients/${selectedClientId}/cancel`,
              {
                reason: trimmedReason,
                cancel_immediately: adminCancelImmediate,
              },
              { headers: { ...stepHeaders, ...govHeaders } },
            );
            toast.success(response.data?.message || 'Subscription cancellation processed');
            setShowAdminCancelDialog(false);
            setAdminCancelReason('');
            setAdminCancelImmediate(false);
            await fetchBillingSnapshot(selectedClientId);
            return response;
          },
        });
      });
    } catch (error) {
      if (error?.message === 'step_up_cancelled') return;
      toast.error(error.response?.data?.detail || error.message || 'Failed to cancel subscription');
    } finally {
      setAdminCancelling(false);
    }
  };

  const handleForceProvision = async () => {
    if (!selectedClientId) return;
    const reason = getRequiredReason('force_provision', 'Force provision');
    if (!reason) return;
    
    setProvisioning(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/force-provision`, { reason });
      
      if (response.data.success) {
        toast.success('Provisioning complete', {
          description: response.data.message,
        });
        await fetchBillingSnapshot(selectedClientId);
      } else {
        toast.error(response.data.message);
      }
    } catch (error) {
      console.error('Provision error:', error);
      toast.error(error.response?.data?.detail || 'Provisioning failed');
    } finally {
      setProvisioning(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedClientId || messageChannels.length === 0) return;
    
    setSendingMessage(true);
    try {
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/message`, {
        channels: messageChannels,
        template_id: messageTemplate || null,
        custom_text: customMessage || null,
      });
      
      if (response.data.success) {
        const results = response.data.results;
        let successCount = 0;
        if (results.in_app?.sent) successCount++;
        if (results.email?.sent) successCount++;
        if (results.sms?.sent) successCount++;
        
        toast.success(`Message sent via ${successCount} channel(s)`);
        setShowMessageModal(false);
        setCustomMessage('');
        setMessageTemplate('');
      }
    } catch (error) {
      console.error('Send message error:', error);
      toast.error(error.response?.data?.detail || 'Failed to send message');
    } finally {
      setSendingMessage(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const handleReceiptDownload = async (row) => {
    if (!selectedClientId || !row.download_available) return;
    const key = row.receipt_key || '';
    setReceiptActionKey(`dl-${key}`);
    try {
      let path;
      if (row.source === 'subscription') {
        const ref = encodeURIComponent(row.invoice_number || row.order_reference || '');
        path = `/admin/billing/clients/${selectedClientId}/receipts/subscription/${ref}/download`;
      } else {
        path = `/admin/billing/clients/${selectedClientId}/receipts/order/${encodeURIComponent(row.order_id)}/download`;
      }
      const response = await api.get(path, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${row.invoice_number || row.order_reference || 'receipt'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Receipt downloaded');
    } catch (error) {
      console.error('Receipt download error:', error);
      toast.error(error.response?.data?.detail || 'Download failed');
    } finally {
      setReceiptActionKey(null);
    }
  };

  const handleReceiptResend = async (row) => {
    if (!selectedClientId || !row.resend_available) return;
    const key = row.receipt_key || '';
    setReceiptActionKey(`rs-${key}`);
    try {
      const source = row.source === 'subscription' ? 'subscription' : 'order';
      const ref =
        source === 'subscription'
          ? (row.invoice_number || row.order_reference || '').trim()
          : (row.order_id || '').trim();
      if (!ref) {
        toast.error('Missing reference for resend');
        return;
      }
      const response = await api.post(`/admin/billing/clients/${selectedClientId}/receipts/resend`, {
        source,
        ref,
      });
      if (response.data.success) {
        toast.success('Receipt email sent', {
          description: response.data.message || 'Check delivery logs if needed.',
        });
        fetchClientReceipts(selectedClientId);
      }
    } catch (error) {
      console.error('Receipt resend error:', error);
      const d = error.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : d?.message || 'Resend failed');
    } finally {
      setReceiptActionKey(null);
    }
  };

  const getEntitlementBadge = (status) => {
    switch (status) {
      case 'ENABLED':
        return <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-700 rounded-full">ENABLED</span>;
      case 'LIMITED':
        return <span className="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">LIMITED</span>;
      case 'DISABLED':
        return <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">DISABLED</span>;
      default:
        return <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-full">{status}</span>;
    }
  };

  const getSubscriptionBadge = (status) => {
    const statusColors = {
      ACTIVE: 'bg-green-100 text-green-700',
      TRIALING: 'bg-blue-100 text-blue-700',
      PAST_DUE: 'bg-amber-100 text-amber-700',
      CANCELED: 'bg-red-100 text-red-700',
      UNPAID: 'bg-red-100 text-red-700',
      NONE: 'bg-gray-100 text-gray-700',
    };
    
    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[status] || 'bg-gray-100 text-gray-700'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-billing-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigate('/admin/dashboard')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer text-gray-700 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-electric-teal focus:ring-offset-1"
              data-testid="back-btn"
              title="Back to Dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
                <CreditCard className="w-6 h-6 text-electric-teal" />
                Billing & Subscriptions
              </h1>
              <p className="text-sm text-gray-500">Manage client billing, subscriptions, and entitlements</p>
            </div>
          </div>
          {/* Tabs: one source of truth for anything money */}
          <div className="flex gap-1 mt-3 border-b border-gray-200">
            <button
              onClick={() => setSearchParams((p) => { const next = new URLSearchParams(p); next.delete('tab'); return next; })}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                tab !== 'pending-payments' && tab !== 'recovery' ? 'bg-gray-100 text-midnight-blue border-b-2 border-electric-teal -mb-px' : 'text-gray-600 hover:bg-gray-50'
              }`}
              data-testid="tab-overview"
            >
              Overview
            </button>
            <button
              onClick={() => setSearchParams((p) => { const next = new URLSearchParams(p); next.set('tab', 'pending-payments'); return next; })}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
                tab === 'pending-payments' ? 'bg-gray-100 text-midnight-blue border-b-2 border-electric-teal -mb-px' : 'text-gray-600 hover:bg-gray-50'
              }`}
              data-testid="tab-pending-payments"
            >
              <Clock className="w-4 h-4" />
              Pending Payments
            </button>
            <button
              onClick={() => setSearchParams((p) => { const next = new URLSearchParams(p); next.set('tab', 'recovery'); return next; })}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
                tab === 'recovery' ? 'bg-gray-100 text-midnight-blue border-b-2 border-electric-teal -mb-px' : 'text-gray-600 hover:bg-gray-50'
              }`}
              data-testid="tab-recovery"
            >
              <AlertTriangle className="w-4 h-4" />
              Recovery
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {tab === 'pending-payments' ? (
          <AdminPendingPaymentsPage embedded />
        ) : tab === 'recovery' ? (
          <AdminBillingRecoveryPanel embedded />
        ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Search & Results */}
          <div className="lg:col-span-1 space-y-4">
            {/* Search */}
            <Card data-testid="search-panel">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Find customer</CardTitle>
                <CardDescription>
                  Canonical admin search (same as header and dashboard). Selecting a customer opens their Client Control Panel;
                  use Billing from there when you need receipts or sync actions.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AdminClientSupportSearch variant="panel" limit={15} initialQuery={searchParams.get('q') || ''} />
              </CardContent>
            </Card>

            {/* Quick Stats */}
            {statistics && (
              <Card data-testid="statistics-panel">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Subscription Stats</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Enabled</span>
                    <span className="font-semibold text-green-600">{statistics.entitlement_counts?.enabled || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Limited</span>
                    <span className="font-semibold text-amber-600">{statistics.entitlement_counts?.limited || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Disabled</span>
                    <span className="font-semibold text-red-600">{statistics.entitlement_counts?.disabled || 0}</span>
                  </div>
                  <hr />
                  <div className="text-xs text-gray-500 space-y-1">
                    <p>Solo: {statistics.plan_counts?.PLAN_1_SOLO || 0}</p>
                    <p>Portfolio: {statistics.plan_counts?.PLAN_2_PORTFOLIO || 0}</p>
                    <p>Professional: {statistics.plan_counts?.PLAN_3_PRO || 0}</p>
                  </div>
                  {statistics.billing_lifecycle_state_counts && (
                    <>
                      <hr />
                      <p className="text-xs font-medium text-gray-700">Billing lifecycle (client_billing)</p>
                      <div className="text-xs text-gray-600 space-y-0.5">
                        <p>Grace: {statistics.billing_lifecycle_state_counts.grace_period ?? 0}</p>
                        <p>Limited: {statistics.billing_lifecycle_state_counts.limited ?? 0}</p>
                        <p>Past due: {statistics.billing_lifecycle_state_counts.past_due ?? 0}</p>
                        <p>Renewing (≤7d): {statistics.billing_lifecycle_state_counts.renewing ?? 0}</p>
                        <p>Active: {statistics.billing_lifecycle_state_counts.active ?? 0}</p>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            <Card data-testid="subscription-ops-events-panel">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-electric-teal" />
                  Subscription operations
                </CardTitle>
                <CardDescription>Recent renewals, failures, and billing lifecycle events (not raw Stripe payloads).</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 max-h-80 overflow-y-auto">
                {subscriptionOpsLoading ? (
                  <p className="text-sm text-gray-500 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Loading…
                  </p>
                ) : subscriptionOpsEvents.length === 0 ? (
                  <p className="text-sm text-gray-500">No recent operational events.</p>
                ) : (
                  subscriptionOpsEvents.map((ev, idx) => (
                    <button
                      key={`${ev.client_id}-${ev.occurred_at}-${idx}`}
                      type="button"
                      onClick={() => ev.client_id && setSelectedClientId(ev.client_id)}
                      className="w-full text-left p-2 rounded border border-gray-200 hover:bg-gray-50 transition-colors"
                    >
                      <p className="text-sm font-medium text-gray-900">{ev.operational_event_label}</p>
                      <p className="text-xs text-gray-600">
                        {ev.customer_name || ev.client_id}
                        {ev.recovered_after_failure ? ' · Recovered' : ''}
                        {ev.provisioning_status === 'pending_reconciliation' || ev.provisioning_status === 'pending'
                          ? ' · Provisioning pending'
                          : ''}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatAdminDate(ev.occurred_at) || '—'}
                        {ev.operational_severity ? ` · ${ev.operational_severity}` : ''}
                      </p>
                    </button>
                  ))
                )}
              </CardContent>
            </Card>

            {statistics?.clients_in_grace?.length > 0 && (
              <Card data-testid="grace-period-panel">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Payment grace ({statistics.clients_in_grace.length})
                  </CardTitle>
                  <CardDescription>Clients with billing_lifecycle_state = grace_period (from database).</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 max-h-72 overflow-y-auto">
                  {statistics.clients_in_grace.map((row) => (
                    <button
                      key={row.client_id}
                      type="button"
                      onClick={() => setSelectedClientId(row.client_id)}
                      className="w-full text-left p-2 rounded border border-amber-200 bg-amber-50/80 hover:bg-amber-100 transition-colors"
                    >
                      <p className="text-sm font-medium text-gray-900">
                        {row.full_name || row.contact_email || row.client_id}
                      </p>
                      {row.crn && <p className="text-xs text-gray-600">CRN: {row.crn}</p>}
                      <p className="text-xs text-amber-800 mt-1">
                        Grace ends: {formatAdminDate(row.grace_period_ends_at) || '—'}
                        {row.payment_failed_at ? ` · Failed: ${formatAdminDate(row.payment_failed_at)}` : ''}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Clients Needing Attention */}
            {statistics?.clients_needing_attention?.length > 0 && (
              <Card data-testid="attention-panel">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Needs Attention
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {statistics.clients_needing_attention.slice(0, 5).map((client) => (
                    <button
                      key={client.client_id}
                      onClick={() => setSelectedClientId(client.client_id)}
                      className="w-full text-left p-2 rounded border border-amber-200 bg-amber-50 hover:bg-amber-100 transition-colors"
                    >
                      <p className="text-sm font-medium text-gray-900">
                        {client.full_name || client.contact_email || 'Unknown'}
                      </p>
                      {(client.crn || client.customer_reference) && (
                        <p className="text-xs text-gray-600">CRN: {client.crn || client.customer_reference}</p>
                      )}
                      <p className="text-xs text-amber-700">
                        {client.entitlement_status === 'LIMITED' ? 'Payment issue' : 'Setup incomplete'}
                      </p>
                    </button>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Client Details */}
          <div className="lg:col-span-2">
            {loadingSnapshot ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-electric-teal mx-auto mb-3" />
                  <p className="text-gray-500">Loading billing details...</p>
                </CardContent>
              </Card>
            ) : billingSnapshot ? (
              <div className="space-y-4">
                {/* Client Identity */}
                <Card data-testid="client-identity">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <User className="w-4 h-4" />
                        Client Details
                      </CardTitle>
                      {getEntitlementBadge(billingSnapshot.entitlement_status)}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Name</p>
                        <p className="font-medium">{billingSnapshot.contact_name || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Email</p>
                        <p className="font-medium">{billingSnapshot.contact_email}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Company</p>
                        <p className="font-medium">{billingSnapshot.company_name || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">CRN</p>
                        <p className="font-medium font-mono text-xs">{billingSnapshot.crn || 'N/A'}</p>
                      </div>
                      <div className="col-span-2">
                        <p className="text-gray-500">Client ID</p>
                        <p className="font-mono text-xs text-gray-600">{billingSnapshot.client_id}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {billingSnapshot.billing_attention_items?.length > 0 && (
                  <Card data-testid="billing-needs-attention" className="border-amber-200">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                        Needs attention
                      </CardTitle>
                      <CardDescription>
                        Rule-based flags from billing records only — verify in Stripe or logs before acting.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {billingSnapshot.billing_attention_items.map((item, idx) => (
                        <Alert
                          key={idx}
                          className={
                            item.severity === 'high'
                              ? 'border-red-200 bg-red-50'
                              : item.severity === 'medium'
                                ? 'border-amber-200 bg-amber-50'
                                : 'border-gray-200 bg-gray-50'
                          }
                        >
                          <AlertCircle className="w-4 h-4" />
                          <AlertDescription className="text-sm">
                            <span className="font-mono text-xs text-gray-500 mr-2">{item.code}</span>
                            {item.message}
                          </AlertDescription>
                        </Alert>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <Card data-testid="client-billing-overview">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      Client billing overview
                    </CardTitle>
                    <CardDescription>Summary fields for support — Stripe remains the billing authority.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700 mb-3">
                      Recovery path: compare Stripe and local state here, then use one safe sync/reconcile action. If
                      mismatch remains after refresh, this is <span className="font-semibold">Engineering escalation required</span>.
                    </div>
                    {billingSnapshot.billing_sync_visibility_note && (
                      <div
                        className={`mb-3 rounded-md border p-2 text-xs ${
                          /incomplete|stripe_error|may be incomplete/i.test(
                            billingSnapshot.billing_sync_visibility_note
                          )
                            ? 'border-amber-200 bg-amber-50 text-amber-900'
                            : 'border-slate-200 bg-white text-slate-700'
                        }`}
                      >
                        <span className="font-semibold">Sync / data caution: </span>
                        {billingSnapshot.billing_sync_visibility_note}
                      </div>
                    )}
                    {Array.isArray(billingSnapshot.billing_operational_narrative_lines) &&
                      billingSnapshot.billing_operational_narrative_lines.length > 0 && (
                        <div className="mb-3 rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-800">
                          <p className="text-xs font-semibold text-slate-500 mb-2">Operational billing narrative</p>
                          <ol className="list-decimal list-inside space-y-1 text-xs">
                            {billingSnapshot.billing_operational_narrative_lines.map((line, idx) => (
                              <li key={idx}>{line}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Plan status (display)</p>
                        <p className="font-medium">{billingSnapshot.plan_status_display || '—'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Billing status (display)</p>
                        <p className="font-medium">{billingSnapshot.billing_status_display || '—'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Next billing / period end</p>
                        <p className="font-medium">
                          {formatAdminDate(
                            billingSnapshot.subscription_lifecycle?.next_renewal_date ||
                              billingSnapshot.subscription_lifecycle?.current_period_end ||
                              billingSnapshot.next_billing_date
                          ) || '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Last updated from Stripe</p>
                        <p className="font-mono text-xs">
                          {billingSnapshot.billing_sync_state || billingSnapshot.subscription_lifecycle?.billing_sync_state || '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Stripe update timestamp</p>
                        <p className="font-medium text-xs">
                          {formatAdminDate(
                            billingSnapshot.billing_last_synced_at ||
                              billingSnapshot.subscription_lifecycle?.billing_last_synced_at
                          ) || '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Latest Stripe invoice (app record)</p>
                        <p className="font-mono text-xs break-all">
                          {billingSnapshot.last_stripe_invoice_id || '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Onboarding</p>
                        <p className="font-medium">{billingSnapshot.onboarding_status || '—'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Portal password setup</p>
                        <p className="font-medium">
                          {billingSnapshot.password_setup_complete ? 'Complete' : billingSnapshot.portal_user ? 'Pending' : 'No portal user'}
                        </p>
                      </div>
                      <div className="sm:col-span-2">
                        <p className="text-gray-500">Subscription checkout PDFs in ledger</p>
                        <p className="font-medium">
                          {typeof billingSnapshot.checkout_receipt_ledger_count === 'number'
                            ? billingSnapshot.checkout_receipt_ledger_count
                            : '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Access state</p>
                        <p className="font-mono text-xs">
                          {billingSnapshot.canonical_entitlement_state ||
                            billingSnapshot.subscription_lifecycle?.canonical_entitlement_state ||
                            '—'}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Last payment (Stripe mirror)</p>
                        <p className="font-medium text-xs">
                          {formatAdminDate(billingSnapshot.last_payment_at) || '—'}
                          {typeof billingSnapshot.last_payment_amount_pence === 'number'
                            ? (() => {
                                const cc = String(billingSnapshot.last_payment_currency || 'gbp').toUpperCase();
                                const sym = cc === 'GBP' ? '£' : `${cc} `;
                                return ` · ${sym}${(billingSnapshot.last_payment_amount_pence / 100).toFixed(2)}`;
                              })()
                            : ''}
                          {billingSnapshot.last_payment_status ? ` · ${billingSnapshot.last_payment_status}` : ''}
                        </p>
                        {billingSnapshot.last_payment_stripe_invoice_id && (
                          <p className="font-mono text-[10px] text-gray-500 break-all mt-0.5">
                            {billingSnapshot.last_payment_stripe_invoice_id}
                          </p>
                        )}
                        {billingSnapshot.last_payment_source_event_id && (
                          <p className="font-mono text-[10px] text-gray-500 break-all mt-0.5">
                            source event {billingSnapshot.last_payment_source_event_id}
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="text-gray-500">Open invoice / retry</p>
                        <p className="font-medium text-xs">
                          {billingSnapshot.open_invoice_status || '—'}
                          {billingSnapshot.stripe_next_payment_attempt_at
                            ? ` · next ${formatAdminDate(billingSnapshot.stripe_next_payment_attempt_at)}`
                            : ''}
                        </p>
                        {billingSnapshot.last_invoice_failure_message && (
                          <p className="text-xs text-red-700 mt-1">{billingSnapshot.last_invoice_failure_message}</p>
                        )}
                      </div>
                      <div className="sm:col-span-2">
                        <p className="text-gray-500">Last Stripe webhook (app)</p>
                        <p className="font-medium text-xs">
                          {formatAdminDate(billingSnapshot.stripe_webhook_last_received_at) || '—'}
                          {billingSnapshot.stripe_webhook_last_event_type
                            ? ` · ${billingSnapshot.stripe_webhook_last_event_type}`
                            : ''}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {billingSnapshot.subscription_lifecycle && (
                  <Card data-testid="subscription-lifecycle-card">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Clock className="w-4 h-4 text-electric-teal" />
                        Subscription lifecycle
                      </CardTitle>
                      <CardDescription>
                        Same fields as tenant billing status API (Stripe + client_billing; period may be refreshed from
                        Stripe).
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {billingSnapshot.billing_reconciliation_needed ? (
                        <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                          Reconciliation required: {billingSnapshot.billing_reconciliation_reason || 'Needs review'}
                        </div>
                      ) : null}
                      {(() => {
                        const sl = billingSnapshot.subscription_lifecycle;
                        const subStripe = String(
                          sl.subscription_status || billingSnapshot.stripe_subscription_status || ''
                        ).toUpperCase();
                        return (
                          <>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <p className="text-gray-500">Lifecycle status</p>
                                <p className="font-medium text-midnight-blue">{humanLifecycleLabel(sl)}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">billing_lifecycle_state</p>
                                <p className="font-mono text-xs">{sl.billing_lifecycle_state || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Stripe subscription status</p>
                                <div className="mt-1">
                                  {subStripe ? getSubscriptionBadge(subStripe) : <span className="text-gray-400">—</span>}
                                </div>
                              </div>
                              <div>
                                <p className="text-gray-500">Entitlement (billing record)</p>
                                <div className="mt-1">{getEntitlementBadge(sl.entitlement_status || '—')}</div>
                              </div>
                              <div>
                                <p className="text-gray-500">Access state</p>
                                <p className="font-mono text-xs">{sl.canonical_entitlement_state || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Period end (API)</p>
                                <p className="font-medium">
                                  {formatAdminDate(sl.next_renewal_date || sl.current_period_end) || '—'}
                                </p>
                              </div>
                              <div>
                                <p className="text-gray-500">Last updated from Stripe</p>
                                <p className="font-mono text-xs">{sl.billing_sync_state || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Reconciliation needed</p>
                                <p className="font-medium">{billingSnapshot.billing_reconciliation_needed ? 'Yes' : 'No'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Reconciliation reason</p>
                                <p className="font-mono text-xs">{billingSnapshot.billing_reconciliation_reason || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Stripe update timestamp</p>
                                <p className="font-medium text-xs">{formatAdminDate(sl.billing_last_synced_at) || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Grace ends</p>
                                <p className="font-medium">{formatAdminDate(sl.grace_period_ends_at) || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Payment failed at</p>
                                <p className="font-medium">{formatAdminDate(sl.payment_failed_at) || '—'}</p>
                              </div>
                              <div>
                                <p className="text-gray-500">Charge automatically</p>
                                <p className="font-medium">
                                  {sl.charge_automatically === true
                                    ? 'Yes'
                                    : sl.charge_automatically === false
                                      ? 'No'
                                      : '—'}
                                </p>
                              </div>
                              <div className="sm:col-span-2">
                                <p className="text-gray-500">Cancel at period end</p>
                                <p className="font-medium">
                                  {sl.cancel_at_period_end === true
                                    ? 'Yes'
                                    : sl.cancel_at_period_end === false
                                      ? 'No'
                                      : '—'}
                                </p>
                              </div>
                            </div>
                            {!sl.has_subscription && (
                              <p className="text-xs text-gray-500">No subscription on file in client_billing for this client.</p>
                            )}
                          </>
                        );
                      })()}
                    </CardContent>
                  </Card>
                )}

                {/* Plan & Subscription */}
                <Card data-testid="subscription-info">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <CreditCard className="w-4 h-4" />
                      Subscription & Plan
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Plan</p>
                        <p className="font-medium">{billingSnapshot.plan_name} ({billingSnapshot.plan_code})</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Property Limit</p>
                        <p className="font-medium">
                          {billingSnapshot.current_property_count} / {billingSnapshot.max_properties}
                          {billingSnapshot.over_property_limit && (
                            <span className="ml-2 text-red-500">(Over limit!)</span>
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Subscription status (client record)</p>
                        <div className="mt-1">
                          {getSubscriptionBadge(
                            String(
                              billingSnapshot.stripe_subscription_status ||
                                billingSnapshot.subscription_status ||
                                'NONE'
                            ).toUpperCase()
                          )}
                        </div>
                      </div>
                      <div>
                        <p className="text-gray-500">Onboarding</p>
                        <p className="font-medium">{billingSnapshot.onboarding_status}</p>
                      </div>
                      {billingSnapshot.current_period_end && (
                        <div className="col-span-2">
                          <p className="text-gray-500">Current Period</p>
                          <p className="font-medium">
                            {billingSnapshot.current_period_start
                              ? `${new Date(billingSnapshot.current_period_start).toLocaleDateString()} - `
                              : '— '}
                            {new Date(billingSnapshot.current_period_end).toLocaleDateString()}
                            {billingSnapshot.cancel_at_period_end && (
                              <span className="ml-2 text-amber-600">(Cancels at end)</span>
                            )}
                          </p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Change plan – support flow for upgrade/downgrade (always show so support can find it) */}
                <Card data-testid="change-plan-card">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <CreditCard className="w-4 h-4" />
                      Change Plan (Support)
                    </CardTitle>
                    <CardDescription>
                      When a client contacts support for an upgrade or downgrade, choose the new plan below. Apply at period end to avoid proration (recommended for downgrades).
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {!billingSnapshot.stripe_subscription_id ? (
                      <Alert className="border-amber-200 bg-amber-50">
                        <Info className="w-4 h-4 text-amber-600" />
                        <AlertDescription>
                          <span className="font-medium text-amber-800">No active Stripe subscription.</span>
                          <span className="block mt-1 text-amber-700 text-sm">
                            Create a billing portal link below and send it to the client so they can subscribe, or create the subscription in Stripe first.
                          </span>
                        </AlertDescription>
                      </Alert>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-700">New plan</label>
                          <select
                            value={changePlanCode}
                            onChange={(e) => setChangePlanCode(e.target.value)}
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                            data-testid="change-plan-select"
                          >
                            <option value="PLAN_1_SOLO">Solo Landlord</option>
                            <option value="PLAN_2_PORTFOLIO">Portfolio / Small Agent</option>
                            <option value="PLAN_3_PRO">Professional / Agent / HMO</option>
                          </select>
                        </div>
                        <label className="flex items-center gap-2 text-sm cursor-pointer">
                          <input
                            type="checkbox"
                            checked={applyAtPeriodEnd}
                            onChange={(e) => setApplyAtPeriodEnd(e.target.checked)}
                            className="rounded border-gray-300"
                            data-testid="apply-at-period-end"
                          />
                          Apply at period end (no proration; recommended for downgrades)
                        </label>
                        <Button
                          onClick={handleChangePlan}
                          disabled={changingPlan || changePlanCode === billingSnapshot.plan_code}
                          variant="default"
                          className="w-full sm:w-auto"
                          data-testid="change-plan-btn"
                        >
                          {changingPlan ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Updating...
                            </>
                          ) : (
                            'Change plan'
                          )}
                        </Button>
                        {changePlanCode === billingSnapshot.plan_code && (
                          <p className="text-sm text-gray-500">Select a different plan to change.</p>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>

                <Card data-testid="admin-cancel-subscription-card">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      Cancel Subscription (Support)
                    </CardTitle>
                    <CardDescription>
                      Cancel on the customer&apos;s behalf using the same billing rules as self-service cancellation.
                      {getGovernanceWarning('admin_cancel_subscription')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {!billingSnapshot.stripe_subscription_id ? (
                      <p className="text-sm text-gray-500">No active subscription to cancel.</p>
                    ) : adminAlreadyCancelled ? (
                      <Alert className="border-gray-200 bg-gray-50">
                        <AlertDescription>
                          Subscription is already cancelled. No further cancellation action is available.
                        </AlertDescription>
                      </Alert>
                    ) : adminCancelScheduled ? (
                      <Alert className="border-amber-200 bg-amber-50">
                        <AlertDescription>
                          Cancellation is already scheduled at period end. Access continues until{' '}
                          {billingSnapshot.current_period_end
                            ? new Date(billingSnapshot.current_period_end).toLocaleDateString('en-GB')
                            : 'the billing period ends'}
                          .
                        </AlertDescription>
                      </Alert>
                    ) : (
                      <>
                        <p className="text-sm text-gray-600">
                          Choose end-of-period (customer keeps access until renewal date) or immediate cancellation
                          (access ends now). A support reason, confirmation, and step-up are required.
                        </p>
                        <p className="text-xs text-gray-500">{getGovernanceEscalationGuidance('admin_cancel_subscription')}</p>
                        <Button
                          variant="destructive"
                          onClick={() => setShowAdminCancelDialog(true)}
                          disabled={!adminCanCancelSubscription}
                          data-testid="admin-cancel-subscription-btn"
                        >
                          Cancel subscription on behalf of client
                        </Button>
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Stripe Details */}
                <Card data-testid="stripe-info">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Stripe Details
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Customer ID</span>
                        {billingSnapshot.stripe_customer_id ? (
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded">{billingSnapshot.stripe_customer_id}</code>
                        ) : (
                          <span className="text-gray-400">Not set</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Subscription ID</span>
                        {billingSnapshot.stripe_subscription_id ? (
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded">{billingSnapshot.stripe_subscription_id}</code>
                        ) : (
                          <span className="text-gray-400">Not set</span>
                        )}
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Onboarding Fee Paid</span>
                        {billingSnapshot.onboarding_fee_paid ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : (
                          <XCircle className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                      {billingSnapshot.payment_failed_at && (
                        <Alert className="border-red-200 bg-red-50">
                          <AlertCircle className="w-4 h-4 text-red-600" />
                          <AlertDescription className="text-red-800">
                            Payment failed on{' '}
                            {formatAdminDate(billingSnapshot.payment_failed_at) ||
                              new Date(billingSnapshot.payment_failed_at).toLocaleDateString()}
                          </AlertDescription>
                        </Alert>
                      )}
                      {billingSnapshot.last_synced_at && (
                        <p className="text-xs text-gray-400 mt-2">
                          Last synced: {new Date(billingSnapshot.last_synced_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Receipts & Invoices */}
                <Card data-testid="admin-receipts-section">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Receipts &amp; Invoices
                    </CardTitle>
                    <CardDescription>
                    Checkout / renewal PDF artefacts, paid-invoice ledger rows (financial evidence), and paid service
                    orders for this client (date filter uses each row&apos;s issued / paid timestamp).
                  </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {(receiptsMeta.stripe_activity_without_payment_ledger ||
                      billingSnapshot?.payment_reconciliation?.stripe_evidence_but_no_payment_ledger_rows) && (
                      <Alert className="border-amber-300 bg-amber-50/90" data-testid="payment-ledger-reconcile-hint">
                        <AlertTriangle className="w-4 h-4 text-amber-800" />
                        <AlertDescription className="text-sm text-amber-950">
                          Stripe subscription webhooks are on file, but no paid-invoice payment ledger rows were found
                          yet. Operational activity is not financial evidence — run reconciliation to materialize paid
                          Stripe invoices into the ledger (idempotent).
                          {typeof receiptsMeta.subscription_payment_ledger_paid_total === 'number' ? (
                            <span className="block mt-1 text-xs text-amber-900/90">
                              Ledger paid rows (total): {receiptsMeta.subscription_payment_ledger_paid_total}; processed
                              payment-like webhooks: {receiptsMeta.stripe_payment_related_processed_webhooks ?? '—'}.
                            </span>
                          ) : null}
                        </AlertDescription>
                      </Alert>
                    )}
                    <div className="flex flex-wrap gap-2 items-end">
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">Type</label>
                        <select
                          value={receiptTypeFilter}
                          onChange={(e) => setReceiptTypeFilter(e.target.value)}
                          className="flex h-9 rounded-md border border-input bg-transparent px-2 text-sm"
                          data-testid="receipt-filter-type"
                        >
                          <option value="all">All</option>
                          <option value="subscription">Subscription only</option>
                          <option value="subscription_ledger">Stripe payment ledger only</option>
                          <option value="order">Orders only</option>
                          <option value="intake_order">Intake orders</option>
                          <option value="one_off_order">One-off services</option>
                          <option value="cvp_order">CVP-linked orders</option>
                        </select>
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">Status</label>
                        <Input
                          placeholder="e.g. PAID"
                          value={receiptStatusFilter}
                          onChange={(e) => setReceiptStatusFilter(e.target.value)}
                          className="h-9 w-28 text-sm"
                          data-testid="receipt-filter-status"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">From</label>
                        <Input
                          type="date"
                          value={receiptDateFrom}
                          onChange={(e) => setReceiptDateFrom(e.target.value)}
                          className="h-9 w-40 text-sm"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-gray-500">To</label>
                        <Input
                          type="date"
                          value={receiptDateTo}
                          onChange={(e) => setReceiptDateTo(e.target.value)}
                          className="h-9 w-40 text-sm"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => fetchClientReceipts(selectedClientId)}
                        disabled={receiptsLoading}
                        data-testid="receipt-refresh"
                      >
                        {receiptsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        <span className="ml-1">Refresh</span>
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleReconcileSubscriptionPaymentLedger}
                        disabled={receiptsLoading || paymentLedgerReconcileRunning || !selectedClientId}
                        data-testid="receipt-ledger-reconcile"
                        title={getGovernanceWarning('reconcile_subscription_payment_ledger')}
                      >
                        {paymentLedgerReconcileRunning ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <CreditCard className="w-4 h-4" />
                        )}
                        <span className="ml-1">Reconcile payment ledger</span>
                      </Button>
                    </div>

                    <AdminPaymentHistoryTable
                      rows={receipts}
                      loading={receiptsLoading}
                      error={receiptsError}
                      actionKey={receiptActionKey}
                      onDownload={handleReceiptDownload}
                      onResend={handleReceiptResend}
                      reconciliationHint={
                        receiptsMeta.stripe_activity_without_payment_ledger
                          ? 'Stripe processed subscription payment webhooks on file, but no paid-invoice payment ledger rows matched this client yet. Use “Reconcile payment ledger” above to materialize paid Stripe invoices (financial evidence).'
                          : ''
                      }
                    />
                  </CardContent>
                </Card>

                {/* Admin Actions */}
                <Card data-testid="admin-actions">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Admin Actions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                      <span className="font-semibold">High-impact operation</span> - run one recovery action at a time,
                      verify snapshot updates, then escalate if inconsistency persists.
                    </div>
                    <div className="rounded-md border border-gray-200 bg-gray-50 p-2 text-xs text-gray-700">
                      {getGovernanceEscalationGuidance('run_subscription_lifecycle_batch')}
                    </div>
                    {/* Sync Button */}
                    <Button
                      onClick={handleSync}
                      disabled={syncing}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="sync-btn"
                    >
                      {syncing ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4 mr-2" />
                      )}
                      Sync Billing Now
                    </Button>

                    <Button
                      type="button"
                      onClick={handleRunSubscriptionLifecycleJob}
                      disabled={lifecycleJobRunning}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="subscription-lifecycle-job-btn"
                      title="Runs the same batch as the scheduled subscription_lifecycle job"
                    >
                      {lifecycleJobRunning ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4 mr-2" />
                      )}
                      Run subscription lifecycle job
                      <span className={`ml-auto rounded border px-2 py-0.5 text-[10px] ${getGovernanceRiskBadgeClass('run_subscription_lifecycle_batch')}`}>
                        Governed
                      </span>
                    </Button>

                    <Button
                      type="button"
                      onClick={handleRunStripeSubscriptionReconcile}
                      disabled={stripeReconcileRunning}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="stripe-subscription-reconcile-job-btn"
                      title="Re-fetch a batch of Stripe subscriptions (scheduled job safety net)"
                    >
                      {stripeReconcileRunning ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4 mr-2" />
                      )}
                      Run Stripe subscription reconcile batch
                      <span className={`ml-auto rounded border px-2 py-0.5 text-[10px] ${getGovernanceRiskBadgeClass('run_stripe_reconcile_batch')}`}>
                        Governed
                      </span>
                    </Button>
                    {lastLifecycleJobResult?.outcome_metrics && (
                      <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-700 space-y-1">
                        <p className="font-medium text-gray-800">Last job metrics</p>
                        <p>Post-grace updates: {lastLifecycleJobResult.outcome_metrics.post_grace_updates ?? '—'}</p>
                        <p>Grace nudges: {lastLifecycleJobResult.outcome_metrics.grace_reminders ?? '—'}</p>
                        <p>Renewal 7d: {lastLifecycleJobResult.outcome_metrics.renewal_7d ?? '—'}</p>
                        <p>Renewal 3d: {lastLifecycleJobResult.outcome_metrics.renewal_3d ?? '—'}</p>
                        {lastLifecycleJobResult.message && (
                          <p className="text-gray-500 pt-1 border-t border-gray-200">{lastLifecycleJobResult.message}</p>
                        )}
                      </div>
                    )}

                    {/* Portal Link */}
                    <Button
                      onClick={handleCreatePortalLink}
                      disabled={creatingPortal || !billingSnapshot.stripe_customer_id}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="portal-link-btn"
                    >
                      {creatingPortal ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <ExternalLink className="w-4 h-4 mr-2" />
                      )}
                      Create Manage Billing Link
                    </Button>

                    {portalLink && (
                      <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                        <p className="text-xs text-green-700 mb-2">Billing Portal Link:</p>
                        <div className="flex gap-2">
                          <Input value={portalLink} readOnly className="text-xs font-mono" />
                          <Button size="sm" variant="outline" onClick={() => copyToClipboard(portalLink)}>
                            <Copy className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Resend Setup */}
                    <Button
                      onClick={handleResendSetup}
                      disabled={resendingSetup || !billingSnapshot.portal_user}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="resend-setup-btn"
                    >
                      {resendingSetup ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Key className="w-4 h-4 mr-2" />
                      )}
                      Resend Password Setup Link
                      {billingSnapshot.password_setup_complete && (
                        <span className="ml-auto text-xs text-green-600">(Already set)</span>
                      )}
                    </Button>

                    {/* Force Provision */}
                    <Button
                      onClick={handleForceProvision}
                      disabled={provisioning || billingSnapshot.entitlement_status !== 'ENABLED'}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="provision-btn"
                    >
                      {provisioning ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4 mr-2" />
                      )}
                      Re-run Provisioning
                      <span className={`ml-auto rounded border px-2 py-0.5 text-[10px] ${getGovernanceRiskBadgeClass('force_provision')}`}>
                        Governed
                      </span>
                      {billingSnapshot.entitlement_status !== 'ENABLED' && (
                        <span className="ml-auto text-xs text-gray-400">(Requires ENABLED)</span>
                      )}
                    </Button>
                    <p className="text-[11px] text-gray-600">{getGovernanceWarning('force_provision')}</p>

                    {/* Send Message */}
                    <Button
                      onClick={() => setShowMessageModal(true)}
                      variant="outline"
                      className="w-full justify-start"
                      data-testid="message-btn"
                    >
                      <MessageSquare className="w-4 h-4 mr-2" />
                      Send Message
                    </Button>
                  </CardContent>
                </Card>

                {/* Subscription activity — stored Stripe webhooks only */}
                <Card data-testid="subscription-activity">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Subscription activity</CardTitle>
                    <CardDescription>
                      Stripe webhook events recorded for this client (processed or failed). Not a full Stripe audit
                      trail.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {!billingSnapshot.stripe_timeline?.length ? (
                      <p className="text-sm text-gray-500 text-center py-8 border border-dashed rounded-md bg-gray-50/50">
                        No subscription webhook history recorded for this client yet.
                      </p>
                    ) : (
                      <div className="overflow-x-auto border rounded-md">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-gray-50 text-left border-b">
                              <th className="p-2 font-medium">When</th>
                              <th className="p-2 font-medium">Summary</th>
                              <th className="p-2 font-medium">Raw type</th>
                              <th className="p-2 font-medium">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {billingSnapshot.stripe_timeline.map((row, idx) => (
                              <tr key={row.event_id || idx} className="border-b last:border-0">
                                <td className="p-2 whitespace-nowrap text-xs text-gray-600">
                                  {row.created ? new Date(row.created).toLocaleString() : '—'}
                                </td>
                                <td className="p-2">{row.summary}</td>
                                <td className="p-2 font-mono text-xs text-gray-500 max-w-[180px] truncate" title={row.type}>
                                  {row.type}
                                </td>
                                <td className="p-2">
                                  <span
                                    className={`px-2 py-0.5 text-xs rounded ${
                                      row.status === 'PROCESSED'
                                        ? 'bg-green-100 text-green-800'
                                        : row.status === 'FAILED'
                                          ? 'bg-red-100 text-red-800'
                                          : 'bg-gray-100 text-gray-700'
                                    }`}
                                  >
                                    {row.status}
                                  </span>
                                  {row.error_preview && (
                                    <p className="text-xs text-red-600 mt-1 max-w-xs truncate" title={row.error_preview}>
                                      {row.error_preview}
                                    </p>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <Card data-testid="admin-billing-empty">
                <CardContent className="py-14 text-center px-6">
                  <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-700 font-medium">No client selected</p>
                  <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
                    Search by email, CRN, client ID, or postcode, then select a client to view billing summary,
                    receipts, subscription activity, and support actions.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
        )}
      </main>

      {/* Message Modal */}
      {showMessageModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full mx-4 shadow-xl" data-testid="message-modal">
            <h3 className="text-lg font-semibold mb-4">Send Message to Client</h3>
            
            {/* Channels */}
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700 mb-2 block">Channels</label>
              <div className="flex gap-2">
                {['in_app', 'email', 'sms'].map((channel) => (
                  <button
                    key={channel}
                    onClick={() => {
                      if (messageChannels.includes(channel)) {
                        setMessageChannels(messageChannels.filter(c => c !== channel));
                      } else {
                        setMessageChannels([...messageChannels, channel]);
                      }
                    }}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      messageChannels.includes(channel)
                        ? 'bg-electric-teal text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {channel === 'in_app' ? 'In-App' : channel.charAt(0).toUpperCase() + channel.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Template */}
            <div className="mb-4">
              <label className="text-sm font-medium text-gray-700 mb-2 block">Template (Optional)</label>
              <select
                value={messageTemplate}
                onChange={(e) => setMessageTemplate(e.target.value)}
                className="w-full p-2 border border-gray-200 rounded-lg"
              >
                <option value="">Custom Message</option>
                <option value="payment_received">Payment Received</option>
                <option value="provisioning_complete">Provisioning Complete</option>
                <option value="payment_failed">Payment Failed</option>
                <option value="subscription_canceled">Subscription Cancelled</option>
              </select>
            </div>
            
            {/* Custom Message */}
            {!messageTemplate && (
              <div className="mb-4">
                <label className="text-sm font-medium text-gray-700 mb-2 block">Message</label>
                <textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  rows={4}
                  className="w-full p-3 border border-gray-200 rounded-lg resize-none"
                  placeholder="Enter your message..."
                />
              </div>
            )}
            
            {/* Actions */}
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowMessageModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSendMessage}
                disabled={sendingMessage || messageChannels.length === 0}
                className="bg-electric-teal hover:bg-teal-600"
              >
                {sendingMessage ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                Send Message
              </Button>
            </div>
          </div>
        </div>
      )}

      {showAdminCancelDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="admin-cancel-modal">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Cancel subscription on behalf of client</h3>
            <p className="text-sm text-gray-600 mb-4">
              {getGovernanceConfirmationWording('admin_cancel_subscription')}
            </p>
            <div className="space-y-4 mb-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Support reason (min 10 characters)</label>
                <textarea
                  value={adminCancelReason}
                  onChange={(e) => setAdminCancelReason(e.target.value)}
                  className="w-full p-2 border border-gray-200 rounded-lg text-sm min-h-[80px]"
                  data-testid="admin-cancel-reason"
                  placeholder="Document why support is cancelling this subscription…"
                />
              </div>
              <div className="space-y-2">
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="adminCancelMode"
                    checked={!adminCancelImmediate}
                    onChange={() => setAdminCancelImmediate(false)}
                    data-testid="admin-cancel-at-period-end"
                  />
                  <span>
                    <span className="font-medium">Cancel at period end</span>
                    <span className="block text-gray-500 text-xs">
                      Customer keeps full access until the current billing period ends.
                    </span>
                  </span>
                </label>
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name="adminCancelMode"
                    checked={adminCancelImmediate}
                    onChange={() => setAdminCancelImmediate(true)}
                    data-testid="admin-cancel-immediate"
                  />
                  <span>
                    <span className="font-medium text-red-700">Cancel immediately</span>
                    <span className="block text-gray-500 text-xs">
                      Ends subscription now and revokes paid access.
                    </span>
                  </span>
                </label>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={() => {
                  setShowAdminCancelDialog(false);
                  setAdminCancelReason('');
                  setAdminCancelImmediate(false);
                }}
                disabled={adminCancelling}
              >
                Close
              </Button>
              <Button
                variant="destructive"
                onClick={handleAdminCancelSubscription}
                disabled={adminCancelling || adminCancelReason.trim().length < 10}
                data-testid="admin-cancel-confirm-btn"
              >
                {adminCancelling ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Processing…
                  </>
                ) : (
                  'Confirm cancellation'
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
      {adminCancelStepUp.modal}
    </div>
  );
};

export default AdminBillingPage;
