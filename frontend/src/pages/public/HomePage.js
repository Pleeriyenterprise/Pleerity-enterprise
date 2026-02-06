import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead, organizationSchema } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import {
  Shield,
  FileCheck,
  Bell,
  BarChart3,
  Sparkles,
  Building2,
  ClipboardCheck,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

const HomePage = () => {
  const features = [
    {
      icon: Shield,
      title: 'Compliance Tracking',
      description: 'Monitor all requirements across your property portfolio with real-time status updates.',
    },
    {
      icon: FileCheck,
      title: 'Document Vault',
      description: 'Securely store all compliance certificates and documents in one central location.',
    },
    {
      icon: Bell,
      title: 'Smart Reminders',
      description: 'Never miss a deadline with automated email and SMS reminders before expiry.',
    },
    {
      icon: BarChart3,
      title: 'Compliance Reports',
      description: 'Generate audit-ready compliance packs and monthly digest reports instantly.',
    },
  ];

  const services = [
    {
      href: '/services/ai-automation',
      icon: Sparkles,
      title: 'AI & Automation',
      description: 'Automate repetitive property management tasks with intelligent workflows.',
    },
    {
      href: '/services/market-research',
      icon: Building2,
      title: 'Market Research',
      description: 'Get comprehensive property market insights for informed decisions.',
    },
    {
      href: '/services/compliance-audits',
      icon: ClipboardCheck,
      title: 'Compliance Audits',
      description: 'Professional HMO and full property compliance audits.',
    },
  ];

  const trustPoints = [
    'GDPR Compliant',
    'UK-Based Company',
    'Bank-Level Security',
    '24/7 System Monitoring',
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="AI-Powered Landlord Compliance & Workflow Automation"
        description="Streamline UK landlord compliance with Compliance Vault Pro. AI-powered document management, automated reminders, and professional audit services."
        canonicalUrl="/"
        schema={organizationSchema}
      />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center px-3 py-1 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
                <Sparkles className="w-4 h-4 mr-2" />
                AI-Powered Compliance Platform
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-midnight-blue leading-tight mb-6">
                UK Landlord Compliance{' '}
                <span className="text-electric-teal">Made Simple</span>
              </h1>
              <p className="text-lg text-gray-600 mb-8 max-w-xl">
                Manage all your property compliance requirements in one secure platform. 
                Stay audit-ready with automated reminders and intelligent document tracking.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Button
                  size="lg"
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
                  asChild
                  data-testid="hero-get-started"
                >
                  <Link to="/intake/start">
                    Get Started
                    <ArrowRight className="w-5 h-5 ml-2" />
                  </Link>
                </Button>
              </div>

              {/* Trust Points */}
              <div className="mt-10 flex flex-wrap gap-4">
                {trustPoints.map((point) => (
                  <div key={point} className="flex items-center text-sm text-gray-600">
                    <CheckCircle2 className="w-4 h-4 text-electric-teal mr-2" />
                    {point}
                  </div>
                ))}
              </div>
            </div>

            {/* Hero Visual */}
            <div className="relative hidden lg:block">
              <div className="relative bg-white rounded-2xl shadow-2xl p-6 border border-gray-200">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center">
                      <Shield className="w-5 h-5 text-electric-teal" />
                    </div>
                    <div>
                      <div className="font-semibold text-midnight-blue">Compliance Score</div>
                      <div className="text-sm text-gray-500">Portfolio Overview</div>
                    </div>
                  </div>
                  <div className="text-3xl font-bold text-electric-teal">94%</div>
                </div>
                <div className="space-y-3">
                  {[
                    { label: 'Gas Safety Certificates', status: 'Compliant', color: 'bg-green-500' },
                    { label: 'EICR Reports', status: 'Compliant', color: 'bg-green-500' },
                    { label: 'EPC Ratings', status: '1 Expiring Soon', color: 'bg-amber-500' },
                    { label: 'HMO Licences', status: 'Compliant', color: 'bg-green-500' },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <span className="text-sm text-gray-700">{item.label}</span>
                      <div className="flex items-center">
                        <div className={`w-2 h-2 rounded-full ${item.color} mr-2`} />
                        <span className="text-sm text-gray-600">{item.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Decorative elements */}
              <div className="absolute -top-4 -right-4 w-24 h-24 bg-electric-teal/10 rounded-full blur-2xl" />
              <div className="absolute -bottom-4 -left-4 w-32 h-32 bg-midnight-blue/5 rounded-full blur-2xl" />
            </div>
          </div>
        </div>
      </section>

      {/* Main Product Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
              Everything You Need for Compliance
            </h2>
            <p className="text-lg text-gray-600">
              Compliance Vault Pro brings all your property compliance requirements into one 
              intelligent platform that works for you.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature) => (
              <Card key={feature.title} className="border-0 shadow-lg hover:shadow-xl transition-shadow">
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

          <div className="text-center mt-12">
            <Button
              size="lg"
              variant="outline"
              className="border-electric-teal text-electric-teal hover:bg-electric-teal hover:text-white"
              asChild
            >
              <Link to="/compliance-vault-pro">
                Learn More About Compliance Vault Pro
                <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
              Professional Property Services
            </h2>
            <p className="text-lg text-gray-600">
              Beyond compliance management, we offer a range of professional services 
              to support your property business.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {services.map((service) => (
              <Link
                key={service.href}
                to={service.href}
                className="group"
                data-testid={`service-link-${service.title.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <Card className="h-full border-0 shadow-lg hover:shadow-xl transition-all hover:-translate-y-1">
                  <CardContent className="pt-6">
                    <div className="w-12 h-12 bg-midnight-blue/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-electric-teal/10 transition-colors">
                      <service.icon className="w-6 h-6 text-midnight-blue group-hover:text-electric-teal transition-colors" />
                    </div>
                    <h3 className="text-xl font-semibold text-midnight-blue mb-2">{service.title}</h3>
                    <p className="text-gray-600 mb-4">{service.description}</p>
                    <span className="inline-flex items-center text-electric-teal font-medium">
                      Learn more
                      <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>

          <div className="text-center mt-12">
            <Button size="lg" variant="outline" asChild>
              <Link to="/services">View All Services</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Ready to Simplify Your Compliance?
          </h2>
          <p className="text-lg text-gray-300 mb-8 max-w-2xl mx-auto">
            Join hundreds of UK landlords and letting agents who trust Compliance Vault Pro 
            to manage their property compliance.
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/intake/start">
              Get Started
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default HomePage;
