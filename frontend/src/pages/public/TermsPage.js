import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';

const TermsPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Terms of Service | Pleerity Enterprise Ltd"
        description="Terms of Service governing the use of services provided by Pleerity Enterprise Ltd."
        canonicalUrl="/legal/terms"
        noIndex={false}
      />

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-midnight-blue mb-8">Terms of Service</h1>
          <p className="text-gray-600 mb-6">
            These Terms of Service ("Terms") govern the use of services provided by Pleerity Enterprise Ltd 
            ("we", "our", or "us"). By engaging our services, you ("Client") agree to comply with and be 
            bound by these Terms. If you do not agree, please do not use our services.
          </p>

          <div className="bg-gray-50 p-6 rounded-lg mb-8 text-sm">
            <p className="font-semibold text-midnight-blue mb-2">Company Name: Pleerity Enterprise Ltd</p>
            <p className="text-gray-700">Company No.: SC855023</p>
            <p className="text-gray-700">Registered Address: 8 Valley Court, Hamilton ML3 8HW</p>
            <p className="text-gray-700">Email: info@pleerityenterprise.co.uk</p>
          </div>

          <div className="prose prose-lg max-w-none text-gray-700 space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">1. Services Provided</h2>
              <p>
                Pleerity Enterprise Ltd provides AI-powered workflow automation, compliance and documentation 
                services for landlords, AI-enhanced market research for SMEs, document automation for 
                professional firms, and professional cleaning services. Service details, inclusions, and fees 
                are specified in proposals or service descriptions provided to clients.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">2. Client Responsibilities</h2>
              <p>
                Clients are responsible for providing accurate, complete, and timely information necessary for 
                the delivery of services. We are not liable for delays or outcomes caused by incorrect or 
                incomplete data provided by the client.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">3. Payments and Refunds</h2>
              <p className="mb-3">
                All payments must be made in accordance with the invoice or payment link provided. Payments are 
                processed securely via Stripe or other approved platforms. Refunds are issued only in cases of 
                proven service error or as outlined in specific service agreements. Once a digital document, 
                report, or automation has been delivered, it is considered a completed service.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">4. Cancellations</h2>
              <p>
                Clients may cancel services prior to commencement by providing written notice. Once processing 
                or automation setup has begun, cancellation may not be eligible for refund. We reserve the right 
                to cancel or suspend services in the event of non-payment or breach of these Terms.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">5. Intellectual Property</h2>
              <p>
                All templates, systems, reports, and automation designs created by Pleerity Enterprise Ltd remain 
                our intellectual property, unless expressly transferred in writing. Clients are granted a 
                non-exclusive, non-transferable licence to use delivered documents or reports for their own 
                lawful business purposes.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">6. Confidentiality</h2>
              <p>
                Both parties agree to maintain confidentiality of all business, personal, or technical information 
                shared during service delivery. We will not disclose client information to any third party except 
                as required by law or to fulfil service obligations through approved partners.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">7. Limitation of Liability</h2>
              <p>
                To the maximum extent permitted by law, Pleerity Enterprise Ltd shall not be liable for any 
                indirect, incidental, or consequential damages arising from the use of our services. Our total 
                liability shall not exceed the amount paid by the client for the specific service in question.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">Service Scope Updates</h2>
              <p className="mb-3">
                Pleerity Enterprise Ltd reserves the right to update, modify, or discontinue any aspect of its 
                services, pricing, or delivery scope at any time, provided such changes do not materially diminish 
                the core functionality of an ongoing service for which the client has already paid.
              </p>
              <p>
                Clients will be notified of significant updates via email or website notice. Continued use of the 
                service after such notice constitutes acceptance of the updated scope.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">8. Termination of Services</h2>
              <p>
                We may suspend or terminate services without liability if the client breaches these Terms, provides 
                misleading information, or uses our services for unlawful purposes.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">9. Data Protection</h2>
              <p>
                We comply with UK GDPR and process all personal data in accordance with our Privacy Policy. By 
                using our services, clients consent to such processing as described in that policy.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">10. Governing Law</h2>
              <p>
                These Terms are governed by and construed in accordance with the laws of Scotland and the United 
                Kingdom. Any disputes shall be subject to the exclusive jurisdiction of the Scottish courts.
              </p>
            </div>

            <div>
              <h2 className="text-2xl font-bold text-midnight-blue mb-4">11. Contact Information</h2>
              <p className="mb-3">For questions about these Terms, please contact:</p>
              <p className="mb-2">
                📧 <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">
                  info@pleerityenterprise.co.uk
                </a>
              </p>
              <p>📍 8 Valley Court, Hamilton ML3 8HW</p>
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

export default TermsPage;
