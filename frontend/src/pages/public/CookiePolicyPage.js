import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';

const CookiePolicyPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Cookie Policy"
        description="Learn about how Pleerity Enterprise Ltd uses cookies and similar technologies."
        canonicalUrl="/legal/cookies"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Cookie Policy</h1>
          <p className="text-gray-500 mb-8">Last updated: January 2026</p>

          <div className="prose prose-lg max-w-none text-gray-700">
            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">1. What Are Cookies?</h2>
            <p>
              Cookies are small text files that are placed on your device when you visit our website. 
              They help us provide you with a better experience and allow certain features to function properly.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">2. How We Use Cookies</h2>
            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.1 Necessary Cookies</h3>
            <p>
              These cookies are essential for the website to function. They include:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Authentication cookies (to keep you logged in)</li>
              <li>Security cookies (to protect against fraud)</li>
              <li>Load balancing cookies</li>
            </ul>

            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.2 Functional Cookies</h3>
            <p>
              These cookies enable enhanced functionality:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Remember your preferences and settings</li>
              <li>Store form data temporarily</li>
              <li>Provide chat support features</li>
            </ul>

            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.3 Analytics Cookies</h3>
            <p>
              These help us understand how visitors use our website (requires your consent):
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Pages visited and time spent</li>
              <li>Click patterns and navigation flow</li>
              <li>Performance metrics</li>
            </ul>

            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.4 Marketing Cookies</h3>
            <p>
              These cookies track your browsing to show relevant ads (requires your consent):
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Track visits across websites</li>
              <li>Measure ad campaign effectiveness</li>
              <li>Personalize content and offers</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">3. Managing Your Cookie Preferences</h2>
            <p>
              You can manage your cookie preferences at any time:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Use our cookie consent banner when you first visit</li>
              <li>Adjust your browser settings to block or delete cookies</li>
              <li>Note: Blocking necessary cookies may affect site functionality</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">4. Third-Party Cookies</h2>
            <p>
              We use third-party services that may set their own cookies:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Stripe (payment processing)</li>
              <li>Google Analytics (website analytics)</li>
              <li>Tawk.to (customer support chat)</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">5. Contact Us</h2>
            <p>
              If you have questions about our use of cookies, please contact us:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Email: info@pleerityenterprise.co.uk</li>
              <li>Phone: 020 3337 6060</li>
            </ul>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CookiePolicyPage;
