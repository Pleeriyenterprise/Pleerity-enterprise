import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { HelpCircle } from 'lucide-react';

const FAQPage = () => {
  const faqs = [
    {
      question: 'What is Compliance Vault Pro?',
      answer: 'Compliance Vault Pro is an all-in-one compliance management platform for UK landlords, helping you track requirements, store documents, and stay audit-ready.'
    },
    {
      question: 'How does pricing work?',
      answer: 'We offer flexible pricing plans to suit portfolios of all sizes. Visit our pricing page for detailed information on our Starter, Growth, and Enterprise plans.'
    },
    {
      question: 'Is my data secure?',
      answer: 'Yes. We use bank-level encryption, are GDPR compliant, and store all data securely in UK-based servers with 24/7 monitoring.'
    },
    {
      question: 'Can I try before I buy?',
      answer: 'Yes! Contact us to arrange a demo or start with our intake wizard to see how the system works.'
    },
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Frequently Asked Questions | Pleerity"
        description="Common questions about Pleerity's compliance management platform and services."
        canonicalUrl="/faq"
      />

      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
          <HelpCircle className="w-4 h-4 mr-2" />
          FAQ
        </div>
        
        <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-4">
          Frequently Asked Questions
        </h1>
        
        <p className="text-lg text-gray-600 mb-12">
          Find answers to common questions about our platform and services.
        </p>

        <div className="space-y-8">
          {faqs.map((faq, index) => (
            <div key={index} className="border-b border-gray-200 pb-6">
              <h3 className="text-xl font-semibold text-midnight-blue mb-3">
                {faq.question}
              </h3>
              <p className="text-gray-600">
                {faq.answer}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center bg-gray-50 rounded-lg p-8">
          <h3 className="text-xl font-semibold text-midnight-blue mb-3">
            Still have questions?
          </h3>
          <p className="text-gray-600 mb-4">
            Our support team is here to help.
          </p>
          <p className="text-gray-600">
            Email: <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">info@pleerityenterprise.co.uk</a>
          </p>
        </div>
      </section>
    </PublicLayout>
  );
};

export default FAQPage;
