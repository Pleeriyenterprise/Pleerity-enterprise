import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import ProductScreenshot from '../../components/public/ProductScreenshot';
import MarketingImage from '../../components/public/MarketingImage';
import { SEOHead, productSchema } from '../../components/public/SEOHead';
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
  Calendar,
  FileText,
  Users,
  Home,
  Briefcase,
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';

const CVPLandingPage = () => {
  const trustBullets = [
    'Expiry reminders',
    'Evidence vault',
    'Portfolio view',
    'PDF reports',
    'Not legal advice',
  ];

  const outcomes = [
    'Know what’s missing',
    'See what’s expiring',
    'Generate a clear audit-style report',
  ];

  const deliverables = [
    { label: 'Property portfolio dashboard', icon: Building2 },
    { label: 'Requirement tracking per property (Gas Safety, EICR, EPC, Fire alarm, Legionella, PAT, licensing where applicable)', icon: FileCheck },
    { label: 'Document vault (uploads per property)', icon: FileText },
    { label: 'Expiry calendar view', icon: Calendar },
    { label: 'Reminders (email / SMS, plan-based) and compliance status change alerts (twice daily)', icon: Bell },
    { label: 'Compliance score (risk indicator) and breakdown', icon: Shield },
    { label: 'Reports (portfolio and per-property PDF)', icon: BarChart3 },
    { label: 'Audit log (changes tracked)', icon: FileText },
  ];

  const steps = [
    { title: 'Add properties (or import)', body: 'Create your portfolio and add property details.' },
    { title: 'Upload evidence', body: 'Optional at intake; you can upload documents later.' },
    { title: 'Confirm key dates', body: 'If extraction is uncertain, confirm expiry and issue dates.' },
    { title: 'Track status and get reminders', body: 'View compliance status per property and receive reminders before deadlines.' },
    { title: 'Generate reports and exports', body: 'Produce portfolio and per-property reports when you need them.' },
  ];

  const segments = [
    { title: 'Solo landlords', body: 'Keep evidence organised and monitored from day one.', icon: Home },
    { title: 'Portfolio landlords', body: 'Track multiple properties with one dashboard and centralised reporting.', icon: Building2 },
    { title: 'Landlords working with agents', body: 'Share visibility with your agent; both can stay on top of deadlines where applicable.', icon: Briefcase },
    { title: 'HMO / licensed properties', body: 'Monitor licensing, renewals, and property-level documentation where applicable.', icon: Users },
  ];

  const plans = [
    {
      name: 'Solo Landlord',
      who: '1–2 properties',
      properties: '2',
      price: '19',
      reminders: 'Email reminders',
      reports: 'Core reports',
      features: ['Portfolio dashboard', 'Document vault', 'Email reminders', 'Compliance score', 'Expiry calendar', 'Basic AI extraction'],
      cta: 'Activate Monitoring',
    },
    {
      name: 'Portfolio',
      who: 'Growing portfolios',
      properties: '10',
      price: '39',
      reminders: 'Email + SMS reminders',
      reports: 'PDF reports, scheduled reports',
      popular: true,
      features: [
        'Everything in Solo',
        'SMS reminders',
        'PDF reports',
        'ZIP bulk upload',
        'Scheduled reports',
      ],
      cta: 'Activate Monitoring',
    },
    {
      name: 'Professional',
      who: 'Agents and larger operators',
      properties: '25',
      price: '79',
      reminders: 'Email + SMS reminders',
      reports: 'White-label reports, audit export, tenant portal',
      features: [
        'Everything in Portfolio',
        'Advanced AI extraction & review tools',
        'Tenant portal access',
        'White-label reports',
        'Audit log & governed evidence pack export',
        'CSV exports',
        'Webhooks & read API',
        'Priority support',
      ],
      cta: 'Activate Monitoring',
    },
  ];

  const faqs = [
    {
      q: 'Is this legal advice?',
      a: 'No. Compliance Vault Pro is a tracking and organisation platform. It helps you see expiry dates and evidence in one place. It does not provide legal advice or regulatory determination. For legal or regulatory questions, consult a qualified professional.',
    },
    {
      q: 'How does expiry tracking work?',
      a: 'You upload certificates or enter expiry dates (or we extract dates from documents). The platform tracks when each item expires and shows status per property. Reminders are sent before deadlines based on your plan and notification preferences.',
    },
    {
      q: 'What if a requirement doesn’t apply to my property?',
      a: 'You can mark requirements as not applicable (e.g. no gas supply). The score and reports then reflect only what applies to each property.',
    },
    {
      q: 'Do you support agents and landlords both receiving reminders?',
      a: 'The account owner sets up properties and receives reminders. Agents can be given access depending on your plan; reminder delivery is configurable in notification preferences.',
    },
    {
      q: 'What happens if I downgrade?',
      a: 'You can upgrade or downgrade anytime. Your data remains secure. Features that are part of higher tiers (e.g. SMS, PDF reports) may no longer be available on a lower tier, but your stored documents and property data are retained.',
    },
    {
      q: 'Can I export my documents and reports?',
      a: 'Yes. You can download documents you’ve uploaded. Report export (PDF/CSV) is available depending on your plan. See the pricing section for what’s included in each tier.',
    },
  ];

  return (
    <PublicLayout>
      {/* A) SEO */}
      <SEOHead
        title="UK Landlord Compliance Tracking | Gas Safety, EICR & EPC Expiry – Compliance Vault Pro"
        description="Compliance Vault Pro: UK landlord compliance tracking, reminders, and evidence vault. Gas safety certificate expiry tracking, EICR expiry reminders, HMO compliance tracking UK. Track portfolios and generate audit-style reports."
        canonicalUrl="/compliance-vault-pro"
        schema={productSchema}
      />

      {/* A) HERO */}
      <section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-8 sm:pt-10 sm:pb-12 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-6 sm:gap-8 lg:gap-12 items-center">
            <div className="min-w-0">
              <h1 className="text-[1.625rem] sm:text-4xl lg:text-[2.75rem] font-bold text-midnight-blue leading-[1.15] sm:leading-tight tracking-tight text-balance mb-3 sm:mb-6">
                Compliance Vault Pro
              </h1>
              <p className="text-[0.9375rem] sm:text-lg leading-snug sm:leading-relaxed text-gray-600 mb-4 sm:mb-8 max-w-xl">
                UK landlord compliance tracking, reminders, and evidence vault — built for portfolios.
              </p>
              <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-4">
                <Button
                  size="lg"
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full sm:w-auto min-h-[48px] px-5 sm:px-8 whitespace-normal text-sm sm:text-base"
                  asChild
                  data-testid="cvp-cta-primary"
                >
                  <Link to="/risk-check">
                    Check Your Risk
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Link>
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  className="border-electric-teal text-electric-teal hover:bg-electric-teal/5 w-full sm:w-auto min-h-[48px] px-5 whitespace-normal text-sm sm:text-base"
                  asChild
                >
                  <Link to="/intake/start">Start Monitoring</Link>
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
            <div className="relative w-full mt-2 lg:mt-0 block">
              <ProductScreenshot className="max-h-[210px] sm:max-h-[320px] lg:max-h-[380px]">
                <MarketingImage
                  name="feature-expiry-list"
                  alt="Upcoming expiries and portfolio view from Compliance Vault Pro"
                  width={1200}
                  height={800}
                  className="w-full h-[200px] sm:h-auto object-cover sm:object-contain object-[center_12%] sm:object-top"
                  fetchPriority="high"
                  placeholderText="Platform preview"
                />
              </ProductScreenshot>
              <p className="text-[0.6875rem] sm:text-xs text-gray-500 text-center mt-2 sm:mt-3 px-1 leading-snug">
                Illustrative preview. Your live view updates as you add properties and evidence.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* B) WHAT IT DOES */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-balance leading-snug sm:leading-tight px-1">
            One platform to track certificates, get reminders, and organise evidence
          </h2>
          <ul className="space-y-3 text-left mb-6">
            {outcomes.map((o) => (
              <li key={o} className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0" />
                <span className="text-gray-700">{o}</span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 inline-block">
            Informational tracking only. Not legal advice.
          </p>
        </div>
      </section>

      {/* B.5) See your compliance risk in 60 seconds — mid-page CTA */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-balance px-1">
            See your compliance risk in 60 seconds
          </h2>
          <p className="text-gray-600 mb-5 sm:mb-6 text-[0.9375rem] sm:text-base leading-relaxed px-1">
            Answer a few questions and get a structured risk report. Lead-only until you activate monitoring.
          </p>
          <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-4 justify-center items-stretch sm:items-center px-1">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white w-full sm:w-auto min-h-[48px] px-5 sm:px-8 whitespace-normal text-sm sm:text-base"
              asChild
            >
              <Link to="/risk-check">
                Check Your Risk
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="border-electric-teal text-electric-teal w-full sm:w-auto min-h-[48px] px-5 whitespace-normal text-sm sm:text-base" asChild>
              <Link to="/pricing">View Pricing</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* C) WHAT YOU GET */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50" id="what-you-get">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-6 sm:mb-8 text-center text-balance px-1">
            What You Get
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            {deliverables.map((item) => (
              <div key={item.label} className="flex gap-3 p-4 bg-white rounded-xl border border-gray-200">
                <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0">
                  <item.icon className="w-5 h-5 text-electric-teal" />
                </div>
                <p className="text-sm font-medium text-midnight-blue">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* D) HOW IT WORKS */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white" id="how-it-works">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance px-1">
            How It Works
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-8 sm:mb-12 max-w-2xl mx-auto leading-relaxed">
            Get set up quickly and start tracking with minimal effort.
          </p>
          <div className="max-w-3xl mx-auto space-y-5 sm:space-y-6">
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
        </div>
      </section>

      {/* E) HOW THE SCORE WORKS */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50" id="how-the-score-works">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-center text-balance">
            How the Compliance Score Works
          </h2>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
            The score is an evidence-based risk indicator. It reflects: whether you have evidence for each requirement, 
            expiry status (valid, expiring soon, overdue), and any overdue penalties. You get a score per property 
            and a portfolio summary on your dashboard with per-property drill-down.
          </p>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
            It is not a legal verdict or regulatory determination — it helps you see where to focus attention.
          </p>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3 mb-8">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">
              <strong>Disclaimer:</strong> The compliance score is an informational tracking indicator and does not constitute legal advice or regulatory determination.
            </p>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            <a href="#score-example" className="text-electric-teal font-medium hover:underline">
              View example breakdown ↓
            </a>
          </p>
          <div id="score-example" className="bg-white border border-gray-200 rounded-xl p-6 mt-4">
            <h3 className="font-semibold text-midnight-blue mb-3">Example breakdown</h3>
            <ul className="space-y-2 text-sm text-gray-700">
              <li>• Valid evidence + future expiry → contributes positively to score</li>
              <li>• Expiring within 30 days → flagged; score reflects higher risk</li>
              <li>• Overdue or missing evidence → reduces score for that requirement</li>
              <li>• Portfolio score aggregates property-level scores for an overall view</li>
            </ul>
          </div>
        </div>
      </section>

      {/* F) WHO IT'S FOR */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-6 sm:mb-8 text-center text-balance px-1">
            Who It’s For
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 sm:gap-8">
            {segments.map((seg) => (
              <Card key={seg.title} className="border border-gray-200">
                <CardContent className="pt-6">
                  <div className="w-12 h-12 bg-midnight-blue/10 rounded-xl flex items-center justify-center mb-4">
                    <seg.icon className="w-6 h-6 text-midnight-blue" />
                  </div>
                  <h3 className="font-semibold text-midnight-blue mb-2">{seg.title}</h3>
                  <p className="text-gray-600 text-sm">{seg.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* G) REMINDERS & NOTIFICATIONS */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-center text-balance">
            Reminders & Notifications
          </h2>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
            Reminders are sent when we have a known or confirmed expiry date for a requirement.
            You’ll get advance notice before deadlines so you can renew in time. Scheduling and frequency depend on your plan.
          </p>
          <p className="text-gray-600 mb-4 text-[0.9375rem] sm:text-base leading-relaxed">
            You control how you’re notified: in your account you can set preferences for email and SMS (where available on your plan) so reminders fit how you work.
          </p>
          <div className="mt-6 sm:mt-8 max-w-2xl mx-auto">
            <ProductScreenshot className="max-h-[220px] sm:max-h-none overflow-hidden">
              <MarketingImage
                name="support-calendar"
                alt="Compliance calendar view with upcoming expiries"
                width={1200}
                height={800}
                className="w-full h-[200px] sm:h-auto object-cover sm:object-contain object-[center_20%] sm:object-center"
                loading="lazy"
                placeholderText="Calendar preview"
              />
            </ProductScreenshot>
          </div>
        </div>
      </section>

      {/* H) REPORTS & EXPORTS */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-5 sm:mb-6 text-center text-balance px-1">
            Reports & Exports
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-6 sm:mb-8 max-w-2xl mx-auto leading-relaxed">
            Organisational reports for internal use or to share with advisers — not legal advice.
          </p>
          {/* TODO: Replace with sample report preview image when available */}
          <div className="max-w-2xl mx-auto bg-gray-50 border border-gray-200 rounded-xl p-6">
            <h3 className="font-semibold text-midnight-blue mb-4">Sample report preview</h3>
            <ul className="space-y-2 text-sm text-gray-700">
              <li>• Portfolio overview</li>
              <li>• Property list</li>
              <li>• Expiring soon</li>
              <li>• Overdue</li>
              <li>• Missing evidence</li>
              <li>• Action checklist</li>
              <li>• Audit log summary</li>
              <li>• Disclaimer (informational only)</li>
            </ul>
            <div className="mt-4 h-32 flex items-center justify-center border border-dashed border-gray-300 rounded-lg text-gray-500 text-sm">
              Report preview image placeholder
            </div>
          </div>
        </div>
      </section>

      {/* I) PRICING */}
      <section className="py-10 sm:py-14 lg:py-20 bg-gray-50" id="pricing">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-3 sm:mb-4 text-center text-balance px-1">
            Pricing
          </h2>
          <p className="text-center text-[0.9375rem] sm:text-base text-gray-600 mb-8 sm:mb-10 max-w-xl mx-auto leading-relaxed">
            Upgrade or downgrade anytime. Your data remains secure.
          </p>
          <div className="grid md:grid-cols-3 gap-5 sm:gap-8 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={`relative h-full flex flex-col ${plan.popular ? 'border-2 border-electric-teal shadow-xl' : 'border-gray-200'}`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-electric-teal text-white text-xs font-medium rounded-full">
                    Most Popular
                  </div>
                )}
                <CardContent className="pt-8 pb-6 flex flex-col flex-1">
                  <h3 className="text-xl font-bold text-midnight-blue mb-1">{plan.name}</h3>
                  <p className="text-sm text-gray-500 mb-2">Who it’s for: {plan.who}</p>
                  <div className="flex items-baseline gap-1 mb-3">
                    <span className="text-2xl font-bold text-midnight-blue">£{plan.price}</span>
                    <span className="text-gray-500 text-sm">/month</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-1">Up to {plan.properties} properties</p>
                  <p className="text-sm text-gray-600 mb-2">Reminders: {plan.reminders}</p>
                  <p className="text-sm text-gray-600 mb-6">Reports: {plan.reports}</p>
                  <ul className="space-y-2 mb-8 flex-1">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm text-gray-700">
                        <CheckCircle2 className="w-4 h-4 text-electric-teal shrink-0 mt-0.5" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    className={`w-full min-h-[48px] ${plan.popular ? 'bg-electric-teal hover:bg-electric-teal/90 text-white' : ''}`}
                    variant={plan.popular ? 'default' : 'outline'}
                    asChild
                  >
                    <Link to="/intake/start">{plan.cta}</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
          <p className="text-center text-sm text-gray-500 mt-6">
            <Link to="/pricing" className="text-electric-teal hover:underline">View full pricing details</Link>
          </p>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center items-stretch sm:items-center mt-8 sm:mt-10 px-1">
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8 w-full sm:w-auto min-h-[48px]" asChild>
              <Link to="/intake/start">Activate Monitoring</Link>
            </Button>
            <Link to="/pricing" className="text-sm text-electric-teal hover:underline">See pricing</Link>
          </div>
        </div>
      </section>

      {/* J) FAQ */}
      <section className="py-10 sm:py-14 lg:py-20 bg-white" id="faq">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-3xl font-bold text-midnight-blue mb-6 sm:mb-8 text-center text-balance">
            Frequently Asked Questions
          </h2>
          <Accordion type="single" collapsible className="w-full">
            {faqs.map((faq, i) => (
              <AccordionItem key={i} value={`cvp-faq-${i}`}>
                <AccordionTrigger className="text-left font-medium text-midnight-blue">
                  {faq.q}
                </AccordionTrigger>
                <AccordionContent className="text-gray-600">{faq.a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* K) FINAL CTA */}
      <section className="py-12 sm:py-16 lg:py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-xl sm:text-3xl font-bold text-white mb-3 sm:mb-4 text-balance leading-snug">
            Take Control of Your Property Compliance
          </h2>
          <p className="text-base sm:text-lg text-gray-300 mb-6 sm:mb-8 leading-relaxed">
            Track certificates, get reminders, and generate clear reports — all in one place.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center items-stretch sm:items-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8 w-full sm:w-auto min-h-[48px]"
              asChild
            >
              <Link to="/intake/start">Start Your Setup</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white/10 w-full sm:w-auto min-h-[48px]"
              asChild
            >
              <Link to="/risk-check">Check your compliance risk</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CVPLandingPage;
