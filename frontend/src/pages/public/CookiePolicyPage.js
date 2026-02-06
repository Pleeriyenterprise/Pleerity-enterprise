import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';

const CookiePolicyPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Cookie Policy | Pleerity Enterprise Ltd"
        description="Learn about how Pleerity Enterprise Ltd uses cookies and similar technologies."
        canonicalUrl="/legal/cookies"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Cookie Policy</h1>
          <p className="text-gray-600 mb-6">Last updated: November 2025</p>
          <p className="text-gray-700 mb-8">
            This Cookie Policy explains how Pleerity Enterprise Ltd ("we", "our", "us") uses cookies and 
            similar technologies to recognize you when you visit our website at pleerityenterprise.co.uk 
            ("Website"). It explains what these technologies are and why we use them, as well as your rights 
            to control our use of them.
          </p>

          <div className="prose prose-lg max-w-none text-gray-700 space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">1. What Are Cookies?</h2>
              <p>
                Cookies are small data files that are placed on your computer or mobile device when you visit 
                a website. They are widely used by website owners to make their websites work more efficiently, 
                as well as to provide reporting information.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">2. How We Use Cookies</h2>
              <p className="mb-3">We use cookies for several reasons:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Essential cookies</strong> – required for the operation of our website and secure login areas.</li>
                <li><strong>Performance and analytics cookies</strong> – to understand how visitors use our site and improve user experience.</li>
                <li><strong>Functionality cookies</strong> – to remember user preferences and provide enhanced features.</li>
                <li><strong>Targeting cookies</strong> – used for limited marketing analysis through anonymized metrics.</li>
              </ul>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">3. Third-Party Cookies</h2>
              <p>
                Our website may use third-party cookies from trusted service providers for payment processing, 
                customer support, and other essential functions.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">4. Managing Cookies</h2>
              <p>
                You have the right to decide whether to accept or reject cookies. You can set your web browser 
                controls to accept or refuse cookies. Note that disabling cookies may affect the functionality 
                of this Website.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">5. Updates to This Policy</h2>
              <p>
                We may update this Cookie Policy periodically to reflect changes to the cookies we use or for 
                other operational, legal, or regulatory reasons. Please revisit this Cookie Policy regularly to 
                stay informed.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">6. Contact Us</h2>
              <p className="mb-3">If you have any questions about our use of cookies or this policy, contact us at:</p>
              <p className="mb-2">
                <strong>Email:</strong>{' '}
                <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">
                  info@pleerityenterprise.co.uk
                </a>
              </p>
              <p><strong>Address:</strong> 8 Valley Court, Hamilton, ML3 8HW, United Kingdom</p>
            </div>

            <div className="mt-12 pt-8 border-t border-gray-200 text-center">
              <p className="text-gray-600">
                Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance
              </p>
              <p className="text-sm text-gray-500 mt-2">Last updated: November 2025</p>
            </div>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CookiePolicyPage;
