import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import ProductScreenshot from '../../components/public/ProductScreenshot';
import MarketingImage from '../../components/public/MarketingImage';
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 sm:pt-10 sm:pb-12 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-6 sm:gap-8 lg:gap-12 items-center">
            <div className="min-w-0">
              <h1 className="text-[1.5625rem] sm:text-4xl lg:text-[2.75rem] font-bold text-midnight-blue leading-[1.18] sm:leading-tight tracking-tight text-balance mb-3 sm:mb-6">
                Are You Fully Compliant as a UK Landlord?
              </h1>
              <p className="text-[0.9375rem] sm:text-lg leading-snug sm:leading-relaxed text-gray-600 mb-4 sm:mb-8 max-w-xl">
                Structured compliance monitoring and renewal tracking for UK portfolios.
              </p>
              <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-4">
                <Button
                  size="lg"
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full sm:w-auto min-h-[48px] px-5 sm:px-8 whitespace-normal text-sm sm:text-base"
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
                  className="border-electric-teal text-electric-teal hover:bg-electric-teal/5 w-full sm:w-auto min-h-[48px] px-5 whitespace-normal text-sm sm:text-base"
                  asChild
                  data-testid="hero-cta-secondary"
                >
                  <Link to="/compliance-vault-pro">View Platform Overview</Link>
                </Button>
              </div>
              <div
                className="mt-4 sm:mt-8 grid grid-cols-2 sm:flex sm:flex-wrap gap-x-3 gap-y-2.5 text-xs sm:text-sm text-gray-600"
                aria-label="Product highlights"
              >
                {trustBullets.map((point) => (
                  <span key={point} className="flex items-start gap-1.5 sm:gap-2 min-w-0">
                    <CheckCircle2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-electric-teal shrink-0 mt-0.5" />
                    <span className="leading-snug">{point}</span>
                  </span>
                ))}
              </div>
            </div>
            {/* Hero: real dashboard screenshot (cropped); headline remains dominant */}
            <div className="relative w-full mt-2 lg:mt-0 lg:block">
              <h2 className="sr-only">UK landlord compliance tracking—risk report in 60 seconds</h2>
              <ProductScreenshot className="max-h-[210px] sm:max-h-[330px] lg:max-h-[420px]">
                <MarketingImage
                  name="hero-command-centre"
                  alt="Compliance dashboard example showing score and quick actions"
                  width={1200}
                  height={850}
                  className="w-full h-[200px] sm:h-auto sm:min-h-0 object-cover sm:object-contain object-[center_8%] sm:object-top"
                  fetchPriority="high"
                  placeholderText="Dashboard preview"
                />
              </ProductScreenshot>
              <p className="text-[0.6875rem] sm:text-xs text-gray-500 text-center mt-2 sm:mt-4 px-1 sm:px-2 leading-snug">
                Illustrative preview. Live score generated after structured assessment.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Dashboard preview — portfolio in one view */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance leading-snug sm:leading-tight px-1">
            See Your Entire Portfolio in One View
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-6 sm:mb-10 max-w-2xl mx-auto leading-relaxed px-1">
            Instantly see expiry risk, expiring documents, and compliance visibility across every property you manage.
          </p>
          <div className="grid lg:grid-cols-2 gap-6 sm:gap-10 lg:gap-12 items-center">
            <ul className="space-y-2.5 sm:space-y-3 text-gray-700 text-sm sm:text-base">
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Portfolio compliance score</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Property-level breakdown</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Expiring soon indicator</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" /> Overdue alert example</li>
            </ul>
            <div className="relative w-full lg:max-w-[60%]">
              <ProductScreenshot>
                <MarketingImage
                  name="feature-expiry-list"
                  alt="Upcoming expiries list from Compliance Calendar"
                  width={1200}
                  height={800}
                  className="w-full h-[180px] sm:h-auto object-cover sm:object-contain object-[center_10%] sm:object-top"
                  loading="lazy"
                  placeholderText="Upcoming expiries preview"
                />
              </ProductScreenshot>
              <p className="text-xs text-gray-500 text-center mt-2">Expiry alerts generated from confirmed certificate dates.</p>
              <div className="mt-4 flex flex-col items-center gap-2">
                <Button className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full sm:w-auto min-h-[48px]" asChild>
                  <Link to="/risk-check">Free compliance risk preview</Link>
                </Button>
                <p className="text-xs text-gray-500 text-center max-w-sm px-2">
                  Short questionnaire — not your live in-app PDF reports.{' '}
                  <Link to="/pricing" className="text-electric-teal font-medium hover:underline">
                    Plans with reports
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* C) THE PROBLEM */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-center text-balance leading-snug sm:leading-tight px-1">
            Compliance Is Easy to Forget — Until It&apos;s Too Late
          </h2>
          <div className="max-w-3xl mx-auto space-y-3 sm:space-y-4 text-gray-600 text-center text-[0.9375rem] sm:text-base mb-6 sm:mb-8 leading-relaxed">
            <p>Certificates buried in inboxes. Expiry dates lost in spreadsheets. No clear overview across properties.</p>
            <p>When documentation is scattered, visibility disappears — and deadlines get missed.</p>
            <p className="text-midnight-blue font-medium">Compliance Vault Pro gives you structured oversight so nothing critical slips through.</p>
          </div>
          <div className="flex justify-center px-1">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full max-w-md sm:w-auto min-h-[48px]" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* D) FOUR PILLARS */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance leading-snug sm:leading-tight px-1">
            All Your Compliance Tracking in One Structured Dashboard
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-8 sm:mb-12 max-w-2xl mx-auto leading-relaxed">
            Track evidence, see risk indicators, get reminders, and generate reports. No legal claims — just structured tracking.
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-8">
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
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance px-1">
            Built for Modern UK Landlords
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-8 sm:mb-12 max-w-2xl mx-auto leading-relaxed">
            Works for solo landlords, portfolio landlords, and HMO operators. Also suitable for managing agents overseeing landlord portfolios.
          </p>
          <div className="grid md:grid-cols-3 gap-5 sm:gap-8">
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
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-2 sm:mb-4 text-center text-balance px-1">
            Get Set Up in Minutes, Not Hours
          </h2>
          <div className="max-w-3xl mx-auto space-y-5 sm:space-y-6 mt-8 sm:mt-12">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-3 sm:gap-4">
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
          <div className="text-center mt-8 sm:mt-12 px-1">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full max-w-md sm:w-auto min-h-[48px]" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* G) COMPLIANCE SCORE TRANSPARENCY */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-center text-balance">
            How the Compliance Score Works
          </h2>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
            Each property gets a structured tracking score based on confirmed evidence and recorded expiry dates. 
            Your dashboard also shows a portfolio-level summary for overall visibility.
          </p>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
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
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance">
            Simple, Transparent Pricing
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-6 sm:mb-8 max-w-xl mx-auto leading-relaxed">
            Choose the plan that fits the size of your portfolio. Solo, Portfolio, or Professional — upgrade or downgrade anytime. Your data remains secure.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-6 justify-center items-stretch sm:items-center px-1">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full sm:w-auto min-h-[48px]" asChild>
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
            <Button size="lg" variant="outline" className="border-electric-teal text-electric-teal w-full sm:w-auto min-h-[48px]" asChild>
              <Link to="/pricing">View plans</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* I) FAQ */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-6 sm:mb-8 text-center text-balance">
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
      <section className="py-12 sm:py-16 lg:py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-xl sm:text-3xl font-bold text-white mb-3 sm:mb-4 text-balance leading-snug">
            Take Control of Your Property Compliance
          </h2>
          <p className="text-base sm:text-lg text-gray-300 mb-6 sm:mb-8 leading-relaxed">
            Start your structured compliance tracking today.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center items-stretch sm:items-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8 w-full sm:w-auto min-h-[48px]"
              asChild
            >
              <Link to="/risk-check">Check Your Compliance Risk</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white/10 w-full sm:w-auto min-h-[48px]"
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
