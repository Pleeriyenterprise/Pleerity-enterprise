/**
 * Dynamic Service Detail Page
 * Fetches service details from the V2 Service Catalogue API.
 * Falls back to static data for legacy slugs.
 */
import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead, createServiceSchema } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Sparkles,
  Building2,
  FileText,
  ClipboardCheck,
  ArrowRight,
  CheckCircle2,
  Clock,
  Shield,
  Zap,
  Package,
  Loader2,
} from 'lucide-react';
import client from '../../api/client';

// Map service codes to icons
const SERVICE_ICONS = {
  AI_WF_BLUEPRINT: Sparkles,
  AI_PROC_MAP: Sparkles,
  AI_TOOL_REPORT: Sparkles,
  MR_BASIC: Building2,
  MR_ADV: Building2,
  HMO_AUDIT: ClipboardCheck,
  FULL_AUDIT: ClipboardCheck,
  MOVE_CHECKLIST: ClipboardCheck,
  DOC_PACK_ESSENTIAL: FileText,
  DOC_PACK_TENANCY: FileText,
  DOC_PACK_ULTIMATE: FileText,
};

// Map categories to colors
const CATEGORY_COLORS = {
  ai_automation: 'bg-purple-500',
  market_research: 'bg-blue-500',
  compliance: 'bg-amber-500',
  document_pack: 'bg-green-500',
};

// Map slug to service code (for backward compatibility)
const SLUG_TO_CODE = {
  'ai-workflow-automation': 'AI_WF_BLUEPRINT',
  'ai-process-mapping': 'AI_PROC_MAP',
  'ai-tool-report': 'AI_TOOL_REPORT',
  'market-research': 'MR_BASIC',
  'market-research-advanced': 'MR_ADV',
  'compliance-audits': 'FULL_AUDIT',
  'hmo-audit': 'HMO_AUDIT',
  'document-packs': 'DOC_PACK_ESSENTIAL',
};

// Static fallback data for legacy pages
const staticFallbackData = {
  'ai-workflow-automation': {
    title: 'AI Workflow Automation',
    description: 'Automate repetitive property management tasks with intelligent AI-powered workflows.',
    longDescription: 'Our AI workflow automation service helps property managers and landlords eliminate manual, repetitive tasks. From document processing to tenant communications, our intelligent systems handle the heavy lifting.',
    features: [
      { title: 'Document Processing', description: 'Automatically extract, categorize, and file incoming documents.' },
      { title: 'Email Automation', description: 'Smart email responses and templated communications.' },
      { title: 'Report Generation', description: 'Automated compliance and portfolio reports.' },
      { title: 'Reminder Scheduling', description: 'Intelligent deadline tracking and alerts.' },
    ],
    benefits: ['Save 10+ hours per week', 'Reduce human error', 'Never miss deadlines', '24/7 processing'],
    pricing: '£79',
    category: 'ai_automation',
  },
  'market-research': {
    title: 'Market Research',
    description: 'Get comprehensive property market insights and area analysis.',
    longDescription: 'Make data-driven property investment decisions with our comprehensive market research service. We analyze local markets, rental yields, demographics, and trends.',
    features: [
      { title: 'Area Analysis', description: 'Detailed neighborhood reports.' },
      { title: 'Rental Yield Reports', description: 'Current and projected yields.' },
      { title: 'Competitor Analysis', description: 'Market positioning insights.' },
      { title: 'Investment Scoring', description: 'Proprietary scoring system.' },
    ],
    benefits: ['Confident decisions', 'Identify opportunities', 'Optimize pricing', 'Reduce risk'],
    pricing: 'From £69',
    category: 'market_research',
  },
  'document-packs': {
    title: 'Document Packs',
    description: 'Professional, legally-compliant document packs for landlords.',
    longDescription: 'Save time and ensure legal compliance with our professionally prepared document packs. Reviewed by legal experts and regularly updated.',
    features: [
      { title: 'Tenancy Agreements', description: 'AST agreements compliant with legislation.' },
      { title: 'Inventory Reports', description: 'Detailed check-in/check-out documentation.' },
      { title: 'Notices', description: 'Section 21/8 and other notices.' },
      { title: 'Reference Templates', description: 'Tenant reference templates.' },
    ],
    benefits: ['Legally compliant', 'Regular updates', 'Professional presentation', 'Ready to use'],
    pricing: 'From £29',
    category: 'document_pack',
  },
  'compliance-audits': {
    title: 'Compliance Audits',
    description: 'Comprehensive property compliance audits.',
    longDescription: 'Ensure your properties meet all regulatory requirements with our professional compliance audit service. Our experts review against current legislation.',
    features: [
      { title: 'HMO Audits', description: 'Full HMO licensing compliance review.' },
      { title: 'Full Property Audits', description: 'Comprehensive assessment.' },
      { title: 'Gap Analysis', description: 'Identify missing certificates.' },
      { title: 'Council Liaison', description: 'Support with applications.' },
    ],
    benefits: ['Avoid enforcement action', 'Expert guidance', 'Peace of mind', 'Clear action plans'],
    pricing: 'From £79',
    category: 'compliance',
  },
};

function LoadingState() {
  return (
    <PublicLayout>
      <section className="py-32 text-center">
        <Loader2 className="h-12 w-12 animate-spin mx-auto text-teal-500" />
        <p className="mt-4 text-gray-600">Loading service details...</p>
      </section>
    </PublicLayout>
  );
}

function NotFoundState() {
  return (
    <PublicLayout>
      <section className="py-32 text-center">
        <Package className="h-16 w-16 mx-auto text-gray-300 mb-4" />
        <h1 className="text-3xl font-bold text-midnight-blue mb-4">Service Not Found</h1>
        <p className="text-gray-600 mb-8">The service you&apos;re looking for doesn&apos;t exist.</p>
        <Button asChild className="bg-electric-teal hover:bg-electric-teal/90">
          <Link to="/services/catalogue">View All Services</Link>
        </Button>
      </section>
    </PublicLayout>
  );
}

const ServiceDetailPage = () => {
  const { serviceSlug } = useParams();
  const navigate = useNavigate();
  const [service, setService] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchService = async () => {
      setLoading(true);
      setError(null);
      
      // Try to map slug to service code
      const serviceCode = SLUG_TO_CODE[serviceSlug] || serviceSlug?.toUpperCase().replace(/-/g, '_');
      
      try {
        // Try V2 API first
        const response = await client.get(`/public/v2/services/${serviceCode}`);
        const data = response.data;
        
        // Transform API data to component format
        setService({
          code: data.service_code,
          title: data.service_name,
          description: data.description,
          longDescription: data.long_description || data.description,
          category: data.category,
          pricing: `£${(data.base_price / 100).toFixed(data.base_price % 100 === 0 ? 0 : 2)}`,
          turnaround: data.turnaround_hours 
            ? `${data.turnaround_hours} hours` 
            : data.standard_turnaround_hours 
              ? `${data.standard_turnaround_hours} hours`
              : 'Standard delivery',
          features: (data.documents_generated || []).map(doc => ({
            title: doc.template_name,
            description: `${doc.format?.toUpperCase() || 'Document'} format`,
          })),
          benefits: [
            'Professional quality documents',
            'Legally compliant content',
            'Fast turnaround time',
            'Digital delivery',
          ],
          fastTrack: data.fast_track_available,
          fastTrackPrice: data.fast_track_price,
          printedCopy: data.printed_copy_available,
          printedCopyPrice: data.printed_copy_price,
          fromApi: true,
        });
      } catch (apiError) {
        console.log('V2 API not available, using fallback:', apiError);
        
        // Try static fallback
        const fallback = staticFallbackData[serviceSlug];
        if (fallback) {
          setService({
            ...fallback,
            code: serviceCode,
            fromApi: false,
          });
        } else {
          setError('Service not found');
        }
      } finally {
        setLoading(false);
      }
    };

    if (serviceSlug) {
      fetchService();
    }
  }, [serviceSlug]);

  if (loading) return <LoadingState />;
  if (error || !service) return <NotFoundState />;

  const IconComponent = SERVICE_ICONS[service.code] || FileText;
  const categoryColor = CATEGORY_COLORS[service.category] || 'bg-teal-500';

  return (
    <PublicLayout>
      <SEOHead
        title={`${service.title} - Pleerity Enterprise`}
        description={service.description}
        canonicalUrl={`/services/${serviceSlug}`}
        schema={createServiceSchema(service.title, service.description)}
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl">
            <div className={`w-16 h-16 ${categoryColor} rounded-xl flex items-center justify-center mb-6`}>
              <IconComponent className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold mb-6 text-midnight-blue">
              {service.title}
            </h1>
            <p className="text-xl mb-8 text-gray-600">
              {service.longDescription}
            </p>
            
            {/* Quick Info Badges */}
            <div className="flex flex-wrap gap-3 mb-8">
              <Badge className="bg-teal-100 text-teal-700 px-3 py-1">
                <Clock className="w-4 h-4 mr-1" />
                {service.turnaround || 'Standard delivery'}
              </Badge>
              {service.fastTrack && (
                <Badge className="bg-purple-100 text-purple-700 px-3 py-1">
                  <Zap className="w-4 h-4 mr-1" />
                  Fast Track Available
                </Badge>
              )}
              {service.printedCopy && (
                <Badge className="bg-cyan-100 text-cyan-700 px-3 py-1">
                  <FileText className="w-4 h-4 mr-1" />
                  Printed Copy Option
                </Badge>
              )}
            </div>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <Button
                size="lg"
                className="bg-electric-teal hover:bg-electric-teal/90 text-white"
                asChild
              >
                <Link to={`/order/intake?service=${service.code}`}>
                  Order Now
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Link>
              </Button>
              <Button
                size="lg"
                variant="outline"
                asChild
              >
                <Link to="/contact">Contact Us</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      {service.features && service.features.length > 0 && (
        <section className="py-20 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">
              What&apos;s Included
            </h2>
            <div className="grid md:grid-cols-2 gap-8">
              {service.features.map((feature, index) => (
                <Card key={index} className="border-0 shadow-lg">
                  <CardContent className="p-6">
                    <div className="flex items-start">
                      <div className={`w-10 h-10 ${categoryColor} rounded-lg flex items-center justify-center shrink-0 mr-4`}>
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
      )}

      {/* Benefits & Pricing */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold text-midnight-blue mb-6">
                Why Choose Our {service.title}
              </h2>
              <ul className="space-y-4">
                {service.benefits.map((benefit, index) => (
                  <li key={index} className="flex items-start">
                    <CheckCircle2 className="w-6 h-6 text-electric-teal shrink-0 mr-3 mt-0.5" />
                    <span className="text-lg text-gray-700">{benefit}</span>
                  </li>
                ))}
              </ul>
            </div>
            <Card className="border-0 shadow-xl">
              <CardContent className="p-8">
                <h3 className="text-xl font-bold text-midnight-blue mb-4">Pricing</h3>
                <p className="text-3xl font-bold text-electric-teal mb-2">{service.pricing}</p>
                {service.fastTrack && (
                  <p className="text-sm text-gray-600 mb-2">
                    + £{(service.fastTrackPrice / 100).toFixed(0)} for Fast Track (24hr)
                  </p>
                )}
                {service.printedCopy && (
                  <p className="text-sm text-gray-600 mb-4">
                    + £{(service.printedCopyPrice / 100).toFixed(0)} for Printed Copy
                  </p>
                )}
                <p className="text-gray-600 mb-6">
                  Professional quality, fast delivery, complete satisfaction guaranteed.
                </p>
                <Button 
                  className="w-full bg-electric-teal hover:bg-electric-teal/90" 
                  asChild
                  data-testid="order-now-btn"
                >
                  <Link to={`/order/intake?service=${service.code}`}>Order Now</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Order now and receive your documents within our standard delivery time.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to={`/order/intake?service=${service.code}`}>
                Order Now
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white hover:text-midnight-blue"
              asChild
            >
              <Link to="/services/catalogue">View All Services</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServiceDetailPage;
