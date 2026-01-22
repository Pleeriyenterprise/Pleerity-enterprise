import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead, productSchema } from '../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
  Shield,
  FileCheck,
  Bell,
  BarChart3,
  Sparkles,
  Users,
  Webhook,
  FileText,
  Calendar,
  Smartphone,
  ArrowRight,
  CheckCircle2,
  Clock,
  Zap,
  Lock,
} from 'lucide-react';

const CVPLandingPage = () => {
  const coreFeatures = [
    {
      icon: Shield,
      title: 'Compliance Dashboard',
      description: 'Real-time overview of all your property compliance statuses. See what needs attention at a glance.',
    },
    {
      icon: FileCheck,
      title: 'Document Management',
      description: 'Upload, store, and organize all compliance certificates. AI-powered extraction fills in the details.',
    },
    {
      icon: Bell,
      title: 'Automated Reminders',
      description: 'Get notified before certificates expire. Email and SMS alerts ensure you never miss a deadline.',
    },
    {
      icon: BarChart3,
      title: 'Professional Reports',
      description: 'Generate PDF compliance packs, audit-ready reports, and monthly digests for your portfolio.',
    },
    {
      icon: Calendar,
      title: 'Expiry Calendar',
      description: 'Visual calendar view of upcoming deadlines. Export to Google Calendar or Outlook.',
    },
    {
      icon: Sparkles,
      title: 'AI Document Scanner',
      description: 'Upload certificates and our AI extracts dates, reference numbers, and validates compliance.',
    },
  ];

  const plans = [
    {
      name: 'Solo Landlord',
      code: 'PLAN_1_SOLO',
      price: '19',
      properties: '2',
      features: [
        'Compliance Dashboard',
        'Document Vault',
        'Email Reminders',
        'Basic AI Extraction',
        'Compliance Score',
      ],
      cta: 'Start with Solo',
    },
    {
      name: 'Portfolio',
      code: 'PLAN_2_PORTFOLIO',
      price: '39',
      properties: '10',
      popular: true,
      features: [
        'Everything in Solo',
        'SMS Reminders',
        'PDF/CSV Reports',
        'Advanced AI Extraction',
        'Tenant Portal Access',
        'Scheduled Reports',
      ],
      cta: 'Start with Portfolio',
    },
    {
      name: 'Professional',
      code: 'PLAN_3_PRO',
      price: '79',
      properties: '25',
      features: [
        'Everything in Portfolio',
        'Webhooks & API Access',
        'White-Label Reports',
        'Audit Log Export',
        'ZIP Bulk Upload',
        'Priority Support',
      ],
      cta: 'Start with Professional',
    },
  ];

  const complianceTypes = [
    { name: 'Gas Safety Certificate', frequency: 'Annual' },
    { name: 'EICR (Electrical)', frequency: 'Every 5 years' },
    { name: 'EPC Rating', frequency: 'Every 10 years' },
    { name: 'HMO Licence', frequency: 'Every 5 years' },
    { name: 'Smoke & CO Alarms', frequency: 'Annual check' },
    { name: 'Legionella Assessment', frequency: 'Every 2 years' },
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Compliance Vault Pro - UK Landlord Compliance Management Platform"
        description="The all-in-one compliance platform for UK landlords. Track certificates, automate reminders, and stay compliant with Gas Safety, EICR, EPC regulations."
        canonicalUrl="/compliance-vault-pro"
        schema={productSchema}
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
              <Lock className="w-4 h-4 mr-2" />
              Trusted by UK Landlords
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-midnight-blue leading-tight mb-6">
              Compliance Vault Pro
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
              The all-in-one platform that keeps your property portfolio compliant. 
              Track every certificate, automate reminders, and generate audit-ready reports.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                size="lg"
                className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
                asChild
                data-testid="cvp-get-started"
              >
                <Link to="/intake/start">
                  Start Free Trial
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Link>
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="border-midnight-blue text-midnight-blue"
                asChild
              >
                <Link to="/pricing">View Pricing</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* What We Track Section */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-midnight-blue mb-4">
              All Your Compliance Requirements in One Place
            </h2>
            <p className="text-lg text-gray-600">
              We track every certificate UK landlords need
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {complianceTypes.map((type) => (
              <Card key={type.name} className="text-center border-gray-200">
                <CardContent className="pt-4 pb-4">
                  <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center mx-auto mb-3">
                    <CheckCircle2 className="w-5 h-5 text-electric-teal" />
                  </div>
                  <h3 className="font-medium text-midnight-blue text-sm mb-1">{type.name}</h3>
                  <p className="text-xs text-gray-500">{type.frequency}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Core Features */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
              Powerful Features for Modern Landlords
            </h2>
            <p className="text-lg text-gray-600">
              Everything you need to manage compliance across your entire portfolio
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {coreFeatures.map((feature) => (
              <Card key={feature.title} className="border-0 shadow-lg">
                <CardContent className="pt-6">
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-xl flex items-center justify-center mb-4">
                    <feature.icon className="w-6 h-6 text-electric-teal" />
                  </div>
                  <h3 className="text-xl font-semibold text-midnight-blue mb-2">{feature.title}</h3>
                  <p className="text-gray-600">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
              How It Works
            </h2>
            <p className="text-lg text-gray-600">
              Get up and running in minutes, not hours
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              { step: '1', title: 'Sign Up', description: 'Create your account and add your properties', icon: Users },
              { step: '2', title: 'Upload Documents', description: 'Upload your certificates or let AI extract them', icon: FileText },
              { step: '3', title: 'Track & Monitor', description: 'See your compliance status at a glance', icon: Shield },
              { step: '4', title: 'Stay Compliant', description: 'Receive reminders before deadlines', icon: Bell },
            ].map((item) => (
              <div key={item.step} className="text-center">
                <div className="w-16 h-16 bg-electric-teal text-white rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                  {item.step}
                </div>
                <h3 className="text-xl font-semibold text-midnight-blue mb-2">{item.title}</h3>
                <p className="text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Preview */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-lg text-gray-600">
              Choose the plan that fits your portfolio
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <Card
                key={plan.code}
                className={`relative ${plan.popular ? 'border-2 border-electric-teal shadow-xl' : 'border-gray-200'}`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-electric-teal text-white text-sm font-medium rounded-full">
                    Most Popular
                  </div>
                )}
                <CardContent className="pt-8">
                  <h3 className="text-xl font-bold text-midnight-blue mb-2">{plan.name}</h3>
                  <div className="flex items-baseline mb-1">
                    <span className="text-4xl font-bold text-midnight-blue">£{plan.price}</span>
                    <span className="text-gray-500 ml-2">/month</span>
                  </div>
                  <p className="text-sm text-gray-500 mb-6">Up to {plan.properties} properties</p>
                  <ul className="space-y-3 mb-8">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start">
                        <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mr-2" />
                        <span className="text-gray-700 text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    className={`w-full ${plan.popular ? 'bg-electric-teal hover:bg-electric-teal/90' : ''}`}
                    variant={plan.popular ? 'default' : 'outline'}
                    asChild
                  >
                    <Link to="/intake/start">{plan.cta}</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="text-center mt-8">
            <Link to="/pricing" className="text-electric-teal hover:underline font-medium">
              View full pricing details <ArrowRight className="w-4 h-4 inline ml-1" />
            </Link>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Start Managing Compliance Today
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Join hundreds of UK landlords who trust Compliance Vault Pro
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/intake/start">
              Get Started Free
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CVPLandingPage;
