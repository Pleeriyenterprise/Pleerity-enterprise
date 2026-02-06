import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Shield, Zap, TrendingUp, Building, ArrowRight } from 'lucide-react';

const AboutPage = () => {
  const principles = [
    { icon: Shield, title: 'Simplicity', description: 'Systems should be easy to understand and use, without unnecessary steps or jargon.' },
    { icon: Zap, title: 'Integrity', description: 'Compliance and automation must be designed with accuracy and data security at the centre.' },
    { icon: TrendingUp, title: 'Scalability', description: 'Solutions should grow with your business, quietly supporting increasing workloads and maturity.' }
  ];

  const partners = [
    { name: 'Stripe', description: 'Secure payment processing' },
    { name: 'AI language models', description: 'Intelligent document generation' },
    { name: 'UK regulatory standards', description: 'Trusted compliance frameworks' }
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="About Us | Pleerity Enterprise Ltd"
        description="Structured compliance and automation systems for organisations operating under regulatory, procedural, or audit pressure."
        canonicalUrl="/about"
      />

      <section className="bg-gradient-to-b from-gray-50 to-white py-20">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
            <Building className="w-4 h-4 mr-2" />
            About Pleerity Enterprise
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
            Structured compliance and automation systems for organisations operating under regulatory, procedural, or audit pressure.
          </h1>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">An Operational Approach to Compliance and Automation</h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              Pleerity Enterprise designs structured compliance and automation systems for organisations that operate 
              under regulatory, procedural, or audit pressure.
            </p>
            <p>
              We do not sell generic software or one-off tools. We build controlled operating systems that track 
              obligations, enforce consistency, and maintain audit-ready documentation over time.
            </p>
            <p>
              Our work is grounded in clear process mapping, defined compliance boundaries, documented workflows, 
              and ongoing visibility.
            </p>
            <p>
              We focus on systems that reduce risk, prevent failure points, and support long-term operational reliability.
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Our Story</h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              Pleerity began with a familiar frustration — hours lost chasing documents, renewals, and updates across 
              multiple platforms. What started as a focused compliance support service has since developed into a full 
              automation and intelligence practice serving landlords, SMEs, and professional service firms across the UK.
            </p>
            <p>
              We design the tools we once needed ourselves: practical automation, structured compliance, and clear 
              documentation suited to real business environments rather than technical experts.
            </p>
            <p>
              Today, our systems help clients reduce administrative workload, prevent missed obligations, and make 
              informed decisions faster — without additional staff or software complexity.
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-8 text-center">Our Philosophy</h2>
          <p className="text-gray-600 text-center mb-12">
            We believe technology should simplify, not overwhelm. Every solution we create follows three core principles:
          </p>
          <div className="grid md:grid-cols-3 gap-8">
            {principles.map((p, i) => {
              const Icon = p.icon;
              return (
                <Card key={i} className="text-center">
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

      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Security & Data Handling</h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              All systems are designed with controlled access, role-based visibility, and secure document handling in mind.
            </p>
            <p>
              We do not monetise client data, resell information, or use client systems for unrelated training or 
              experimentation. Data access is limited strictly to what is operationally required to deliver agreed services.
            </p>
            <p>
              Client data is stored using secure infrastructure with encryption in transit and access controls. 
              Access controls are role-based and auditable. We do not share client information with third parties 
              except where required for service delivery or legal compliance.
            </p>
            <p className="font-semibold text-midnight-blue">
              Compliance should never be uncertain. Our role is to provide clarity and confidence at every stage.
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Our Team</h2>
          <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
            <p>
              Pleerity is a UK-based team of automation specialists, compliance professionals, and workflow designers. 
              Each project is shaped by people who understand the relationship between regulation, operations, and trust.
            </p>
            <p>
              We do not outsource client work, and we do not rely on rigid templates. Instead, we build systems that 
              fit the way you work and deliver consistent results day after day.
            </p>
          </div>
        </div>
      </section>

      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-midnight-blue mb-8">Our Partners</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {partners.map((p, i) => (
              <div key={i} className="bg-white p-6 rounded-lg border">
                <h3 className="font-semibold text-midnight-blue mb-2">{p.name}</h3>
                <p className="text-sm text-gray-600">{p.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">Ready to Get Started?</h2>
          <p className="text-lg text-gray-300 mb-8">Explore our services and see how we can help your organisation.</p>
          <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
            <Link to="/services">View Services<ArrowRight className="w-5 h-5 ml-2" /></Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default AboutPage;
