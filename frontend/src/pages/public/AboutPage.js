/**
 * About — Product-led positioning, trust, and Compliance Vault Pro alignment.
 * Compliance-safe language throughout; no legal claims.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import {
  FileSearch,
  Gauge,
  History,
  Shield,
  Lock,
  Users,
  Eye,
  Cpu,
  AlertCircle,
  Building2,
  UserCheck,
  Briefcase,
  ArrowRight,
} from 'lucide-react';

const PRINCIPLES = [
  {
    icon: FileSearch,
    title: 'Evidence First',
    description: 'We track documents, not assumptions.',
  },
  {
    icon: Gauge,
    title: 'Structured Indicators',
    description: 'We provide risk indicators, not legal verdicts.',
  },
  {
    icon: History,
    title: 'Audit Visibility',
    description: 'Every update is logged. Every change traceable.',
  },
];

const WHO_ITS_FOR = [
  { icon: UserCheck, label: 'Solo landlords' },
  { icon: Building2, label: 'Portfolio landlords' },
  { icon: Briefcase, label: 'Managing agents' },
  { icon: Users, label: 'Property professionals' },
];

const AboutPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="About | Pleerity Enterprise"
        description="Built for organisations that need structure, not guesswork. Structured compliance technology and audit visibility for UK landlords and property professionals."
        canonicalUrl="/about"
      />

      {/* Hero — Founder-driven positioning */}
      <section className="bg-gradient-to-b from-gray-50 to-white py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
            Built for Organisations That Need Structure — Not Guesswork
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Compliance is often reactive. We built structured systems to make it proactive.
          </p>
        </div>
      </section>

      {/* The Problem We Saw */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">The Problem We Saw</h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              Landlords juggling certificates in email folders. Deadlines missed. Spreadsheets breaking. 
              No central audit trail.
            </p>
            <p>
              Compliance Vault Pro was created to bring structure, visibility, and automation to this process.
            </p>
          </div>
        </div>
      </section>

      {/* Our Approach — Three principles */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-4 text-center">Our Approach</h2>
          <p className="text-gray-600 text-center mb-12 max-w-2xl mx-auto">
            Our approach is built on three principles:
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {PRINCIPLES.map((p, i) => {
              const Icon = p.icon;
              return (
                <Card key={i} className="text-center border-2 border-transparent hover:border-electric-teal/30 transition-colors">
                  <CardContent className="pt-6">
                    <div className="w-16 h-16 bg-electric-teal/10 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Icon className="w-8 h-8 text-electric-teal" />
                    </div>
                    <h3 className="text-xl font-semibold text-midnight-blue mb-3">{p.title}</h3>
                    <p className="text-gray-600">{p.description}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Security & Data Handling — Expanded */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6 flex items-center gap-2">
            <Shield className="w-8 h-8 text-electric-teal" />
            Security & Data Handling
          </h2>
          <ul className="space-y-3 text-gray-700">
            <li className="flex items-start gap-3">
              <Lock className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
              <span>Secure cloud infrastructure with encryption in transit</span>
            </li>
            <li className="flex items-start gap-3">
              <Users className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
              <span>Role-based access controls</span>
            </li>
            <li className="flex items-start gap-3">
              <History className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
              <span>Audit logs for traceability</span>
            </li>
            <li className="flex items-start gap-3">
              <Eye className="w-5 h-5 text-electric-teal shrink-0 mt-0.5" />
              <span>Data access limited to what is operationally required; we do not monetise or resell client data</span>
            </li>
          </ul>
          <div className="mt-8 p-4 rounded-lg bg-amber-50 border border-amber-200">
            <p className="text-gray-700 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <span>
                <strong className="text-midnight-blue">Compliance disclaimer:</strong> We do not provide legal advice or certification. 
                Our platform supports compliance oversight through structured tracking and reporting; you remain responsible for 
                meeting your legal and regulatory obligations.
              </span>
            </p>
          </div>
        </div>
      </section>

      {/* AI Philosophy */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6 flex items-center gap-2">
            <Cpu className="w-8 h-8 text-electric-teal" />
            AI Philosophy
          </h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              <strong className="text-midnight-blue">AI is assistive only.</strong> All extracted data requires user confirmation 
              before it is applied. Compliance status is determined by structured rules and your confirmed inputs, not by 
              AI-generated legal conclusions.
            </p>
          </div>
        </div>
      </section>

      {/* Who It's Built For */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-8 text-center">Who It's Built For</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {WHO_ITS_FOR.map((item, i) => {
              const Icon = item.icon;
              return (
                <div
                  key={i}
                  className="flex flex-col items-center text-center p-6 rounded-lg border-2 border-gray-100 hover:border-electric-teal/30 transition-colors"
                >
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-full flex items-center justify-center mb-3">
                    <Icon className="w-6 h-6 text-electric-teal" />
                  </div>
                  <span className="font-medium text-midnight-blue">{item.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">See How Structured Compliance Works</h2>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/compliance-vault-pro">
              Explore Compliance Vault Pro
              <ArrowRight className="w-5 h-5 ml-2 inline-block" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default AboutPage;
