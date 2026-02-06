import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Shield, Bell, Eye, ArrowRight } from 'lucide-react';

const AssureStackPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="AssureStack - 24/7 Compliance Monitoring | Pleerity"
        description="Always on. Always watching. Advanced compliance monitoring and alerting system coming soon."
        canonicalUrl="/products/assurestack"
      />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32 text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-amber-100 text-amber-700 text-sm font-medium mb-6">
            <Eye className="w-4 h-4 mr-2" />
            Coming Soon
          </div>
          
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-midnight-blue leading-tight mb-6">
            AssureStack
          </h1>
          
          <p className="text-xl text-gray-600 mb-4">
            Always on. Always watching.
          </p>
          
          <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-8">
            Advanced 24/7 compliance monitoring and intelligent alerting system. 
            Stay ahead of requirements with real-time tracking and proactive notifications.
          </p>

          {/* Key Features Preview */}
          <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto mt-12">
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <Shield className="w-8 h-8 text-electric-teal mx-auto mb-3" />
              <h3 className="font-semibold text-midnight-blue mb-2">24/7 Monitoring</h3>
              <p className="text-sm text-gray-600">Continuous compliance tracking across all properties</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <Bell className="w-8 h-8 text-electric-teal mx-auto mb-3" />
              <h3 className="font-semibold text-midnight-blue mb-2">Smart Alerts</h3>
              <p className="text-sm text-gray-600">Intelligent notifications before issues arise</p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
              <Eye className="w-8 h-8 text-electric-teal mx-auto mb-3" />
              <h3 className="font-semibold text-midnight-blue mb-2">Real-time Insights</h3>
              <p className="text-sm text-gray-600">Live compliance dashboard and reporting</p>
            </div>
          </div>

          {/* CTA */}
          <div className="mt-12">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
              asChild
            >
              <Link to="/">
                Explore Compliance Vault Pro
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default AssureStackPage;
