/**
 * Marketing Category Page - CMS-Driven
 * 
 * Displays a service category with all its services.
 * Content is fetched from CMS backend.
 */

import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Cpu,
  BarChart2,
  ShieldCheck,
  FileText,
  ArrowRight,
  ArrowLeft,
  Clock,
  Zap,
  AlertTriangle,
  Lock,
} from 'lucide-react';
import client from '../../api/client';

// Icon mapping
const CATEGORY_ICONS = {
  'cpu': Cpu,
  'bar-chart-2': BarChart2,
  'shield-check': ShieldCheck,
  'file-text': FileText,
};

const ServiceCard = ({ service, categorySlug }) => {
  const price = service.pricing?.base_price || service.price || 0;
  const priceDisplay = price > 0 ? `£${(price / 100).toFixed(0)}` : 'Free';
  
  return (
    <Link to={service.full_path || `/services/${categorySlug}/${service.slug}`}>
      <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer group border-2 border-transparent hover:border-electric-teal">
        <CardHeader>
          <div className="flex justify-between items-start mb-2">
            <CardTitle className="text-xl font-semibold text-midnight-blue group-hover:text-electric-teal transition-colors">
              {service.title}
            </CardTitle>
            <Badge variant="secondary" className="text-lg font-bold">
              {priceDisplay}
            </Badge>
          </div>
          {service.requires_cvp && (
            <Badge variant="outline" className="w-fit">
              <Lock className="w-3 h-3 mr-1" />
              CVP Required
            </Badge>
          )}
        </CardHeader>
        <CardContent>
          <CardDescription className="text-gray-600 mb-4 line-clamp-2">
            {service.description || service.subtitle}
          </CardDescription>
          
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div className="flex items-center gap-4">
              {service.turnaround_hours && (
                <span className="flex items-center">
                  <Clock className="w-4 h-4 mr-1" />
                  {service.turnaround_hours}h
                </span>
              )}
              {service.fast_track_available && (
                <span className="flex items-center text-amber-600">
                  <Zap className="w-4 h-4 mr-1" />
                  Fast Track
                </span>
              )}
            </div>
            <ArrowRight className="w-4 h-4 text-electric-teal group-hover:translate-x-1 transition-transform" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
};

const CategoryPageCMS = () => {
  const { categorySlug } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [categoryData, setCategoryData] = useState(null);
  const [isPreview, setIsPreview] = useState(false);

  useEffect(() => {
    const fetchCategoryData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const response = await client.get(`/marketing/services/category/${categorySlug}`);
        
        if (response.data.success) {
          setCategoryData(response.data.data);
          setIsPreview(response.data._meta?.show_preview_banner || false);
        } else if (response.data.redirect) {
          navigate(response.data.redirect_to, { replace: true });
        }
      } catch (err) {
        console.error('Failed to fetch category:', err);
        if (err.response?.status === 404) {
          setError('Category not found');
        } else {
          setError('Failed to load category');
        }
      } finally {
        setLoading(false);
      }
    };

    if (categorySlug) {
      fetchCategoryData();
    }
  }, [categorySlug, navigate]);

  if (loading) {
    return (
      <PublicLayout>
        <div className="py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <Skeleton className="h-12 w-1/2 mx-auto mb-4" />
            <Skeleton className="h-6 w-2/3 mx-auto mb-12" />
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-3/4 mb-2" />
                    <Skeleton className="h-4 w-1/4" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-4 w-full mb-2" />
                    <Skeleton className="h-4 w-2/3" />
                  </CardContent>
                </Card>
              ))}
            </div>
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
              The category you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
            <Button asChild>
              <Link to="/services">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Services
              </Link>
            </Button>
          </div>
        </div>
      </PublicLayout>
    );
  }

  const { page, category_config, services } = categoryData || {};
  const IconComponent = CATEGORY_ICONS[category_config?.icon] || FileText;

  return (
    <PublicLayout>
      <SEOHead
        title={`${page?.title || category_config?.name} | Pleerity Enterprise`}
        description={page?.description || category_config?.description}
        canonicalUrl={`/services/${categorySlug}`}
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
            <span className="text-midnight-blue font-medium">
              {page?.title || category_config?.name}
            </span>
          </nav>
        </div>
      </div>

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <div className="w-16 h-16 rounded-xl bg-electric-teal/10 flex items-center justify-center mx-auto mb-6">
              <IconComponent className="w-8 h-8 text-electric-teal" />
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-4">
              {page?.title || category_config?.name}
            </h1>
            <p className="text-xl text-gray-600">
              {page?.subtitle || category_config?.tagline}
            </p>
          </div>
        </div>
      </section>

      {/* Services Grid */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-midnight-blue mb-8">
            Available Services
          </h2>
          
          {services && services.length > 0 ? (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {services.map((service) => (
                <ServiceCard 
                  key={service.slug} 
                  service={service} 
                  categorySlug={categorySlug}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <p className="text-gray-500">
                No services available in this category yet.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Category Description */}
      {(page?.description || category_config?.description) && (
        <section className="py-16 bg-gray-50">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">
              About {page?.title || category_config?.name}
            </h2>
            <p className="text-gray-600 text-lg leading-relaxed">
              {page?.description || category_config?.description}
            </p>
          </div>
        </section>
      )}

      {/* CTA Section */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Need help choosing?
          </h2>
          <p className="text-gray-300 mb-8 text-lg">
            Our team can help you find the right service for your specific needs.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/contact">
                Contact Us
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white/10"
              asChild
            >
              <Link to="/services">
                View All Categories
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CategoryPageCMS;
