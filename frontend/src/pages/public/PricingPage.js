import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import {
  CheckCircle2,
  X,
  ArrowRight,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Building,
  Send,
  Loader2,
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';
import { capturePricing } from '../../api/leadsApi';
import { toast } from '@/utils/portalNotifications';

function getUtmParams() {
  if (typeof window === 'undefined') return {};
  const p = new URLSearchParams(window.location.search);
  return {
    utm_source: p.get('utm_source') || null,
    utm_medium: p.get('utm_medium') || null,
    utm_campaign: p.get('utm_campaign') || null,
  };
}

const PricingPage = () => {
  const [billingCycle, setBillingCycle] = useState('monthly');
  const [quoteForm, setQuoteForm] = useState({ name: '', email: '', phone: '', message: '', marketing_consent: false });
  const [quoteSubmitting, setQuoteSubmitting] = useState(false);
  const [quoteSubmitted, setQuoteSubmitted] = useState(false);

  // CVP Plans — Best for + grouped features (Core, Reminders, Reports, AI, Support)
  const cvpPlans = [
    {
      name: 'Solo Landlord',
      code: 'PLAN_1_SOLO',
      bestFor: '1–2 properties',
      monthlyPrice: 19,
      yearlyPrice: 190,
      onboarding: 49,
      properties: 2,
      ctaLabel: 'Start Solo Plan',
      features: {
        'Core Tracking': [
          { name: 'Portfolio dashboard', included: true },
          { name: 'Expiry tracking', included: true },
          { name: 'Compliance score', included: true },
          { name: 'Document upload', included: true },
          { name: 'ZIP bulk upload', included: false },
        ],
        'Reminders': [
          { name: 'Email reminders', included: true },
          { name: 'Basic alerts', included: true },
          { name: 'SMS reminders', included: false },
        ],
        'Reports & Exports': [
          { name: 'Viewable report', included: true },
          { name: 'Basic export', included: true },
          { name: 'PDF reports', included: false },
          { name: 'CSV export', included: false },
          { name: 'Scheduled reports', included: false },
          { name: 'Audit log export', included: false },
        ],
        'AI Extraction': [
          { name: 'Basic AI extraction', included: true },
          { name: 'Advanced AI extraction', included: false },
        ],
        'Support': [
          { name: 'Email support', included: true },
          { name: 'Priority support', included: false },
        ],
        'Extras': [
          { name: 'Tenant portal access', included: false },
          { name: 'White-label reports', included: false },
        ],
      },
    },
    {
      name: 'Portfolio',
      code: 'PLAN_2_PORTFOLIO',
      bestFor: '3–10 properties',
      monthlyPrice: 39,
      yearlyPrice: 390,
      onboarding: 79,
      properties: 10,
      popular: true,
      ctaLabel: 'Start Portfolio Plan',
      features: {
        'Core Tracking': [
          { name: 'Portfolio dashboard', included: true },
          { name: 'Expiry tracking', included: true },
          { name: 'Compliance score', included: true },
          { name: 'Document upload', included: true },
          { name: 'ZIP bulk upload', included: true },
        ],
        'Reminders': [
          { name: 'Email reminders', included: true },
          { name: 'Basic alerts', included: true },
          { name: 'SMS reminders', included: true },
        ],
        'Reports & Exports': [
          { name: 'Viewable report', included: true },
          { name: 'Basic export', included: true },
          { name: 'PDF reports', included: true },
          { name: 'CSV export', included: false },
          { name: 'Scheduled reports', included: true },
          { name: 'Audit log export', included: true },
        ],
        'AI Extraction': [
          { name: 'Basic AI extraction', included: true },
          { name: 'Advanced AI extraction', included: true },
        ],
        'Support': [
          { name: 'Email support', included: true },
          { name: 'Priority support', included: false },
        ],
        'Extras': [
          { name: 'Tenant portal access', included: false },
          { name: 'White-label reports', included: false },
        ],
      },
    },
    {
      name: 'Professional',
      code: 'PLAN_3_PRO',
      bestFor: 'Up to 25 properties',
      monthlyPrice: 79,
      yearlyPrice: 790,
      onboarding: 149,
      properties: 25,
      ctaLabel: 'Start Professional Plan',
      features: {
        'Core Tracking': [
          { name: 'Portfolio dashboard', included: true },
          { name: 'Expiry tracking', included: true },
          { name: 'Compliance score', included: true },
          { name: 'Document upload', included: true },
          { name: 'ZIP bulk upload', included: true },
        ],
        'Reminders': [
          { name: 'Email reminders', included: true },
          { name: 'Basic alerts', included: true },
          { name: 'SMS reminders', included: true },
        ],
        'Reports & Exports': [
          { name: 'Viewable report', included: true },
          { name: 'Basic export', included: true },
          { name: 'PDF reports', included: true },
          { name: 'CSV export', included: true },
          { name: 'Scheduled reports', included: true },
          { name: 'Audit log export', included: true },
        ],
        'AI Extraction': [
          { name: 'Basic AI extraction', included: true },
          { name: 'Advanced AI extraction', included: true },
        ],
        'Support': [
          { name: 'Email support', included: true },
          { name: 'Priority support', included: true },
        ],
        'Extras': [
          { name: 'Tenant portal access', included: true },
          { name: 'White-label reports', included: true },
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
        description="Transparent pricing for Compliance Vault Pro — structured compliance tracking for landlords."
        canonicalUrl="/pricing"
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Pricing Built Around Your Portfolio
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Start small. Upgrade as your portfolio grows.
            </p>

          </div>
        </div>
      </section>

      {/* CVP Pricing */}
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
                  <span className="ml-1.5 text-electric-teal text-xs font-medium">(save 17%)</span>
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
                      <p className="text-gray-500 text-sm mt-1">Best for: {plan.bestFor}</p>
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
                          {plan.ctaLabel}
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
              <p className="text-center text-sm text-gray-500 mt-8 max-w-2xl mx-auto">
                Compliance Vault Pro provides structured tracking and informational indicators. It does not provide legal advice or regulatory certification.
              </p>
            </div>
          </section>
      </>

      {/* Why Choose Compliance Vault Pro */}
      <section className="py-16 bg-white">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-bold text-midnight-blue mb-8 text-center">
              Why Choose Compliance Vault Pro?
            </h2>
            <ul className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
              <li className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
                <span className="text-gray-700">Structured tracking and expiry visibility—no spreadsheets.</span>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
                <span className="text-gray-700">Reminders and reports to support your compliance oversight.</span>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
                <span className="text-gray-700">Scale from one property to a portfolio on one plan.</span>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
                <span className="text-gray-700">UK-focused; built for landlords and property professionals.</span>
              </li>
            </ul>
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
          <p className="text-lg text-gray-300 mb-2">
            Get started with Compliance Vault Pro. Choose a plan below and sign up—no long-term contract.
          </p>
          <p className="text-base text-gray-400 mb-8">
            No long-term contract. Cancel anytime.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
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
          {/* Request a quote form */}
          <Card className="max-w-md mx-auto bg-white/10 border-white/20">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-white mb-2">Get a custom quote</h3>
              <p className="text-sm text-gray-300 mb-4">Tell us your needs and we&apos;ll get back with tailored pricing.</p>
              {quoteSubmitted ? (
                <div className="text-electric-teal font-medium">Thank you. We&apos;ll be in touch shortly.</div>
              ) : (
                <form
                  className="space-y-3 text-left"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!quoteForm.email?.trim()) {
                      toast.error('Please enter your email.');
                      return;
                    }
                    setQuoteSubmitting(true);
                    try {
                      await capturePricing({
                        name: quoteForm.name.trim() || null,
                        email: quoteForm.email.trim(),
                        phone: quoteForm.phone.trim() || null,
                        message: quoteForm.message.trim() || null,
                        marketing_consent: quoteForm.marketing_consent,
                        ...getUtmParams(),
                      });
                      setQuoteSubmitted(true);
                      toast.success('Request sent. We\'ll be in touch shortly.');
                    } catch (err) {
                      toast.error(err.message || 'Failed to send request.');
                    } finally {
                      setQuoteSubmitting(false);
                    }
                  }}
                >
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="quote-name" className="text-gray-200">Name</Label>
                      <Input
                        id="quote-name"
                        value={quoteForm.name}
                        onChange={(e) => setQuoteForm((p) => ({ ...p, name: e.target.value }))}
                        className="bg-white/10 border-white/30 text-white placeholder:text-gray-400"
                        placeholder="Your name"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="quote-email" className="text-gray-200">Email *</Label>
                      <Input
                        id="quote-email"
                        type="email"
                        required
                        value={quoteForm.email}
                        onChange={(e) => setQuoteForm((p) => ({ ...p, email: e.target.value }))}
                        className="bg-white/10 border-white/30 text-white placeholder:text-gray-400"
                        placeholder="you@example.com"
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="quote-phone" className="text-gray-200">Phone</Label>
                    <Input
                      id="quote-phone"
                      type="tel"
                      value={quoteForm.phone}
                      onChange={(e) => setQuoteForm((p) => ({ ...p, phone: e.target.value }))}
                      className="bg-white/10 border-white/30 text-white placeholder:text-gray-400"
                      placeholder="Optional"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="quote-message" className="text-gray-200">Message</Label>
                    <Textarea
                      id="quote-message"
                      rows={2}
                      value={quoteForm.message}
                      onChange={(e) => setQuoteForm((p) => ({ ...p, message: e.target.value }))}
                      className="bg-white/10 border-white/30 text-white placeholder:text-gray-400"
                      placeholder="Portfolio size, requirements..."
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="quote-marketing"
                      checked={quoteForm.marketing_consent}
                      onCheckedChange={(c) => setQuoteForm((p) => ({ ...p, marketing_consent: !!c }))}
                      className="border-white/50 data-[state=checked]:bg-electric-teal"
                    />
                    <Label htmlFor="quote-marketing" className="text-sm text-gray-300">Send me occasional updates and offers</Label>
                  </div>
                  <Button
                    type="submit"
                    disabled={quoteSubmitting}
                    className="w-full bg-electric-teal hover:bg-electric-teal/90 text-white"
                  >
                    {quoteSubmitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : <>Send request <Send className="w-4 h-4 ml-2 inline" /></>}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PricingPage;
