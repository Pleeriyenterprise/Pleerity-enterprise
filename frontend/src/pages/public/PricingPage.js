import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  CheckCircle2,
  X,
  ArrowRight,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  Building,
  Zap,
  Crown,
  Star,
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';

const PricingPage = () => {
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [activeProduct, setActiveProduct] = useState('cvp');

  // ClearForm Credit Packages
  const clearformCredits = [
    { id: 'credits_10', credits: 10, price: 5, pricePerCredit: 0.50 },
    { id: 'credits_25', credits: 25, price: 10, pricePerCredit: 0.40, popular: true, savings: '20%' },
    { id: 'credits_75', credits: 75, price: 25, pricePerCredit: 0.33, savings: '33%' },
  ];

  // ClearForm Subscription Plans
  const clearformPlans = [
    {
      name: 'Free',
      price: 0,
      credits: 3,
      creditsNote: 'one-time',
      features: ['3 credits (one-time)', 'Watermarked documents', 'All document types'],
      limitations: ['Watermarked output'],
    },
    {
      name: 'Personal',
      price: 9.99,
      credits: 20,
      creditsNote: 'per month',
      popular: true,
      features: ['20 credits per month', 'No watermark', 'All document types', 'Priority support'],
      limitations: ['Unused credits don\'t roll over'],
    },
    {
      name: 'Power User',
      price: 24.99,
      credits: 75,
      creditsNote: 'per month',
      features: ['75 credits per month', 'No watermark', 'Priority generation', 'Early access to new document types', 'Dedicated support'],
      limitations: ['Unused credits don\'t roll over'],
      icon: Crown,
    },
  ];

  // CVP Plans (existing)
  const cvpPlans = [
    {
      name: 'Solo Landlord',
      code: 'PLAN_1_SOLO',
      description: 'Perfect for landlords with 1-2 properties',
      monthlyPrice: 19,
      yearlyPrice: 190,
      onboarding: 49,
      properties: 2,
      features: {
        'Core Features': [
          { name: 'Compliance Dashboard', included: true },
          { name: 'Compliance Score', included: true },
          { name: 'Expiry Calendar', included: true },
          { name: 'Email Notifications', included: true },
          { name: 'Document Upload', included: true },
          { name: 'Score Trending', included: true },
        ],
        'AI Features': [
          { name: 'Basic AI Extraction', included: true },
          { name: 'Advanced AI Extraction', included: false },
          { name: 'AI Review Interface', included: false },
        ],
        'Documents': [
          { name: 'ZIP Bulk Upload', included: false },
        ],
        'Reporting': [
          { name: 'PDF Reports', included: false },
          { name: 'CSV Export', included: false },
          { name: 'Scheduled Reports', included: false },
        ],
        'Communication': [
          { name: 'SMS Reminders', included: false },
        ],
        'Tenant Portal': [
          { name: 'Tenant View Access', included: false },
        ],
        'Integrations': [
          { name: 'Webhooks', included: false },
        ],
        'Advanced': [
          { name: 'White-Label Reports', included: false },
          { name: 'Audit Log Export', included: false },
        ],
      },
    },
    {
      name: 'Portfolio',
      code: 'PLAN_2_PORTFOLIO',
      description: 'For growing landlords and small agents',
      monthlyPrice: 39,
      yearlyPrice: 390,
      onboarding: 79,
      properties: 10,
      popular: true,
      features: {
        'Core Features': [
          { name: 'Compliance Dashboard', included: true },
          { name: 'Compliance Score', included: true },
          { name: 'Expiry Calendar', included: true },
          { name: 'Email Notifications', included: true },
          { name: 'Document Upload', included: true },
          { name: 'Score Trending', included: true },
        ],
        'AI Features': [
          { name: 'Basic AI Extraction', included: true },
          { name: 'Advanced AI Extraction', included: true },
          { name: 'AI Review Interface', included: true },
        ],
        'Documents': [
          { name: 'ZIP Bulk Upload', included: true },
        ],
        'Reporting': [
          { name: 'PDF Reports', included: true },
          { name: 'CSV Export', included: true },
          { name: 'Scheduled Reports', included: true },
        ],
        'Communication': [
          { name: 'SMS Reminders', included: true },
        ],
        'Tenant Portal': [
          { name: 'Tenant View Access', included: true },
        ],
        'Integrations': [
          { name: 'Webhooks', included: false },
        ],
        'Advanced': [
          { name: 'White-Label Reports', included: false },
          { name: 'Audit Log Export', included: false },
        ],
      },
    },
    {
      name: 'Professional',
      code: 'PLAN_3_PRO',
      description: 'For letting agents and serious operators',
      monthlyPrice: 79,
      yearlyPrice: 790,
      onboarding: 149,
      properties: 25,
      features: {
        'Core Features': [
          { name: 'Compliance Dashboard', included: true },
          { name: 'Compliance Score', included: true },
          { name: 'Expiry Calendar', included: true },
          { name: 'Email Notifications', included: true },
          { name: 'Document Upload', included: true },
          { name: 'Score Trending', included: true },
        ],
        'AI Features': [
          { name: 'Basic AI Extraction', included: true },
          { name: 'Advanced AI Extraction', included: true },
          { name: 'AI Review Interface', included: true },
        ],
        'Documents': [
          { name: 'ZIP Bulk Upload', included: true },
        ],
        'Reporting': [
          { name: 'PDF Reports', included: true },
          { name: 'CSV Export', included: true },
          { name: 'Scheduled Reports', included: true },
        ],
        'Communication': [
          { name: 'SMS Reminders', included: true },
        ],
        'Tenant Portal': [
          { name: 'Tenant View Access', included: true },
        ],
        'Integrations': [
          { name: 'Webhooks', included: true },
        ],
        'Advanced': [
          { name: 'White-Label Reports', included: true },
          { name: 'Audit Log Export', included: true },
        ],
      },
    },
  ];

  const faqs = [
    {
      question: 'Can I change my plan later?',
      answer: 'Yes, you can upgrade or downgrade your plan at any time. Upgrades take effect immediately, and downgrades apply at the end of your current billing period.',
    },
    {
      question: 'What happens if I exceed my property limit?',
      answer: 'You\'ll need to upgrade to a higher plan to add more properties. We\'ll notify you when you\'re approaching your limit so you can plan ahead.',
    },
    {
      question: 'How do I get started?',
      answer: 'Simply choose your plan and complete the signup process. You can start using the platform immediately after setup. Our team will guide you through the onboarding process.',
    },
    {
      question: 'What is the onboarding fee for?',
      answer: 'The one-time onboarding fee covers account setup, data migration assistance, and a personalised walkthrough of the platform to ensure you get the most value.',
    },
    {
      question: 'Can I cancel anytime?',
      answer: 'Yes, you can cancel your subscription at any time. Your access will continue until the end of your current billing period.',
    },
    {
      question: 'Do you offer discounts for annual billing?',
      answer: 'Yes! When you choose annual billing, you get 2 months free compared to monthly billing.',
    },
  ];

  const getPrice = (plan) => {
    return billingCycle === 'yearly' ? plan.yearlyPrice : plan.monthlyPrice;
  };

  const getSavings = (plan) => {
    return (plan.monthlyPrice * 12) - plan.yearlyPrice;
  };

  return (
    <PublicLayout>
      <SEOHead
        title="Pricing - Pleerity Products"
        description="Transparent pricing for all Pleerity products. Compliance Vault Pro for landlords and ClearForm for document generation."
        canonicalUrl="/pricing"
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Simple, Transparent Pricing
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Choose the product and plan that fits your needs.
            </p>

            {/* Product Tabs */}
            <Tabs value={activeProduct} onValueChange={setActiveProduct} className="w-full max-w-md mx-auto">
              <TabsList className="grid w-full grid-cols-2 h-12">
                <TabsTrigger value="cvp" className="flex items-center gap-2 text-sm" data-testid="pricing-tab-cvp">
                  <Building className="w-4 h-4" />
                  Compliance Vault Pro
                </TabsTrigger>
                <TabsTrigger value="clearform" className="flex items-center gap-2 text-sm" data-testid="pricing-tab-clearform">
                  <FileText className="w-4 h-4" />
                  ClearForm
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </section>

      {/* CVP Pricing */}
      {activeProduct === 'cvp' && (
        <>
          {/* Billing Toggle for CVP */}
          <section className="py-4 bg-white">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
              <div className="inline-flex items-center p-1 bg-gray-100 rounded-lg">
                <button
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    billingCycle === 'monthly'
                      ? 'bg-white text-midnight-blue shadow'
                      : 'text-gray-600 hover:text-midnight-blue'
                  }`}
                  onClick={() => setBillingCycle('monthly')}
                >
                  Monthly
                </button>
                <button
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    billingCycle === 'yearly'
                      ? 'bg-white text-midnight-blue shadow'
                      : 'text-gray-600 hover:text-midnight-blue'
                  }`}
                  onClick={() => setBillingCycle('yearly')}
                >
                  Yearly
                  <span className="ml-1 text-electric-teal text-xs">Save 2 months</span>
                </button>
              </div>
            </div>
          </section>

          {/* CVP Pricing Cards */}
          <section className="py-12 bg-white">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="grid md:grid-cols-3 gap-8">
                {cvpPlans.map((plan) => (
                  <Card
                    key={plan.code}
                    className={`relative ${
                      plan.popular
                        ? 'border-2 border-electric-teal shadow-xl scale-105'
                        : 'border-gray-200'
                    }`}
                    data-testid={`pricing-card-${plan.code.toLowerCase()}`}
                  >
                    {plan.popular && (
                      <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-electric-teal text-white text-sm font-medium rounded-full">
                        Most Popular
                      </div>
                    )}
                    <CardHeader className="text-center pb-4">
                      <CardTitle className="text-2xl font-bold text-midnight-blue">{plan.name}</CardTitle>
                      <p className="text-gray-500 text-sm">{plan.description}</p>
                    </CardHeader>
                    <CardContent>
                      <div className="text-center mb-6">
                        <div className="flex items-baseline justify-center">
                          <span className="text-5xl font-bold text-midnight-blue">£{getPrice(plan)}</span>
                          <span className="text-gray-500 ml-2">
                            /{billingCycle === 'yearly' ? 'year' : 'month'}
                          </span>
                        </div>
                        {billingCycle === 'yearly' && (
                          <p className="text-sm text-electric-teal mt-1">
                            Save £{getSavings(plan)} per year
                          </p>
                        )}
                        <p className="text-sm text-gray-500 mt-2">
                          + £{plan.onboarding} one-time setup
                        </p>
                        <p className="text-sm font-medium text-midnight-blue mt-3">
                          Up to {plan.properties} properties
                        </p>
                      </div>

                      <Button
                        className={`w-full mb-6 ${
                          plan.popular
                            ? 'bg-electric-teal hover:bg-electric-teal/90'
                            : ''
                        }`}
                        variant={plan.popular ? 'default' : 'outline'}
                        asChild
                      >
                        <Link to="/intake/start">
                          Get Started
                          <ArrowRight className="w-4 h-4 ml-2" />
                        </Link>
                      </Button>

                      {/* Feature Categories */}
                      <div className="space-y-4">
                        {Object.entries(plan.features).map(([category, features]) => (
                          <div key={category}>
                            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                              {category}
                            </h4>
                            <ul className="space-y-2">
                              {features.map((feature) => (
                                <li key={feature.name} className="flex items-center">
                                  {feature.included ? (
                                    <CheckCircle2 className="w-4 h-4 text-electric-teal shrink-0 mr-2" />
                                  ) : (
                                    <X className="w-4 h-4 text-gray-300 shrink-0 mr-2" />
                                  )}
                                  <span className={`text-sm ${feature.included ? 'text-gray-700' : 'text-gray-400'}`}>
                                    {feature.name}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </section>
        </>
      )}

      {/* ClearForm Pricing */}
      {activeProduct === 'clearform' && (
        <section className="py-12 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {/* Credit Top-ups */}
            <div className="mb-16">
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-midnight-blue mb-2">Credit Top-ups</h2>
                <p className="text-gray-600">Pay as you go. Credits never expire.</p>
              </div>

              <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
                {clearformCredits.map((pkg) => (
                  <Card 
                    key={pkg.id}
                    className={`relative ${pkg.popular ? 'border-2 border-emerald-500 shadow-lg scale-105' : ''}`}
                    data-testid={`clearform-credits-${pkg.id}`}
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
                        <span className="text-3xl font-bold text-midnight-blue">£{pkg.price}</span>
                        {pkg.savings && (
                          <Badge variant="outline" className="ml-2 text-emerald-600 border-emerald-600">
                            Save {pkg.savings}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 mb-4">
                        £{pkg.pricePerCredit.toFixed(2)} per credit
                      </p>
                      <Button 
                        className="w-full"
                        variant={pkg.popular ? 'default' : 'outline'}
                        asChild
                      >
                        <Link to="/clearform/credits">
                          Buy Now
                          <ArrowRight className="w-4 h-4 ml-2" />
                        </Link>
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Subscription Plans */}
            <div>
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-midnight-blue mb-2">Subscription Plans</h2>
                <p className="text-gray-600">Get monthly credits at a discount.</p>
              </div>

              <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                {clearformPlans.map((plan) => {
                  const Icon = plan.icon || Star;
                  return (
                    <Card 
                      key={plan.name}
                      className={`relative ${plan.popular ? 'border-2 border-emerald-500 shadow-lg scale-105' : ''}`}
                      data-testid={`clearform-plan-${plan.name.toLowerCase().replace(' ', '-')}`}
                    >
                      {plan.popular && (
                        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                          <Badge className="bg-emerald-500 text-white">Popular</Badge>
                        </div>
                      )}
                      <CardHeader className="text-center pb-2">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3 ${
                          plan.icon ? 'bg-amber-100' : 'bg-gray-100'
                        }`}>
                          <Icon className={`w-6 h-6 ${plan.icon ? 'text-amber-600' : 'text-gray-600'}`} />
                        </div>
                        <CardTitle>{plan.name}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-center mb-4">
                          <div className="flex items-baseline justify-center">
                            <span className="text-3xl font-bold text-midnight-blue">
                              {plan.price === 0 ? 'Free' : `£${plan.price}`}
                            </span>
                            {plan.price > 0 && (
                              <span className="text-gray-500 ml-1">/month</span>
                            )}
                          </div>
                          <p className="text-sm text-emerald-600 font-medium mt-1">
                            {plan.credits} credits {plan.creditsNote}
                          </p>
                        </div>

                        <ul className="space-y-2 mb-6">
                          {plan.features.map((feature, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                              <span className="text-gray-600">{feature}</span>
                            </li>
                          ))}
                          {plan.limitations?.map((limitation, i) => (
                            <li key={`limit-${i}`} className="text-sm text-gray-400 pl-6">
                              {limitation}
                            </li>
                          ))}
                        </ul>

                        <Button 
                          className="w-full"
                          variant={plan.popular ? 'default' : 'outline'}
                          asChild
                        >
                          <Link to="/clearform/register">
                            {plan.price === 0 ? 'Get Started' : 'Subscribe'}
                            <ArrowRight className="w-4 h-4 ml-2" />
                          </Link>
                        </Button>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Important Notes */}
              <div className="mt-8 max-w-2xl mx-auto">
                <Card className="bg-gray-50 border-gray-200">
                  <CardContent className="py-4">
                    <p className="text-sm text-gray-600 text-center">
                      <strong>Note:</strong> Subscription credits reset monthly. Top-up credits are separate and never expire. 
                      Credits are usable across all active document types.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* FAQ Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-midnight-blue mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-gray-600">
              Have questions? We&apos;ve got answers.
            </p>
          </div>

          <Accordion type="single" collapsible className="space-y-4">
            {faqs.map((faq, index) => (
              <AccordionItem
                key={index}
                value={`item-${index}`}
                className="bg-white rounded-lg border border-gray-200 px-6"
              >
                <AccordionTrigger className="text-left font-medium text-midnight-blue hover:no-underline">
                  {faq.question}
                </AccordionTrigger>
                <AccordionContent className="text-gray-600">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Try Compliance Vault Pro free for 14 days. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/intake/start">Get Started Today</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white hover:text-midnight-blue"
              asChild
            >
              <Link to="/booking">Talk to Sales</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PricingPage;
