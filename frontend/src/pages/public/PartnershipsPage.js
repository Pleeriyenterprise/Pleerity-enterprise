import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead } from '../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Handshake, Building2, Users, ArrowRight, CheckCircle2 } from 'lucide-react';

const PartnershipsPage = () => {
  const partnerTypes = [
    {
      icon: Building2,
      title: 'Letting Agents',
      description: 'White-label Compliance Vault Pro for your clients. Offer compliance management as part of your service.',
      benefits: ['Custom branding', 'Volume discounts', 'Dedicated support', 'API integration'],
    },
    {
      icon: Users,
      title: 'Landlord Associations',
      description: 'Exclusive member benefits and group pricing for your association members.',
      benefits: ['Member discounts', 'Co-branded materials', 'Training sessions', 'Priority support'],
    },
    {
      icon: Handshake,
      title: 'Service Providers',
      description: 'Integrate your services with Compliance Vault Pro. Gas engineers, electricians, and contractors.',
      benefits: ['Lead generation', 'Automated bookings', 'Certificate uploads', 'Featured listing'],
    },
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Partnerships"
        description="Partner with Pleerity Enterprise. Opportunities for letting agents, landlord associations, and service providers."
        canonicalUrl="/partnerships"
      />

      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
            Partner With Us
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Join our partner ecosystem and grow your business while helping landlords stay compliant.
          </p>
          <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90" asChild>
            <Link to="/contact">
              Become a Partner
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-midnight-blue mb-12 text-center">
            Partnership Opportunities
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {partnerTypes.map((type) => (
              <Card key={type.title} className="border-0 shadow-lg">
                <CardContent className="p-8">
                  <div className="w-14 h-14 bg-electric-teal/10 rounded-xl flex items-center justify-center mb-6">
                    <type.icon className="w-7 h-7 text-electric-teal" />
                  </div>
                  <h3 className="text-xl font-bold text-midnight-blue mb-3">{type.title}</h3>
                  <p className="text-gray-600 mb-6">{type.description}</p>
                  <ul className="space-y-2">
                    {type.benefits.map((benefit) => (
                      <li key={benefit} className="flex items-center text-sm text-gray-700">
                        <CheckCircle2 className="w-4 h-4 text-electric-teal mr-2" />
                        {benefit}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-6">
            Ready to Partner?
          </h2>
          <p className="text-gray-300 mb-8">
            Get in touch to discuss partnership opportunities and how we can work together.
          </p>
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90"
            asChild
          >
            <Link to="/contact">Contact Us</Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PartnershipsPage;
