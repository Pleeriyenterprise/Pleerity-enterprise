import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Building2, CheckCircle, CreditCard, Loader2, AlertCircle, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';
import { onboardingContinuationAPI } from '../api/client';
import { apiErrorMessage } from '../utils/apiErrorMessage';
import { SUPPORT_EMAIL } from '../config';
import { toast } from '@/utils/portalNotifications';

const NEXT_STEP_COPY = {
  complete_payment: 'Complete your subscription payment to activate your compliance workspace.',
  set_password: 'Check your email for the activation link to set your password.',
  wait_provisioning: 'We are setting up your portal. This usually takes under a minute.',
  go_to_dashboard: 'Your portal is ready. Sign in to get started.',
  track_progress: 'View your onboarding progress and next steps.',
};

export default function OnboardingContinuePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Missing continuation link. Please use the link from your email.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await onboardingContinuationAPI.resolveContinuation(token);
        if (cancelled) return;
        setContext(res.data);
        if (res.data?.client_id) {
          sessionStorage.setItem('pending_client_id', res.data.client_id);
        }
        if (res.data?.customer_reference) {
          sessionStorage.setItem('customer_reference', res.data.customer_reference);
        }
      } catch (err) {
        if (!cancelled) {
          setError(apiErrorMessage(err, 'This continuation link is not valid or has expired.'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleContinuePayment = useCallback(async () => {
    setCheckoutLoading(true);
    try {
      const res = await onboardingContinuationAPI.startContinuationCheckout({ token });
      const url = res.data?.checkout_url;
      if (!url) throw new Error('Payment link was not returned');
      window.location.href = url;
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Could not start payment'));
      setCheckoutLoading(false);
    }
  }, [token]);

  const goToStatus = useCallback(() => {
    const cid = context?.client_id;
    if (cid) {
      navigate(`/onboarding-status?client_id=${encodeURIComponent(cid)}`);
    }
  }, [context?.client_id, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="onboarding-continue-loading">
        <Loader2 className="h-10 w-10 animate-spin text-teal-600" />
      </div>
    );
  }

  if (error || !context?.valid) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4" data-testid="onboarding-continue-error">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <AlertCircle className="w-14 h-14 text-amber-600 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900 mb-2">Unable to continue</h1>
          <p className="text-gray-600 mb-6">{error || 'Invalid link'}</p>
          <p className="text-sm text-gray-500">
            Contact support at{' '}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-teal-600 underline">
              {SUPPORT_EMAIL}
            </a>
          </p>
        </div>
      </div>
    );
  }

  const nextStep = context.next_step || 'track_progress';
  const propertiesLabel =
    context.properties_count === 1
      ? '1 property saved'
      : `${context.properties_count || 0} properties saved`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" data-testid="onboarding-continue-page">
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-2xl mx-auto px-4">
          <h1 className="text-xl font-bold">Compliance Vault Pro</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-10">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 space-y-6">
          <div className="flex items-start gap-3">
            <CheckCircle className="h-8 w-8 text-teal-600 shrink-0" aria-hidden />
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue" data-testid="continue-welcome-heading">
                Welcome back, {context.client_first_name || 'there'}
              </h2>
              <p className="text-gray-600 mt-2" data-testid="continue-welcome-message">
                {context.welcome_message}
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Building2 className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Saved progress</p>
                <p className="font-medium text-gray-900" data-testid="continue-properties-count">
                  {propertiesLabel}
                </p>
              </div>
            </div>
            {context.customer_reference && (
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 w-full">
                  Reference:{' '}
                  <span className="font-mono font-semibold text-gray-900" data-testid="continue-crn">
                    {context.customer_reference}
                  </span>
                </p>
              </div>
            )}
          </div>

          <p className="text-sm text-slate-700">{NEXT_STEP_COPY[nextStep] || NEXT_STEP_COPY.track_progress}</p>

          <div className="flex flex-wrap gap-3">
            {nextStep === 'complete_payment' && (
              <Button
                onClick={handleContinuePayment}
                disabled={checkoutLoading}
                className="bg-teal-600 hover:bg-teal-700"
                data-testid="continue-payment-btn"
              >
                {checkoutLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <CreditCard className="h-4 w-4 mr-2" />
                    Continue to payment
                  </>
                )}
              </Button>
            )}
            <Button variant="outline" onClick={goToStatus} data-testid="continue-view-status-btn">
              View setup progress <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>

          {context.masked_email && (
            <p className="text-xs text-gray-500">
              Registered email: {context.masked_email}.{' '}
              <Link to="/onboarding-status" className="text-teal-600 hover:underline">
                Onboarding help
              </Link>
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
