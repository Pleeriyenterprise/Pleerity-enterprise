/**
 * Thank-you page after compliance checklist lead capture.
 * Confirmation message, download button (PDF), CTA to Start Free Trial.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { ArrowRight, Download } from 'lucide-react';

const PDF_PATH = '/compliance-checklist-2026.pdf';

export default function ChecklistThankYouPage() {
  return (
    <PublicLayout>
      <SEOHead
        title="Your Checklist is Ready"
        description="Download your free UK Landlord Compliance Checklist and explore Compliance Vault Pro."
        canonicalUrl="/checklist-thank-you"
      />
      <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 py-16">
        <div className="max-w-lg mx-auto text-center">
          <h1 className="text-3xl font-bold text-midnight-blue mb-4">
            Your checklist is ready
          </h1>
          <p className="text-gray-600 mb-8">
            Thanks for signing up. Click below to download your free UK Landlord Compliance Master Checklist (2026 Edition).
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-10">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <a href={PDF_PATH} download target="_blank" rel="noopener noreferrer">
                <Download className="w-5 h-5 mr-2 inline" />
                Download checklist (PDF)
              </a>
            </Button>
          </div>
          <p className="text-sm text-gray-500 mb-8">
            The checklist is for information only and does not constitute legal advice. Requirements may vary by property type and local authority.
          </p>
          <div className="pt-8 border-t border-gray-200">
            <p className="text-gray-700 mb-4">
              Track compliance automatically and never miss a renewal.
            </p>
            <Button size="lg" variant="outline" className="border-electric-teal text-electric-teal hover:bg-electric-teal/10" asChild>
              <Link to="/intake/start">
                Start Free Trial of Compliance Vault Pro
                <ArrowRight className="w-5 h-5 ml-2 inline" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}
