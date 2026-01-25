/**
 * Marketing Service Page - CMS-Driven
 * 
 * Individual service detail page with all required sections.
 * Content is fetched from CMS backend with Service Catalogue integration.
 */

import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '../../components/ui/alert';
import {
  ArrowRight,
  ArrowLeft,
  Clock,
  Zap,
  CheckCircle2,
  XCircle,
  FileText,
  Users,
  ListChecks,
  Timer,
  Shield,
  AlertTriangle,
  Info,
} from 'lucide-react';
import client from '../../api/client';

const ServicePageCMS = () => {
  const { categorySlug, serviceSlug } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [serviceData, setServiceData] = useState(null);
  const [isPreview, setIsPreview] = useState(false);

  useEffect(() => {
    const fetchServiceData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const response = await client.get(`/marketing/services/${categorySlug}/${serviceSlug}`);
        
        if (response.data.success) {
          setServiceData(response.data.data);
          setIsPreview(response.data._meta?.show_preview_banner || false);
        } else if (response.data.redirect) {
          navigate(response.data.redirect_to, { replace: true });
        }
      } catch (err) {
        console.error('Failed to fetch service:', err);
        if (err.response?.status === 404) {
          setError('Service not found');
        } else {
          setError('Failed to load service');
        }
      } finally {
        setLoading(false);
      }
    };

    if (categorySlug && serviceSlug) {
      fetchServiceData();
    }
  }, [categorySlug, serviceSlug, navigate]);

  if (loading) {
    return (
      <PublicLayout>
        <div className="py-20">
          <div className="max-w-4xl mx-auto px-4">
            <Skeleton className="h-12 w-3/4 mb-4" />
            <Skeleton className="h-6 w-1/2 mb-8" />
            <Skeleton className="h-40 w-full mb-8" />
            <Skeleton className="h-60 w-full" />
          </div>
        </div>
      </PublicLayout>
    );
  }

  if (error) {
    return (
      <PublicLayout>
        <div className="py-20">
          <div className="max-w-4xl mx-auto px-4 text-center">
            <h1 className="text-3xl font-bold text-midnight-blue mb-4">
              {error}
            </h1>
            <p className="text-gray-600 mb-8">
              The service you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
            <Button asChild>
              <Link to={`/services/${categorySlug}`}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Category
              </Link>
            </Button>
          </div>
        </div>
      </PublicLayout>
    );
  }

  const { page, service, cta_config, category } = serviceData || {};
  
  // Extract service details from catalogue
  const price = service?.base_price || 0;
  const priceDisplay = price > 0 ? `£${(price / 100).toFixed(0)}` : 'Free';
  const turnaround = service?.standard_turnaround_hours || 48;
  const hasFastTrack = service?.fast_track_available || false;
  const fastTrackHours = service?.fast_track_hours || 24;

  return (
    <PublicLayout>
      <SEOHead
        title={`${page?.title || service?.service_name} | Pleerity Enterprise`}
        description={page?.description || service?.description}
        canonicalUrl={`/services/${categorySlug}/${serviceSlug}`}
      />

      {/* Preview Environment Banner */}
      {isPreview && (
        <div className="bg-amber-500 text-white text-center py-2 text-sm font-medium">
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          Preview Environment - Content may not reflect production
        </div>
      )}

      {/* Breadcrumb */}
      <div className="bg-gray-50 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex items-center text-sm text-gray-500">
            <Link to="/services" className="hover:text-electric-teal">
              Services
            </Link>
            <span className="mx-2">/</span>
            <Link to={`/services/${categorySlug}`} className="hover:text-electric-teal">
              {category?.name}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-midnight-blue font-medium">
              {page?.title || service?.service_name}
            </span>
          </nav>
        </div>
      </div>

      {/* Hero Section */}
      <section className="py-12 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-3 gap-12">
            {/* Main Content */}
            <div className="lg:col-span-2">
              <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-4">
                {page?.title || service?.service_name}
              </h1>
              <p className="text-xl text-gray-600 mb-6">
                {page?.subtitle || service?.description}
              </p>
              
              {/* Quick Stats */}
              <div className="flex flex-wrap gap-4 mb-6">
                <Badge variant="secondary" className="text-lg px-4 py-2">
                  {priceDisplay}
                </Badge>
                <Badge variant="outline" className="px-4 py-2">
                  <Clock className="w-4 h-4 mr-2" />
                  {turnaround}h delivery
                </Badge>
                {hasFastTrack && (
                  <Badge variant="outline" className="px-4 py-2 text-amber-600 border-amber-600">
                    <Zap className="w-4 h-4 mr-2" />
                    {fastTrackHours}h Fast Track
                  </Badge>
                )}
              </div>
            </div>

            {/* CTA Card */}
            <div className="lg:col-span-1">
              <Card className="sticky top-24 border-2 border-electric-teal/20">
                <CardHeader className="bg-electric-teal/5">
                  <CardTitle className="text-2xl text-midnight-blue">
                    {priceDisplay}
                  </CardTitle>
                  <p className="text-gray-600">One-time purchase</p>
                </CardHeader>
                <CardContent className="pt-6 space-y-4">
                  {cta_config?.requires_cvp_message && (
                    <Alert>
                      <Info className="h-4 w-4" />
                      <AlertDescription>
                        {cta_config.requires_cvp_message}
                      </AlertDescription>
                    </Alert>
                  )}
                  
                  {cta_config?.primary_cta && (
                    <Button
                      size="lg"
                      className="w-full bg-electric-teal hover:bg-electric-teal/90"
                      asChild
                    >
                      <Link to={cta_config.primary_cta.url}>
                        {cta_config.primary_cta.label}
                        <ArrowRight className="w-5 h-5 ml-2" />
                      </Link>
                    </Button>
                  )}
                  
                  {cta_config?.secondary_cta && (
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full"
                      asChild
                    >
                      <Link to={cta_config.secondary_cta.url}>
                        {cta_config.secondary_cta.label}
                      </Link>
                    </Button>
                  )}

                  <div className="pt-4 border-t text-sm text-gray-500">
                    <div className="flex items-center mb-2">
                      <CheckCircle2 className="w-4 h-4 mr-2 text-green-500" />
                      Secure checkout
                    </div>
                    <div className="flex items-center">
                      <CheckCircle2 className="w-4 h-4 mr-2 text-green-500" />
                      Instant access to intake form
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* Service Overview */}
      <section className="py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <FileText className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              Service Overview
            </h2>
          </div>
          <p className="text-gray-600 text-lg leading-relaxed">
            {service?.long_description || service?.description}
          </p>
        </div>
      </section>

      {/* Who It's For */}
      <section className="py-12 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <Users className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              Who It&apos;s For
            </h2>
          </div>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold text-midnight-blue mb-4">Ideal for:</h3>
              <ul className="space-y-3">
                {(service?.tags || ['Landlords', 'Property Managers', 'Letting Agents']).map((item, i) => (
                  <li key={i} className="flex items-start">
                    <CheckCircle2 className="w-5 h-5 mr-3 text-green-500 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-600">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* What You Receive */}
      <section className="py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <ListChecks className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              What You Receive
            </h2>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {(service?.documents_generated || []).map((doc, i) => (
              <Card key={i} className="border-l-4 border-l-electric-teal">
                <CardContent className="py-4">
                  <div className="flex items-start">
                    <FileText className="w-5 h-5 mr-3 text-electric-teal flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-midnight-blue">
                        {doc.template_name}
                      </h4>
                      <p className="text-sm text-gray-500">
                        Format: {doc.format?.toUpperCase() || 'PDF'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-12 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <ListChecks className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              How It Works
            </h2>
          </div>
          <div className="space-y-6">
            {[
              { step: 1, title: 'Complete the Intake Form', desc: 'Provide the required information about your needs.' },
              { step: 2, title: 'Payment & Processing', desc: 'Secure payment followed by AI-powered document generation.' },
              { step: 3, title: 'Review & Delivery', desc: 'Documents are reviewed for quality and delivered to your portal.' },
            ].map((item) => (
              <div key={item.step} className="flex items-start">
                <div className="w-10 h-10 rounded-full bg-electric-teal text-white flex items-center justify-center font-bold flex-shrink-0">
                  {item.step}
                </div>
                <div className="ml-4">
                  <h4 className="font-semibold text-midnight-blue">{item.title}</h4>
                  <p className="text-gray-600">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Timeline */}
      <section className="py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <Timer className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              Timeline
            </h2>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardContent className="py-6">
                <div className="flex items-center">
                  <Clock className="w-8 h-8 mr-4 text-electric-teal" />
                  <div>
                    <h4 className="font-semibold text-midnight-blue">Standard Delivery</h4>
                    <p className="text-2xl font-bold text-electric-teal">{turnaround} hours</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            {hasFastTrack && (
              <Card className="border-amber-200 bg-amber-50">
                <CardContent className="py-6">
                  <div className="flex items-center">
                    <Zap className="w-8 h-8 mr-4 text-amber-600" />
                    <div>
                      <h4 className="font-semibold text-midnight-blue">Fast Track</h4>
                      <p className="text-2xl font-bold text-amber-600">{fastTrackHours} hours</p>
                      <p className="text-sm text-gray-500">+£{(service?.fast_track_price || 2000) / 100}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </section>

      {/* Important Notes / Disclaimers */}
      <section className="py-12 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center mb-6">
            <Shield className="w-6 h-6 mr-3 text-electric-teal" />
            <h2 className="text-2xl font-bold text-midnight-blue">
              Important Notes
            </h2>
          </div>
          <Alert>
            <Info className="h-4 w-4" />
            <AlertTitle>This service provides guidance only</AlertTitle>
            <AlertDescription>
              Our documents and reports provide professional guidance but do not constitute legal advice. 
              For specific legal requirements, please consult a qualified solicitor.
            </AlertDescription>
          </Alert>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to get started?
          </h2>
          <p className="text-gray-300 mb-8 text-lg">
            Complete our simple intake form and receive your documents within {turnaround} hours.
          </p>
          {cta_config?.primary_cta && (
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to={cta_config.primary_cta.url}>
                {cta_config.primary_cta.label}
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
          )}
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServicePageCMS;
