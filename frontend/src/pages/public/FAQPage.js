/**
 * FAQ — Structured, conversion-focused with objection handling and compliance-safe language.
 * SEO phrases and accordion layout; brand styling preserved.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';
import { HelpCircle, ArrowRight } from 'lucide-react';

const FAQ_SECTIONS = [
  {
    id: 'general',
    title: 'General',
    items: [
      {
        q: 'What is Compliance Vault Pro?',
        a: 'Compliance Vault Pro is a structured compliance tracking platform for UK landlords and property professionals. It helps you track certificates, expiry dates, and documentation in one place—with reminders and reporting to support your compliance oversight. It is not legal advice and does not guarantee compliance with regulations.',
      },
      {
        q: 'Who is it for?',
        a: 'Solo landlords, portfolio landlords, managing agents, and property professionals who need visibility over gas safety certificate expiry tracking, EICR expiry reminders, and other property obligations. It supports both standard and HMO compliance tracking in the UK.',
      },
      {
        q: 'Is this legal advice?',
        a: 'No. Compliance Vault Pro provides informational indicators and structured tracking only. We do not provide legal advice or certification. You remain responsible for meeting your legal and regulatory obligations. Our platform supports your oversight—it does not replace professional advice where required.',
      },
    ],
  },
  {
    id: 'compliance-tracking',
    title: 'Compliance Tracking',
    items: [
      {
        q: 'How does UK landlord compliance tracking work?',
        a: 'You add properties and the certificates or checks that apply (e.g. gas safety, EICR, EPC). You upload documents and confirm or edit expiry and issue dates. The platform calculates status from your inputs and shows risk indicators and upcoming expiries. Compliance status is based on structured rules and your confirmed data—not legal verdicts.',
      },
      {
        q: 'Do you support HMO compliance tracking in the UK?',
        a: 'Yes. You can configure requirements per property so that HMO-specific obligations are tracked alongside standard ones. The same expiry monitoring, reminders, and reporting apply. This is for organisational visibility only; we do not guarantee that your setup meets HMO regulatory requirements.',
      },
      {
        q: 'Can I track gas safety certificate expiry and EICR expiry?',
        a: 'Yes. Gas safety certificate expiry tracking and EICR expiry reminders are supported. You upload certificates, confirm dates (or use AI-assisted extraction and then confirm), and the platform surfaces upcoming and overdue items on your dashboard and calendar.',
      },
    ],
  },
  {
    id: 'documents-ai',
    title: 'Documents & AI',
    items: [
      {
        q: 'How does document extraction work?',
        a: 'When you upload a document (e.g. PDF or image), our system can suggest dates and reference numbers from the file. All extracted data requires your confirmation before it is applied. AI is assistive only—we do not generate legal conclusions or certify documents.',
      },
      {
        q: 'What file types are supported?',
        a: 'We support PDF and common image formats (e.g. JPG, PNG) for upload and extraction. After extraction, you review and confirm or edit the details in the confirmation step.',
      },
      {
        q: 'Is AI used to decide my compliance status?',
        a: 'No. Compliance status is determined by structured rules and the dates and data you have confirmed. AI may help pre-fill fields from documents; it does not make legal or compliance determinations.',
      },
    ],
  },
  {
    id: 'reminders',
    title: 'Reminders',
    items: [
      {
        q: 'What reminders do I get?',
        a: 'You can receive reminders for upcoming expiries (e.g. gas safety certificate expiry tracking and EICR expiry reminders) based on your plan. Reminder timing and channels (e.g. email) depend on your settings and subscription.',
      },
      {
        q: 'Can I customise when I’m reminded?',
        a: 'Reminder preferences can be adjusted in your account settings where available. This helps you stay ahead of renewals without relying on guesswork.',
      },
    ],
  },
  {
    id: 'billing-plans',
    title: 'Billing & Plans',
    items: [
      {
        q: 'What plans are available?',
        a: 'We offer tiered plans (e.g. Solo, Pro) with different features such as reminder options, reports, and tenant portal access. See the pricing or product page for current plan details.',
      },
      {
        q: 'Can I change or cancel my plan?',
        a: 'Plan changes and cancellations are handled according to your subscription terms. You can manage billing and plan options from your account settings or by contacting support.',
      },
    ],
  },
  {
    id: 'data-security',
    title: 'Data & Security',
    items: [
      {
        q: 'How is my data stored and protected?',
        a: 'We use secure cloud infrastructure with encryption in transit. Access is role-based and actions are recorded in audit logs. We do not monetise or resell your data.',
      },
      {
        q: 'Who can see my data?',
        a: 'Access is controlled by roles and permissions. Only users with the appropriate access can see the relevant properties and documents. Audit logs provide traceability of changes.',
      },
      {
        q: 'Do you guarantee compliance if I use the platform?',
        a: 'No. We provide tools for structured tracking and reporting to support your compliance oversight. We do not provide legal advice, certification, or a guarantee that you meet regulatory requirements. You remain responsible for your obligations.',
      },
    ],
  },
];

const FAQPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="FAQ | UK Landlord Compliance Tracking & Support | Pleerity"
        description="Clear answers on UK landlord compliance tracking, HMO compliance tracking UK, gas safety certificate expiry tracking, EICR expiry reminders, and Compliance Vault Pro. No legal advice."
        canonicalUrl="/faq"
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero */}
        <div className="text-center mb-12">
          <HelpCircle className="w-12 h-12 text-electric-teal mx-auto mb-4" />
          <h1 className="text-4xl font-bold text-midnight-blue mb-4">
            Clear Answers. No Guesswork.
          </h1>
          <p className="text-lg text-gray-600">
            Transparency builds trust. Here are the questions we hear most about Compliance Vault Pro and compliance tracking.
          </p>
        </div>

        {/* FAQ sections with accordions */}
        <div className="space-y-12">
          {FAQ_SECTIONS.map((section) => (
            <section key={section.id}>
              <h2 className="text-2xl font-bold text-midnight-blue mb-6 pb-3 border-b-2 border-electric-teal">
                {section.title}
              </h2>
              <Accordion type="single" collapsible className="w-full">
                {section.items.map((item, i) => (
                  <AccordionItem key={i} value={`${section.id}-${i}`} className="border rounded-lg mb-3 px-4 hover:border-electric-teal/50 transition-colors">
                    <AccordionTrigger className="text-left font-medium text-midnight-blue hover:no-underline py-4">
                      {item.q}
                    </AccordionTrigger>
                    <AccordionContent className="text-gray-700 pb-4">
                      {item.a}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </section>
          ))}
        </div>

        {/* Closing CTA */}
        <section className="mt-16 py-12 bg-midnight-blue rounded-xl px-6 text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Still Need Clarity?</h2>
          <p className="text-gray-300 mb-8 max-w-lg mx-auto">
            Speak with us or try the platform and see how structured compliance tracking works for you.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              variant="outline"
              className="bg-transparent border-white text-white hover:bg-white/10 hover:text-white"
              asChild
            >
              <Link to="/demo">
                Schedule a Demo
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/intake/start">
                Start Free Trial
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
            </Button>
          </div>
        </section>
      </div>
    </PublicLayout>
  );
};

export default FAQPage;
