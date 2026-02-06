import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Handshake, Shield, Zap, Lock, Rocket, CheckCircle, Users, Building, GraduationCap, ArrowRight } from 'lucide-react';

const PartnershipsPage = () => {
  const benefits = [
    { icon: Shield, title: 'Proven Compliance Expertise', description: 'We specialise in automated documentation, digital compliance, data governance, and landlord regulatory workflows. Our systems meet UK GDPR and Home Office-aligned standards.' },
    { icon: Zap, title: 'Scalable AI Automation', description: 'Partners can integrate our AI-powered templates, document generation tools, and workflow engines into their service delivery.' },
    { icon: Lock, title: 'Secure Infrastructure', description: 'All automation and data handling are delivered through a secure, auditable environment suitable for regulated sectors.' },
    { icon: Handshake, title: 'Flexible Collaboration Models', description: 'We support referral partnerships, white-label solutions, API integrations, and research collaborations.' },
    { icon: Rocket, title: 'Fast Implementation', description: 'Our systems are designed for rapid deployment, enabling partners to offer new capabilities without long development cycles.' }
  ];

  const partnershipTypes = [
    'Referral Partnerships',
    'White-Label Automations',
    'Technology Integrations',
    'Compliance Collaboration',
    'Service Delivery Partnerships',
    'Research & Development Collaborations',
    'Enterprise partnership integration network'
  ];

  const partners = [
    { icon: Building, text: 'Property management companies' },
    { icon: Shield, text: 'Legal and professional service firms' },
    { icon: Zap, text: 'Technology and SaaS companies' },
    { icon: Building, text: 'Government-related programmes' },
    { icon: GraduationCap, text: 'Universities and research groups' },
    { icon: Users, text: 'Recruitment and HR agencies' },
    { icon: Shield, text: 'Compliance consultants' },
    { icon: GraduationCap, text: 'Training organisations' }
  ];

  const standards = [
    'UK GDPR and the Data Protection Act 2018',
    'Ethical AI usage practices',
    'Transparent operational standards',
    'Security and confidentiality requirements',
    'Home Office-aligned frameworks where applicable'
  ];

  const faqs = [
    { q: 'Do you accept international partners?', a: 'Yes, provided regulatory and data handling standards can be met.' },
    { q: 'Is there a minimum business size required?', a: 'No. We work with start-ups, SMEs, and established organisations.' },
    { q: 'Do you offer exclusivity?', a: 'Only in rare, strategic cases.' },
    { q: 'Can partnerships be fully remote?', a: 'Yes. All communication and collaboration can be delivered online.' }
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Partnerships | Pleerity Enterprise Ltd"
        description="Collaborate with Pleerity to deliver secure automation, compliance, and digital transformation solutions."
        canonicalUrl="/partnerships"
      />

      {/* Hero */}
      <section className="bg-gradient-to-b from-gray-50 to-white py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
            <Handshake className="w-4 h-4 mr-2" />
            Partnerships
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-midnight-blue leading-tight mb-6">
            Partnerships Built on Trust and Operational Excellence
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Collaborate with Pleerity Enterprise Ltd to deliver secure automation, compliance, and digital 
            transformation solutions that create measurable value.
          </p>
          <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
            <a href="#partner-form">Become a Partner<ArrowRight className="w-5 h-5 ml-2" /></a>
          </Button>
        </div>
      </section>

      {/* Introduction */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="prose prose-lg max-w-none text-gray-700">
            <p>
              Pleerity Enterprise Ltd collaborates with organisations that share a commitment to operational 
              excellence, regulatory compliance, and intelligent automation.
            </p>
            <p>
              Our partnership model is designed to help organisations integrate trusted AI solutions, expand 
              service capabilities, or unlock new efficiencies across compliance and documentation workflows.
            </p>
            <p>
              Whether you are a technology provider, consultancy, property service business, or academic 
              institution, we welcome proposals that create measurable value and uphold strong compliance standards.
            </p>
          </div>
        </div>
      </section>

      {/* Why Partner */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">Why Partner With Us</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {benefits.map((benefit, i) => {
              const Icon = benefit.icon;
              return (
                <Card key={i} className="border-2 hover:border-electric-teal transition-colors">
                  <CardContent className="p-6">
                    <Icon className="w-10 h-10 text-electric-teal mb-4" />
                    <h3 className="text-lg font-semibold text-midnight-blue mb-2">{benefit.title}</h3>
                    <p className="text-sm text-gray-600">{benefit.description}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Types of Partnerships */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-8">Types of Partnerships We Support</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {partnershipTypes.map((type, i) => (
              <div key={i} className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
                <CheckCircle className="w-5 h-5 text-electric-teal flex-shrink-0" />
                <span className="text-gray-700">{type}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Who We Work With */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-4">Who We Work With</h2>
          <p className="text-gray-600 mb-8">Our partnerships are suitable for:</p>
          <div className="grid md:grid-cols-2 gap-4">
            {partners.map((p, i) => {
              const Icon = p.icon;
              return (
                <div key={i} className="flex items-center gap-3">
                  <Icon className="w-5 h-5 text-electric-teal" />
                  <span className="text-gray-700">{p.text}</span>
                </div>
              );
            })}
          </div>
          <p className="text-gray-600 mt-6 italic">
            If your organisation delivers compliance, automation, risk, or digital transformation services, 
            we are open to a conversation.
          </p>
        </div>
      </section>

      {/* Partnership Standards */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Partnership Standards</h2>
          <p className="text-gray-700 mb-4">All partnerships must align with:</p>
          <ul className="space-y-3">
            {standards.map((std, i) => (
              <li key={i} className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-electric-teal flex-shrink-0 mt-0.5" />
                <span className="text-gray-700">{std}</span>
              </li>
            ))}
          </ul>
          <p className="text-gray-600 mt-6">
            Each partnership request undergoes a structured review before approval.
          </p>
        </div>
      </section>

      {/* Process */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">How the Partnership Works</h2>
          <div className="grid md:grid-cols-5 gap-4">
            {[
              {n:'1',t:'Submit Your Enquiry',d:'Complete the online partnership form'},
              {n:'2',t:'Compliance Review',d:'We evaluate suitability based on capability'},
              {n:'3',t:'Proposal Discussion',d:'Structured call to refine scope'},
              {n:'4',t:'Agreement & Onboarding',d:'Review and sign cooperation agreement'},
              {n:'5',t:'Launch & Support',d:'Onboarding and technical support'}
            ].map(s => (
              <div key={s.n} className="text-center">
                <div className="w-12 h-12 bg-electric-teal text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-3">{s.n}</div>
                <h3 className="font-semibold text-midnight-blue mb-2 text-sm">{s.t}</h3>
                <p className="text-xs text-gray-600">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-8">Partnership FAQ</h2>
          <div className="space-y-6">
            {faqs.map((faq, i) => (
              <div key={i} className="border-b pb-4">
                <h3 className="text-lg font-semibold text-midnight-blue mb-2">{faq.q}</h3>
                <p className="text-gray-600">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 bg-midnight-blue" id="partner-form">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">Ready to Partner With Us?</h2>
          <p className="text-lg text-gray-300 mb-8">Submit your partnership enquiry and let's explore how we can work together.</p>
          <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
            <Link to="/partnerships/enquiry">Become a Partner<ArrowRight className="w-5 h-5 ml-2" /></Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PartnershipsPage;
