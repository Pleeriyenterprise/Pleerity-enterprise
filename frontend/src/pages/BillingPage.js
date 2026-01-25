import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Check, 
  X, 
  ArrowLeft, 
  Sparkles, 
  Building2, 
  Users, 
  Zap,
  Crown,
  Shield,
  FileText,
  Bell,
  Webhook,
  Palette,
  Calendar,
  ChevronDown,
  ChevronUp,
  Loader2,
  ArrowRight,
  AlertTriangle,
  XCircle,
  ExternalLink
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import api from '../api/client';

// Plan configuration - matches backend plan_registry.py
const PLANS = [
  {
    code: 'PLAN_1_SOLO',
    name: 'Solo Landlord',
    description: 'Perfect for DIY landlords managing 1-2 properties',
    monthlyPrice: 19,
    onboardingFee: 49,
    maxProperties: 2,
    color: '#6B7280',
    icon: Building2,
    badge: null,
    targetAudience: 'DIY landlords',
  },
  {
    code: 'PLAN_2_PORTFOLIO',
    name: 'Portfolio',
    description: 'For portfolio landlords and small letting agents',
    monthlyPrice: 39,
    onboardingFee: 79,
    maxProperties: 10,
    color: '#00B8A9',
    icon: Users,
    badge: 'Most Popular',
    targetAudience: 'Portfolio landlords, small agents',
  },
  {
    code: 'PLAN_3_PRO',
    name: 'Professional',
    description: 'For letting agents, HMOs, and serious operators',
    monthlyPrice: 79,
    onboardingFee: 149,
    maxProperties: 25,
    color: '#0B1D3A',
    icon: Crown,
    badge: 'Full Features',
    targetAudience: 'Letting agents, HMOs',
  },
];

// Feature categories with all features
const FEATURE_CATEGORIES = [
  {
    name: 'Core Features',
    icon: Shield,
    features: [
      { key: 'compliance_dashboard', name: 'Compliance Dashboard', description: 'View property compliance status at a glance' },
      { key: 'compliance_score', name: 'Compliance Score', description: 'Track your compliance score with explanations' },
      { key: 'compliance_calendar', name: 'Compliance Calendar', description: 'View expiry dates in calendar format' },
      { key: 'email_notifications', name: 'Email Notifications', description: 'Receive compliance reminders via email' },
      { key: 'multi_file_upload', name: 'Multi-File Upload', description: 'Upload multiple documents at once' },
      { key: 'score_trending', name: 'Score Trending', description: 'View compliance score history and trends' },
    ],
  },
  {
    name: 'AI Features',
    icon: Sparkles,
    features: [
      { key: 'ai_extraction_basic', name: 'AI Extraction (Basic)', description: 'Auto-extract document type, issue and expiry dates' },
      { key: 'ai_extraction_advanced', name: 'AI Extraction (Advanced)', description: 'Confidence scoring and field validation' },
      { key: 'extraction_review_ui', name: 'Extraction Review UI', description: 'Review and approve AI-extracted data' },
    ],
  },
  {
    name: 'Documents',
    icon: FileText,
    features: [
      { key: 'zip_upload', name: 'ZIP Archive Upload', description: 'Upload documents as a single ZIP archive' },
    ],
  },
  {
    name: 'Reporting',
    icon: FileText,
    features: [
      { key: 'reports_pdf', name: 'PDF Reports', description: 'Download compliance reports as PDF' },
      { key: 'reports_csv', name: 'CSV Reports', description: 'Download compliance data as CSV' },
      { key: 'scheduled_reports', name: 'Scheduled Reports', description: 'Automatically receive reports on schedule' },
    ],
  },
  {
    name: 'Communication',
    icon: Bell,
    features: [
      { key: 'sms_reminders', name: 'SMS Reminders', description: 'Receive compliance reminders via SMS' },
    ],
  },
  {
    name: 'Tenant Portal',
    icon: Users,
    features: [
      { key: 'tenant_portal', name: 'Tenant Portal', description: 'Allow tenants to view property compliance (read-only)' },
    ],
  },
  {
    name: 'Integrations',
    icon: Webhook,
    features: [
      { key: 'webhooks', name: 'Webhooks', description: 'Send compliance events to external systems' },
      { key: 'api_access', name: 'API Access', description: 'Programmatic access to compliance data' },
    ],
  },
  {
    name: 'Advanced',
    icon: Palette,
    features: [
      { key: 'white_label_reports', name: 'White-Label Reports', description: 'Custom branding for reports' },
      { key: 'audit_log_export', name: 'Audit Log Export', description: 'Export audit logs for compliance review' },
    ],
  },
];

// Feature availability matrix
const FEATURE_MATRIX = {
  PLAN_1_SOLO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: false,
    extraction_review_ui: false,
    zip_upload: false,
    reports_pdf: false,
    reports_csv: false,
    scheduled_reports: false,
    sms_reminders: false,
    tenant_portal: false,
    webhooks: false,
    api_access: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_2_PORTFOLIO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: true,
    extraction_review_ui: true,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: true,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: true,
    webhooks: false,
    api_access: false,
    white_label_reports: false,
    audit_log_export: false,
  },
  PLAN_3_PRO: {
    compliance_dashboard: true,
    compliance_score: true,
    compliance_calendar: true,
    email_notifications: true,
    multi_file_upload: true,
    score_trending: true,
    ai_extraction_basic: true,
    ai_extraction_advanced: true,
    extraction_review_ui: true,
    zip_upload: true,
    reports_pdf: true,
    reports_csv: true,
    scheduled_reports: true,
    sms_reminders: true,
    tenant_portal: true,
    webhooks: true,
    api_access: true,
    white_label_reports: true,
    audit_log_export: true,
  },
};

const BillingPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [currentPlan, setCurrentPlan] = useState(null);
  const [entitlements, setEntitlements] = useState(null);
  const [billingStatus, setBillingStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState({});
  const [upgrading, setUpgrading] = useState(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  
  const highlightPlan = searchParams.get('upgrade_to');

  useEffect(() => {
    fetchEntitlements();
    fetchBillingStatus();
    // Expand all categories by default
    const expanded = {};
    FEATURE_CATEGORIES.forEach(cat => {
      expanded[cat.name] = true;
    });
    setExpandedCategories(expanded);
  }, []);

  const fetchEntitlements = async () => {
    try {
      const response = await api.get('/client/entitlements');
      setEntitlements(response.data);
      setCurrentPlan(response.data.plan);
    } catch (error) {
      console.error('Failed to fetch entitlements:', error);
      toast.error('Failed to load plan information');
    } finally {
      setLoading(false);
    }
  };

  const fetchBillingStatus = async () => {
    try {
      const response = await api.get('/billing/status');
      setBillingStatus(response.data);
    } catch (error) {
      console.error('Failed to fetch billing status:', error);
    }
  };

  const handleCancelSubscription = async (cancelImmediately = false) => {
    setCancelling(true);
    try {
      await api.post('/billing/cancel', { cancel_immediately: cancelImmediately });
      
      if (cancelImmediately) {
        toast.success('Subscription cancelled', {
          description: 'Your subscription has been cancelled immediately.',
        });
      } else {
        toast.success('Cancellation scheduled', {
          description: 'Your subscription will end at the current billing period.',
        });
      }
      
      setShowCancelModal(false);
      // Refresh billing status
      await fetchBillingStatus();
      await fetchEntitlements();
      
    } catch (error) {
      console.error('Cancel error:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to cancel subscription';
      toast.error(errorMessage);
    } finally {
      setCancelling(false);
    }
  };

  const toggleCategory = (categoryName) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryName]: !prev[categoryName]
    }));
  };

  const handleUpgrade = async (planCode) => {
    if (planCode === currentPlan) {
      toast.info('You are already on this plan');
      return;
    }
    
    // Check if it's a downgrade
    const currentPlanIndex = PLANS.findIndex(p => p.code === currentPlan);
    const targetPlanIndex = PLANS.findIndex(p => p.code === planCode);
    
    if (targetPlanIndex < currentPlanIndex) {
      toast.error('Please contact support to downgrade your plan');
      return;
    }
    
    setUpgrading(planCode);
    
    try {
      // Call the billing API to create checkout session
      const response = await api.post('/billing/checkout', { plan_code: planCode });
      
      toast.success('Redirecting to payment...', {
        description: 'You will be redirected to complete your upgrade.',
      });
      
      // Redirect to checkout or billing portal
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else if (response.data.portal_url) {
        window.location.href = response.data.portal_url;
      } else {
        toast.error('No checkout URL received');
        setUpgrading(null);
      }
      
    } catch (error) {
      console.error('Upgrade error:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to initiate upgrade';
      toast.error(errorMessage);
      setUpgrading(null);
    }
  };

  const getPlanStatus = (planCode) => {
    if (planCode === currentPlan) return 'current';
    
    const currentPlanIndex = PLANS.findIndex(p => p.code === currentPlan);
    const targetPlanIndex = PLANS.findIndex(p => p.code === planCode);
    
    if (targetPlanIndex > currentPlanIndex) return 'upgrade';
    return 'downgrade';
  };

  const getFeatureCount = (planCode) => {
    const features = FEATURE_MATRIX[planCode];
    return Object.values(features).filter(Boolean).length;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="billing-loading">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal mx-auto mb-3" />
          <p className="text-gray-600">Loading plan information...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="billing-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/app/dashboard')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-midnight-blue">Plans & Billing</h1>
              <p className="text-sm text-gray-500">Compare plans and manage your subscription</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Cancellation Pending Notice */}
        {billingStatus?.cancel_at_period_end && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="cancellation-notice">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              <strong>Cancellation Scheduled</strong>
              <p className="mt-1">
                Your subscription will end on {billingStatus.current_period_end ? new Date(billingStatus.current_period_end).toLocaleDateString() : 'the end of your billing period'}. 
                You'll continue to have full access until then.
              </p>
            </AlertDescription>
          </Alert>
        )}

        {/* Current Plan Banner */}
        {currentPlan && (
          <div className="bg-gradient-to-r from-midnight-blue to-midnight-blue/90 text-white rounded-2xl p-6 mb-8" data-testid="current-plan-banner">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-300 mb-1">Your Current Plan</p>
                <h2 className="text-2xl font-bold">
                  {PLANS.find(p => p.code === currentPlan)?.name || currentPlan}
                </h2>
                <p className="text-sm text-gray-300 mt-1">
                  {entitlements?.max_properties} properties • {getFeatureCount(currentPlan)} features enabled
                </p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold">
                  £{PLANS.find(p => p.code === currentPlan)?.monthlyPrice || 0}
                  <span className="text-lg font-normal text-gray-300">/mo</span>
                </p>
                {billingStatus?.has_subscription && !billingStatus?.cancel_at_period_end && (
                  <button
                    onClick={() => setShowCancelModal(true)}
                    className="text-xs text-gray-400 hover:text-white mt-2 underline"
                    data-testid="cancel-subscription-link"
                  >
                    Cancel subscription
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Plan Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12" data-testid="plan-cards">
          {PLANS.map((plan) => {
            const status = getPlanStatus(plan.code);
            const isHighlighted = highlightPlan === plan.code;
            const PlanIcon = plan.icon;
            
            return (
              <Card 
                key={plan.code}
                className={`relative overflow-hidden transition-all duration-300 ${
                  isHighlighted ? 'ring-2 ring-electric-teal shadow-lg scale-[1.02]' : ''
                } ${status === 'current' ? 'border-2 border-electric-teal' : ''}`}
                data-testid={`plan-card-${plan.code}`}
              >
                {/* Badge */}
                {plan.badge && (
                  <div 
                    className="absolute top-0 right-0 px-3 py-1 text-xs font-semibold text-white rounded-bl-lg"
                    style={{ backgroundColor: plan.color }}
                  >
                    {plan.badge}
                  </div>
                )}
                
                {/* Current Plan Indicator */}
                {status === 'current' && (
                  <div className="absolute top-0 left-0 right-0 bg-electric-teal text-white text-center text-xs py-1 font-medium">
                    Current Plan
                  </div>
                )}
                
                <CardHeader className={status === 'current' ? 'pt-8' : ''}>
                  <div className="flex items-center gap-3 mb-2">
                    <div 
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${plan.color}15` }}
                    >
                      <PlanIcon className="w-5 h-5" style={{ color: plan.color }} />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{plan.name}</CardTitle>
                      <CardDescription className="text-xs">{plan.targetAudience}</CardDescription>
                    </div>
                  </div>
                  
                  <div className="mt-4">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-bold text-midnight-blue">£{plan.monthlyPrice}</span>
                      <span className="text-gray-500">/month</span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      + £{plan.onboardingFee} one-time setup
                    </p>
                  </div>
                </CardHeader>
                
                <CardContent>
                  <p className="text-sm text-gray-600 mb-4">{plan.description}</p>
                  
                  {/* Key Features */}
                  <div className="space-y-2 mb-6">
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500" />
                      <span><strong>{plan.maxProperties}</strong> properties</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500" />
                      <span><strong>{getFeatureCount(plan.code)}</strong> features</span>
                    </div>
                    {plan.code !== 'PLAN_1_SOLO' && (
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-500" />
                        <span>Advanced AI extraction</span>
                      </div>
                    )}
                    {plan.code === 'PLAN_3_PRO' && (
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="w-4 h-4 text-green-500" />
                        <span>Webhooks & API access</span>
                      </div>
                    )}
                  </div>
                  
                  {/* CTA Button */}
                  <Button
                    className={`w-full ${
                      status === 'current' 
                        ? 'bg-gray-100 text-gray-500 cursor-not-allowed' 
                        : status === 'upgrade'
                          ? 'bg-electric-teal hover:bg-teal-600 text-white'
                          : 'bg-gray-200 text-gray-600'
                    }`}
                    onClick={() => handleUpgrade(plan.code)}
                    disabled={status === 'current' || status === 'downgrade' || upgrading === plan.code}
                    data-testid={`upgrade-btn-${plan.code}`}
                  >
                    {upgrading === plan.code ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Processing...
                      </>
                    ) : status === 'current' ? (
                      'Current Plan'
                    ) : status === 'upgrade' ? (
                      <>
                        Upgrade to {plan.name}
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </>
                    ) : (
                      'Contact Support'
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Feature Comparison Matrix */}
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden" data-testid="feature-matrix">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-midnight-blue">Feature Comparison</h2>
            <p className="text-sm text-gray-500 mt-1">Compare all features across plans</p>
          </div>
          
          {/* Header Row */}
          <div className="grid grid-cols-4 gap-4 p-4 bg-gray-50 border-b border-gray-200 sticky top-[73px] z-10">
            <div className="font-medium text-gray-700">Feature</div>
            {PLANS.map(plan => (
              <div key={plan.code} className="text-center">
                <span 
                  className="font-semibold text-sm"
                  style={{ color: plan.color }}
                >
                  {plan.name}
                </span>
              </div>
            ))}
          </div>
          
          {/* Feature Categories */}
          {FEATURE_CATEGORIES.map((category) => {
            const CategoryIcon = category.icon;
            const isExpanded = expandedCategories[category.name];
            
            return (
              <div key={category.name} className="border-b border-gray-100 last:border-b-0">
                {/* Category Header */}
                <button
                  onClick={() => toggleCategory(category.name)}
                  className="w-full grid grid-cols-4 gap-4 p-4 hover:bg-gray-50 transition-colors"
                  data-testid={`category-${category.name}`}
                >
                  <div className="flex items-center gap-2">
                    <CategoryIcon className="w-4 h-4 text-gray-500" />
                    <span className="font-medium text-gray-900">{category.name}</span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                  {PLANS.map(plan => {
                    const enabledCount = category.features.filter(f => FEATURE_MATRIX[plan.code][f.key]).length;
                    return (
                      <div key={plan.code} className="text-center text-sm text-gray-500">
                        {enabledCount}/{category.features.length}
                      </div>
                    );
                  })}
                </button>
                
                {/* Features */}
                {isExpanded && (
                  <div className="bg-gray-50/50">
                    {category.features.map((feature, idx) => (
                      <div 
                        key={feature.key}
                        className={`grid grid-cols-4 gap-4 px-4 py-3 ${
                          idx < category.features.length - 1 ? 'border-b border-gray-100' : ''
                        }`}
                        data-testid={`feature-row-${feature.key}`}
                      >
                        <div className="pl-6">
                          <p className="text-sm text-gray-700">{feature.name}</p>
                          <p className="text-xs text-gray-500">{feature.description}</p>
                        </div>
                        {PLANS.map(plan => {
                          const isEnabled = FEATURE_MATRIX[plan.code][feature.key];
                          return (
                            <div key={plan.code} className="flex items-center justify-center">
                              {isEnabled ? (
                                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                                  <Check className="w-4 h-4 text-green-600" />
                                </div>
                              ) : (
                                <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center">
                                  <X className="w-4 h-4 text-gray-400" />
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* FAQ Section */}
        <div className="mt-12" data-testid="billing-faq">
          <h2 className="text-xl font-semibold text-midnight-blue mb-6">Frequently Asked Questions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">Can I upgrade at any time?</h3>
                <p className="text-sm text-gray-600">
                  Yes! You can upgrade your plan at any time. The new pricing will be prorated based on your billing cycle.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">What happens to my data if I downgrade?</h3>
                <p className="text-sm text-gray-600">
                  Your data is never deleted. If you exceed the property limit of a lower plan, you'll need to archive properties before downgrading.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">What is your refund policy?</h3>
                <p className="text-sm text-gray-600">
                  We offer a 14-day money-back guarantee on all plans. Contact support within 14 days for a full refund if you&apos;re not satisfied.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <h3 className="font-semibold text-gray-900 mb-2">How do I cancel my subscription?</h3>
                <p className="text-sm text-gray-600">
                  You can cancel anytime from your account settings or by contacting support. Your access continues until the end of your billing period.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Contact Support */}
        <div className="mt-12 text-center">
          <p className="text-gray-600 mb-4">
            Need help choosing the right plan? Have questions about enterprise pricing?
          </p>
          <Button 
            variant="outline"
            onClick={() => window.location.href = 'mailto:info@pleerityenterprise.co.uk'}
          >
            Contact Support
          </Button>
        </div>
      </main>

      {/* Cancel Subscription Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="cancel-modal">
          <div className="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Cancel Subscription</h3>
            </div>
            
            <p className="text-gray-600 mb-6">
              Are you sure you want to cancel your subscription? You have two options:
            </p>
            
            <div className="space-y-3 mb-6">
              <div className="p-4 border border-gray-200 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-1">Cancel at Period End</h4>
                <p className="text-sm text-gray-500">
                  Keep full access until {billingStatus?.current_period_end ? new Date(billingStatus.current_period_end).toLocaleDateString() : 'the end of your billing period'}, then your subscription ends.
                </p>
              </div>
              <div className="p-4 border border-red-200 rounded-lg bg-red-50">
                <h4 className="font-medium text-red-800 mb-1">Cancel Immediately</h4>
                <p className="text-sm text-red-600">
                  Lose access immediately. Your data will be preserved but features will be locked.
                </p>
              </div>
            </div>
            
            <div className="flex flex-col gap-2">
              <Button
                onClick={() => handleCancelSubscription(false)}
                variant="outline"
                className="w-full"
                disabled={cancelling}
                data-testid="cancel-at-period-end-btn"
              >
                {cancelling ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                Cancel at Period End
              </Button>
              <Button
                onClick={() => handleCancelSubscription(true)}
                variant="destructive"
                className="w-full bg-red-600 hover:bg-red-700"
                disabled={cancelling}
                data-testid="cancel-immediately-btn"
              >
                {cancelling ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                Cancel Immediately
              </Button>
              <Button
                onClick={() => setShowCancelModal(false)}
                variant="ghost"
                className="w-full"
                disabled={cancelling}
              >
                Keep My Subscription
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BillingPage;
