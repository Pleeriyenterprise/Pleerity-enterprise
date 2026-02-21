import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  CheckCircle,
  Circle,
  AlertCircle,
  CreditCard,
  Settings,
  Key,
  ClipboardCheck,
  Loader2,
  ArrowRight,
  Building2,
  FileText,
  Copy,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import api from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import { toast } from 'sonner';

const POLL_INTERVAL_MS = 5000;
const POLL_DURATION_MS = 180000;
const BANNER_EARLY_SEC = 20;
const BANNER_LATE_CONFIRMING_SEC = 120; // 2 minutes

/** Build steps from backend truth flags only. payment_state: unpaid | pending_webhook | paid; provisioning_status: NOT_STARTED | IN_PROGRESS | COMPLETED | FAILED; activation_email_status: NOT_SENT | SENT | FAILED; password_set: bool; portal_user_exists: bool. */
function buildSteps(data) {
  if (!data) return [];
  const intakeSubmitted = data.intake_submitted === true;
  const paymentState = (data.payment_state || 'unpaid').toLowerCase();
  const provStatus = (data.provisioning_status || 'NOT_STARTED').toUpperCase();
  const portalUserExists = data.portal_user_exists === true;
  const actEmail = (data.activation_email_status || 'NOT_SENT').toUpperCase();
  const passwordSet = data.password_set === true;

  // Step 1 Intake: complete iff intake_submitted
  const step1Status = intakeSubmitted ? 'complete' : 'pending';
  const step1Label = intakeSubmitted ? 'Complete' : 'Pending';

  // Step 2 Payment: unpaid -> Action Required; pending_webhook -> Confirming…; paid -> Complete. Never show Action Required after Stripe success (pending_webhook is post-success).
  const step2Status = paymentState === 'paid' ? 'complete' : paymentState === 'pending_webhook' ? 'in_progress' : 'pending';
  const step2Label = paymentState === 'paid' ? 'Complete' : paymentState === 'pending_webhook' ? 'Confirming…' : 'Action required';

  // Step 3 Portal Setup: depends only on provisioning_status
  const step3Status = provStatus === 'COMPLETED' ? 'complete' : provStatus === 'FAILED' ? 'failed' : provStatus === 'IN_PROGRESS' ? 'in_progress' : 'pending';
  const step3Label = provStatus === 'COMPLETED' ? 'Complete' : provStatus === 'FAILED' ? 'Failed' : provStatus === 'IN_PROGRESS' ? 'In progress' : 'Waiting';

  // Step 4 Account Activation: only portal_user_exists, activation_email_status, password_set
  let step4Status = 'pending';
  let step4Label = 'Waiting';
  if (passwordSet) {
    step4Status = 'complete';
    step4Label = 'Complete';
  } else if (!portalUserExists) {
    step4Label = 'Waiting';
  } else if (actEmail === 'SENT') {
    step4Label = 'Email sent (Waiting for user)';
  } else if (actEmail === 'FAILED') {
    step4Status = 'failed';
    step4Label = 'Email failed';
  } else {
    step4Label = 'Waiting';
  }

  // Step 5 Ready to Use: complete iff password_set
  const step5Status = passwordSet ? 'complete' : 'pending';
  const step5Label = passwordSet ? 'Complete' : 'Waiting';

  return [
    { step: 1, name: 'Intake Form', description: 'Submit your details and property information', status: step1Status, icon: 'clipboard-check', label: step1Label },
    { step: 2, name: 'Payment', description: 'Complete subscription payment', status: step2Status, icon: 'credit-card', label: step2Label },
    { step: 3, name: 'Portal Setup', description: 'We provision your compliance portal', status: step3Status, icon: 'settings', label: step3Label },
    { step: 4, name: 'Account Activation', description: 'Set your password from the email we sent', status: step4Status, icon: 'key', label: step4Label },
    { step: 5, name: 'Ready to Use', description: 'Access your portal', status: step5Status, icon: 'check-circle', label: step5Label },
  ];
}

/** Compute progress percent from steps. */
function progressPercent(steps) {
  if (!steps?.length) return 0;
  const complete = steps.filter((s) => s.status === 'complete').length;
  return Math.round((complete / steps.length) * 100);
}

/** Should polling stop? */
function shouldStopPolling(data) {
  if (!data) return false;
  if (data.password_set === true) return true;
  const vs = data.provisioning_status || data.provisioning_state || '';
  if (String(vs).toUpperCase() === 'FAILED') return true;
  const na = data.next_action || '';
  return na === 'set_password' || na === 'go_to_dashboard';
}

/** Should we show the early "payment received" banner? */
function showEarlyBanner(data, elapsedSec) {
  if (!data) return false;
  const ps = (data.payment_state || '').toLowerCase();
  return (ps === 'pending_webhook' || data.next_action === 'wait_provisioning') && elapsedSec < BANNER_EARLY_SEC;
}

/** Should we show the "still confirming" banner? */
function showLateConfirmingBanner(data, elapsedSec) {
  return (data?.payment_state || '').toLowerCase() === 'pending_webhook' && elapsedSec >= BANNER_LATE_CONFIRMING_SEC;
}

const SUPPORT_EMAIL_FALLBACK = 'info@pleerityenterprise.co.uk';

const NEXT_ACTION_MESSAGES = {
  pay: 'Complete your payment to continue.',
  wait_provisioning: "We're setting up your portal. This usually takes under a minute.",
  set_password: 'Check your email for the account activation link to set your password.',
  go_to_dashboard: 'All set! You can now access your compliance portal.',
};

const OnboardingStatusPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const clientId = searchParams.get('client_id');
  const paymentSuccess = searchParams.get('payment') === 'success';
  const fromStripeRedirect = !!sessionStorage.getItem('pleerity_stripe_redirect');

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timedOut, setTimedOut] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendError, setResendError] = useState(null);
  const pollStartRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const fetchSetupStatus = useCallback(async () => {
    const params = clientId ? { client_id: clientId } : {};
    try {
      const res = await api.get('/portal/setup-status', { params });
      setStatus(res.data);
      setError(null);
      setResendError(null);
      return res.data;
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to load setup status';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      setLoading(false);
      return null;
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  const handleRefresh = useCallback(() => {
    if (!status?.client_id && !clientId) return;
    setTimedOut(false);
    pollStartRef.current = Date.now();
    fetchSetupStatus();
  }, [status?.client_id, clientId, fetchSetupStatus]);

  useEffect(() => {
    if ((status?.payment_state || '').toLowerCase() === 'paid') sessionStorage.removeItem('pleerity_stripe_redirect');
  }, [status]);

  // Auto-redirect to client dashboard when password_set (Ready to Use) after 2s
  useEffect(() => {
    if (status?.password_set !== true) return;
    const t = setTimeout(() => navigate('/app/dashboard'), 2000);
    return () => clearTimeout(t);
  }, [status?.password_set, navigate]);

  const handleCopyCRN = useCallback(() => {
    const crn = status?.customer_reference;
    if (!crn) return;
    navigator.clipboard.writeText(crn).then(() => toast.success('CRN copied to clipboard')).catch(() => toast.error('Copy failed'));
  }, [status?.customer_reference]);

  const handleResendActivation = useCallback(async () => {
    const cid = status?.client_id || clientId;
    if (!cid) return;
    setResending(true);
    setResendError(null);
    try {
      await api.post('/portal/resend-activation', null, { params: { client_id: cid } });
      toast.success('Activation email sent');
      await fetchSetupStatus();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to send activation email';
      const msgStr = typeof msg === 'string' ? msg : msg?.message || 'Failed to send activation email';
      toast.error(msgStr);
      setResendError(msgStr);
    } finally {
      setResending(false);
    }
  }, [status?.client_id, clientId, fetchSetupStatus]);

  useEffect(() => {
    setLoading(true);
    fetchSetupStatus().then((data) => {
      if (data) pollStartRef.current = Date.now();
    });
  }, [fetchSetupStatus]);

  // Polling: status in deps satisfies exhaustive-deps; cleanup + shouldStopPolling prevent infinite loop.
  useEffect(() => {
    if (!pollStartRef.current) return;
    const cid = status?.client_id || clientId;
    if (!cid) return;

    const runPoll = async () => {
      const elapsed = Date.now() - pollStartRef.current;
      if (elapsed >= POLL_DURATION_MS) {
        setTimedOut(true);
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        return;
      }
      const params = cid ? { client_id: cid } : {};
      const data = await api.get('/portal/setup-status', { params }).then((r) => r.data).catch(() => null);
      if (data) {
        setStatus(data);
        if (shouldStopPolling(data)) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      }
    };

    const shouldStartPolling = () => paymentSuccess || fromStripeRedirect || (status?.payment_state || '').toLowerCase() === 'pending_webhook' || status?.next_action === 'wait_provisioning';
    if (shouldStartPolling() && !shouldStopPolling(status)) {
      pollIntervalRef.current = setInterval(runPoll, POLL_INTERVAL_MS);
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [clientId, status, paymentSuccess, fromStripeRedirect]);

  const getStepIcon = (step) => {
    const icons = { 'clipboard-check': ClipboardCheck, 'credit-card': CreditCard, 'settings': Settings, 'key': Key, 'check-circle': CheckCircle };
    return icons[step.icon] || Circle;
  };

  const getStepStatusStyle = (stepStatus) => {
    switch (stepStatus) {
      case 'complete':
        return { container: 'bg-green-50 border-green-200', icon: 'bg-green-500 text-white', text: 'text-green-800', badge: 'bg-green-100 text-green-700' };
      case 'in_progress':
        return { container: 'bg-teal-50 border-teal-200', icon: 'bg-electric-teal text-white animate-pulse', text: 'text-teal-800', badge: 'bg-teal-100 text-teal-700' };
      case 'pending':
        return { container: 'bg-amber-50 border-amber-200', icon: 'bg-amber-500 text-white', text: 'text-amber-800', badge: 'bg-amber-100 text-amber-700' };
      case 'failed':
        return { container: 'bg-red-50 border-red-200', icon: 'bg-red-500 text-white', text: 'text-red-800', badge: 'bg-red-100 text-red-700' };
      default:
        return { container: 'bg-gray-50 border-gray-200', icon: 'bg-gray-300 text-gray-500', text: 'text-gray-500', badge: 'bg-gray-100 text-gray-500' };
    }
  };

  const steps = buildSteps(status);
  const progressPercentVal = progressPercent(steps);
  const passwordSet = status?.password_set === true;
  const isComplete = passwordSet;
  const elapsedSec = pollStartRef.current ? Math.floor((Date.now() - pollStartRef.current) / 1000) : 0;
  const showEarly = showEarlyBanner(status, elapsedSec);
  const showLateConfirming = showLateConfirmingBanner(status, elapsedSec);
  const provisioningFailed = String(status?.provisioning_status || status?.provisioning_state || '').toUpperCase() === 'FAILED';
  const activationEmailFailed = (status?.activation_email_status || '').toUpperCase() === 'FAILED';
  const nextActionMsg = NEXT_ACTION_MESSAGES[status?.next_action] || status?.next_action;

  if (loading && !status) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-electric-teal mx-auto mb-4" />
          <p className="text-gray-600">Loading your onboarding status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Unable to Load Status</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <Button onClick={() => navigate('/')} variant="outline">Return Home</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" data-testid="onboarding-status-page">
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-4xl mx-auto px-4 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-bold">Compliance Vault Pro</h1>
          {status?.customer_reference && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-300">Your CRN:</span>
              <span className="font-mono font-semibold">{status.customer_reference}</span>
              <button type="button" onClick={handleCopyCRN} className="flex items-center gap-1 px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-sm" title="Copy CRN">
                <Copy className="h-3.5 w-3.5" /> Copy
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Banners */}
        {showEarly && (
          <div className="mb-6 p-4 rounded-xl bg-teal-50 border border-teal-200 text-teal-800">
            <p className="font-medium">Payment received. We&apos;re setting up your portal now… (usually under 1 minute)</p>
          </div>
        )}
        {showLateConfirming && !showEarly && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
            <p className="font-medium">Still confirming payment… this can take a moment. You can refresh or contact support with your CRN.</p>
          </div>
        )}
        {timedOut && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
            <p className="font-medium">We&apos;re still setting things up. Please use <strong>Refresh status</strong> below, or contact support with your CRN: <strong>{status?.customer_reference || '—'}</strong></p>
            <p className="mt-2 text-sm">Email: <a href={`mailto:${SUPPORT_EMAIL_FALLBACK}`} className="underline">{SUPPORT_EMAIL_FALLBACK}</a></p>
          </div>
        )}
        {provisioningFailed && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
            <p className="font-medium">Setup encountered an issue. Contact support with CRN {status?.customer_reference || '—'}.</p>
            {status?.last_error?.message && <p className="mt-1 text-sm">{status.last_error.message}</p>}
          </div>
        )}
        {(activationEmailFailed || resendError) && !provisioningFailed && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
            <p className="font-medium">
              Activation email could not be sent. Use &quot;Resend activation email&quot; below or contact support with your CRN: <strong>{status?.customer_reference || status?.crn || '—'}</strong>
            </p>
            {(status?.last_error?.message || resendError) && <p className="mt-1 text-sm">{resendError || status?.last_error?.message}</p>}
          </div>
        )}

        {/* Refresh button */}
        <div className="mb-4 flex justify-end">
          <Button variant="outline" size="sm" onClick={handleRefresh} data-testid="refresh-status-btn">
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh status
          </Button>
        </div>

        {/* Welcome Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-2">Welcome, {status?.client_name || 'there'}!</h2>
              <p className="text-gray-600">
                {isComplete ? 'Your compliance portal is ready to use.' : "We're setting up your compliance portal. Here's your progress:"}
              </p>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold text-electric-teal">{progressPercentVal}%</div>
              <p className="text-sm text-gray-500">Complete</p>
            </div>
          </div>
          <div className="mt-6">
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-electric-teal rounded-full transition-all duration-500" style={{ width: `${progressPercentVal}%` }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Building2 className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-lg font-semibold text-midnight-blue">{status?.properties_count ?? 0}</p>
                <p className="text-xs text-gray-500">Properties Registered</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <FileText className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-lg font-semibold text-midnight-blue">{status?.requirements_count ?? 0}</p>
                <p className="text-xs text-gray-500">Requirements Created</p>
              </div>
            </div>
          </div>
        </div>

        {/* Steps Timeline */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h3 className="text-lg font-semibold text-midnight-blue mb-6">Setup Progress</h3>
          <div className="space-y-4">
            {steps.map((step, index) => {
              const Icon = getStepIcon(step);
              const styles = getStepStatusStyle(step.status);
              const isCurrentStep = step.status === 'in_progress' || step.status === 'pending';
              return (
                <div key={step.step} className="relative">
                  {index < steps.length - 1 && (
                    <div className={`absolute left-6 top-14 w-0.5 h-8 ${step.status === 'complete' ? 'bg-green-300' : 'bg-gray-200'}`} />
                  )}
                  <div
                    className={`flex items-start gap-4 p-4 rounded-xl border-2 transition-all ${styles.container} ${isCurrentStep ? 'ring-2 ring-electric-teal ring-offset-2' : ''}`}
                    data-testid={`onboarding-step-${step.step}`}
                  >
                    <div className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center ${styles.icon}`}>
                      {step.status === 'in_progress' ? <Loader2 className="w-6 h-6 animate-spin" /> : step.status === 'complete' ? <CheckCircle className="w-6 h-6" /> : <Icon className="w-6 h-6" />}
                    </div>
                    <div className="flex-grow">
                      <div className="flex items-center gap-3 mb-1">
                        <h4 className={`font-semibold ${styles.text}`}>{step.name}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${styles.badge}`}>{step.label}</span>
                      </div>
                      <p className="text-sm text-gray-600">{step.description}</p>
                    </div>
                    <div className="text-2xl font-bold text-gray-200">{step.step}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Next Action Card / CTA */}
        {(status?.next_action || status?.client_id) && (
          <div className={`rounded-xl shadow-sm border-2 p-6 ${isComplete ? 'bg-green-50 border-green-200' : 'bg-teal-50 border-teal-200'}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className={`font-semibold ${isComplete ? 'text-green-800' : 'text-teal-800'}`}>{isComplete ? '🎉 All Set!' : 'Next Step'}</h3>
                <p className={`mt-1 ${isComplete ? 'text-green-700' : 'text-teal-700'}`}>{nextActionMsg}</p>
                {!passwordSet && (status?.activation_email_status === 'SENT') && (status?.activation_email_to_masked || status?.masked_email) && (
                  <p className="mt-2 text-sm text-teal-700">
                    Activation email sent to: {status?.masked_email ?? status?.activation_email_to_masked}
                    {status?.activation_email_sent_at || status?.activation_email_last_sent_at
                      ? ` at ${new Date(status?.activation_email_last_sent_at ?? status?.activation_email_sent_at).toLocaleString()}`
                      : ''}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {passwordSet && (
                  <Button onClick={() => navigate('/app/dashboard')} className="bg-green-600 hover:bg-green-700" data-testid="go-to-portal-btn">
                    Go to Dashboard <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                )}
                {!passwordSet && (
                  <>
                    {/* Do not link to /set-password without token — user must use the link from the activation email. */}
                    {(status?.portal_user_exists && (status?.activation_email_status === 'SENT' || status?.activation_email_status === 'FAILED' || status?.next_action === 'set_password')) && (
                      <Button className="bg-teal-600 hover:bg-teal-700 text-white" onClick={handleResendActivation} disabled={resending} data-testid="resend-activation-btn">
                        {resending ? 'Sending…' : 'Resend activation email'}
                      </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={handleRefresh} className="border-teal-300 text-teal-700" data-testid="refresh-status-cta-btn">
                      <RefreshCw className="w-4 h-4 mr-2" /> Refresh status
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 text-center">
          <p className="text-sm text-gray-500">
            Need help? Contact us at <a href={`mailto:${SUPPORT_EMAIL}`} className="text-electric-teal hover:underline">{SUPPORT_EMAIL}</a>
          </p>
        </div>
      </main>
    </div>
  );
};

export default OnboardingStatusPage;
