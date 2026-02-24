/**
 * UK Landlord Compliance Checklist (2026 Guide) — SEO-optimised long-form article.
 * Compliance-safe language; no legal claims. Inline CTAs, FAQ schema, lead magnet.
 */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../../components/public/PublicLayout';
import { SEOHead, createArticleSchema, createFAQSchema } from '../../../components/public/SEOHead';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Card, CardContent } from '../../../components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../../components/ui/accordion';
import { ChevronLeft, ArrowRight } from 'lucide-react';

const META_TITLE = 'UK Landlord Compliance Checklist (2026 Guide)';
const META_DESCRIPTION = 'A practical UK landlord compliance checklist for 2026. Track gas safety, EICR, EPC, HMO licences and expiry dates with structured reminders and documentation.';
const CANONICAL = '/insights/uk-landlord-compliance-checklist-2026';
const PUBLISHED = '2026-01-01';
const UPDATED = '2026-01-01';

const FAQ_ITEMS = [
  {
    question: 'Is landlord compliance mandatory in the UK?',
    answer: 'Yes. Landlords in the UK have legal obligations around gas safety, electrical safety (EICR), energy performance (EPC), and—where applicable—HMO licensing and deposit protection. Requirements vary by property type and location. This guide is informational; check current legislation and your local authority for your specific duties.',
  },
  {
    question: 'How often do gas safety certificates expire?',
    answer: 'Gas safety records (CP12) are typically valid for 12 months and must be renewed annually where gas appliances are present. Landlords must arrange an inspection by a Gas Safe registered engineer and provide a copy to tenants. Keeping track of the expiry date helps avoid gaps in compliance.',
  },
  {
    question: 'Do all landlords need an HMO licence?',
    answer: 'Not all. HMO (House in Multiple Occupation) licensing applies to certain multi-occupancy properties; rules and thresholds vary by local authority. Some areas have additional or selective licensing. Check your local authority guidance to see if your property requires a licence and what the renewal period is.',
  },
  {
    question: 'What happens if I miss an EICR renewal?',
    answer: 'Electrical safety (EICR) requirements must be met for most rented properties. Missing a renewal can create risk and potential enforcement action depending on the circumstances. Consequences vary; this guide does not constitute legal advice. Proactive tracking and reminders help you stay ahead of renewal dates.',
  },
];

export default function UKLandlordComplianceChecklist2026() {
  const [leadEmail, setLeadEmail] = useState('');

  const articleSchema = createArticleSchema(
    META_TITLE,
    META_DESCRIPTION,
    PUBLISHED,
    UPDATED
  );
  const faqSchema = createFAQSchema(FAQ_ITEMS);

  const handleLeadSubmit = (e) => {
    e.preventDefault();
    // Placeholder: wire to your email/CRM endpoint when ready
  };

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
              UK Landlord Compliance Checklist (2026)
            </h1>
            <p className="text-xl text-gray-600 leading-relaxed mb-6">
              Being a UK landlord involves managing multiple certificates, documents, and renewal deadlines. This guide outlines the core compliance items commonly required and how to track them in a structured way.
            </p>
            <p className="text-sm text-gray-500 italic border-l-4 border-amber-200 pl-4">
              This guide is informational and does not constitute legal advice. Requirements may vary depending on property type and local authority.
            </p>
          </header>

          {/* Core Safety Certificates */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Core Safety Certificates</h2>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Gas Safety Record (CP12)</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Required annually (where gas appliances exist)</li>
              <li>Issued by a Gas Safe registered engineer</li>
              <li>Keep a record and provide a copy to tenants</li>
            </ul>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700 mb-3">
                  Instead of tracking CP12 dates manually, use automated expiry reminders inside{' '}
                  <Link to="/compliance-vault-pro" className="text-electric-teal font-medium hover:underline">Compliance Vault Pro</Link>.
                </p>
                <Button size="sm" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
                  <Link to="/intake/start">Start Free Trial <ArrowRight className="w-4 h-4 ml-1 inline" /></Link>
                </Button>
              </CardContent>
            </Card>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Electrical Installation Condition Report (EICR)</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Typically every 5 years (subject to property type)</li>
              <li>Required for most rented properties</li>
            </ul>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700">
                  Set automated <Link to="/insights/understanding-eicr-expiry-reminders" className="text-electric-teal font-medium hover:underline">EICR expiry reminders</Link> to avoid missed deadlines.
                </p>
              </CardContent>
            </Card>

            <h3 className="text-lg font-semibold text-midnight-blue mt-6 mb-3">Energy Performance Certificate (EPC)</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-2">
              <li>Required when letting</li>
              <li>Must meet minimum rating where applicable</li>
            </ul>
          </section>

          {/* Licensing & Property Type */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Licensing & Property Type Requirements</h2>
            <h3 className="text-lg font-semibold text-midnight-blue mb-3">HMO Licence (where applicable)</h3>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Required for certain multi-occupancy properties</li>
              <li>Renewal periods vary by council</li>
            </ul>
            <p className="text-gray-600 text-sm mb-4">Check local authority guidance for your area.</p>
            <Card className="bg-electric-teal/5 border-electric-teal/20 my-6">
              <CardContent className="p-4">
                <p className="text-gray-700">
                  Track HMO licence renewal dates inside a structured compliance dashboard. See our{' '}
                  <Link to="/insights/hmo-compliance-tracking-uk-explained" className="text-electric-teal font-medium hover:underline">HMO compliance tracking guide</Link>.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Tenancy & Documentation */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Tenancy & Documentation Records</h2>
            <ul className="list-disc list-inside text-gray-700 space-y-2 mb-4">
              <li>Tenancy agreements</li>
              <li>Deposit protection evidence</li>
              <li>Prescribed information</li>
              <li>Right-to-rent checks</li>
              <li>Inventory and check-in reports</li>
            </ul>
            <p className="text-gray-600">
              These may not have expiry dates but should be stored and organised for each tenancy.
            </p>
          </section>

          {/* How to Track Compliance */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">How to Track Compliance Properly</h2>
            <p className="text-gray-700 mb-4">
              Most landlords track compliance using spreadsheets, email reminders, and calendar alerts. Common risks include missed renewals, fragmented storage, and no single view across the portfolio.
            </p>
            <p className="text-gray-700 mb-4">
              A structured compliance tracking system centralises documents, expiry dates, reminder schedules, and property-level visibility.
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
              Each property may have different certificates, expiry dates, and licence requirements. Tracking per property prevents confusion. A structured risk indicator can help you see which properties need attention—without overpromising outcomes.
            </p>
          </section>

          {/* What Happens If You Miss a Deadline */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">What Happens If You Miss a Deadline?</h2>
            <p className="text-gray-700 mb-4">
              Consequences can vary depending on the obligation and circumstances. This is why proactive tracking matters. Set reminders before expiry instead of reacting after.
            </p>
            <Button variant="outline" className="border-electric-teal text-electric-teal hover:bg-electric-teal/10" asChild>
              <Link to="/intake/start">Set up reminders in Compliance Vault Pro <ArrowRight className="w-4 h-4 ml-2 inline" /></Link>
            </Button>
          </section>

          {/* Lead magnet: Downloadable Checklist */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Downloadable Landlord Compliance Checklist (Free PDF)</h2>
            <p className="text-gray-700 mb-6">
              Get our free, editable checklist for UK landlord compliance. Enter your email and we&apos;ll send the PDF to your inbox.
            </p>
            <Card className="bg-gray-50 border-gray-200 max-w-lg">
              <CardContent className="p-6">
                <form onSubmit={handleLeadSubmit} className="space-y-4">
                  <Input
                    type="email"
                    placeholder="Your email"
                    value={leadEmail}
                    onChange={(e) => setLeadEmail(e.target.value)}
                    className="h-11"
                    required
                  />
                  <Button type="submit" className="w-full bg-electric-teal hover:bg-electric-teal/90">
                    Send me the checklist
                  </Button>
                </form>
                <p className="text-xs text-gray-500 mt-4">
                  Track this digitally at pleerityenterprise.co.uk
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Final Thoughts */}
          <section className="mb-10">
            <h2 className="text-2xl font-bold text-midnight-blue mb-6">Final Thoughts</h2>
            <p className="text-gray-700 mb-6">
              Compliance is not about panic. It&apos;s about structure and visibility. Start tracking your landlord compliance checklist today.
            </p>
            <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
              <Link to="/intake/start">
                Start Free Trial
                <ArrowRight className="w-5 h-5 ml-2 inline" />
              </Link>
            </Button>
          </section>

          {/* Internal links */}
          <section className="mb-10 pt-8 border-t border-gray-200">
            <h2 className="text-lg font-semibold text-midnight-blue mb-4">Related guides</h2>
            <ul className="space-y-2 text-gray-700">
              <li><Link to="/insights/gas-safety-certificate-expiry-tracking-guide" className="text-electric-teal hover:underline">Gas Safety Certificate Expiry Tracking Guide</Link></li>
              <li><Link to="/insights/understanding-eicr-expiry-reminders" className="text-electric-teal hover:underline">Understanding EICR Expiry & Reminders</Link></li>
              <li><Link to="/insights/hmo-compliance-tracking-uk-explained" className="text-electric-teal hover:underline">HMO Compliance Tracking UK Explained</Link></li>
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
