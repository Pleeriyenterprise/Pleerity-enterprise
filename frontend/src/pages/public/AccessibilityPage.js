import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Accessibility } from 'lucide-react';

const AccessibilityPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Accessibility Statement | Pleerity"
        description="Pleerity is committed to ensuring digital accessibility for people with disabilities."
        canonicalUrl="/accessibility"
      />

      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
          <Accessibility className="w-4 h-4 mr-2" />
          Accessibility
        </div>
        
        <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-8">
          Accessibility Statement
        </h1>

        <div className="prose max-w-none">
          <p className="text-lg text-gray-600 mb-6">
            Pleerity Enterprise Ltd is committed to ensuring digital accessibility for people with disabilities. 
            We are continually improving the user experience for everyone and applying the relevant accessibility standards.
          </p>

          <h2 className="text-2xl font-semibold text-midnight-blue mt-8 mb-4">Our Commitment</h2>
          <p className="text-gray-600 mb-4">
            We strive to conform to level AA of the Web Content Accessibility Guidelines (WCAG) 2.1. 
            These guidelines explain how to make web content more accessible for people with disabilities.
          </p>

          <h2 className="text-2xl font-semibold text-midnight-blue mt-8 mb-4">Feedback</h2>
          <p className="text-gray-600 mb-4">
            We welcome your feedback on the accessibility of our website. 
            Please contact us if you encounter accessibility barriers:
          </p>
          <ul className="list-disc list-inside text-gray-600 space-y-2 mb-6">
            <li>Email: <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">info@pleerityenterprise.co.uk</a></li>
            <li>Phone: 020 3337 6060</li>
          </ul>

          <h2 className="text-2xl font-semibold text-midnight-blue mt-8 mb-4">Technical Specifications</h2>
          <p className="text-gray-600 mb-4">
            Our website is designed to be compatible with:
          </p>
          <ul className="list-disc list-inside text-gray-600 space-y-2">
            <li>Modern web browsers (Chrome, Firefox, Safari, Edge)</li>
            <li>Screen readers and assistive technologies</li>
            <li>Keyboard navigation</li>
            <li>Text magnification up to 200%</li>
          </ul>

          <p className="text-sm text-gray-500 mt-8">
            Last updated: January 2026
          </p>
        </div>
      </section>
    </PublicLayout>
  );
};

export default AccessibilityPage;
