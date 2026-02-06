/**
 * Marketing Services Hub - CMS-Driven
 * 
 * Main entry point for the services marketing website.
 * Content is fetched from CMS backend.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { Alert, AlertDescription } from '../../components/ui/alert';
import {
  Cpu,
  BarChart2,
  ShieldCheck,
  FileText,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react';
import client from '../../api/client';

// Icon mapping for categories
const CATEGORY_ICONS = {
  'cpu': Cpu,
  'bar-chart-2': BarChart2,
  'shield-check': ShieldCheck,
  'file-text': FileText,
};

// Default categories in case CMS data not loaded
const DEFAULT_CATEGORIES = [
  {
    slug: 'ai-automation',
    name: 'AI & Automation Services',
    tagline: 'Streamline your operations with intelligent automation solutions',
    icon: 'cpu',
    path: '/services/ai-automation',
  },
  {
    slug: 'market-research',
    name: 'Market Research Services',
    tagline: 'Data-driven insights to inform your business decisions',
    icon: 'bar-chart-2',
    path: '/services/market-research',
  },
  {
    slug: 'compliance-audits',
    name: 'Compliance & Audit Services',
    tagline: 'Ensure your properties meet regulatory requirements',
    icon: 'shield-check',
    path: '/services/compliance-audits',
  },
  {
    slug: 'document-packs',
    name: 'Landlord Document Packs',
    tagline: 'Professional documentation for property management',
    icon: 'file-text',
    path: '/services/document-packs',
  },
];

const CategoryCard = ({ category }) => {
  const IconComponent = CATEGORY_ICONS[category.icon] || FileText;
  
  return (
    <Link to={category.full_path || category.path || `/services/${category.slug}`}>
      <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer group border-2 border-transparent hover:border-electric-teal">
        <CardHeader>
          <div className="w-12 h-12 rounded-lg bg-electric-teal/10 flex items-center justify-center mb-4 group-hover:bg-electric-teal/20 transition-colors">
            <IconComponent className="w-6 h-6 text-electric-teal" />
          </div>
          <CardTitle className="text-xl font-semibold text-midnight-blue group-hover:text-electric-teal transition-colors">
            {category.name || category.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600 mb-4">
            {category.tagline || category.description}
          </p>
          <div className="flex items-center text-electric-teal font-medium">
            Explore Services
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
};

const ServicesHubPageCMS = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hubData, setHubData] = useState(null);
  const [categories, setCategories] = useState(DEFAULT_CATEGORIES);
  const [isPreview, setIsPreview] = useState(false);

  useEffect(() => {
    const fetchHubData = async () => {
      try {
        setLoading(true);
        const response = await client.get('/marketing/services');
        
        if (response.data.success) {
          setHubData(response.data.data);
          if (response.data.data.categories?.length > 0) {
            setCategories(response.data.data.categories);
          }
          setIsPreview(response.data._meta?.show_preview_banner || false);
        }
      } catch (err) {
        console.error('Failed to fetch services hub:', err);
        // Use default categories on error
        setError('Using default content');
      } finally {
        setLoading(false);
      }
    };

    fetchHubData();
  }, []);

  // Get page content from CMS or use defaults
  const pageTitle = hubData?.page?.title || 'Our Services';
  const pageSubtitle = hubData?.page?.subtitle || 'Professional business services to help you grow and succeed';

  return (
    <PublicLayout>
      <SEOHead
        title="Services | Pleerity Enterprise"
        description="Explore our professional services: AI automation, market research, compliance audits, and document packs for landlords and businesses."
        canonicalUrl="/services"
      />

      {/* Preview Environment Banner */}
      {isPreview && (
        <div className="bg-amber-500 text-white text-center py-2 text-sm font-medium">
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          Preview Environment - Content may not reflect production
        </div>
      )}

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              {pageTitle}
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              {pageSubtitle}
            </p>
          </div>
        </div>
      </section>

      {/* Categories Grid */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-midnight-blue mb-8 text-center">
            Service Categories
          </h2>
          
          {loading ? (
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              {[1, 2, 3, 4].map((i) => (
                <Card key={i} className="h-full">
                  <CardHeader>
                    <Skeleton className="w-12 h-12 rounded-lg mb-4" />
                    <Skeleton className="h-6 w-3/4" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-4 w-full mb-2" />
                    <Skeleton className="h-4 w-2/3" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              {categories.map((category) => (
                <CategoryCard key={category.slug} category={category} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Not sure which service you need?
          </h2>
          <p className="text-gray-300 mb-8 text-lg">
            Our team can help you identify the right solution for your business needs.
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/contact">
              Contact Us
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServicesHubPageCMS;
