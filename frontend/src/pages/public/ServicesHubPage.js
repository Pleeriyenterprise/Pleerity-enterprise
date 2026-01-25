import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import {
  Sparkles,
  Building2,
  FileText,
  ClipboardCheck,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

const ServicesHubPage = () => {
  const services = [
    {
      href: '/services/ai-automation',
      icon: Sparkles,
      title: 'AI & Automation',
      description: 'Automate repetitive property management tasks with intelligent AI-powered workflows. Save time and reduce errors.',
      features: ['Document Processing', 'Email Automation', 'Report Generation'],
      color: 'bg-purple-500',
    },
    {
      href: '/services/market-research',
      icon: Building2,
      title: 'Market Research',
      description: 'Get comprehensive property market insights and area analysis to make informed investment decisions.',
      features: ['Area Analysis', 'Rental Yields', 'Market Trends'],
      color: 'bg-blue-500',
    },
    {
      href: '/services/document-packs',
      icon: FileText,
      title: 'Document Packs',
      description: 'Professional, legally-compliant document packs for tenancies, inventories, and property management.',
      features: ['Tenancy Agreements', 'Inventory Reports', 'Legal Documents'],
      color: 'bg-green-500',
    },
    {
      href: '/services/compliance-audits',
      icon: ClipboardCheck,
      title: 'Compliance Audits',
      description: 'Comprehensive property compliance audits including HMO licensing reviews and full property assessments.',
      features: ['HMO Audits', 'Full Audits', 'Gap Analysis'],
      color: 'bg-amber-500',
    },
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Property Compliance Services"
        description="Professional compliance services for UK landlords: AI workflow automation, market research, document packs, and compliance audits."
        canonicalUrl="/services"
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Professional Property Services
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Beyond compliance management, we offer a complete range of professional services 
              to support your property business from start to finish.
            </p>
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/booking">
                Discuss Your Needs
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Main Services */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-8">
            {services.filter(s => !s.separate).map((service) => (
              <Link
                key={service.href}
                to={service.href}
                className="group"
                data-testid={`service-card-${service.title.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <Card className="h-full border-0 shadow-lg hover:shadow-xl transition-all hover:-translate-y-1">
                  <CardContent className="p-8">
                    <div className={`w-14 h-14 ${service.color} rounded-xl flex items-center justify-center mb-6`}>
                      <service.icon className="w-7 h-7 text-white" />
                    </div>
                    <h2 className="text-2xl font-bold text-midnight-blue mb-3">{service.title}</h2>
                    <p className="text-gray-600 mb-6">{service.description}</p>
                    <div className="flex flex-wrap gap-2 mb-6">
                      {service.features.map((feature) => (
                        <span
                          key={feature}
                          className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 text-gray-700 text-sm"
                        >
                          <CheckCircle2 className="w-3 h-3 mr-1 text-electric-teal" />
                          {feature}
                        </span>
                      ))}
                    </div>
                    <span className="inline-flex items-center text-electric-teal font-medium">
                      Learn more
                      <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Need Help Choosing?
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Book a free consultation and we will help you find the right services for your properties.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/booking">Book a Consultation</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white hover:text-midnight-blue"
              asChild
            >
              <Link to="/contact">Contact Us</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServicesHubPage;
