import React from 'react';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead } from '../components/public/SEOHead';

const PrivacyPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Privacy Policy"
        description="Pleerity Enterprise Ltd privacy policy. Learn how we collect, use, and protect your personal data."
        canonicalUrl="/legal/privacy"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Privacy Policy</h1>
          <p className="text-gray-500 mb-8">Last updated: January 2026</p>

          <div className="prose prose-lg max-w-none text-gray-700">
            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">1. Introduction</h2>
            <p>
              Pleerity Enterprise Ltd ("we", "our", "us") is committed to protecting your privacy. 
              This Privacy Policy explains how we collect, use, disclose, and safeguard your information 
              when you use our Compliance Vault Pro platform and related services.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">2. Information We Collect</h2>
            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.1 Personal Information</h3>
            <p>We may collect the following personal information:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Name and contact details (email, phone number)</li>
              <li>Company name and business address</li>
              <li>Property addresses and details</li>
              <li>Payment information (processed securely via Stripe)</li>
              <li>Documents you upload (compliance certificates)</li>
            </ul>

            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">2.2 Usage Information</h3>
            <p>We automatically collect:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>IP address and browser type</li>
              <li>Pages visited and features used</li>
              <li>Time and date of access</li>
              <li>Device information</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">3. How We Use Your Information</h2>
            <p>We use your information to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Provide and maintain our services</li>
              <li>Send compliance reminders and notifications</li>
              <li>Process payments</li>
              <li>Improve our platform</li>
              <li>Communicate with you about your account</li>
              <li>Comply with legal obligations</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">4. Data Sharing</h2>
            <p>
              We do not sell your personal information. We may share data with:
            </p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Service providers (payment processors, email services)</li>
              <li>Legal authorities when required by law</li>
              <li>Business partners with your consent</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">5. Data Security</h2>
            <p>
              We implement appropriate technical and organizational measures to protect your data, 
              including encryption, access controls, and regular security assessments.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">6. Your Rights (GDPR)</h2>
            <p>Under GDPR, you have the right to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Access your personal data</li>
              <li>Rectify inaccurate data</li>
              <li>Request erasure of your data</li>
              <li>Restrict processing</li>
              <li>Data portability</li>
              <li>Object to processing</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">7. Data Retention</h2>
            <p>
              We retain your data for as long as your account is active or as needed to provide services. 
              Compliance documents are retained for the legally required period.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">8. Cookies</h2>
            <p>
              We use essential cookies to provide our service. We do not use tracking cookies for 
              advertising purposes.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">9. Contact Us</h2>
            <p>
              For privacy-related inquiries, contact us at:
            </p>
            <p className="mt-2">
              <strong>Email:</strong> privacy@pleerityenterprise.co.uk<br />
              <strong>Address:</strong> Pleerity Enterprise Ltd, United Kingdom
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">10. Changes to This Policy</h2>
            <p>
              We may update this policy from time to time. We will notify you of significant changes 
              via email or through the platform.
            </p>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PrivacyPage;
