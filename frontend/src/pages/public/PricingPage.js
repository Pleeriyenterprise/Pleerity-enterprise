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
          { name: 'API Access', included: false },
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
          { name: 'API Access', included: false },
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
          { name: 'API Access', included: true },
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
      question: 'Is there a free trial?',
      answer: 'Yes, all plans come with a 14-day free trial. No credit card required to start. You can explore all features of your chosen plan before committing.',
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
        title="Pricing - Compliance Vault Pro Plans"
        description="Transparent pricing for Compliance Vault Pro. Choose from Solo (£19/mo), Portfolio (£39/mo), or Professional (£79/mo) plans."
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
              Choose the plan that fits your portfolio. All plans include a 14-day free trial.
            </p>

            {/* Billing Toggle */}
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
        </div>
      </section>

      {/* Pricing Cards */}
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
                      Start Free Trial
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

      {/* FAQ Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-midnight-blue mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-gray-600">
              Have questions? We've got answers.
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
              <Link to="/intake/start">Start Free Trial</Link>
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
