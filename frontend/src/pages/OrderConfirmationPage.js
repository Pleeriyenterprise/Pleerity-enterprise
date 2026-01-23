/**
 * Order Confirmation Page - Displayed after successful payment
 * 
 * Polls for draft → order conversion and displays order details.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, Loader2, AlertCircle, Package, Mail, Clock, FileText, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import client from '../api/client';

export default function OrderConfirmationPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const draftId = searchParams.get('draft_id');
  
  const [status, setStatus] = useState('loading'); // loading, converted, pending, error
  const [orderData, setOrderData] = useState(null);
  const [draftRef, setDraftRef] = useState(null);
  const [pollCount, setPollCount] = useState(0);
  const maxPolls = 20; // Max 20 polls (about 40 seconds)

  const checkStatus = useCallback(async () => {
    if (!draftId) {
      setStatus('error');
      return;
    }

    try {
      const res = await client.get(`/intake/draft/${draftId}/confirmation`);
      const data = res.data;
      
      setDraftRef(data.draft_ref);
      
      if (data.converted) {
        setOrderData(data.order);
        setStatus('converted');
      } else {
        setPollCount(prev => prev + 1);
        if (pollCount >= maxPolls) {
          setStatus('pending');
        }
      }
    } catch (err) {
      console.error('Failed to check status:', err);
      setStatus('error');
    }
  }, [draftId, pollCount]);

  // Initial check and polling combined
  useEffect(() => {
    let interval;
    
    const doCheck = async () => {
      if (!draftId) {
        setStatus('error');
        return;
      }

      try {
        const res = await client.get(`/intake/draft/${draftId}/confirmation`);
        const data = res.data;
        
        setDraftRef(data.draft_ref);
        
        if (data.converted) {
          setOrderData(data.order);
          setStatus('converted');
        } else {
          setPollCount(prev => {
            if (prev >= maxPolls) {
              setStatus('pending');
            }
            return prev + 1;
          });
        }
      } catch (err) {
        console.error('Failed to check status:', err);
        setStatus('error');
      }
    };
    
    // Initial check
    doCheck();
    
    // Start polling
    interval = setInterval(doCheck, 2000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [draftId]);

  // Stop polling when status changes
  useEffect(() => {
    if (status !== 'loading') {
      // Status changed, no need to poll anymore
    }
  }, [status]);

  // Loading state
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-16 w-16 animate-spin mx-auto text-teal-600" />
          <h2 className="mt-4 text-xl font-semibold text-gray-900">Processing Your Payment</h2>
          <p className="mt-2 text-gray-600">Please wait while we confirm your order...</p>
          <p className="mt-1 text-sm text-gray-500">This usually takes a few seconds</p>
        </div>
      </div>
    );
  }

  // Pending state (payment received but webhook pending)
  if (status === 'pending') {
    return (
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-lg mx-auto px-4">
          <Card>
            <CardContent className="p-8 text-center">
              <Clock className="h-16 w-16 mx-auto text-yellow-500" />
              <h2 className="mt-4 text-xl font-semibold text-gray-900">Payment Received</h2>
              <p className="mt-2 text-gray-600">
                Your payment was successful! We are processing your order now.
              </p>
              <p className="mt-4 text-sm text-gray-500">
                Reference: <span className="font-mono">{draftRef}</span>
              </p>
              <p className="mt-4 text-sm text-gray-600">
                You will receive an email confirmation shortly with your order details.
              </p>
              <Button
                className="mt-6 bg-teal-600 hover:bg-teal-700"
                onClick={() => navigate('/app/orders')}
              >
                View My Orders
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Error state
  if (status === 'error') {
    return (
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-lg mx-auto px-4">
          <Card>
            <CardContent className="p-8 text-center">
              <AlertCircle className="h-16 w-16 mx-auto text-red-500" />
              <h2 className="mt-4 text-xl font-semibold text-gray-900">Something Went Wrong</h2>
              <p className="mt-2 text-gray-600">
                We could not confirm your order. If you have been charged, please contact support.
              </p>
              <div className="mt-6 space-x-4">
                <Button variant="outline" onClick={() => navigate('/services')}>
                  Back to Services
                </Button>
                <Button
                  className="bg-teal-600 hover:bg-teal-700"
                  onClick={() => window.location.href = 'mailto:support@pleerity.com'}
                >
                  Contact Support
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Success state
  return (
    <div className="min-h-screen bg-gray-50 py-12" data-testid="order-confirmation-page">
      <div className="max-w-2xl mx-auto px-4">
        {/* Success Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 mb-4">
            <CheckCircle2 className="h-10 w-10 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Order Confirmed!</h1>
          <p className="mt-2 text-gray-600">Thank you for your order. We have received your payment.</p>
        </div>

        {/* Order Details Card */}
        <Card className="mb-6">
          <CardHeader className="bg-gray-50 border-b">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-500">Order Reference</p>
                <CardTitle className="text-xl font-mono">{orderData?.order_ref}</CardTitle>
              </div>
              <Badge className="bg-green-100 text-green-800">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Confirmed
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b">
                <div className="flex items-center gap-2">
                  <Package className="h-5 w-5 text-gray-400" />
                  <span className="text-gray-600">Service</span>
                </div>
                <span className="font-medium">{orderData?.service_code}</span>
              </div>
              
              <div className="flex justify-between items-center py-2 border-b">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-gray-400" />
                  <span className="text-gray-600">Status</span>
                </div>
                <Badge variant="secondary">{orderData?.status}</Badge>
              </div>
              
              <div className="flex justify-between items-center py-2">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-gray-400" />
                  <span className="text-gray-600">Order Date</span>
                </div>
                <span className="font-medium">
                  {orderData?.created_at 
                    ? new Date(orderData.created_at).toLocaleDateString('en-GB', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric'
                      })
                    : 'Today'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* What's Next */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">What Happens Next?</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-100 text-teal-600 flex items-center justify-center text-sm font-medium">
                  1
                </div>
                <div>
                  <p className="font-medium text-gray-900">Order Processing</p>
                  <p className="text-sm text-gray-600">Your order has been queued and will be processed by our team.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-100 text-teal-600 flex items-center justify-center text-sm font-medium">
                  2
                </div>
                <div>
                  <p className="font-medium text-gray-900">Document Generation</p>
                  <p className="text-sm text-gray-600">We'll generate your documents based on the information you provided.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-100 text-teal-600 flex items-center justify-center text-sm font-medium">
                  3
                </div>
                <div>
                  <p className="font-medium text-gray-900">Delivery</p>
                  <p className="text-sm text-gray-600">Once complete, you'll receive an email with download links.</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Email Confirmation Notice */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3 mb-6">
          <Mail className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-blue-900">Confirmation Email Sent</p>
            <p className="text-sm text-blue-700">
              We've sent a confirmation email to your registered address. Please check your inbox (and spam folder).
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button
            variant="outline"
            onClick={() => navigate('/services')}
            className="flex-1 sm:flex-none"
          >
            Browse More Services
          </Button>
          <Button
            className="bg-teal-600 hover:bg-teal-700 flex-1 sm:flex-none"
            onClick={() => navigate('/app/orders')}
          >
            View My Orders
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
}
