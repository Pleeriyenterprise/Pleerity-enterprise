/**
 * Order Checkout Page – /order/checkout?draft=DRAFT_REF
 *
 * Loads draft by draft_ref, shows order summary, and "Pay now" redirects to Stripe.
 * Enables "save and resume": user can return via link with draft_ref to complete payment.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Loader2, AlertCircle, CreditCard, ArrowLeft } from 'lucide-react';
import PublicLayout from '../components/public/PublicLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import client from '../api/client';
import { createCheckoutSession } from '../api/checkoutApi';
import { toast } from 'sonner';

export default function OrderCheckoutPage() {
  const [searchParams] = useSearchParams();
  const draftRef = searchParams.get('draft');

  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(false);
  const [validation, setValidation] = useState(null);
  const [rechecking, setRechecking] = useState(false);

  const loadDraft = useCallback(async () => {
    if (!draftRef) return;
    const res = await client.get(`/intake/draft/by-ref/${encodeURIComponent(draftRef)}`);
    const data = res.data;
    if (data.status === 'CONVERTED') {
      setError('This order has already been paid. Check your confirmation email.');
      setDraft(null);
      setValidation(null);
      return;
    }
    setDraft(data);
    setValidation(data.validation || null);
  }, [draftRef]);

  useEffect(() => {
    if (!draftRef) {
      setError('Missing draft reference. Use the link from your saved intake.');
      setLoading(false);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        await loadDraft();
      } catch (err) {
        if (cancelled) return;
        const msg = err.response?.data?.detail || err.message || 'Draft not found';
        setError(typeof msg === 'string' ? msg : 'Draft not found or expired.');
        setDraft(null);
        setValidation(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [draftRef, loadDraft]);

  const handleRecheckReady = async () => {
    if (!draftRef) return;
    try {
      setRechecking(true);
      await loadDraft();
      toast.success('Status refreshed');
    } catch {
      toast.error('Could not refresh draft');
    } finally {
      setRechecking(false);
    }
  };

  const payReady = Boolean(validation?.ready_for_payment);

  const handlePayNow = async () => {
    if (!draft?.draft_ref || !draft?.draft_id) return;
    try {
      setPaying(true);
      const vRes = await client.post(`/intake/draft/${draft.draft_id}/validate`);
      setValidation({
        ready_for_payment: vRes.data.ready_for_payment,
        errors: vRes.data.errors || [],
        missing_sections: vRes.data.missing_sections || [],
        warnings: vRes.data.warnings || [],
      });
      if (!vRes.data.ready_for_payment) {
        const errs = vRes.data.errors || [];
        const miss = vRes.data.missing_sections || [];
        toast.error(
          errs[0]?.message ||
            (miss.includes('service_intake')
              ? 'Complete all service questions in Edit order, then return here.'
              : miss.length
                ? `Missing: ${miss.join(', ')}`
                : 'Draft not ready for payment'),
        );
        errs.slice(1, 4).forEach((e) => toast.error(e.message));
        setPaying(false);
        return;
      }
      const res = await createCheckoutSession(draft.draft_ref);
      if (res?.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        toast.error('Could not start checkout');
        setPaying(false);
      }
    } catch (err) {
      const d = err.response?.data?.detail;
      const msg =
        (typeof d === 'object' && d?.message) ||
        (typeof d === 'string' ? d : null) ||
        'Payment failed';
      toast.error(msg);
      if (typeof d === 'object' && Array.isArray(d?.errors) && d.errors.length > 1) {
        d.errors.slice(1, 6).forEach((e) => toast.error(e?.message || String(e)));
      }
      setPaying(false);
    }
  };

  const formatPrice = (pence) => {
    if (pence == null || pence === 0) return '£0.00';
    return `£${(pence / 100).toFixed(2)}`;
  };

  if (loading) {
    return (
      <PublicLayout>
        <div className="min-h-[40vh] flex items-center justify-center">
          <Loader2 className="h-10 w-10 animate-spin text-electric-teal" />
        </div>
      </PublicLayout>
    );
  }

  if (error && !draft) {
    return (
      <PublicLayout>
        <div className="max-w-lg mx-auto px-4 py-16">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2 text-amber-600">
                <AlertCircle className="h-5 w-5" />
                <CardTitle>Cannot load checkout</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600 mb-6">{error}</p>
              <Button variant="outline" asChild>
                <Link to="/order/intake">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Start a new order
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </PublicLayout>
    );
  }

  const pricing = draft?.pricing_snapshot || {};
  const totalPence = pricing.total_price_pence ?? pricing.base_price_pence ?? 0;

  return (
    <PublicLayout>
      <div className="max-w-xl mx-auto px-4 py-12">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Complete your order
            </CardTitle>
            <p className="text-sm text-gray-500">
              Draft reference: <span className="font-mono">{draft?.draft_ref}</span>
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <p className="text-sm text-gray-500">Service</p>
              <p className="font-medium">{draft?.service_name || draft?.service_code}</p>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Total</span>
              <span className="font-medium">{formatPrice(totalPence)}</span>
            </div>

            {!payReady && validation && (
              <div
                className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                role="alert"
              >
                <p className="font-medium mb-2">Complete your order before paying</p>
                <p className="text-amber-800 mb-2">
                  Use <strong>Edit order</strong> to finish all steps (details, service questions, and tick both
                  consent boxes on the review screen), then come back or tap &quot;Refresh status&quot;.
                </p>
                {(validation.errors || []).length > 0 && (
                  <ul className="list-disc pl-5 space-y-1 text-amber-900">
                    {validation.errors.slice(0, 8).map((e, i) => (
                      <li key={i}>{e.message || e.field_key}</li>
                    ))}
                  </ul>
                )}
                {(validation.missing_sections || []).length > 0 &&
                  !(validation.errors || []).length && (
                    <p className="text-amber-800">
                      Missing: {validation.missing_sections.join(', ')}
                    </p>
                  )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3 border-amber-300"
                  disabled={rechecking}
                  onClick={handleRecheckReady}
                >
                  {rechecking ? 'Checking…' : 'Refresh status'}
                </Button>
              </div>
            )}

            <div className="pt-4 border-t flex flex-col sm:flex-row gap-3">
              <Button
                className="flex-1"
                disabled={paying || !payReady}
                onClick={handlePayNow}
                title={!payReady ? 'Finish intake first (see message above)' : undefined}
              >
                {paying ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Redirecting to payment…
                  </>
                ) : (
                  <>
                    <CreditCard className="h-4 w-4 mr-2" />
                    Pay now
                  </>
                )}
              </Button>
              <Button variant="outline" asChild>
                <Link to={`/order/intake?draft=${encodeURIComponent(draft?.draft_ref || '')}`}>
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Edit order
                </Link>
              </Button>
            </div>
            <p className="text-xs text-gray-400">
              You will be redirected to our secure payment page. No payment is taken on this page.
            </p>
          </CardContent>
        </Card>
      </div>
    </PublicLayout>
  );
}
