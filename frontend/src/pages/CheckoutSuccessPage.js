import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Clock, Loader2, Mail } from 'lucide-react';
import api from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import { buildClientLoginUrlWithNext } from '../utils/clientLoginRedirect';

const POLL_INTERVAL_MS = 5000;
const POLL_DURATION_MS = 180000;

function shouldStopPolling(data) {
  if (!data) return false;
  const next = data.next_action || '';
  if (next === 'set_password' || next === 'go_to_dashboard') return true;
  if (data.password_set === true) return true;
  const vs = String(data.provisioning_status || data.provisioning_state || '').toUpperCase();
  return vs === 'FAILED' || vs === 'COMPLETED';
}

function storedPendingClientId() {
  if (typeof window === 'undefined') return '';
  try {
    return (localStorage.getItem('pending_client_id') || '').trim();
  } catch {
    return '';
  }
}

const CheckoutSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const sessionId = (searchParams.get('session_id') || '').trim();
  const pendingClientIdRef = useRef(storedPendingClientId());
  const resolvedClientIdRef = useRef('');

  const [status, setStatus] = useState(null);
  const [lookupError, setLookupError] = useState(null);
  const [lookupCode, setLookupCode] = useState(null);
  const pollStartRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    const params = {};
    if (resolvedClientIdRef.current) params.client_id = resolvedClientIdRef.current;
    else if (pendingClientIdRef.current) params.client_id = pendingClientIdRef.current;
    if (sessionId) params.session_id = sessionId;
    if (!params.client_id && !params.session_id) {
      return null;
    }
    try {
      const res = await api.get('/portal/setup-status', { params });
      setStatus(res.data);
      setLookupError(null);
      setLookupCode(null);
      if (res.data?.client_id) {
        resolvedClientIdRef.current = res.data.client_id;
      }
      if (pendingClientIdRef.current && typeof window !== 'undefined') {
        try {
          localStorage.removeItem('pending_client_id');
        } catch {
          /* ignore */
        }
        pendingClientIdRef.current = '';
      }
      return res.data;
    } catch (err) {
      const httpStatus = err.response?.status;
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'We could not confirm this checkout yet.';
      setLookupCode(httpStatus || 'error');
      setLookupError(msg);
      return null;
    }
  }, [sessionId]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('pleerity_stripe_redirect', Date.now().toString());
    }
  }, []);

  useEffect(() => {
    if (!sessionId && !pendingClientIdRef.current) return undefined;
    let cancelled = false;
    fetchStatus().then((data) => {
      if (!cancelled && data) pollStartRef.current = Date.now();
    });
    return () => {
      cancelled = true;
    };
  }, [fetchStatus, sessionId]);

  useEffect(() => {
    if (!pollStartRef.current) return undefined;
    if (shouldStopPolling(status)) return undefined;

    const runPoll = async () => {
      const elapsed = Date.now() - pollStartRef.current;
      if (elapsed >= POLL_DURATION_MS) {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        return;
      }
      const data = await fetchStatus();
      if (data && shouldStopPolling(data) && pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };

    pollIntervalRef.current = setInterval(runPoll, POLL_INTERVAL_MS);
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [fetchStatus, status]);

  const missingSession = !sessionId && !pendingClientIdRef.current && !status?.client_id;
  const nextAction = status?.next_action || '';
  const paymentPaid = (status?.payment_state || '').toLowerCase() === 'paid';
  const provisioningComplete =
    String(status?.provisioning_status || '').toUpperCase() === 'COMPLETED' ||
    nextAction === 'set_password' ||
    nextAction === 'go_to_dashboard';
  const provisioningPending = Boolean(status) && !provisioningComplete;
  const clientId = status?.client_id;
  const statusHref = clientId
    ? `/onboarding-status?client_id=${encodeURIComponent(clientId)}${
        sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ''
      }`
    : null;
  const signInHref = buildClientLoginUrlWithNext('/dashboard?first_login=1');

  let heading = 'Checkout complete';
  let body =
    'Your payment has been received. We are continuing your account setup. This can take a minute.';
  let stateTestId = 'checkout-success-confirming';

  if (missingSession) {
    heading = 'Checkout details missing';
    body =
      'This page needs a checkout reference from your payment. If you have just paid, check your email for the next step. Do not start another registration.';
    stateTestId = 'checkout-success-missing-session';
  } else if (lookupError && !status) {
    if (lookupCode === 404 || lookupCode === 400) {
      heading = 'We could not match this checkout';
      body =
        'If you have just paid, check your email for the next step. Do not start another registration.';
      stateTestId = 'checkout-success-invalid-session';
    } else {
      heading = 'Confirming your checkout';
      body =
        'Your payment may still be processing. Stay on this page or check your email. Do not start another registration.';
      stateTestId = 'checkout-success-lookup-pending';
    }
  } else if (provisioningComplete && nextAction === 'go_to_dashboard') {
    heading = 'Your account is ready';
    body = 'Checkout is complete and your portal setup has finished. Sign in to continue. Do not start another registration.';
    stateTestId = 'checkout-success-complete';
  } else if (provisioningComplete) {
    heading = 'Checkout complete — check your email';
    body =
      'Payment is complete and we are finishing account setup. Use the activation email to set your password. Do not start another registration.';
    stateTestId = 'checkout-success-complete';
  } else if (provisioningPending || paymentPaid) {
    heading = 'Checkout complete';
    body =
      'Payment is complete. We are still finishing your account setup. This usually takes under a minute. Do not start another registration.';
    stateTestId = 'checkout-success-pending';
  }

  const showSpinner = !missingSession && !status && !lookupError;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" data-testid="checkout-success-page">
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-xl mx-auto px-4">
          <h1 className="text-xl font-bold">Compliance Vault Pro</h1>
        </div>
      </header>
      <main className="max-w-xl mx-auto px-4 py-12">
        <div className="bg-white rounded-xl shadow-lg p-8 text-center" data-testid={stateTestId}>
          {showSpinner ? (
            <Loader2 className="w-12 h-12 animate-spin text-electric-teal mx-auto mb-4" data-testid="checkout-success-spinner" />
          ) : missingSession || (lookupError && !status && (lookupCode === 404 || lookupCode === 400)) ? (
            <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          ) : provisioningComplete ? (
            <CheckCircle2 className="w-12 h-12 text-green-600 mx-auto mb-4" />
          ) : (
            <Clock className="w-12 h-12 text-electric-teal mx-auto mb-4" />
          )}
          <h2 className="text-2xl font-semibold text-midnight-blue mb-3">{heading}</h2>
          <p className="text-gray-600 mb-6">{body}</p>
          {sessionId ? (
            <p className="text-xs text-gray-400 mb-6 break-all" data-testid="checkout-success-session-id">
              Checkout reference: {sessionId}
            </p>
          ) : null}
          {status?.customer_reference ? (
            <p className="text-sm text-gray-500 mb-6">
              Your customer reference: <span className="font-mono font-semibold">{status.customer_reference}</span>
            </p>
          ) : null}
          <div className="space-y-3">
            {provisioningComplete && nextAction === 'go_to_dashboard' ? (
              <Link
                to={signInHref}
                className="inline-flex items-center justify-center rounded-md bg-electric-teal px-4 py-2 text-sm font-medium text-white hover:bg-electric-teal/90"
                data-testid="checkout-success-sign-in"
              >
                Sign in
              </Link>
            ) : null}
            {provisioningComplete && nextAction === 'set_password' ? (
              <p className="text-sm text-gray-600 inline-flex items-center justify-center gap-2">
                <Mail className="w-4 h-4" /> Check your inbox for the activation link.
              </p>
            ) : null}
            {statusHref ? (
              <div>
                <Link
                  to={statusHref}
                  className="text-sm text-electric-teal hover:underline"
                  data-testid="checkout-success-progress-link"
                >
                  View setup progress
                </Link>
              </div>
            ) : null}
          </div>
          <p className="text-sm text-gray-500 mt-8">
            Need help? Contact{' '}
            <a className="text-electric-teal hover:underline" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>
          </p>
        </div>
      </main>
    </div>
  );
};

export default CheckoutSuccessPage;
