import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Play } from 'lucide-react';

/**
 * Platform demo page. Placeholder for video/screenshots; primary CTA goes to intake.
 */
const DemoPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="View Platform Demo | Compliance Vault Pro"
        description="See how Compliance Vault Pro helps UK landlords track certificate expiry dates, monitor compliance, and generate audit-ready reports."
        canonicalUrl="/demo"
      />
      <section className="min-h-[60vh] flex flex-col items-center justify-center py-20 px-4">
        <div className="max-w-2xl mx-auto text-center">
          <h1 className="text-3xl sm:text-4xl font-bold text-midnight-blue mb-4">
            Platform Demo
          </h1>
          <p className="text-lg text-gray-600 mb-8">
            See how Compliance Vault Pro gives you a clear view of certificate expiries, 
            portfolio compliance, and reminders — all in one place.
          </p>
          {/* TODO: Add 60-second explainer video or dashboard walkthrough when asset available */}
          <div className="aspect-video bg-gray-100 rounded-xl border border-gray-200 flex items-center justify-center mb-8">
            <div className="text-center text-gray-500">
              <Play className="w-12 h-12 mx-auto mb-2 opacity-60" />
              <p className="text-sm">Demo video placeholder</p>
              <p className="text-xs mt-1">Replace with screen recording or embed</p>
            </div>
          </div>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/intake/start">Start Your Setup</Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default DemoPage;
