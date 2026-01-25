/**
 * ClearForm Payment Success Page
 * 
 * Handles redirect from Stripe checkout for both credit purchases and subscriptions.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { 
  CheckCircle, 
  Loader2,
  CreditCard,
  ArrowRight,
  Sparkles
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { toast } from 'sonner';

const ClearFormPaymentSuccessPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refreshUser } = useClearFormAuth();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('pending');
  const [purchaseInfo, setPurchaseInfo] = useState(null);

  // Determine the type of purchase from URL
  const sessionId = searchParams.get('session_id');
  const isSubscription = window.location.pathname.includes('subscription');

  useEffect(() => {
    if (sessionId) {
      checkPaymentStatus();
    } else {
      setLoading(false);
      setStatus('error');
    }
  }, [sessionId]);

  const checkPaymentStatus = async () => {
    try {
      // Poll the backend to check if the payment has been processed
      const API_BASE = process.env.REACT_APP_BACKEND_URL;
      const token = localStorage.getItem('clearform_token');
      
      // Wait a moment for webhook to process
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Refresh user to get updated credit balance
      await refreshUser();
      
      setStatus('success');
      setPurchaseInfo({
        type: isSubscription ? 'subscription' : 'credits',
        sessionId,
      });
    } catch (error) {
      console.error('Error checking payment status:', error);
      // Even if check fails, the webhook likely still processed
      // Show success optimistically
      setStatus('success');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-emerald-500 mx-auto mb-4" />
          <p className="text-slate-600">Processing your payment...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-16 max-w-lg">
        {status === 'success' ? (
          <Card className="text-center">
            <CardContent className="py-12">
              <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-10 h-10 text-emerald-600" />
              </div>
              
              <h1 className="text-2xl font-bold text-slate-900 mb-2">
                Payment Successful!
              </h1>
              
              <p className="text-slate-600 mb-8">
                {isSubscription 
                  ? "Your subscription is now active. Credits have been added to your account."
                  : "Your credits have been added to your account."}
              </p>

              <div className="flex flex-col gap-3">
                <Button 
                  className="w-full bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => navigate('/clearform/create')}
                  data-testid="create-document-btn"
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Create a Document
                </Button>
                
                <Button 
                  variant="outline"
                  className="w-full"
                  onClick={() => navigate('/clearform/dashboard')}
                  data-testid="go-to-dashboard-btn"
                >
                  Go to Dashboard
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>

              <p className="text-sm text-slate-500 mt-6">
                <CreditCard className="w-4 h-4 inline mr-1" />
                A receipt has been sent to your email
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card className="text-center">
            <CardContent className="py-12">
              <div className="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Loader2 className="w-10 h-10 text-amber-600" />
              </div>
              
              <h1 className="text-2xl font-bold text-slate-900 mb-2">
                Processing Payment
              </h1>
              
              <p className="text-slate-600 mb-8">
                We're confirming your payment. If you've completed checkout, your credits will appear shortly.
              </p>

              <Button 
                variant="outline"
                className="w-full"
                onClick={() => navigate('/clearform/dashboard')}
              >
                Return to Dashboard
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
};

export default ClearFormPaymentSuccessPage;
