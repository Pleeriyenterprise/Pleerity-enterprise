import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';

const AccessibilityPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Accessibility Statement | Pleerity Enterprise Ltd"
        description="Pleerity is committed to ensuring digital accessibility for people with disabilities."
        canonicalUrl="/accessibility"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Accessibility Statement</h1>
          <p className="text-gray-600 mb-8">Last updated: November 2025</p>
          <p className="text-gray-700 mb-8">
            Pleerity Enterprise Ltd is committed to ensuring digital accessibility for people with disabilities. 
            We continuously work to improve the user experience for everyone and apply relevant accessibility standards.
          </p>

          <div className="prose prose-lg max-w-none text-gray-700 space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">1. Our Commitment</h2>
              <p>
                We aim to conform to the Web Content Accessibility Guidelines (WCAG) 2.1 Level AA standard. 
                These guidelines explain how to make web content more accessible for people with disabilities 
                and more user-friendly for everyone.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">2. Measures to Support Accessibility</h2>
              <p className="mb-3">We take the following measures to ensure accessibility:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Regular accessibility audits and testing on all main pages.</li>
                <li>Use of readable font contrasts and resizable text.</li>
                <li>Alt-text for images and descriptive labels for forms.</li>
                <li>Screen reader and keyboard navigation support.</li>
              </ul>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">3. Known Limitations</h2>
              <p>
                Despite our best efforts to ensure accessibility, some content may not yet fully comply. 
                We are committed to continuous improvement and encourage feedback.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">4. Feedback and Contact</h2>
              <p className="mb-3">
                We welcome your feedback on the accessibility of our website. If you encounter any barriers, 
                please contact us:
              </p>
              <ul className="list-none space-y-2">
                <li>
                  <strong>Email:</strong>{' '}
                  <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">
                    info@pleerityenterprise.co.uk
                  </a>
                </li>
                <li><strong>Phone:</strong> 020 3337 6060</li>
                <li><strong>Postal Address:</strong> 8 Valley Court, Hamilton, ML3 8HW, United Kingdom</li>
              </ul>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">5. Enforcement Procedure</h2>
              <p>
                If you are dissatisfied with our response to any accessibility concern, you have the right to 
                escalate the issue to the Equality and Human Rights Commission (EHRC) in the United Kingdom.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">6. Ongoing Improvements</h2>
              <p>
                We continue to review and update our accessibility approach in line with changes to technology, 
                user feedback, and updates to accessibility standards.
              </p>
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

export default AccessibilityPage;
