import React from 'react';
import { Link, useParams } from 'react-router-dom';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead, createServiceSchema } from '../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
  Sparkles,
  Building2,
  FileText,
  ClipboardCheck,
  Brush,
  ArrowRight,
  CheckCircle2,
  Clock,
  Shield,
  Zap,
} from 'lucide-react';

// Service data
const serviceData = {
  'ai-workflow-automation': {
    title: 'AI Workflow Automation',
    description: 'Automate repetitive property management tasks with intelligent AI-powered workflows. Save time and reduce errors.',
    longDescription: 'Our AI workflow automation service helps property managers and landlords eliminate manual, repetitive tasks. From document processing to tenant communications, our intelligent systems handle the heavy lifting so you can focus on what matters.',
    icon: Sparkles,
    color: 'bg-purple-500',
    features: [
      { title: 'Document Processing', description: 'Automatically extract, categorize, and file incoming documents.' },
      { title: 'Email Automation', description: 'Smart email responses and templated communications.' },
      { title: 'Report Generation', description: 'Automated compliance and portfolio reports.' },
      { title: 'Reminder Scheduling', description: 'Intelligent deadline tracking and alerts.' },
    ],
    benefits: [
      'Save 10+ hours per week on admin tasks',
      'Reduce human error in document handling',
      'Never miss a compliance deadline',
      '24/7 automated processing',
    ],
    pricing: 'Custom pricing based on portfolio size',
    cta: 'Book a consultation to discuss your automation needs',
  },
  'market-research': {
    title: 'Market Research',
    description: 'Get comprehensive property market insights and area analysis to make informed investment decisions.',
    longDescription: 'Make data-driven property investment decisions with our comprehensive market research service. We analyze local markets, rental yields, demographics, and trends to give you the insights you need.',
    icon: Building2,
    color: 'bg-blue-500',
    features: [
      { title: 'Area Analysis', description: 'Detailed neighborhood reports including demographics and amenities.' },
      { title: 'Rental Yield Reports', description: 'Current and projected rental yields for target areas.' },
      { title: 'Competitor Analysis', description: 'See what similar properties are achieving in your market.' },
      { title: 'Investment Scoring', description: 'Our proprietary scoring system rates investment potential.' },
    ],
    benefits: [
      'Make confident investment decisions',
      'Identify undervalued areas',
      'Optimize rental pricing',
      'Reduce investment risk',
    ],
    pricing: 'From £149 per report',
    cta: 'Request a market research report',
  },
  'document-packs': {
    title: 'Document Packs',
    description: 'Professional, legally-compliant document packs for tenancies, inventories, and property management.',
    longDescription: 'Save time and ensure legal compliance with our professionally prepared document packs. From tenancy agreements to inventory reports, our documents are reviewed by legal experts and updated regularly.',
    icon: FileText,
    color: 'bg-green-500',
    features: [
      { title: 'Tenancy Agreements', description: 'AST agreements compliant with current legislation.' },
      { title: 'Inventory Reports', description: 'Detailed check-in/check-out documentation with photos.' },
      { title: 'Section 21/8 Notices', description: 'Properly formatted eviction notices.' },
      { title: 'Reference Templates', description: 'Tenant reference request and response templates.' },
    ],
    benefits: [
      'Legally compliant documents',
      'Regularly updated for legislation changes',
      'Professional presentation',
      'Ready to use immediately',
    ],
    pricing: 'From £29 per pack',
    cta: 'Browse our document packs',
  },
  'compliance-audits': {
    title: 'Compliance Audits',
    description: 'Comprehensive property compliance audits including HMO licensing reviews and full property assessments.',
    longDescription: 'Ensure your properties meet all regulatory requirements with our professional compliance audit service. Our experts review your property against current legislation and provide actionable recommendations.',
    icon: ClipboardCheck,
    color: 'bg-amber-500',
    features: [
      { title: 'HMO Audits', description: 'Full HMO licensing compliance review with room measurements.' },
      { title: 'Full Property Audits', description: 'Comprehensive assessment of all compliance requirements.' },
      { title: 'Gap Analysis', description: 'Identify missing certificates and upcoming requirements.' },
      { title: 'Council Liaison', description: 'Support with licensing applications and council queries.' },
    ],
    benefits: [
      'Avoid costly enforcement action',
      'Expert guidance on complex regulations',
      'Peace of mind before inspections',
      'Clear action plans for compliance',
    ],
    pricing: 'From £199 for HMO audit, £299 for full audit',
    cta: 'Book a compliance audit',
    subpages: [
      { href: '/services/compliance-audits/hmo', label: 'HMO Audit' },
      { href: '/services/compliance-audits/full', label: 'Full Audit' },
    ],
  },
  'cleaning': {
    title: 'Cleaning Services',
    description: 'Professional property cleaning services for end-of-tenancy, deep cleans, and regular maintenance.',
    longDescription: 'Our professional cleaning service ensures your properties are presented to the highest standard. Whether you need an end-of-tenancy clean or regular maintenance, our trained teams deliver consistent quality.',
    icon: Brush,
    color: 'bg-teal-500',
    features: [
      { title: 'End of Tenancy', description: 'Thorough clean meeting deposit scheme standards.' },
      { title: 'Deep Clean', description: 'Intensive cleaning for neglected properties.' },
      { title: 'Regular Service', description: 'Scheduled cleaning for HMO common areas.' },
      { title: 'Post-Renovation', description: 'Builder\'s clean after property works.' },
    ],
    benefits: [
      'Deposit scheme approved standards',
      'Insured and vetted cleaners',
      'Flexible scheduling',
      'Satisfaction guaranteed',
    ],
    pricing: 'From £149 for end-of-tenancy (1-bed)',
    cta: 'Get a cleaning quote',
    separate: true,
  },
};

const ServiceDetailPage = () => {
  const { serviceSlug } = useParams();
  const service = serviceData[serviceSlug];

  if (!service) {
    return (
      <PublicLayout>
        <section className="py-32 text-center">
          <h1 className="text-3xl font-bold text-midnight-blue mb-4">Service Not Found</h1>
          <p className="text-gray-600 mb-8">The service you're looking for doesn't exist.</p>
          <Button asChild>
            <Link to="/services">View All Services</Link>
          </Button>
        </section>
      </PublicLayout>
    );
  }

  const IconComponent = service.icon;

  return (
    <PublicLayout>
      <SEOHead
        title={`${service.title} - Pleerity Enterprise`}
        description={service.description}
        canonicalUrl={`/services/${serviceSlug}`}
        schema={createServiceSchema(service.title, service.description)}
      />

      {/* Hero Section */}
      <section className={`py-20 ${service.separate ? 'bg-gradient-to-br from-teal-500 to-teal-600' : 'bg-gradient-to-b from-gray-50 to-white'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl">
            <div className={`w-16 h-16 ${service.separate ? 'bg-white/20' : service.color} rounded-xl flex items-center justify-center mb-6`}>
              <IconComponent className={`w-8 h-8 ${service.separate ? 'text-white' : 'text-white'}`} />
            </div>
            <h1 className={`text-4xl sm:text-5xl font-bold mb-6 ${service.separate ? 'text-white' : 'text-midnight-blue'}`}>
              {service.title}
            </h1>
            <p className={`text-xl mb-8 ${service.separate ? 'text-white/90' : 'text-gray-600'}`}>
              {service.longDescription}
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Button
                size="lg"
                className={service.separate ? 'bg-white text-teal-600 hover:bg-white/90' : 'bg-electric-teal hover:bg-electric-teal/90 text-white'}
                asChild
              >
                <Link to="/booking">
                  Get Started
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Link>
              </Button>
              <Button
                size="lg"
                variant="outline"
                className={service.separate ? 'border-white text-white hover:bg-white hover:text-teal-600' : ''}
                asChild
              >
                <Link to="/contact">Contact Us</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">
            What's Included
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            {service.features.map((feature) => (
              <Card key={feature.title} className="border-0 shadow-lg">
                <CardContent className="p-6">
                  <div className="flex items-start">
                    <div className={`w-10 h-10 ${service.color} rounded-lg flex items-center justify-center shrink-0 mr-4`}>
                      <CheckCircle2 className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-midnight-blue mb-2">{feature.title}</h3>
                      <p className="text-gray-600">{feature.description}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold text-midnight-blue mb-6">
                Why Choose Our {service.title}
              </h2>
              <ul className="space-y-4">
                {service.benefits.map((benefit) => (
                  <li key={benefit} className="flex items-start">
                    <CheckCircle2 className="w-6 h-6 text-electric-teal shrink-0 mr-3 mt-0.5" />
                    <span className="text-lg text-gray-700">{benefit}</span>
                  </li>
                ))}
              </ul>
            </div>
            <Card className="border-0 shadow-xl">
              <CardContent className="p-8">
                <h3 className="text-xl font-bold text-midnight-blue mb-4">Pricing</h3>
                <p className="text-2xl font-bold text-electric-teal mb-4">{service.pricing}</p>
                <p className="text-gray-600 mb-6">{service.cta}</p>
                <Button className="w-full bg-electric-teal hover:bg-electric-teal/90" asChild>
                  <Link to="/booking">Book Now</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Sub-pages for Compliance Audits */}
      {service.subpages && (
        <section className="py-16 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-bold text-midnight-blue mb-8 text-center">
              Choose Your Audit Type
            </h2>
            <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto">
              {service.subpages.map((subpage) => (
                <Link key={subpage.href} to={subpage.href}>
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                    <CardContent className="p-6 text-center">
                      <h3 className="text-lg font-semibold text-midnight-blue">{subpage.label}</h3>
                      <ArrowRight className="w-5 h-5 mx-auto mt-2 text-electric-teal" />
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Book a consultation to discuss your requirements and get a personalized quote.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/booking">Book Consultation</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white hover:text-midnight-blue"
              asChild
            >
              <Link to="/services">View All Services</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServiceDetailPage;
