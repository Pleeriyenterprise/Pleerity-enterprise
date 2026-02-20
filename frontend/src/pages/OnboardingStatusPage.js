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
const BANNER_LATE_CONFIRMING_SEC = 30;

/** Build steps array from setup-status response. */
function buildSteps(data) {
  if (!data) return [];
  const ps = data.payment_state || 'UNPAID';
  const vs = data.provisioning_state || 'NOT_STARTED';
  const pw = data.password_state || 'NOT_SET';
  const na = data.next_action || 'PAYMENT';

  const step2Status = ps === 'PAID' ? 'complete' : ps === 'CONFIRMING' ? 'in_progress' : 'pending';
  const step2Label = ps === 'PAID' ? 'Complete' : ps === 'CONFIRMING' ? 'Confirming…' : 'Action required';

  const step3Status = vs === 'PROVISIONED' ? 'complete' : vs === 'FAILED' ? 'failed' : 'in_progress';
  const step3Label = vs === 'PROVISIONED' ? 'Complete' : vs === 'FAILED' ? 'Failed' : vs === 'RUNNING' ? 'In progress' : 'Waiting';

  const step4Status = pw === 'SET' ? 'complete' : 'pending';
  const step4Label = pw === 'SET' ? 'Complete' : 'Waiting';

  const step5Status = na === 'DASHBOARD' ? 'complete' : 'pending';
  const step5Label = na === 'DASHBOARD' ? 'Complete' : 'Waiting';

  return [
    { step: 1, name: 'Intake Form', description: 'Submit your details and property information', status: 'complete', icon: 'clipboard-check', label: 'Complete' },
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
  const na = data.next_action || '';
  const vs = data.provisioning_state || '';
  return na === 'SET_PASSWORD' || na === 'DASHBOARD' || vs === 'FAILED';
}

/** Should we show the early "payment received" banner? */
function showEarlyBanner(data, elapsedSec) {
  if (!data) return false;
  return (data.payment_state === 'CONFIRMING' || data.next_action === 'WAIT_PROVISIONING') && elapsedSec < BANNER_EARLY_SEC;
}

/** Should we show the "still confirming" banner? */
function showLateConfirmingBanner(data, elapsedSec) {
  return data?.payment_state === 'CONFIRMING' && elapsedSec >= BANNER_LATE_CONFIRMING_SEC;
}

const NEXT_ACTION_MESSAGES = {
  PAYMENT: 'Complete your payment to continue.',
  WAIT_PROVISIONING: "We're setting up your portal. This usually takes under a minute.",
  SET_PASSWORD: 'Check your email for the account activation link to set your password.',
  DASHBOARD: 'All set! You can now access your compliance portal.',
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
  const pollStartRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const fetchSetupStatus = useCallback(async () => {
    const params = clientId ? { client_id: clientId } : {};
    try {
      const res = await api.get('/portal/setup-status', { params });
      setStatus(res.data);
      setError(null);
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
    if (status?.payment_state === 'PAID') sessionStorage.removeItem('pleerity_stripe_redirect');
  }, [status]);

  const handleCopyCRN = useCallback(() => {
    const crn = status?.customer_reference;
    if (!crn) return;
    navigator.clipboard.writeText(crn).then(() => toast.success('CRN copied to clipboard')).catch(() => toast.error('Copy failed'));
  }, [status?.customer_reference]);

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

    const shouldStartPolling = () => paymentSuccess || fromStripeRedirect || status?.payment_state === 'CONFIRMING' || status?.next_action === 'WAIT_PROVISIONING';
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
  const isComplete = status?.next_action === 'DASHBOARD';
  const elapsedSec = pollStartRef.current ? Math.floor((Date.now() - pollStartRef.current) / 1000) : 0;
  const showEarly = showEarlyBanner(status, elapsedSec);
  const showLateConfirming = showLateConfirmingBanner(status, elapsedSec);
  const provisioningFailed = status?.provisioning_state === 'FAILED';
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
            <p className="font-medium">We&apos;re still setting things up. Please refresh in a moment. If it continues, contact support with your CRN.</p>
          </div>
        )}
        {provisioningFailed && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
            <p className="font-medium">Setup encountered an issue. Contact support with CRN {status?.customer_reference || '—'}.</p>
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

        {/* Next Action Card */}
        {status?.next_action && (
          <div className={`rounded-xl shadow-sm border-2 p-6 ${isComplete ? 'bg-green-50 border-green-200' : 'bg-teal-50 border-teal-200'}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className={`font-semibold ${isComplete ? 'text-green-800' : 'text-teal-800'}`}>{isComplete ? '🎉 All Set!' : 'Next Step'}</h3>
                <p className={`mt-1 ${isComplete ? 'text-green-700' : 'text-teal-700'}`}>{nextActionMsg}</p>
              </div>
              {isComplete && (
                <Button onClick={() => navigate('/login')} className="bg-green-600 hover:bg-green-700" data-testid="go-to-portal-btn">
                  Go to Portal <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
              {status.next_action === 'SET_PASSWORD' && (
                <Button variant="outline" className="border-teal-300 text-teal-700">Check Your Email</Button>
              )}
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
