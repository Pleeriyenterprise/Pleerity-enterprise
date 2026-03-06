/**
 * Order Checkout Page – /order/checkout?draft=DRAFT_REF
 *
 * Loads draft by draft_ref, shows order summary, and "Pay now" redirects to Stripe.
 * Enables "save and resume": user can return via link with draft_ref to complete payment.
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Loader2, AlertCircle, CreditCard, ArrowLeft } from 'lucide-react';
import PublicLayout from '../components/public/PublicLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import client from '../api/client';
import { createCheckoutSession, isDocumentPack, validateCheckout } from '../api/checkoutApi';
import { toast } from 'sonner';

export default function OrderCheckoutPage() {
  const [searchParams] = useSearchParams();
  const draftRef = searchParams.get('draft');

  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    if (!draftRef) {
      setError('Missing draft reference. Use the link from your saved intake.');
      setLoading(false);
      return;
    }

    const fetchDraft = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await client.get(`/intake/draft/by-ref/${encodeURIComponent(draftRef)}`);
        const data = res.data;
        if (data.status === 'CONVERTED') {
          setError('This order has already been paid. Check your confirmation email.');
          setDraft(null);
        } else {
          setDraft(data);
        }
      } catch (err) {
        const msg = err.response?.data?.detail || err.message || 'Draft not found';
        setError(typeof msg === 'string' ? msg : 'Draft not found or expired.');
        setDraft(null);
      } finally {
        setLoading(false);
      }
    };

    fetchDraft();
  }, [draftRef]);

  const handlePayNow = async () => {
    if (!draft?.draft_ref) return;
    try {
      setPaying(true);
      const res = await createCheckoutSession(draft.draft_ref);
      if (res?.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        toast.error('Could not start checkout');
        setPaying(false);
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || 'Payment failed';
      toast.error(typeof msg === 'string' ? msg : 'Payment failed');
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
            <div className="pt-4 border-t flex flex-col sm:flex-row gap-3">
              <Button
                className="flex-1"
                disabled={paying}
                onClick={handlePayNow}
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
