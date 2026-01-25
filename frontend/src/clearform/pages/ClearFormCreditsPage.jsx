/**
 * ClearForm Credits Page
 * 
 * View credit balance, purchase top-ups, and manage subscriptions.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  CreditCard,
  Zap,
  Crown,
  Star,
  Check,
  ArrowLeft,
  Loader2,
  Sparkles,
  Clock,
  TrendingUp
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { creditsApi } from '../api/clearformApi';
import { toast } from 'sonner';

const ClearFormCreditsPage = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useClearFormAuth();
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(null);

  useEffect(() => {
    loadWallet();
  }, []);

  const loadWallet = async () => {
    try {
      const data = await creditsApi.getWallet();
      setWallet(data);
    } catch (error) {
      console.error('Failed to load wallet:', error);
    } finally {
      setLoading(false);
    }
  };

  // Credit top-up packages
  const creditPackages = [
    {
      id: 'credits_10',
      credits: 10,
      price: 5,
      pricePerCredit: 0.50,
      popular: false,
    },
    {
      id: 'credits_25',
      credits: 25,
      price: 10,
      pricePerCredit: 0.40,
      popular: true,
      savings: '20%',
    },
    {
      id: 'credits_75',
      credits: 75,
      price: 25,
      pricePerCredit: 0.33,
      popular: false,
      savings: '33%',
    },
  ];

  // Subscription plans
  const subscriptionPlans = [
    {
      id: 'free',
      name: 'Free',
      price: 0,
      credits: 3,
      creditsNote: 'one-time',
      features: [
        '3 credits (one-time)',
        'Watermarked documents',
        'All document types',
      ],
      limitations: ['Watermarked output'],
      cta: 'Current Plan',
      disabled: true,
    },
    {
      id: 'personal',
      name: 'Personal',
      price: 9.99,
      credits: 20,
      creditsNote: 'per month',
      features: [
        '20 credits per month',
        'No watermark',
        'All document types',
        'Priority support',
      ],
      limitations: ['Credits don\'t roll over'],
      popular: true,
      cta: 'Subscribe',
    },
    {
      id: 'power_user',
      name: 'Power User',
      price: 24.99,
      credits: 75,
      creditsNote: 'per month',
      features: [
        '75 credits per month',
        'No watermark',
        'Priority generation',
        'Early access to new types',
        'Dedicated support',
      ],
      limitations: ['Credits don\'t roll over'],
      cta: 'Subscribe',
      icon: Crown,
    },
  ];

  const handlePurchaseCredits = async (packageId) => {
    setPurchasing(packageId);
    try {
      // Call the backend to create a Stripe checkout session
      const result = await creditsApi.createPurchase(packageId);
      
      if (result.checkout_url) {
        // Redirect to Stripe checkout
        window.location.href = result.checkout_url;
      } else {
        throw new Error('No checkout URL returned');
      }
    } catch (error) {
      console.error('Purchase error:', error);
      toast.error(error.message || 'Failed to start purchase. Please try again.');
      setPurchasing(null);
    }
  };

  const handleSubscribe = async (planId) => {
    setPurchasing(planId);
    try {
      // Call the subscriptions API to create a subscription checkout
      const result = await subscriptionsApi.subscribe(planId);
      
      if (result.checkout_url) {
        // Redirect to Stripe checkout
        window.location.href = result.checkout_url;
      } else {
        throw new Error('No checkout URL returned');
      }
    } catch (error) {
      console.error('Subscription error:', error);
      toast.error(error.message || 'Failed to start subscription. Please try again.');
      setPurchasing(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50">
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
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{user?.credit_balance || 0} credits</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Back Link */}
        <Button 
          variant="ghost" 
          className="mb-6"
          onClick={() => navigate('/clearform/dashboard')}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Button>

        {/* Current Balance */}
        <Card className="mb-8 bg-gradient-to-r from-emerald-500 to-teal-600 text-white">
          <CardContent className="py-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <p className="text-emerald-100 text-sm mb-1">Current Balance</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-5xl font-bold">{wallet?.total_balance || 0}</span>
                  <span className="text-emerald-100">credits</span>
                </div>
                {wallet?.subscription_credits > 0 && (
                  <p className="text-sm text-emerald-100 mt-2">
                    {wallet.subscription_credits} from subscription • {wallet.purchased_credits || 0} purchased
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 text-emerald-100">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm">{wallet?.documents_generated_this_month || 0} docs this month</span>
                </div>
                <div className="flex items-center gap-2 text-emerald-100">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm">Top-up credits never expire</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Credit Top-ups */}
        <div className="mb-12">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-slate-900">Buy Credits</h2>
            <p className="text-slate-500">Top up your balance. Credits never expire.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {creditPackages.map((pkg) => (
              <Card 
                key={pkg.id}
                className={`relative ${pkg.popular ? 'border-2 border-emerald-500 shadow-lg' : ''}`}
                data-testid={`credit-package-${pkg.id}`}
              >
                {pkg.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-emerald-500 text-white">Best Value</Badge>
                  </div>
                )}
                <CardHeader className="text-center pb-2">
                  <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Zap className="w-6 h-6 text-emerald-600" />
                  </div>
                  <CardTitle className="text-3xl font-bold">{pkg.credits}</CardTitle>
                  <CardDescription>credits</CardDescription>
                </CardHeader>
                <CardContent className="text-center">
                  <div className="mb-4">
                    <span className="text-3xl font-bold text-slate-900">£{pkg.price}</span>
                    {pkg.savings && (
                      <Badge variant="outline" className="ml-2 text-emerald-600 border-emerald-600">
                        Save {pkg.savings}
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-slate-500 mb-4">
                    £{pkg.pricePerCredit.toFixed(2)} per credit
                  </p>
                  <Button 
                    className="w-full"
                    variant={pkg.popular ? 'default' : 'outline'}
                    onClick={() => handlePurchaseCredits(pkg.id)}
                    disabled={purchasing === pkg.id}
                  >
                    {purchasing === pkg.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4 mr-2" />
                        Buy Now
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Subscription Plans */}
        <div>
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-slate-900">Subscription Plans</h2>
            <p className="text-slate-500">Get monthly credits at a discount. Subscriptions renew automatically.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {subscriptionPlans.map((plan) => {
              const Icon = plan.icon || Star;
              return (
                <Card 
                  key={plan.id}
                  className={`relative ${plan.popular ? 'border-2 border-emerald-500 shadow-lg' : ''}`}
                  data-testid={`subscription-plan-${plan.id}`}
                >
                  {plan.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <Badge className="bg-emerald-500 text-white">Popular</Badge>
                    </div>
                  )}
                  <CardHeader className="text-center pb-2">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3 ${
                      plan.id === 'power_user' ? 'bg-amber-100' : 'bg-slate-100'
                    }`}>
                      <Icon className={`w-6 h-6 ${plan.id === 'power_user' ? 'text-amber-600' : 'text-slate-600'}`} />
                    </div>
                    <CardTitle>{plan.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center mb-4">
                      <div className="flex items-baseline justify-center">
                        <span className="text-3xl font-bold text-slate-900">
                          {plan.price === 0 ? 'Free' : `£${plan.price}`}
                        </span>
                        {plan.price > 0 && (
                          <span className="text-slate-500 ml-1">/month</span>
                        )}
                      </div>
                      <p className="text-sm text-emerald-600 font-medium mt-1">
                        {plan.credits} credits {plan.creditsNote}
                      </p>
                    </div>

                    <ul className="space-y-2 mb-6">
                      {plan.features.map((feature, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                          <span className="text-slate-600">{feature}</span>
                        </li>
                      ))}
                      {plan.limitations?.map((limitation, i) => (
                        <li key={`limit-${i}`} className="flex items-start gap-2 text-sm text-slate-400">
                          <span className="w-4 h-4 shrink-0" />
                          <span>{limitation}</span>
                        </li>
                      ))}
                    </ul>

                    <Button 
                      className="w-full"
                      variant={plan.popular ? 'default' : 'outline'}
                      disabled={plan.disabled || purchasing === plan.id}
                      onClick={() => !plan.disabled && handleSubscribe(plan.id)}
                    >
                      {purchasing === plan.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        plan.cta
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Important Notes */}
          <Card className="mt-8 bg-slate-50">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                <div className="text-sm text-slate-600">
                  <p className="font-medium text-slate-900 mb-1">Important Notes</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Subscriptions grant <strong>monthly</strong> credits that reset each billing cycle</li>
                    <li>Top-up credits are <strong>separate</strong> and never expire</li>
                    <li>Credits show price before generation and confirm deduction</li>
                    <li>Unused subscription credits do not roll over to the next month</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default ClearFormCreditsPage;
