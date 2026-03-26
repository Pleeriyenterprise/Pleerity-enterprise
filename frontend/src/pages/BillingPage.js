import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useStepUpApi } from '../hooks/useStepUpApi';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { 
  Check, 
  X, 
  ArrowLeft, 
  Sparkles, 
  Building2, 
  Users, 
  Zap,
  Crown,
  Shield,
  FileText,
  Bell,
  Webhook,
  Palette,
  Calendar,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  ArrowRight,
  AlertTriangle,
  XCircle,
  ExternalLink
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import api, { clientAPI } from '../api/client';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { formatUpgradeUsageContext } from '../components/UpgradePrompt';

// Plan configuration - matches backend plan_registry.py
const PLANS = [
  {
    code: 'PLAN_1_SOLO',
    name: 'Solo Landlord',
    description: 'Perfect for DIY landlords managing 1-2 properties',
    monthlyPrice: 19,
    onboardingFee: 49,
    maxProperties: 2,
    color: '#6B7280',
    icon: Building2,
    badge: null,
    targetAudience: 'DIY landlords',
  },
  {
    code: 'PLAN_2_PORTFOLIO',
    name: 'Portfolio',
    description: 'For portfolio landlords and small letting agents',
    monthlyPrice: 39,
    onboardingFee: 79,
    maxProperties: 10,
    color: '#00B8A9',
    icon: Users,
    badge: 'Most Popular',
    targetAudience: 'Portfolio landlords, small agents',
  },
  {
    code: 'PLAN_3_PRO',
    name: 'Professional',
    description: 'For letting agents, HMOs, and serious operators',
    monthlyPrice: 79,
    onboardingFee: 149,
    maxProperties: 25,
    color: '#0B1D3A',
    icon: Crown,
    badge: 'Full Features',
    targetAudience: 'Letting agents, HMOs',
  },
];

// Feature categories with all features
const FEATURE_CATEGORIES = [
  {
    name: 'Core Features',
    icon: Shield,
    features: [
      { key: 'compliance_dashboard', name: 'Compliance Dashboard', description: 'View property compliance status at a glance' },
      { key: 'compliance_score', name: 'Compliance Score', description: 'Track your compliance score with explanations' },
      { key: 'compliance_calendar', name: 'Compliance Calendar', description: 'View expiry dates in calendar format' },
      { key: 'email_notifications', name: 'Email Notifications', description: 'Receive compliance reminders via email' },
      { key: 'multi_file_upload', name: 'Multi-File Upload', description: 'Upload multiple documents at once' },
      { key: 'score_trending', name: 'Score Trending', description: 'View compliance score history and trends' },
    ],
  },
  {
    name: 'AI Features',
    icon: Sparkles,
    features: [
      { key: 'ai_extraction_basic', name: 'AI Extraction (Basic)', description: 'Auto-extract document type, issue and expiry dates' },
      { key: 'ai_extraction_advanced', name: 'AI Extraction (Advanced)', description: 'Confidence scoring and field validation' },
      { key: 'extraction_review_ui', name: 'Extraction Review UI', description: 'Review and approve AI-extracted data' },
    ],
  },
  {
    name: 'Documents',
    icon: FileText,
    features: [
      { key: 'zip_upload', name: 'ZIP Archive Upload', description: 'Upload documents as a single ZIP archive' },
    ],
  },
  {
    name: 'Reporting',
    icon: FileText,
    features: [
      { key: 'reports_pdf', name: 'PDF Reports', description: 'Download compliance reports as PDF' },
      { key: 'reports_csv', name: 'CSV Reports', description: 'Download compliance data as CSV' },
      { key: 'scheduled_reports', name: 'Scheduled Reports', description: 'Automatically receive reports on schedule' },
    ],
  },
  {
    name: 'Communication',
    icon: Bell,
    features: [
      { key: 'sms_reminders', name: 'SMS Reminders', description: 'Receive compliance reminders via SMS' },
    ],
  },
  {
    name: 'Tenant Portal',
    icon: Users,
    features: [
      { key: 'tenant_portal', name: 'Tenant Portal', description: 'Allow tenants to view property compliance (read-only)' },
    ],
  },
  {
    name: 'Integrations',
    icon: Webhook,
    features: [
      {
        key: 'webhooks',
        name: 'Webhooks & read API',
        description: 'Outbound webhooks (push) and scoped read API keys (HTTP pull) for integrations',
      },
    ],
  },
  {
    name: 'Advanced',
    icon: Palette,
    features: [
      { key: 'white_label_reports', name: 'White-Label Reports', description: 'Custom branding for reports' },
      { key: 'audit_log_export', name: 'Audit Log Export', description: 'Export audit logs for compliance review' },
    ],
  },
];

// Feature availability matrix
const FEATURE_MATRIX = {
  PLAN_1_SOLO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: false,
    extraction_review_ui: false,
    zip_upload: false,
    reports_pdf: false,
    reports_csv: false,
    scheduled_reports: false,
    sms_reminders: false,
    tenant_portal: false,
    webhooks: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_2_PORTFOLIO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: true,
    extraction_review_ui: true,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: false,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: false,
    webhooks: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_3_PRO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: true,
    extraction_review_ui: true,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: true,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: true,
    webhooks: true,
    white_label_reports: true,
    audit_log_export: true,
  },
};

/** Stripe epoch or missing dates must not surface as 1970 in the UI */
const MIN_VALID_RENEWAL_MS = 946684800000;

function formatRenewalDisplay(isoOrDate) {
  if (isoOrDate == null || isoOrDate === '') return null;
  const t = new Date(isoOrDate).getTime();
  if (Number.isNaN(t) || t < MIN_VALID_RENEWAL_MS) return null;
  return new Date(isoOrDate).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

function humanBillingStatusLabel(bs) {
  if (!bs?.has_subscription) return 'No active subscription';
  if (bs.cancel_at_period_end) return 'Cancelling at period end';
  const lc = (bs.billing_lifecycle_state || 'active').toLowerCase();
  if (lc === 'grace_period') return 'Payment retry (grace period)';
  if (lc === 'limited') return 'Restricted — payment overdue';
  if (lc === 'past_due') return 'Payment past due';
  if (lc === 'expired') return 'Subscription expired';
  if (lc === 'cancelled') return 'Subscription cancelled';
  if (lc === 'renewing') return 'Active — renewal soon';
  return 'Active';
}

const BillingPage = () => {
  const navigate = useNavigate();
  const { usageContext, refetch: refetchEntitlements } = useEntitlements();
  const billingUsageHint = formatUpgradeUsageContext(usageContext);
  const [usageRefreshing, setUsageRefreshing] = useState(false);
  const billingStepUp = useStepUpApi();
  const [searchParams] = useSearchParams();
  const [currentPlan, setCurrentPlan] = useState(null);
  const [entitlements, setEntitlements] = useState(null);
  const [billingStatus, setBillingStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState({});
  const [upgrading, setUpgrading] = useState(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelContextSnapshot, setCancelContextSnapshot] = useState(null);
  const [cancelContextLoading, setCancelContextLoading] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [billingMainTab, setBillingMainTab] = useState('account');
  const [paymentMethodInfo, setPaymentMethodInfo] = useState(null);
  const [pdfReceipts, setPdfReceipts] = useState([]);
  const [portalOpening, setPortalOpening] = useState(false);
  const [planCatalog, setPlanCatalog] = useState(null);

  const highlightPlan = searchParams.get('upgrade_to');

  const displayPlans = useMemo(() => {
    if (!planCatalog || planCatalog.length === 0) return PLANS;
    const byCode = Object.fromEntries(planCatalog.map((p) => [p.code, p]));
    return PLANS.map((p) => {
      const api = byCode[p.code];
      if (!api) return p;
      return {
        ...p,
        name: api.name ?? p.name,
        description: api.description ?? p.description,
        monthlyPrice: api.monthly_price != null ? Number(api.monthly_price) : p.monthlyPrice,
        onboardingFee: api.onboarding_fee != null ? Number(api.onboarding_fee) : p.onboardingFee,
        maxProperties: api.max_properties != null ? api.max_properties : p.maxProperties,
        color: api.color ?? p.color,
        badge: api.badge !== undefined ? api.badge : p.badge,
        targetAudience: api.target_audience ?? p.targetAudience,
      };
    });
  }, [planCatalog]);

  const handleRefreshUsage = useCallback(async () => {
    setUsageRefreshing(true);
    try {
      const ok = await refetchEntitlements();
      if (ok) {
        toast.success('Usage data updated');
      } else {
        toast.error('Could not refresh usage data');
      }
    } finally {
      setUsageRefreshing(false);
    }
  }, [refetchEntitlements]);

  useEffect(() => {
    fetchEntitlements();
    fetchBillingStatus();
    const loadPlans = async () => {
      try {
        const res = await api.get('/billing/plans');
        setPlanCatalog(res.data?.plans || []);
      } catch {
        setPlanCatalog(null);
      }
    };
    loadPlans();
    // Expand all categories by default
    const expanded = {};
    FEATURE_CATEGORIES.forEach(cat => {
      expanded[cat.name] = true;
    });
    setExpandedCategories(expanded);
  }, []);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'account' || tab === 'plans') {
      setBillingMainTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!billingStatus?.has_subscription) {
      setInvoices([]);
      return;
    }
    if (billingMainTab === 'account') {
      fetchInvoices();
    }
  }, [billingStatus?.has_subscription, billingMainTab]);

  useEffect(() => {
    if (billingMainTab !== 'account') return;
    const loadPm = async () => {
      if (!billingStatus?.has_subscription) {
        setPaymentMethodInfo(null);
        return;
      }
      try {
        const res = await api.get('/billing/payment-method-summary');
        setPaymentMethodInfo(res.data);
      } catch {
        setPaymentMethodInfo(null);
      }
    };
    loadPm();
  }, [billingMainTab, billingStatus?.has_subscription]);

  useEffect(() => {
    if (billingMainTab !== 'account' || !billingStatus?.has_subscription) {
      setPdfReceipts([]);
      return;
    }
    const loadPdf = async () => {
      try {
        const res = await api.get('/client/billing/receipts');
        setPdfReceipts(res.data.receipts || []);
      } catch {
        setPdfReceipts([]);
      }
    };
    loadPdf();
  }, [billingMainTab, billingStatus?.has_subscription]);

  useEffect(() => {
    if (!showCancelModal) return;
    let cancelled = false;
    setCancelContextLoading(true);
    setCancelContextSnapshot(null);
    clientAPI
      .getProtectionSnapshot()
      .then((res) => {
        if (!cancelled) setCancelContextSnapshot(res.data || null);
      })
      .catch(() => {
        if (!cancelled) setCancelContextSnapshot(null);
      })
      .finally(() => {
        if (!cancelled) setCancelContextLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [showCancelModal]);

  const openBillingPortal = async () => {
    setPortalOpening(true);
    try {
      const origin = window.location.origin;
      const res = await billingStepUp.request((headers) =>
        api.post('/billing/portal', {}, { headers: { ...headers, Origin: origin } })
      );
      if (res.data?.portal_url) {
        window.location.href = res.data.portal_url;
      } else {
        toast.error('Could not open billing portal');
      }
    } catch (e) {
      if (e?.message === 'step_up_cancelled') return;
      toast.error(e.response?.data?.detail || 'Billing portal unavailable');
    } finally {
      setPortalOpening(false);
    }
  };

  const fetchEntitlements = async () => {
    try {
      const response = await api.get('/client/entitlements');
      setEntitlements(response.data);
      setCurrentPlan(response.data.plan);
    } catch (error) {
      console.error('Failed to fetch entitlements:', error);
      toast.error('Failed to load plan information');
    } finally {
      setLoading(false);
    }
  };

  const fetchBillingStatus = async () => {
    try {
      const response = await api.get('/billing/status');
      setBillingStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch billing status:', error);
    }
  };

  const fetchInvoices = async () => {
    try {
      const response = await api.get('/billing/invoices');
      setInvoices(response.data.invoices || []);
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
    }
  };

  const handleCancelSubscription = async (cancelImmediately = false) => {
    setCancelling(true);
    try {
      await billingStepUp.request((headers) =>
        api.post('/billing/cancel', { cancel_immediately: cancelImmediately }, { headers })
      );

      if (cancelImmediately) {
        toast.success('Subscription cancelled', {
          description: 'Your subscription has been cancelled immediately.',
        });
      } else {
        toast.success('Cancellation scheduled', {
          description: 'Your subscription will end at the current billing period.',
        });
      }
      
      setShowCancelModal(false);
      // Refresh billing status
      await fetchBillingStatus();
      await fetchEntitlements();
      
    } catch (error) {
      if (error?.message === 'step_up_cancelled') {
        return;
      }
      console.error('Cancel error:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to cancel subscription';
      toast.error(errorMessage);
    } finally {
      setCancelling(false);
    }
  };

  const toggleCategory = (categoryName) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryName]: !prev[categoryName]
    }));
  };

  const handlePlanChange = async (planCode) => {
    if (planCode === currentPlan) {
      toast.info('You are already on this plan');
      return;
    }

    const currentPlanIndex = displayPlans.findIndex((p) => p.code === currentPlan);
    const targetPlanIndex = displayPlans.findIndex((p) => p.code === planCode);
    const isDowngrade = currentPlanIndex >= 0 && targetPlanIndex >= 0 && targetPlanIndex < currentPlanIndex;

    setUpgrading(planCode);

    try {
      const response = await billingStepUp.request((headers) =>
        api.post('/billing/checkout', { plan_code: planCode }, { headers })
      );

      toast.success('Redirecting to Stripe…', {
        description: isDowngrade
          ? 'Confirm your plan change. Downgrades typically apply from the next billing period.'
          : 'You will confirm payment or plan change in Stripe.',
      });
      
      // Redirect to checkout or billing portal
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else if (response.data.portal_url) {
        window.location.href = response.data.portal_url;
      } else {
        toast.error('No checkout URL received');
        setUpgrading(null);
      }
      
    } catch (error) {
      if (error?.message === 'step_up_cancelled') {
        setUpgrading(null);
        return;
      }
      console.error('Plan change error:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to start plan change';
      toast.error(errorMessage);
      setUpgrading(null);
    }
  };

  const getPlanStatus = (planCode) => {
    if (planCode === currentPlan) return 'current';

    const currentPlanIndex = displayPlans.findIndex((p) => p.code === currentPlan);
    const targetPlanIndex = displayPlans.findIndex((p) => p.code === planCode);
    if (currentPlanIndex < 0 || targetPlanIndex < 0) {
      return 'upgrade';
    }
    if (targetPlanIndex > currentPlanIndex) return 'upgrade';
    return 'downgrade';
  };

  const getFeatureCount = (planCode) => {
    const features = FEATURE_MATRIX[planCode];
    return Object.values(features).filter(Boolean).length;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="billing-loading">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal mx-auto mb-3" />
          <p className="text-gray-600">Loading plan information...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="billing-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-midnight-blue">Billing</h1>
              <p className="text-sm text-gray-500">
                {billingMainTab === 'account'
                  ? 'Subscription summary, billing history, and payment details'
                  : 'Compare plans and upgrade your subscription'}
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex flex-wrap gap-2 mb-8 border-b border-gray-200 pb-4" data-testid="billing-main-tabs">
          <button
            type="button"
            onClick={() => setBillingMainTab('account')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              billingMainTab === 'account'
                ? 'bg-midnight-blue text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Billing &amp; history
          </button>
          <button
            type="button"
            onClick={() => setBillingMainTab('plans')}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              billingMainTab === 'plans'
                ? 'bg-midnight-blue text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Plans &amp; upgrades
          </button>
        </div>

        <div
          className="flex flex-wrap items-center justify-between gap-3 mb-6 p-3 bg-white border border-gray-200 rounded-lg"
          data-testid="billing-usage-row"
        >
          {billingUsageHint ? (
            <p className="text-sm text-gray-600 flex-1 min-w-[200px]" data-testid="billing-usage-context">
              {billingUsageHint}
            </p>
          ) : (
            <span className="text-sm text-gray-500 flex-1 min-w-[200px]">
              Portfolio usage syncs with your account. Refresh to pull the latest property count and limits.
            </span>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={handleRefreshUsage}
            disabled={usageRefreshing}
            data-testid="billing-refresh-usage"
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${usageRefreshing ? 'animate-spin' : ''}`} />
            Refresh usage
          </Button>
        </div>

        {billingMainTab === 'account' ? (
          <div className="space-y-6" data-testid="billing-account-tab">
            {billingStatus?.has_subscription && billingStatus?.billing_lifecycle_state && (
              <>
                {billingStatus.billing_lifecycle_state === 'grace_period' && (
                  <Alert className="border-amber-300 bg-amber-50" data-testid="billing-grace-alert">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <AlertDescription className="text-amber-900 text-sm">
                      <strong>Payment issue</strong> — we could not charge your card. Update your payment method in
                      Stripe below. Resolve payment by{' '}
                      {billingStatus.grace_period_ends_at
                        ? new Date(billingStatus.grace_period_ends_at).toLocaleDateString('en-GB')
                        : 'the end of your grace period'}
                      . Some automations (SMS, webhooks, scheduled reports) stay paused until payment succeeds; core
                      compliance remains available.
                    </AlertDescription>
                  </Alert>
                )}
                {billingStatus.billing_lifecycle_state === 'limited' && (
                  <Alert className="border-red-200 bg-red-50" data-testid="billing-limited-alert">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    <AlertDescription className="text-red-900 text-sm">
                      <strong>Account restricted</strong> — the grace period for this invoice has ended. Update billing
                      to restore full access. Core compliance features stay available until you pay.
                    </AlertDescription>
                  </Alert>
                )}
                {billingStatus.billing_lifecycle_state === 'renewing' && !billingStatus.cancel_at_period_end && (
                  <Alert className="border-teal-200 bg-teal-50/50" data-testid="billing-renewing-alert">
                    <Calendar className="w-4 h-4 text-teal-700" />
                    <AlertDescription className="text-teal-900 text-sm">
                      {billingStatus.charge_automatically === false ? (
                        <>
                          Your billing period renews soon (
                          {formatRenewalDisplay(billingStatus?.current_period_end) || 'see date below'}). Complete
                          payment when invoiced to avoid interruption.
                        </>
                      ) : (
                        <>
                          Your subscription renews soon (
                          {formatRenewalDisplay(billingStatus?.current_period_end) || 'see date below'}). Payment is
                          automatic — confirm your card on file is valid.
                        </>
                      )}
                    </AlertDescription>
                  </Alert>
                )}
              </>
            )}
            {/* A. Subscription summary */}
            <Card data-testid="subscription-summary-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Subscription summary</CardTitle>
                <CardDescription>Your Compliance Vault Pro subscription status</CardDescription>
              </CardHeader>
              <CardContent className="grid sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Current plan</p>
                  <p className="font-medium text-midnight-blue">
                    {displayPlans.find((p) => p.code === currentPlan)?.name || currentPlan || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Billing status</p>
                  <p className="font-medium">{humanBillingStatusLabel(billingStatus)}</p>
                </div>
                <div>
                  <p className="text-gray-500">Next renewal / period end</p>
                  <p className="font-medium">
                    {formatRenewalDisplay(billingStatus?.current_period_end) || 'Not available'}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Price (plan rate)</p>
                  <p className="font-medium">
                    {currentPlan && displayPlans.find((p) => p.code === currentPlan) ? (
                      <>
                        £{displayPlans.find((p) => p.code === currentPlan).monthlyPrice}/mo
                        <span className="text-gray-500 font-normal">
                          {' '}
                          + £{displayPlans.find((p) => p.code === currentPlan).onboardingFee} setup
                        </span>
                      </>
                    ) : (
                      '—'
                    )}
                  </p>
                </div>
                <div className="sm:col-span-2">
                  <p className="text-gray-500">Subscription state</p>
                  <p className="font-medium font-mono text-xs mt-1">
                    {billingStatus?.subscription_status || (billingStatus?.has_subscription ? '—' : 'NONE')}
                    {billingStatus?.billing_lifecycle_state ? (
                      <span className="block text-gray-600 normal-case mt-1">
                        Lifecycle: {billingStatus.billing_lifecycle_state}
                        {billingStatus?.entitlement_status
                          ? ` · Entitlement: ${billingStatus.entitlement_status}`
                          : ''}
                      </span>
                    ) : null}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* C. Payment method — Stripe portal is source of truth */}
            <Card data-testid="payment-method-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Payment method</CardTitle>
                <CardDescription>
                  Card and billing details are managed securely in Stripe. We only show a masked summary here when
                  available.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!billingStatus?.has_subscription ? (
                  <p className="text-sm text-gray-600">Subscribe to a plan to add a payment method.</p>
                ) : (
                  <>
                    {paymentMethodInfo?.display && (
                      <p className="text-sm font-medium text-midnight-blue">{paymentMethodInfo.display}</p>
                    )}
                    {paymentMethodInfo?.message && !paymentMethodInfo?.display && (
                      <p className="text-sm text-gray-600">{paymentMethodInfo.message}</p>
                    )}
                    {!paymentMethodInfo?.display && !paymentMethodInfo?.message && paymentMethodInfo?.available === false && (
                      <p className="text-sm text-gray-600">Unable to load card summary. You can still manage payment methods in the portal.</p>
                    )}
                    <Button
                      type="button"
                      variant="outline"
                      className="border-electric-teal text-electric-teal"
                      onClick={openBillingPortal}
                      disabled={portalOpening}
                    >
                      {portalOpening ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <ExternalLink className="w-4 h-4 mr-2" />}
                      Update payment method in Stripe
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Unified billing history: Stripe invoices + Pleerity PDF receipts */}
            <Card data-testid="billing-history-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Billing history</CardTitle>
                <CardDescription>
                  Stripe invoices (paid charges) and Pleerity PDF receipts generated from subscription checkouts.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-10">
                {!billingStatus?.has_subscription ? (
                  <p className="text-sm text-gray-600 py-2">
                    No active subscription — billing history appears after you subscribe and pay.
                  </p>
                ) : (
                  <>
                    <div data-testid="stripe-invoice-history">
                      <h3 className="text-sm font-semibold text-midnight-blue mb-1">Stripe invoices</h3>
                      <p className="text-xs text-gray-500 mb-3">Line items and amounts as recorded by Stripe.</p>
                      {invoices.length === 0 ? (
                        <div className="py-8 text-center text-gray-500 text-sm border border-dashed rounded-lg bg-gray-50/50">
                          No Stripe invoices loaded yet. They appear after successful payments.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {invoices.map((inv) => (
                            <Card key={inv.id}>
                              <CardContent className="pt-4 pb-4">
                                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                                  <span className="text-sm font-medium text-gray-700">{inv.number || inv.id}</span>
                                  <span className="text-sm text-gray-500">
                                    {inv.created ? new Date(inv.created * 1000).toLocaleDateString('en-GB') : ''}
                                  </span>
                                </div>
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="space-y-1">
                                    {(inv.lines || []).map((line, idx) => (
                                      <div key={idx} className="text-sm text-gray-600">
                                        {line.description}
                                        {line.type === 'setup_fee' && (
                                          <span className="ml-2 text-gray-500">
                                            £{((line.amount_cents || 0) / 100).toFixed(2)}
                                          </span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                  <span className="font-semibold text-midnight-blue">
                                    £{((inv.amount_paid || 0) / 100).toFixed(2)}
                                  </span>
                                </div>
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                      )}
                    </div>

                    <div data-testid="pleerity-pdf-receipts">
                      <h3 className="text-sm font-semibold text-midnight-blue mb-1">Pleerity receipts (PDF)</h3>
                      <p className="text-xs text-gray-500 mb-3">Official PDF receipts stored in your account.</p>
                      {pdfReceipts.length === 0 ? (
                        <div className="text-center py-10 text-gray-500 border border-dashed rounded-lg bg-gray-50/50">
                          <FileText className="w-10 h-10 mx-auto mb-2 opacity-40" />
                          <p className="text-sm">No PDF receipts on file yet.</p>
                          <p className="text-xs mt-1">Created after each subscription checkout.</p>
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b text-left text-gray-500">
                                <th className="py-2 pr-4">Invoice #</th>
                                <th className="py-2 pr-4">Date</th>
                                <th className="py-2 pr-4">Description</th>
                                <th className="py-2 pr-4">Amount</th>
                                <th className="py-2 pr-4">Status</th>
                                <th className="py-2 text-right">Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {pdfReceipts.map((r) => (
                                <tr key={r.invoice_number || r.stripe_checkout_session_id} className="border-b border-gray-100">
                                  <td className="py-3 pr-4 font-mono text-xs">{r.invoice_number}</td>
                                  <td className="py-3 pr-4">
                                    {r.date_issued ? new Date(r.date_issued).toLocaleDateString('en-GB') : '—'}
                                  </td>
                                  <td className="py-3 pr-4 text-gray-700">CVP subscription payment</td>
                                  <td className="py-3 pr-4">{r.amount_display || '—'}</td>
                                  <td className="py-3 pr-4">{r.payment_status}</td>
                                  <td className="py-3 text-right">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={!r.invoice_number}
                                      onClick={async () => {
                                        if (!r.invoice_number) return;
                                        try {
                                          const response = await api.get(
                                            `/client/billing/receipt/${encodeURIComponent(r.invoice_number)}/download`,
                                            { responseType: 'blob' }
                                          );
                                          const blob = new Blob([response.data], { type: 'application/pdf' });
                                          const url = window.URL.createObjectURL(blob);
                                          const a = document.createElement('a');
                                          a.href = url;
                                          a.download = `${r.invoice_number}.pdf`;
                                          a.click();
                                          window.URL.revokeObjectURL(url);
                                          toast.success('Download started');
                                        } catch {
                                          toast.error('Download failed');
                                        }
                                      }}
                                    >
                                      PDF
                                    </Button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="border-teal-100 bg-teal-50/30" data-testid="billing-support-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Billing support</CardTitle>
                <CardDescription>We&apos;re here if something doesn&apos;t look right.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-gray-700 space-y-2">
                <p>
                  Email{' '}
                  <a className="text-electric-teal font-medium hover:underline" href="mailto:info@pleerityenterprise.co.uk">
                    info@pleerityenterprise.co.uk
                  </a>
                </p>
                <p className="text-xs text-gray-600">Include your account email and any invoice numbers if you need help with a charge.</p>
              </CardContent>
            </Card>

            <p className="text-sm text-gray-600">
              Paid service orders (one-off) have receipts in{' '}
              <Link to="/orders" className="text-electric-teal font-medium hover:underline">
                Orders
              </Link>
              .
            </p>
          </div>
        ) : (
          <>
        {/* Cancellation Pending Notice */}
        {billingStatus?.cancel_at_period_end && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="cancellation-notice">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              <strong>Cancellation Scheduled</strong>
              <p className="mt-1">
                Your subscription will end on{' '}
                {formatRenewalDisplay(billingStatus.current_period_end) || 'the end of your billing period'}. 
                You'll continue to have full access until then.
              </p>
            </AlertDescription>
          </Alert>
        )}

        {/* Current Plan Banner */}
        {currentPlan && (
          <div className="bg-gradient-to-r from-midnight-blue to-midnight-blue/90 text-white rounded-2xl p-6 mb-8" data-testid="current-plan-banner">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-300 mb-1">Your Current Plan</p>
                <h2 className="text-2xl font-bold">
                  {displayPlans.find((p) => p.code === currentPlan)?.name || currentPlan}
                </h2>
                <p className="text-sm text-gray-300 mt-1">
                  {entitlements?.max_properties} properties • {getFeatureCount(currentPlan)} features enabled
                </p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">
                  £{displayPlans.find((p) => p.code === currentPlan)?.monthlyPrice || 0}
                  <span className="text-lg font-normal text-gray-300">/mo</span>
                </p>
                {billingStatus?.has_subscription && !billingStatus?.cancel_at_period_end && (
                  <button
                    onClick={() => setShowCancelModal(true)}
                    className="text-xs text-gray-400 hover:text-white mt-2 underline"
                    data-testid="cancel-subscription-link"
                  >
                    Cancel subscription
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Plan Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12" data-testid="plan-cards">
          {displayPlans.map((plan) => {
            const status = getPlanStatus(plan.code);
            const isHighlighted = highlightPlan === plan.code;
            const PlanIcon = plan.icon;
            
            return (
              <Card 
                key={plan.code}
                className={`relative overflow-hidden transition-all duration-300 ${
                  isHighlighted ? 'ring-2 ring-electric-teal shadow-lg scale-[1.02]' : ''
                } ${status === 'current' ? 'border-2 border-electric-teal' : ''}`}
                data-testid={`plan-card-${plan.code}`}
              >
                {/* Badge */}
                {plan.badge && (
                  <div 
                    className="absolute top-0 right-0 px-3 py-1 text-xs font-semibold text-white rounded-bl-lg"
                    style={{ backgroundColor: plan.color }}
                  >
                    {plan.badge}
                  </div>
                )}
                
                {/* Current Plan Indicator */}
                {status === 'current' && (
                  <div className="absolute top-0 left-0 right-0 bg-electric-teal text-white text-center text-xs py-1 font-medium">
                    Current Plan
                  </div>
                )}
                
                <CardHeader className={status === 'current' ? 'pt-8' : ''}>
                  <div className="flex items-center gap-3 mb-2">
                    <div 
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${plan.color}15` }}
                    >
                      <PlanIcon className="w-5 h-5" style={{ color: plan.color }} />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{plan.name}</CardTitle>
                      <CardDescription className="text-xs">{plan.targetAudience}</CardDescription>
                    </div>
                  </div>
                  
                  <div className="mt-4">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold text-midnight-blue">£{plan.monthlyPrice}</span>
                      <span className="text-gray-500">/month</span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      + £{plan.onboardingFee} one-time setup
                    </p>
                  </div>
                </CardHeader>
                
                <CardContent>
                  <p className="text-sm text-gray-600 mb-4">{plan.description}</p>
                  
                  {/* Key Features */}
                  <div className="space-y-2 mb-6">
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500" />
                      <span><strong>{plan.maxProperties}</strong> properties</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500" />
                      <span><strong>{getFeatureCount(plan.code)}</strong> features</span>
                    </div>
                    {plan.code !== 'PLAN_1_SOLO' && (
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-500" />
                        <span>Advanced AI extraction</span>
                      </div>
                    )}
                    {plan.code === 'PLAN_3_PRO' && (
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-500" />
                        <span>Webhooks</span>
                      </div>
                    )}
                  </div>
                  
                  {/* CTA Button */}
                  <Button
                    className={`w-full ${
                      status === 'current'
                        ? 'bg-gray-100 text-gray-500 cursor-not-allowed'
                        : status === 'upgrade'
                          ? 'bg-electric-teal hover:bg-teal-600 text-white'
                          : 'border-amber-600 text-amber-900 bg-amber-50 hover:bg-amber-100'
                    }`}
                    variant={status === 'downgrade' ? 'outline' : 'default'}
                    onClick={() => handlePlanChange(plan.code)}
                    disabled={status === 'current' || upgrading === plan.code}
                    data-testid={`upgrade-btn-${plan.code}`}
                  >
                    {upgrading === plan.code ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Processing...
                      </>
                    ) : status === 'current' ? (
                      'Current plan'
                    ) : status === 'upgrade' ? (
                      <>
                        Upgrade to {plan.name}
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    ) : (
                      <>
                        Downgrade (next billing cycle)
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Feature Comparison Matrix */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden" data-testid="feature-matrix">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-midnight-blue">Feature Comparison</h2>
            <p className="text-sm text-gray-500 mt-1">Compare all features across plans</p>
          </div>
          
          {/* Header Row */}
          <div className="grid grid-cols-4 gap-4 p-4 bg-gray-50 border-b border-gray-200 sticky top-[73px] z-10">
            <div className="font-medium text-gray-700">Feature</div>
            {displayPlans.map((plan) => (
              <div key={plan.code} className="text-center">
                <span 
                  className="font-semibold text-sm"
                  style={{ color: plan.color }}
                >
                  {plan.name}
                </span>
              </div>
            ))}
          </div>
          
          {/* Feature Categories */}
          {FEATURE_CATEGORIES.map((category) => {
            const CategoryIcon = category.icon;
            const isExpanded = expandedCategories[category.name];
            
            return (
              <div key={category.name} className="border-b border-gray-100 last:border-b-0">
                {/* Category Header */}
                <button
                  onClick={() => toggleCategory(category.name)}
                  className="w-full grid grid-cols-4 gap-4 p-4 hover:bg-gray-50 transition-colors"
                  data-testid={`category-${category.name}`}
                >
                  <div className="flex items-center gap-2">
                    <CategoryIcon className="w-4 h-4 text-gray-500" />
                    <span className="font-medium text-gray-900">{category.name}</span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                  {displayPlans.map((plan) => {
                    const enabledCount = category.features.filter(f => FEATURE_MATRIX[plan.code][f.key]).length;
                    return (
                      <div key={plan.code} className="text-center text-sm text-gray-500">
                        {enabledCount}/{category.features.length}
                      </div>
                    );
                  })}
                </button>
                
                {/* Features */}
                {isExpanded && (
                  <div className="bg-gray-50/50">
                    {category.features.map((feature, idx) => (
                      <div 
                        key={feature.key}
                        className={`grid grid-cols-4 gap-4 px-4 py-3 ${
                          idx < category.features.length - 1 ? 'border-b border-gray-100' : ''
                        }`}
                        data-testid={`feature-row-${feature.key}`}
                      >
                        <div className="pl-6">
                          <p className="text-sm text-gray-700">{feature.name}</p>
                          <p className="text-xs text-gray-500">{feature.description}</p>
                        </div>
                        {displayPlans.map((plan) => {
                          const isEnabled = FEATURE_MATRIX[plan.code][feature.key];
                          return (
                            <div key={plan.code} className="flex items-center justify-center">
                              {isEnabled ? (
                                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                                  <Check className="w-4 h-4 text-green-600" />
                                </div>
                              ) : (
                                <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center">
                                  <X className="w-4 h-4 text-gray-400" />
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* FAQ Section */}
        <div className="mt-12" data-testid="billing-faq">
          <h2 className="text-xl font-semibold text-midnight-blue mb-6">Frequently Asked Questions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">Can I upgrade at any time?</h3>
                <p className="text-sm text-gray-600">
                  Yes! You can upgrade your plan at any time. The new pricing will be prorated based on your billing cycle.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">What happens to my data if I downgrade?</h3>
                <p className="text-sm text-gray-600">
                  Your data is not deleted on downgrade. If you exceed the property limit of a lower plan, you choose which properties stay active; the rest become archived (read-only). You can view archived property data but cannot add new documents until you activate a property or upgrade.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">What is your refund policy?</h3>
                <p className="text-sm text-gray-600">
                  We offer a 14-day money-back guarantee on all plans. Contact support within 14 days for a full refund if you&apos;re not satisfied.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">How do I cancel my subscription?</h3>
                <p className="text-sm text-gray-600">
                  You can cancel anytime from your account settings or by contacting support. Your access continues until the end of your billing period.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

          </>
        )}
      </main>

      {/* Cancel Subscription Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="cancel-modal">
          <div className="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Cancel Subscription</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Are you sure you want to cancel your subscription? You have two options:
            </p>

            {(cancelContextLoading || cancelContextSnapshot) && (
              <div
                className="mb-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700"
                data-testid="cancel-modal-context-snapshot"
              >
                <p className="font-medium text-gray-800 mb-2">Portfolio snapshot</p>
                {cancelContextLoading && <p className="text-gray-500">Loading…</p>}
                {!cancelContextLoading && cancelContextSnapshot && (
                  <ul className="list-disc list-inside space-y-1 text-gray-600">
                    <li>
                      Compliance:{' '}
                      {Number(cancelContextSnapshot.compliance?.requirements_overdue || 0)} overdue,{' '}
                      {Number(cancelContextSnapshot.compliance?.requirements_expiring_soon || 0)} expiring soon,{' '}
                      {Number(cancelContextSnapshot.compliance?.requirements_pending || 0)} pending
                    </li>
                    {cancelContextSnapshot.operations?.maintenance_workflows_enabled &&
                      cancelContextSnapshot.operations?.open_maintenance_issues != null && (
                        <li>Open maintenance issues: {cancelContextSnapshot.operations.open_maintenance_issues}</li>
                      )}
                    {cancelContextSnapshot.risk?.predictive_enabled &&
                      cancelContextSnapshot.risk?.active_risk_signals_count != null && (
                        <li>
                          Active risk signals: {cancelContextSnapshot.risk.active_risk_signals_count}
                          {Number(cancelContextSnapshot.risk.high_or_critical_active_count || 0) > 0
                            ? ` (${cancelContextSnapshot.risk.high_or_critical_active_count} high or critical)`
                            : ''}
                        </li>
                      )}
                  </ul>
                )}
                <p className="text-xs text-gray-500 mt-2">For your records only — you can still cancel.</p>
              </div>
            )}
            
            <div className="space-y-3 mb-6">
              <div className="p-4 border border-gray-200 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-1">Cancel at Period End</h4>
                <p className="text-sm text-gray-500">
                  Keep full access until{' '}
                  {formatRenewalDisplay(billingStatus?.current_period_end) || 'the end of your billing period'}, then
                  your subscription ends.
                </p>
              </div>
              <div className="p-4 border border-red-200 rounded-lg bg-red-50">
                <h4 className="font-medium text-red-800 mb-1">Cancel Immediately</h4>
                <p className="text-sm text-red-600">
                  Lose access immediately. Your data will be preserved but features will be locked.
                </p>
              </div>
            </div>
            
            <div className="flex flex-col gap-2">
              <Button
                onClick={() => handleCancelSubscription(false)}
                variant="outline"
                className="w-full"
                disabled={cancelling}
                data-testid="cancel-at-period-end-btn"
              >
                {cancelling ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                Cancel at Period End
              </Button>
              <Button
                onClick={() => handleCancelSubscription(true)}
                variant="destructive"
                className="w-full bg-red-600 hover:bg-red-700"
                disabled={cancelling}
                data-testid="cancel-immediately-btn"
              >
                {cancelling ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                Cancel Immediately
              </Button>
              <Button
                onClick={() => setShowCancelModal(false)}
                variant="ghost"
                className="w-full"
                disabled={cancelling}
              >
                Keep My Subscription
              </Button>
            </div>
          </div>
        </div>
      )}
      {billingStepUp.modal}
    </div>
  );
};

export default BillingPage;
