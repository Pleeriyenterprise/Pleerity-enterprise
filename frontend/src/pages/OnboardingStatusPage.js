import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { 
  CheckCircle, 
  Circle, 
  Clock, 
  AlertCircle,
  CreditCard,
  Settings,
  Key,
  ClipboardCheck,
  Loader2,
  ArrowRight,
  Building2,
  FileText,
  Copy
} from 'lucide-react';
import { Button } from '../components/ui/button';
import api from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import { toast } from 'sonner';

const POLL_INTERVAL_MS = 7000;
const POLL_DURATION_MS = 120000;

const OnboardingStatusPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const clientId = searchParams.get('client_id');
  
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollStatus, setPollStatus] = useState(null);
  const pollStartRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.get(`/intake/onboarding-status/${clientId}`);
      setStatus(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load onboarding status');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  const fetchPollStatus = useCallback(async () => {
    if (!clientId) return;
    try {
      const res = await api.get('/onboarding/status', { params: { client_id: clientId } });
      setPollStatus(res.data);
    } catch {
      // Non-fatal; keep polling
    }
  }, [clientId]);

  const handleCopyCRN = useCallback(() => {
    const crn = status?.customer_reference || pollStatus?.customer_reference;
    if (!crn) return;
    navigator.clipboard.writeText(crn).then(() => toast.success('CRN copied to clipboard')).catch(() => toast.error('Copy failed'));
  }, [status?.customer_reference, pollStatus?.customer_reference]);

  useEffect(() => {
    if (clientId) {
      fetchStatus();
      fetchPollStatus();
      pollStartRef.current = Date.now();
    } else {
      setError('No client ID provided');
      setLoading(false);
    }
  }, [clientId, fetchStatus, fetchPollStatus]);

  useEffect(() => {
    if (!clientId) return;
    const t0 = Date.now();
    const prevRef = { current: null };
    const interval = setInterval(async () => {
      if (Date.now() - t0 >= POLL_DURATION_MS) return;
      const poll = await api.get('/onboarding/status', { params: { client_id: clientId } }).then(r => r.data).catch(() => null);
      if (poll) {
        const prev = prevRef.current;
        prevRef.current = poll;
        setPollStatus(poll);
        const changed = !prev || poll.payment_status !== prev.payment_status || poll.portal_user_exists !== prev.portal_user_exists || poll.password_set !== prev.password_set;
        if (changed) fetchStatus();
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [clientId, fetchStatus]);

  const getStepIcon = (step) => {
    const icons = {
      'clipboard-check': ClipboardCheck,
      'credit-card': CreditCard,
      'settings': Settings,
      'key': Key,
      'check-circle': CheckCircle
    };
    return icons[step.icon] || Circle;
  };

  const getStepStatusStyle = (stepStatus) => {
    switch (stepStatus) {
      case 'complete':
        return {
          container: 'bg-green-50 border-green-200',
          icon: 'bg-green-500 text-white',
          text: 'text-green-800',
          badge: 'bg-green-100 text-green-700'
        };
      case 'in_progress':
        return {
          container: 'bg-teal-50 border-teal-200',
          icon: 'bg-electric-teal text-white animate-pulse',
          text: 'text-teal-800',
          badge: 'bg-teal-100 text-teal-700'
        };
      case 'pending':
        return {
          container: 'bg-amber-50 border-amber-200',
          icon: 'bg-amber-500 text-white',
          text: 'text-amber-800',
          badge: 'bg-amber-100 text-amber-700'
        };
      case 'failed':
        return {
          container: 'bg-red-50 border-red-200',
          icon: 'bg-red-500 text-white',
          text: 'text-red-800',
          badge: 'bg-red-100 text-red-700'
        };
      default:
        return {
          container: 'bg-gray-50 border-gray-200',
          icon: 'bg-gray-300 text-gray-500',
          text: 'text-gray-500',
          badge: 'bg-gray-100 text-gray-500'
        };
    }
  };

  const getStatusLabel = (stepStatus, stepNum) => {
    const isPaymentStep = stepNum === 2;
    const subActive = ['ACTIVE', 'PAID'].includes((status?.subscription_status || pollStatus?.subscription_status || '').toUpperCase());
    const fromStripeRedirect = !!sessionStorage.getItem('pleerity_stripe_redirect');
    let createdWithin2Min = false;
    const createdStr = pollStatus?.created_at || status?.created_at;
    if (createdStr) {
      try {
        const created = new Date(createdStr).getTime();
        createdWithin2Min = Date.now() - created < 120000;
      } catch {}
    }
    if (isPaymentStep && subActive) sessionStorage.removeItem('pleerity_stripe_redirect');
    const isConfirming = isPaymentStep && !subActive && (fromStripeRedirect || createdWithin2Min);

    if (isConfirming) return 'Confirming…';
    switch (stepStatus) {
      case 'complete': return 'Complete';
      case 'in_progress': return 'In Progress';
      case 'pending': return 'Action Required';
      case 'failed': return 'Failed';
      default: return 'Waiting';
    }
  };

  if (loading) {
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
          <Button onClick={() => navigate('/')} variant="outline">
            Return Home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" data-testid="onboarding-status-page">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-4xl mx-auto px-4 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-bold">Compliance Vault Pro</h1>
          {(status?.customer_reference || pollStatus?.customer_reference) && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-300">Your CRN:</span>
              <span className="font-mono font-semibold">{status?.customer_reference || pollStatus?.customer_reference}</span>
              <button
                type="button"
                onClick={handleCopyCRN}
                className="flex items-center gap-1 px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-sm"
                title="Copy CRN"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Welcome Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-2">
                Welcome, {status?.client_name}!
              </h2>
              <p className="text-gray-600">
                {status?.is_complete 
                  ? "Your compliance portal is ready to use."
                  : "We're setting up your compliance portal. Here's your progress:"}
              </p>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold text-electric-teal">{status?.progress_percent}%</div>
              <p className="text-sm text-gray-500">Complete</p>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-6">
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-electric-teal rounded-full transition-all duration-500"
                style={{ width: `${status?.progress_percent}%` }}
              />
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Building2 className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-lg font-semibold text-midnight-blue">{status?.properties_count || 0}</p>
                <p className="text-xs text-gray-500">Properties Registered</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <FileText className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-lg font-semibold text-midnight-blue">{status?.requirements_count || 0}</p>
                <p className="text-xs text-gray-500">Requirements Created</p>
              </div>
            </div>
          </div>
        </div>

        {/* Steps Timeline */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h3 className="text-lg font-semibold text-midnight-blue mb-6">Setup Progress</h3>
          
          <div className="space-y-4">
            {status?.steps?.map((step, index) => {
              const Icon = getStepIcon(step);
              const styles = getStepStatusStyle(step.status);
              const isCurrentStep = step.step === status.current_step;
              
              return (
                <div key={step.step} className="relative">
                  {/* Connector Line */}
                  {index < status.steps.length - 1 && (
                    <div className={`absolute left-6 top-14 w-0.5 h-8 ${
                      step.status === 'complete' ? 'bg-green-300' : 'bg-gray-200'
                    }`} />
                  )}
                  
                  <div 
                    className={`flex items-start gap-4 p-4 rounded-xl border-2 transition-all ${styles.container} ${
                      isCurrentStep ? 'ring-2 ring-electric-teal ring-offset-2' : ''
                    }`}
                    data-testid={`onboarding-step-${step.step}`}
                  >
                    {/* Step Number & Icon */}
                    <div className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center ${styles.icon}`}>
                      {step.status === 'in_progress' ? (
                        <Loader2 className="w-6 h-6 animate-spin" />
                      ) : step.status === 'complete' ? (
                        <CheckCircle className="w-6 h-6" />
                      ) : (
                        <Icon className="w-6 h-6" />
                      )}
                    </div>
                    
                    {/* Step Content */}
                    <div className="flex-grow">
                      <div className="flex items-center gap-3 mb-1">
                        <h4 className={`font-semibold ${styles.text}`}>{step.name}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${styles.badge}`}>
                          {getStatusLabel(step.status, step.step)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600">{step.description}</p>
                    </div>
                    
                    {/* Step Number */}
                    <div className="text-2xl font-bold text-gray-200">
                      {step.step}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Next Action Card */}
        {status?.next_action && (
          <div className={`rounded-xl shadow-sm border-2 p-6 ${
            status.is_complete 
              ? 'bg-green-50 border-green-200' 
              : 'bg-teal-50 border-teal-200'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className={`font-semibold ${status.is_complete ? 'text-green-800' : 'text-teal-800'}`}>
                  {status.is_complete ? '🎉 All Set!' : 'Next Step'}
                </h3>
                <p className={`mt-1 ${status.is_complete ? 'text-green-700' : 'text-teal-700'}`}>
                  {status.next_action.message}
                </p>
              </div>
              
              {status.is_complete && (
                <Button 
                  onClick={() => navigate('/login')}
                  className="bg-green-600 hover:bg-green-700"
                  data-testid="go-to-portal-btn"
                >
                  Go to Portal
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
              
              {status.next_action.action === 'set_password' && (
                <Button 
                  variant="outline"
                  onClick={() => {/* Email should contain the link */}}
                  className="border-teal-300 text-teal-700"
                >
                  Check Your Email
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Help Section */}
        <div className="mt-8 text-center">
          <p className="text-sm text-gray-500">
            Need help? Contact us at{' '}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-electric-teal hover:underline">
              {SUPPORT_EMAIL}
            </a>
          </p>
        </div>
      </main>
    </div>
  );
};

export default OnboardingStatusPage;
