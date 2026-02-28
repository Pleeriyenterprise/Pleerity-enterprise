import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import ProductScreenshot from '../../components/public/ProductScreenshot';
import { SEOHead, organizationSchema } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import {
  Shield,
  FileCheck,
  Bell,
  BarChart3,
  Building2,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Users,
  Home,
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';

const HomePage = () => {
  const [heroImageError, setHeroImageError] = useState(false);
  const [featureImageError, setFeatureImageError] = useState(false);
  const trustBullets = [
    'Expiry reminders',
    'Evidence vault',
    'Portfolio view',
    'PDF reports (plan-based)',
    'Not legal advice',
  ];

  const pillars = [
    {
      icon: FileCheck,
      title: 'Track evidence and expiries',
      description: 'Securely store Gas Safety (CP12), EICR, EPC, HMO licences and supporting documents. Track issue and expiry dates in one organised portal.',
    },
    {
      icon: Shield,
      title: 'Compliance score (risk indicator)',
      description: 'See a clear risk indicator per property and across your portfolio based on evidence and expiry status. Transparency over what’s valid, expiring, or missing.',
    },
    {
      icon: Bell,
      title: 'Reminders',
      description: 'Receive email and SMS reminders before deadlines (plan-based) so you can renew in good time.',
    },
    {
      icon: BarChart3,
      title: 'Reports and exports',
      description: 'Generate structured PDF and CSV reports (plan-based) for internal reviews or professional consultation.',
    },
  ];

  const segments = [
    {
      icon: Home,
      title: 'Solo landlords',
      description: 'Keep your compliance documentation organised and monitored from day one.',
    },
    {
      icon: Building2,
      title: 'Portfolio landlords',
      description: 'Track multiple properties with structured oversight and centralised reporting.',
    },
    {
      icon: Users,
      title: 'HMO / managed properties',
      description: 'Monitor licensing, renewals, and property-level documentation clearly.',
    },
  ];

  const steps = [
    { title: 'Add your properties', body: 'Enter your property details to create your portfolio dashboard.' },
    { title: 'Upload evidence', body: 'Store documents securely. You can upload at intake or later.' },
    { title: 'Confirm key dates', body: 'Confirm expiry and issue dates when needed so tracking is accurate.' },
    { title: 'Track status and reminders', body: 'View compliance status per property and receive reminders before deadlines.' },
    { title: 'Generate reports', body: 'Produce structured compliance reports (plan-based) when you need them.' },
  ];

  const faqs = [
    {
      q: 'Is this legal advice?',
      a: 'No. Compliance Vault Pro is a tracking and organisation tool. It helps you see expiry dates and evidence in one place. It does not provide legal advice or regulatory determination. For legal or regulatory questions, please consult a qualified professional.',
    },
    {
      q: 'What happens if I downgrade?',
      a: 'You can upgrade or downgrade your plan at any time. Your data remains secure. Features that are part of higher tiers (e.g. PDF reports, SMS reminders) may no longer be available on a lower tier, but your stored documents and property data are retained.',
    },
    {
      q: 'Does it support HMO?',
      a: 'Yes. You can track HMO licensing and property-level documentation, including renewal dates and supporting evidence, so HMO operators can monitor compliance in one place.',
    },
    {
      q: 'Do you send expiry reminders?',
      a: 'Yes. We send email reminders before certificates expire (plan-dependent). Some plans also include SMS reminders. You can manage notification preferences in your account.',
    },
    {
      q: 'Can I export reports?',
      a: 'Yes. Depending on your plan, you can generate PDF and CSV reports for your portfolio. These are structured for internal use or to share with advisers.',
    },
    {
      q: 'Is my data secure?',
      a: 'We use secure storage and encryption for your documents and data. Access is controlled and we do not use your data for purposes other than providing the service. See our Privacy Policy for details.',
    },
  ];

  return (
    <PublicLayout>
      {/* A) SEO meta */}
      <SEOHead
        title="UK Landlord Compliance Software | Track Gas Safety, EICR & EPC Expiry"
        description="Compliance Vault Pro helps UK landlords track certificate expiry dates, monitor property compliance visibility, and generate structured reports across their portfolio. HMO compliance tracking UK. Gas safety certificate expiry tracking. EICR expiry reminders."
        canonicalUrl="/"
        schema={organizationSchema}
      />

      {/* B) HERO */}
      <section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-midnight-blue leading-tight mb-6">
                Are You Fully Compliant as a UK Landlord?
              </h1>
              <p className="text-lg text-gray-600 mb-8 max-w-xl">
                Structured compliance monitoring and renewal tracking for UK portfolios.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Button
                  size="lg"
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
                  asChild
                  data-testid="hero-cta-primary"
                >
                  <Link to="/risk-check">
                    Check Your Compliance Risk
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Link>
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="border-electric-teal text-electric-teal hover:bg-electric-teal/5"
                  asChild
                  data-testid="hero-cta-secondary"
                >
                  <Link to="/compliance-vault-pro">View Platform Overview</Link>
                </Button>
              </div>
              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-600">
                {trustBullets.map((point) => (
                  <span key={point} className="flex items-center">
                    <CheckCircle2 className="w-4 h-4 text-electric-teal mr-2 shrink-0" />
                    {point}
                  </span>
                ))}
              </div>
            </div>
            {/* Hero: real dashboard screenshot (cropped); headline remains dominant */}
            <div className="relative w-full lg:block">
              <h2 className="sr-only">UK landlord compliance tracking—risk report in 60 seconds</h2>
              <ProductScreenshot className="max-h-[380px] lg:max-h-[420px]">
                {heroImageError ? (
                  <div className="w-full min-h-[280px] flex items-center justify-center bg-gray-100 text-gray-500 text-sm rounded-lg">
                    Dashboard preview
                  </div>
                ) : (
                  <img
                    src="/images/marketing/hero-command-centre.svg"
                    alt="Compliance dashboard example showing score and quick actions"
                    width={1200}
                    height={850}
                    className="w-full h-auto object-contain object-top"
                    fetchPriority="high"
                    onError={() => setHeroImageError(true)}
                  />
                )}
              </ProductScreenshot>
              <p className="text-xs text-gray-500 text-center mt-4 px-2">
                Illustrative portfolio example. Live score generated after structured assessment.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Dashboard preview — portfolio in one view */}
      <section className="py-16 lg:py-20 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-4 text-center">
            See Your Entire Portfolio in One View
          </h2>
          <p className="text-center text-gray-600 mb-10 max-w-2xl mx-auto">
            Instantly see expiry risk, expiring documents, and compliance visibility across every property you manage.
          </p>
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <ul className="space-y-3 text-gray-700">
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Portfolio compliance score</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Property-level breakdown</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Expiring soon indicator</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Overdue alert example</li>
            </ul>
            <div className="relative w-full lg:max-w-[60%]">
              <ProductScreenshot>
                {featureImageError ? (
                  <div className="w-full min-h-[200px] flex items-center justify-center bg-gray-100 text-gray-500 text-sm rounded-lg">
                    Upcoming expiries preview
                  </div>
                ) : (
                  <img
                    src="/images/marketing/feature-expiry-list.svg"
                    alt="Upcoming expiries list from Compliance Calendar"
                    width={1200}
                    height={800}
                    className="w-full h-auto"
                    loading="lazy"
                    onError={() => setFeatureImageError(true)}
                  />
                )}
              </ProductScreenshot>
              <p className="text-xs text-gray-500 text-center mt-2">Expiry alerts generated from confirmed certificate dates.</p>
              <div className="mt-4 flex justify-center">
                <Button className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
                  <Link to="/risk-check">Generate Report</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* C) THE PROBLEM */}
      <section className="py-16 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-6 text-center">
            Compliance Is Easy to Forget — Until It&apos;s Too Late
          </h2>
          <div className="max-w-3xl mx-auto space-y-4 text-gray-600 text-center mb-8">
            <p>Certificates buried in inboxes. Expiry dates lost in spreadsheets. No clear overview across properties.</p>
            <p>When documentation is scattered, visibility disappears — and deadlines get missed.</p>
            <p className="text-midnight-blue font-medium">Compliance Vault Pro gives you structured oversight so nothing critical slips through.</p>
          </div>
          <div className="flex justify-center">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* D) FOUR PILLARS */}
      <section className="py-16 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-4 text-center">
            All Your Compliance Tracking in One Structured Dashboard
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
            Track evidence, see risk indicators, get reminders, and generate reports. No legal claims — just structured tracking.
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {pillars.map((item) => (
              <Card key={item.title} className="border-0 shadow-lg hover:shadow-xl transition-shadow h-full">
                <CardContent className="pt-6">
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-xl flex items-center justify-center mb-4">
                    <item.icon className="w-6 h-6 text-electric-teal" />
                  </div>
                  <h3 className="text-lg font-semibold text-midnight-blue mb-2">{item.title}</h3>
                  <p className="text-gray-600 text-sm">{item.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* E) SEGMENTATION */}
      <section className="py-16 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-4 text-center">
            Built for Modern UK Landlords
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
            Works for solo landlords, portfolio landlords, and HMO operators. Also suitable for managing agents overseeing landlord portfolios.
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {segments.map((seg) => (
              <Card key={seg.title} className="border border-gray-200 shadow-sm h-full">
                <CardContent className="pt-6">
                  <div className="w-12 h-12 bg-midnight-blue/10 rounded-xl flex items-center justify-center mb-4">
                    <seg.icon className="w-6 h-6 text-midnight-blue" />
                  </div>
                  <h3 className="text-lg font-semibold text-midnight-blue mb-2">{seg.title}</h3>
                  <p className="text-gray-600 text-sm">{seg.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* F) HOW IT WORKS */}
      <section className="py-16 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-4 text-center">
            Get Set Up in Minutes, Not Hours
          </h2>
          <div className="max-w-3xl mx-auto space-y-6 mt-12">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="w-10 h-10 rounded-full bg-electric-teal text-white flex items-center justify-center font-semibold shrink-0">
                  {i + 1}
                </div>
                <div>
                  <h3 className="font-semibold text-midnight-blue">{step.title}</h3>
                  <p className="text-gray-600 text-sm mt-1">{step.body}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="text-center mt-12">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* G) COMPLIANCE SCORE TRANSPARENCY */}
      <section className="py-16 lg:py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-6 text-center">
            How the Compliance Score Works
          </h2>
          <p className="text-gray-600 mb-4">
            Each property gets a structured tracking score based on confirmed evidence and recorded expiry dates. 
            Your dashboard also shows a portfolio-level summary for overall visibility.
          </p>
          <p className="text-gray-600 mb-4">
            For example: valid certificates and no overdue items support a stronger score; expiring or missing items reduce it. 
            It&apos;s a risk indicator to help you prioritise — not a legal verdict.
          </p>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">
              <strong>Disclaimer:</strong> The compliance score is an informational tracking indicator and does not constitute legal advice or regulatory determination.
            </p>
          </div>
        </div>
      </section>

      {/* H) PRICING FRAMING */}
      <section className="py-16 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-4 text-center">
            Simple, Transparent Pricing
          </h2>
          <p className="text-center text-gray-600 mb-8 max-w-xl mx-auto">
            Choose the plan that fits the size of your portfolio. Solo, Portfolio, or Professional — upgrade or downgrade anytime. Your data remains secure.
          </p>
          <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
            <Button size="lg" variant="outline" className="border-electric-teal text-electric-teal" asChild>
              <Link to="/pricing">View plans</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* I) FAQ */}
      <section className="py-16 lg:py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-midnight-blue mb-8 text-center">
            Frequently Asked Questions
          </h2>
          <Accordion type="single" collapsible className="w-full">
            {faqs.map((faq, i) => (
              <AccordionItem key={i} value={`faq-${i}`}>
                <AccordionTrigger className="text-left font-medium text-midnight-blue">
                  {faq.q}
                </AccordionTrigger>
                <AccordionContent className="text-gray-600">{faq.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* J) FINAL CTA */}
      <section className="py-16 lg:py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-4">
            Take Control of Your Property Compliance
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Start your structured compliance tracking today.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
              asChild
            >
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white/10"
              asChild
            >
              <Link to="/compliance-vault-pro">View Platform Overview</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default HomePage;
