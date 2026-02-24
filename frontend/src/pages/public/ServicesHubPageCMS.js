/**
 * Platforms & Professional Services
 *
 * Clear hierarchy: Technology Platforms (CVP dominant) and Professional Support Services.
 * Compliance-safe language throughout.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Cpu,
  BarChart2,
  ShieldCheck,
  FileText,
  ArrowRight,
  AlertTriangle,
  LayoutGrid,
  Briefcase,
} from 'lucide-react';
import client from '../../api/client';

// Technology platforms: CVP primary, others secondary (coming soon)
const PLATFORMS = [
  {
    id: 'cvp',
    name: 'Compliance Vault Pro',
    description: 'Structured compliance tracking and expiry monitoring for landlords.',
    cta: 'View Platform',
    href: '/compliance-vault-pro',
    primary: true,
  },
  {
    id: 'clearform',
    name: 'ClearForm',
    description: 'AI-powered structured document generation.',
    comingSoon: true,
    primary: false,
  },
  {
    id: 'assurestack',
    name: 'AssureStack',
    description: 'Continuous monitoring and risk oversight.',
    comingSoon: true,
    primary: false,
  },
];

// Professional support services — compliance-safe wording only
const PROFESSIONAL_SERVICES = [
  {
    slug: 'compliance-audits',
    name: 'Compliance Audits',
    description: 'Structured review and reporting to support your compliance oversight.',
    icon: ShieldCheck,
    path: '/services/compliance-audits',
  },
  {
    slug: 'document-packs',
    name: 'Landlord Document Packs',
    description: 'Documentation preparation and pack assembly for property management.',
    icon: FileText,
    path: '/services/document-packs',
  },
  {
    slug: 'ai-automation',
    name: 'AI & Automation',
    description: 'Intelligent automation to streamline operations and document handling.',
    icon: Cpu,
    path: '/services/ai-automation',
  },
  {
    slug: 'market-research',
    name: 'Market Research',
    description: 'Data-driven insights to inform business and portfolio decisions.',
    icon: BarChart2,
    path: '/services/market-research',
  },
];

const ServicesHubPageCMS = () => {
  const [isPreview, setIsPreview] = useState(false);

  useEffect(() => {
    client
      .get('/marketing/services')
      .then((response) => {
        if (response.data._meta?.show_preview_banner) {
          setIsPreview(true);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <PublicLayout>
      <SEOHead
        title="Platforms & Professional Services | Pleerity Enterprise"
        description="Structured compliance technology and professional support services for UK landlords. Compliance Vault Pro and specialist services."
        canonicalUrl="/services"
      />

      {isPreview && (
        <div className="bg-amber-500 text-white text-center py-2 text-sm font-medium">
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          Preview Environment - Content may not reflect production
        </div>
      )}

      {/* Hero */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Platforms & Professional Services
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Structured compliance technology and professional support services for UK landlords.
            </p>
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
              asChild
            >
              <Link to="/compliance-vault-pro">
                Explore Compliance Vault Pro
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Technology Platforms */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-midnight-blue mb-8 flex items-center gap-2">
            <LayoutGrid className="w-7 h-7 text-electric-teal" />
            Technology Platforms
          </h2>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Primary: Compliance Vault Pro — larger card */}
            {PLATFORMS.filter((p) => p.primary).map((platform) => (
              <Card
                key={platform.id}
                className="lg:col-span-2 h-full border-2 border-electric-teal/30 bg-electric-teal/5 hover:shadow-lg transition-shadow"
              >
                <CardHeader>
                  <CardTitle className="text-2xl font-bold text-midnight-blue">
                    {platform.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600 mb-6 text-lg">
                    {platform.description}
                  </p>
                  <Button className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
                    <Link to={platform.href}>
                      {platform.cta}
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            ))}

            {/* Secondary: ClearForm & AssureStack — single column of smaller cards */}
            <div className="flex flex-col gap-6">
              {PLATFORMS.filter((p) => !p.primary).map((platform) => (
                <Card
                  key={platform.id}
                  className="h-full border border-gray-200 hover:shadow-md transition-shadow opacity-90"
                >
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg font-semibold text-midnight-blue flex items-center gap-2">
                      {platform.name}
                      {platform.comingSoon && (
                        <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                          Coming Soon
                        </span>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-gray-600 text-sm">{platform.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Professional Support Services */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-midnight-blue mb-8 flex items-center gap-2">
            <Briefcase className="w-7 h-7 text-electric-teal" />
            Professional Support Services
          </h2>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {PROFESSIONAL_SERVICES.map((service) => {
              const Icon = service.icon;
              return (
                <Link key={service.slug} to={service.path}>
                  <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer group border-2 border-transparent hover:border-electric-teal">
                    <CardHeader>
                      <div className="w-12 h-12 rounded-lg bg-electric-teal/10 flex items-center justify-center mb-4 group-hover:bg-electric-teal/20 transition-colors">
                        <Icon className="w-6 h-6 text-electric-teal" />
                      </div>
                      <CardTitle className="text-lg font-semibold text-midnight-blue group-hover:text-electric-teal transition-colors">
                        {service.name}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-gray-600 text-sm mb-4">{service.description}</p>
                      <span className="inline-flex items-center text-electric-teal font-medium text-sm">
                        Learn more
                        <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                      </span>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Need Help Choosing — CTA */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Need Help Choosing?
          </h2>
          <p className="text-gray-300 mb-8 text-lg">
            Speak with us to determine whether you need structured tracking, documentation, or a professional audit.
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/contact">
              Book Consultation
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServicesHubPageCMS;
