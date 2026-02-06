import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';

const PrivacyPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Privacy Policy | Pleerity Enterprise Ltd"
        description="Learn how Pleerity Enterprise Ltd collects, uses, and protects your personal information in accordance with UK GDPR."
        canonicalUrl="/legal/privacy"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Privacy Policy</h1>
          <p className="text-gray-600 mb-8">
            Pleerity Enterprise Ltd ("we", "our", or "us") is committed to protecting the privacy and security 
            of the personal information we collect from our clients and website visitors. This Privacy Policy 
            explains how we collect, use, store, and protect personal data in accordance with the UK General 
            Data Protection Regulation (UK GDPR).
          </p>

          <div className="bg-gray-50 p-6 rounded-lg mb-8 text-sm">
            <p className="font-semibold text-midnight-blue mb-2">Registered Company: Pleerity Enterprise Ltd</p>
            <p className="text-gray-700">Company No.: SC855023</p>
            <p className="text-gray-700">Registered Address: 8 Valley Court, Hamilton ML3 8HW</p>
            <p className="text-gray-700">Email: info@pleerityenterprise.co.uk</p>
          </div>

          <div className="prose prose-lg max-w-none text-gray-700 space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">1. Information We Collect</h2>
              <p className="mb-3">
                We collect and process personal data necessary for providing our services, including:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Contact information (name, email, phone number)</li>
                <li>Business or property details (address, ownership, compliance data)</li>
                <li>Payment information (processed securely via Stripe)</li>
                <li>Documents uploaded or shared during service delivery</li>
                <li>Communication records via email or portal correspondence.</li>
              </ul>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">2. How We Use Your Information</h2>
              <p className="mb-3">We process personal data to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Deliver and manage our services</li>
                <li>Create, send, and track compliance and automation reports</li>
                <li>Communicate with clients and respond to enquiries</li>
                <li>Process payments and issue invoices</li>
                <li>Improve our services and maintain security of our systems.</li>
              </ul>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">3. Data Sharing and Third Parties</h2>
              <p className="mb-3">
                We use trusted third-party providers to support our operations, including:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Stripe (secure online payment processing)</li>
                <li>AI language model providers (for automated document generation and insights)</li>
                <li>Email service providers (for transactional communications)</li>
                <li>Secure cloud storage systems (for encrypted document storage).</li>
              </ul>
              <p className="mt-3">
                These providers only process data in accordance with our instructions and applicable data protection laws.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">4. Data Storage and Retention</h2>
              <p>
                Personal data is stored securely using encrypted cloud systems. We retain data only as long as 
                necessary to fulfil the purpose it was collected for or to comply with legal obligations. 
                Documents and reports are archived or deleted upon client request or at the end of the retention period.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">5. Your Rights</h2>
              <p className="mb-3">Under UK GDPR, you have the right to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Access the personal data we hold about you</li>
                <li>Request correction of inaccurate information</li>
                <li>Request erasure of your data (where applicable)</li>
                <li>Restrict or object to data processing</li>
                <li>Request data portability</li>
              </ul>
              <p className="mt-3">
                To exercise any of these rights, contact us at{' '}
                <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">
                  info@pleerityenterprise.co.uk
                </a>.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">6. Security</h2>
              <p>
                We implement appropriate technical and organisational measures to safeguard data against 
                unauthorised access, loss, or misuse. This includes encryption, access controls, and 
                secure transfer protocols.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">7. Updates to This Policy</h2>
              <p>
                We may update this Privacy Policy periodically to reflect changes in law or business operations. 
                The latest version will always be available on our website at pleerityenterprise.co.uk.
              </p>
            </div>

            <div className="mt-12 pt-8 border-t border-gray-200 text-center">
              <p className="text-gray-600">
                Pleerity Enterprise Ltd – AI-Driven Solutions & Compliance
              </p>
              <p className="text-sm text-gray-500 mt-2">Last updated: January 2026</p>
            </div>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PrivacyPage;
