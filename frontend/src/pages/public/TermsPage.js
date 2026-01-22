import React from 'react';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead } from '../components/public/SEOHead';

const TermsPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Terms of Service"
        description="Pleerity Enterprise Ltd terms of service. Read the terms and conditions for using Compliance Vault Pro."
        canonicalUrl="/legal/terms"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Terms of Service</h1>
          <p className="text-gray-500 mb-8">Last updated: January 2026</p>

          <div className="prose prose-lg max-w-none text-gray-700">
            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">1. Acceptance of Terms</h2>
            <p>
              By accessing or using Compliance Vault Pro ("the Service"), provided by Pleerity Enterprise Ltd 
              ("we", "our", "us"), you agree to be bound by these Terms of Service. If you do not agree, 
              please do not use the Service.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">2. Description of Service</h2>
            <p>
              Compliance Vault Pro is a property compliance management platform that helps landlords and 
              letting agents track compliance requirements, store documents, and receive reminders.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">3. Account Registration</h2>
            <p>To use the Service, you must:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Provide accurate and complete registration information</li>
              <li>Maintain the security of your account credentials</li>
              <li>Notify us immediately of any unauthorized access</li>
              <li>Be at least 18 years of age</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">4. Subscription and Payment</h2>
            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">4.1 Fees</h3>
            <p>
              Subscription fees are charged monthly or annually as selected. Prices are in GBP and 
              may be subject to VAT.
            </p>
            
            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">4.2 Billing</h3>
            <p>
              Payments are processed through Stripe. By providing payment information, you authorize 
              us to charge your payment method for all fees incurred.
            </p>

            <h3 className="text-xl font-semibold text-midnight-blue mt-6 mb-3">4.3 Cancellation</h3>
            <p>
              You may cancel your subscription at any time. Access continues until the end of the 
              current billing period.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">5. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Use the Service for any unlawful purpose</li>
              <li>Upload malicious content or viruses</li>
              <li>Attempt to gain unauthorized access</li>
              <li>Interfere with or disrupt the Service</li>
              <li>Resell or redistribute the Service without permission</li>
            </ul>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">6. Intellectual Property</h2>
            <p>
              The Service, including all content, features, and functionality, is owned by 
              Pleerity Enterprise Ltd and protected by intellectual property laws.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">7. Your Content</h2>
            <p>
              You retain ownership of documents and data you upload. By uploading content, you grant 
              us a licence to store, process, and display it as necessary to provide the Service.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">8. Disclaimer</h2>
            <p>
              <strong>The Service is provided "as is" without warranties of any kind.</strong> While we 
              strive for accuracy, we do not guarantee that compliance reminders will be error-free. 
              You remain responsible for your own compliance obligations.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">9. Limitation of Liability</h2>
            <p>
              To the maximum extent permitted by law, Pleerity Enterprise Ltd shall not be liable for 
              any indirect, incidental, special, consequential, or punitive damages, including but not 
              limited to fines, penalties, or losses arising from missed compliance deadlines.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">10. Indemnification</h2>
            <p>
              You agree to indemnify and hold harmless Pleerity Enterprise Ltd from any claims arising 
              from your use of the Service or violation of these Terms.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">11. Termination</h2>
            <p>
              We may suspend or terminate your access to the Service at any time for violation of 
              these Terms or for any other reason at our discretion.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">12. Governing Law</h2>
            <p>
              These Terms are governed by the laws of England and Wales. Any disputes shall be 
              subject to the exclusive jurisdiction of the courts of England and Wales.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">13. Changes to Terms</h2>
            <p>
              We reserve the right to modify these Terms at any time. We will notify you of 
              significant changes via email or through the Service.
            </p>

            <h2 className="text-2xl font-bold text-midnight-blue mt-8 mb-4">14. Contact</h2>
            <p>
              For questions about these Terms, contact us at:
            </p>
            <p className="mt-2">
              <strong>Email:</strong> legal@pleerityenterprise.co.uk<br />
              <strong>Address:</strong> Pleerity Enterprise Ltd, United Kingdom
            </p>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default TermsPage;
