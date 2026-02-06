import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Briefcase, CheckCircle, ArrowRight, Users, Shield, Zap, BookOpen } from 'lucide-react';

const CareersPage = () => {
  const benefits = [
    {
      icon: Shield,
      title: 'Structured, Process-Driven Work',
      description: 'Clear compliance frameworks guide our systems and workflows.'
    },
    {
      icon: Zap,
      title: 'Work With Real Impact',
      description: 'Our work helps landlords, SMEs, and professional firms meet legal requirements and improve operational safety.'
    },
    {
      icon: Users,
      title: 'Flexible Working Options',
      description: 'Hybrid and remote roles may be available depending on position.'
    },
    {
      icon: BookOpen,
      title: 'Training and Professional Development',
      description: 'Structured onboarding and training in AI tools, compliance procedures, digital record-keeping, and secure workflow systems.'
    },
    {
      icon: Shield,
      title: 'Ethical and Secure Environment',
      description: 'We follow UK GDPR data standards and maintain strict operational governance.'
    }
  ];

  const hiringValues = [
    'Professional integrity',
    'Strong ethics and data responsibility',
    'Accuracy in documentation and record-keeping',
    'Willingness to learn emerging technologies',
    'Commitment to secure and compliant working practices'
  ];

  const futureRoles = [
    {
      category: 'AI & Workflow Operations',
      roles: ['Automation Technician', 'Workflow Assistant', 'Data Quality and Review Officer']
    },
    {
      category: 'Compliance & Documentation',
      roles: ['Compliance Assistant', 'Documentation Analyst', 'Tenancy & Property Compliance Officer']
    },
    {
      category: 'Client Delivery',
      roles: ['Client Onboarding Coordinator', 'Support Desk Advisor']
    },
    {
      category: 'Administrative & Governance',
      roles: ['HR & Compliance Administrator', 'Operations Assistant']
    }
  ];

  const recruitmentSteps = [
    {
      number: '1',
      title: 'Join the Talent Pool',
      description: 'Submit your details using the Careers Form.'
    },
    {
      number: '2',
      title: 'Document Screening',
      description: 'Applications are reviewed against compliance criteria and role requirements.'
    },
    {
      number: '3',
      title: 'Interview & Assessment',
      description: 'Shortlisted applicants may complete a practical task.'
    },
    {
      number: '4',
      title: 'Onboarding',
      description: 'Successful applicants receive structured onboarding covering governance, internal systems, and right-to-work compliance.'
    }
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Careers - Join Our Team | Pleerity Enterprise Ltd"
        description="Join Pleerity Enterprise as we develop secure automation, compliance, and documentation solutions for organisations across the UK."
        canonicalUrl="/careers"
      />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28 text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
            <Briefcase className="w-4 h-4 mr-2" />
            Careers
          </div>
          
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-midnight-blue leading-tight mb-6">
            Build Systems That Make Businesses Stronger
          </h1>
          
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Join Pleerity Enterprise Ltd as we develop secure automation, compliance, and documentation 
            solutions for organisations across the UK.
          </p>
        </div>
      </section>

      {/* Join the Talent Pool */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Join the Talent Pool</h2>
          <div className="prose prose-lg max-w-none text-gray-700">
            <p>
              Pleerity Enterprise Ltd is a UK-based automation and compliance company providing AI-driven 
              workflows, digital documentation, and landlord compliance solutions. Our goal is to make complex 
              regulatory work simpler, safer, and more efficient for individuals and organisations.
            </p>
            <p>
              We are building a structured, professional team. As the company expands, we aim to recruit 
              individuals who value accuracy, responsibility, and strong attention to detail.
            </p>
            <p>
              We encourage prospective applicants to join our Talent Pool so they can be contacted when 
              suitable roles become available.
            </p>
          </div>
        </div>
      </section>

      {/* Our Hiring Philosophy */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Our Hiring Philosophy</h2>
          <p className="text-lg text-gray-700 mb-6">We recruit with care, prioritising:</p>
          <div className="grid md:grid-cols-2 gap-4">
            {hiringValues.map((value, index) => (
              <div key={index} className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-electric-teal flex-shrink-0 mt-1" />
                <span className="text-gray-700">{value}</span>
              </div>
            ))}
          </div>
          <p className="text-gray-600 mt-6">
            We believe that a stable and well-supported team produces the most reliable work for clients.
          </p>
        </div>
      </section>

      {/* Why Work With Us */}
      <section className="py-16 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">Why Work With Us</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {benefits.map((benefit, index) => {
              const Icon = benefit.icon;
              return (
                <Card key={index} className="border-2 hover:border-electric-teal transition-colors">
                  <CardContent className="p-6">
                    <div className="w-12 h-12 bg-electric-teal/10 rounded-lg flex items-center justify-center mb-4">
                      <Icon className="w-6 h-6 text-electric-teal" />
                    </div>
                    <h3 className="text-lg font-semibold text-midnight-blue mb-2">{benefit.title}</h3>
                    <p className="text-gray-600 text-sm">{benefit.description}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Future Roles */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-4">Future Roles</h2>
          <p className="text-gray-600 mb-8">
            As the company grows, we expect to recruit for:
          </p>
          <div className="space-y-6">
            {futureRoles.map((category, index) => (
              <div key={index} className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-xl font-semibold text-midnight-blue mb-3">{category.category}</h3>
                <ul className="space-y-2">
                  {category.roles.map((role, roleIndex) => (
                    <li key={roleIndex} className="flex items-center gap-2 text-gray-700">
                      <div className="w-1.5 h-1.5 bg-electric-teal rounded-full" />
                      {role}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="text-sm text-gray-500 mt-6 italic">
            These are not open positions yet. They reflect our anticipated hiring plan.
          </p>
        </div>
      </section>

      {/* How Recruitment Works */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">How Recruitment Works</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {recruitmentSteps.map((step, index) => (
              <div key={index} className="text-center">
                <div className="w-16 h-16 bg-electric-teal text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                  {step.number}
                </div>
                <h3 className="text-lg font-semibold text-midnight-blue mb-2">{step.title}</h3>
                <p className="text-sm text-gray-600">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Equal Opportunities */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">Equal Opportunities Statement</h2>
          <div className="prose prose-lg max-w-none text-gray-700">
            <p>Pleerity Enterprise Ltd is an equal-opportunity employer.</p>
            <p>We assess all applicants based on capability, competence, and integrity.</p>
            <p>
              We do not discriminate on the basis of age, gender, race, nationality, disability, or any 
              protected characteristic.
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Ready to Join Our Team?
          </h2>
          <p className="text-lg text-gray-300 mb-8 max-w-2xl mx-auto">
            Submit your details to our Talent Pool and we'll contact you when suitable roles become available.
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/careers/talent-pool">
              Join the Talent Pool
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CareersPage;
