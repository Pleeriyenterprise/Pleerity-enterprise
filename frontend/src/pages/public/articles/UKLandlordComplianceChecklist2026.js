/**
 * UK Landlord Compliance Checklist (2026 Guide) — SEO-optimised long-form article.
 * Compliance-safe language; no legal claims. Inline CTAs, FAQ schema, lead magnet.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../../components/public/PublicLayout';
import { SEOHead, createArticleSchema, createFAQSchema } from '../../../components/public/SEOHead';
import { Button } from '../../../components/ui/button';
import { Card, CardContent } from '../../../components/ui/card';
import ChecklistDownloadModal from '../../../components/public/ChecklistDownloadModal';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../../components/ui/accordion';
import { ChevronLeft, ArrowRight } from 'lucide-react';

const META_TITLE = 'UK Landlord Compliance Checklist (2026 Guide)';
const META_DESCRIPTION = 'A practical UK landlord compliance checklist covering gas safety, EICR, EPC and HMO licence tracking. Learn how to organise and monitor expiry dates.';
const CANONICAL = '/insights/uk-landlord-compliance-checklist-2026';
const PUBLISHED = '2026-01-01';
const UPDATED = '2026-01-01';

const FAQ_ITEMS = [
  {
    question: 'Is this legal advice?',
    answer: 'No. This guide provides informational content only. Always consult official guidance or a qualified professional where necessary.',
  },
  {
    question: 'How often do gas safety certificates expire?',
    answer: 'Gas Safety Records are typically valid for 12 months where gas appliances are present.',
  },
  {
    question: 'How long does an EICR last?',
    answer: 'An EICR is commonly valid for up to 5 years, though this can vary depending on circumstances.',
  },
  {
    question: 'Do all landlords need an HMO licence?',
    answer: 'No. Licensing depends on property type and local council regulations.',
  },
  {
    question: 'What is the best way to track landlord compliance?',
    answer: 'A structured tracking system centralises documents, expiry dates, and reminders across properties.',
  },
];

export default function UKLandlordComplianceChecklist2026() {
  const [showChecklistModal, setShowChecklistModal] = useState(false);

  const articleSchema = createArticleSchema(
    META_TITLE,
    META_DESCRIPTION,
    PUBLISHED,
    UPDATED
  );
  const faqSchema = createFAQSchema(FAQ_ITEMS);

  return (
    <PublicLayout>
      <SEOHead
        title={META_TITLE}
        description={META_DESCRIPTION}
        canonicalUrl={CANONICAL}
        schema={[articleSchema, faqSchema]}
      />

      <article className="py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <Link
            to="/insights"
            className="inline-flex items-center text-electric-teal hover:underline mb-8"
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back to Insights
          </Link>

          <header className="mb-10">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              UK Landlord Compliance Checklist (2026 Guide)
            </h1>
            <p className="text-xl text-gray-600 leading-relaxed mb-4">
              Managing rental property in the UK involves tracking multiple safety certificates, documents, and renewal deadlines. Requirements vary depending on property type and local authority, but most landlords must maintain a structured record of safety and tenancy documentation.
            </p>
            <p className="text-gray-700 leading-relaxed mb-6">
              This guide outlines the core compliance items commonly required and explains how to track them in a practical, organised way.
            </p>
            <p className="text-sm text-gray-500 italic border-l-4 border-amber-200 pl-4">
              This guide is informational and does not constitute legal advice. Requirements may vary based on property type and council regulations.
            </p>
          </header>

          {/* Core Safety Certificates */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Core Safety Certificates</h2>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Gas Safety Record (CP12)</h3>
            <p className="text-gray-700 mb-4">
              If your property contains gas appliances, an annual Gas Safety Record (CP12) is typically required.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Key points:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Carried out by a Gas Safe registered engineer</li>
              <li>Valid for 12 months</li>
              <li>Copy must be provided to tenants</li>
            </ul>
            <p className="text-gray-700 mb-4">
              Missing renewals often occur due to manual tracking errors.
            </p>
            <p className="text-gray-700 mb-4">
              <strong>Structured approach:</strong> Instead of relying on calendar reminders, many landlords use automated expiry tracking systems to monitor CP12 renewal dates across properties.
            </p>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700 mb-3">
                  Track CP12 expiry automatically inside{' '}
                  <Link to="/compliance-vault-pro" className="text-electric-teal font-medium hover:underline">Compliance Vault Pro</Link>.
                </p>
                <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
                  <Link to="/intake/start">Start Free Trial <ArrowRight className="w-4 h-4 ml-1 inline" /></Link>
                </Button>
              </CardContent>
            </Card>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Electrical Installation Condition Report (EICR)</h3>
            <p className="text-gray-700 mb-4">
              Most rental properties require periodic electrical inspection.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Typical considerations:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Usually valid for 5 years (subject to circumstances)</li>
              <li>Must be carried out by a qualified electrician</li>
              <li>Reports may include remedial actions</li>
            </ul>
            <p className="text-gray-700 mb-4">
              Tracking EICR expiry is especially important for portfolio landlords managing multiple properties.
            </p>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700">
                  Set automated <Link to="/insights/understanding-eicr-expiry-reminders" className="text-electric-teal font-medium hover:underline">EICR expiry reminders</Link> inside your compliance dashboard.
                </p>
              </CardContent>
            </Card>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Energy Performance Certificate (EPC)</h3>
            <p className="text-gray-700 mb-4">
              An EPC is required when letting a property.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Important notes:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2">
              <li>Must meet minimum rating thresholds where applicable</li>
              <li>Valid for 10 years</li>
              <li>Required before marketing a property</li>
            </ul>
          </section>

          {/* Licensing & Property Type */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Licensing & Property Type Requirements</h2>
            <h3 className="text-lg font-semibold text-midnight-blue mb-3">HMO Licence (Where Applicable)</h3>
            <p className="text-gray-700 mb-4">
              Certain Houses in Multiple Occupation require licensing.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Licensing depends on:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Number of occupants</li>
              <li>Property layout</li>
              <li>Local council regulations</li>
            </ul>
            <p className="text-gray-700 mb-4">
              Renewal cycles vary by council.
            </p>
            <p className="text-gray-700 mb-4">
              Because licence expiry dates differ from safety certificate dates, they should be tracked separately.
            </p>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700">
                  Track HMO licence renewal dates per property to avoid confusion. See our{' '}
                  <Link to="/insights/hmo-compliance-tracking-uk-explained" className="text-electric-teal font-medium hover:underline">HMO Compliance Guide</Link>.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Tenancy & Documentation */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Tenancy & Documentation Records</h2>
            <p className="text-gray-700 mb-4">
              Beyond safety certificates, landlords typically maintain:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Tenancy agreements</li>
              <li>Deposit protection confirmation</li>
              <li>Prescribed information</li>
              <li>Right-to-rent checks</li>
              <li>Inventory / check-in documentation</li>
            </ul>
            <p className="text-gray-700">
              While some of these do not expire annually, they should be centrally stored and accessible in case of audit or dispute.
            </p>
          </section>

          {/* How to Track Landlord Compliance Properly */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">How to Track Landlord Compliance Properly</h2>
            <p className="text-gray-700 mb-4">
              Many landlords manage compliance using:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Spreadsheets</li>
              <li>Email folders</li>
              <li>Phone reminders</li>
              <li>Paper files</li>
            </ul>
            <p className="text-sm font-medium text-gray-700 mb-2">Common risks include:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Missed renewals</li>
              <li>Fragmented storage</li>
              <li>No portfolio overview</li>
              <li>Difficulty identifying which property requires attention</li>
            </ul>
            <p className="text-gray-700 mb-4">
              A structured compliance tracking system centralises:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Documents</li>
              <li>Expiry dates</li>
              <li>Reminder schedules</li>
              <li>Property-level visibility</li>
            </ul>
            <p className="text-gray-700 mb-6">
              Instead of reacting after deadlines pass, you can monitor everything in one dashboard.
            </p>
            <Card className="bg-midnight-blue text-white my-8 p-6 rounded-xl">
              <p className="text-lg mb-4">
                See how <Link to="/compliance-vault-pro" className="text-electric-teal font-medium hover:underline">Compliance Vault Pro</Link> structures your landlord compliance checklist automatically.
              </p>
              <Button className="bg-electric-teal hover:bg-electric-teal/90" asChild>
                <Link to="/intake/start">Start Free Trial <ArrowRight className="w-4 h-4 ml-2 inline" /></Link>
              </Button>
            </Card>
          </section>

          {/* Portfolio-Level */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Portfolio-Level Compliance Tracking</h2>
            <p className="text-gray-700 mb-4">
              If you manage more than one property, tracking becomes more complex.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Each property may have:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Different certificate expiry dates</li>
              <li>Different licensing status</li>
              <li>Different inspection schedules</li>
            </ul>
            <p className="text-gray-700 mb-4">
              A structured system assigns compliance tracking at the property level, reducing confusion and improving visibility.
            </p>
            <p className="text-gray-700">
              Some platforms provide informational risk indicators to highlight which properties require attention. These indicators are based on uploaded evidence and confirmed dates.
            </p>
          </section>

          {/* What Happens If You Miss a Compliance Deadline? */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">What Happens If You Miss a Compliance Deadline?</h2>
            <p className="text-gray-700 mb-4">
              Consequences vary depending on the requirement and local authority.
            </p>
            <p className="text-sm font-medium text-gray-700 mb-2">Common issues include:</p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Enforcement notices</li>
              <li>Financial penalties</li>
              <li>Restrictions on serving notices</li>
              <li>Tenant disputes</li>
            </ul>
            <p className="text-gray-700 mb-4">
              Proactive tracking reduces the likelihood of oversight.
            </p>
            <p className="text-gray-700 mb-4">
              Instead of manual reminders, automated systems send notifications before expiry.
            </p>
          </section>

          {/* Lead magnet: Download the Free Landlord Compliance Checklist (PDF) */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Download the Free Landlord Compliance Checklist (PDF)</h2>
            <p className="text-gray-700 mb-4">
              If you prefer a manual overview, you can use a structured checklist covering:
            </p>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Gas Safety</li>
              <li>EICR</li>
              <li>EPC</li>
              <li>Licensing</li>
              <li>Tenancy documentation</li>
            </ul>
            <p className="text-gray-700 mb-6">
              Download the editable checklist and use it as a starting framework.
            </p>
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              onClick={() => setShowChecklistModal(true)}
            >
              Download Free Checklist
            </Button>
            <p className="text-xs text-gray-500 mt-4">
              Track this digitally at pleerityenterprise.co.uk
            </p>
          </section>
          <ChecklistDownloadModal open={showChecklistModal} onOpenChange={setShowChecklistModal} />

          {/* Final Thoughts */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Final Thoughts</h2>
            <p className="text-gray-700 mb-4">
              Landlord compliance is not about complexity.
              <br />
              It is about structure.
            </p>
            <p className="text-gray-700 mb-6">
              When documents, dates, and reminders are centralised, oversight becomes significantly easier.
            </p>
            <p className="text-gray-700 mb-6">
              If you want to track your UK landlord compliance checklist digitally, automate reminders, and organise documents per property:
            </p>
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
              <Link to="/compliance-vault-pro">
                Access Compliance Vault Pro
                <ArrowRight className="w-5 h-5 ml-2 inline" />
              </Link>
            </Button>
          </section>

          {/* Internal links */}
          <section className="mb-10 pt-8 border-t border-gray-200">
            <h2 className="text-lg font-semibold text-midnight-blue mb-4">Related guides</h2>
            <ul className="space-y-2 text-gray-700">
              <li><Link to="/insights/gas-safety-certificate-expiry-tracking-guide" className="text-electric-teal hover:underline">Gas Safety Expiry Guide</Link></li>
              <li><Link to="/insights/understanding-eicr-expiry-reminders" className="text-electric-teal hover:underline">EICR Expiry Guide</Link></li>
              <li><Link to="/insights/hmo-compliance-tracking-uk-explained" className="text-electric-teal hover:underline">HMO Compliance Guide</Link></li>
              <li><Link to="/compliance-vault-pro" className="text-electric-teal hover:underline">Compliance Vault Pro</Link></li>
              <li><Link to="/pricing" className="text-electric-teal hover:underline">Pricing</Link></li>
            </ul>
          </section>

          {/* FAQ */}
          <section className="mb-12">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Frequently asked questions</h2>
            <Accordion type="single" collapsible className="w-full">
              {FAQ_ITEMS.map((item, i) => (
                <AccordionItem key={i} value={`faq-${i}`} className="border rounded-lg mb-3 px-4">
                  <AccordionTrigger className="text-left font-medium text-midnight-blue hover:no-underline py-4">
                    {item.question}
                  </AccordionTrigger>
                  <AccordionContent className="text-gray-700 pb-4">
                    {item.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </section>
        </div>
      </article>
    </PublicLayout>
  );
}
