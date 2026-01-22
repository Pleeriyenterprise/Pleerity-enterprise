import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
  Shield,
  Users,
  Award,
  Target,
  ArrowRight,
  MapPin,
  Building2,
} from 'lucide-react';

const AboutPage = () => {
  const values = [
    {
      icon: Shield,
      title: 'Trust & Reliability',
      description: 'We build systems that landlords can depend on. Your compliance is our priority.',
    },
    {
      icon: Target,
      title: 'Precision',
      description: 'Every deadline matters. Our platform tracks every certificate with exacting accuracy.',
    },
    {
      icon: Users,
      title: 'Customer Focus',
      description: 'We listen to landlords and build features that solve real problems.',
    },
    {
      icon: Award,
      title: 'Excellence',
      description: 'We strive for excellence in everything we do, from code to customer service.',
    },
  ];

  const stats = [
    { value: '500+', label: 'Properties Managed' },
    { value: '99.9%', label: 'Uptime' },
    { value: '24/7', label: 'System Monitoring' },
    { value: 'UK', label: 'Based & Operated' },
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="About Us"
        description="Learn about Pleerity Enterprise, a UK-based company providing AI-powered compliance and workflow automation for landlords and letting agents."
        canonicalUrl="/about"
      />

      {/* Hero Section */}
      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              About Pleerity Enterprise
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              We're on a mission to make property compliance simple, reliable, and stress-free 
              for UK landlords and letting agents.
            </p>
          </div>
        </div>
      </section>

      {/* Our Story */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold text-midnight-blue mb-6">Our Story</h2>
              <div className="space-y-4 text-gray-600">
                <p>
                  Pleerity Enterprise was founded with a simple observation: managing property 
                  compliance in the UK is unnecessarily complicated. Landlords juggle spreadsheets, 
                  chase contractors, and live in fear of missing crucial deadlines.
                </p>
                <p>
                  We built Compliance Vault Pro to change that. Our platform brings together 
                  intelligent document management, automated reminders, and professional services 
                  into one cohesive solution.
                </p>
                <p>
                  Today, we help landlords across the UK stay compliant with confidence. 
                  Our AI-powered tools save hours of admin work, while our expert services 
                  handle the complex stuff.
                </p>
              </div>
            </div>
            <div className="bg-gray-50 rounded-2xl p-8">
              <div className="grid grid-cols-2 gap-8">
                {stats.map((stat) => (
                  <div key={stat.label} className="text-center">
                    <div className="text-4xl font-bold text-electric-teal mb-2">{stat.value}</div>
                    <div className="text-sm text-gray-600">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Our Values */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold text-midnight-blue mb-4">Our Values</h2>
            <p className="text-lg text-gray-600">
              The principles that guide everything we do
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {values.map((value) => (
              <Card key={value.title} className="border-0 shadow-lg text-center">
                <CardContent className="pt-8">
                  <div className="w-14 h-14 bg-electric-teal/10 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <value.icon className="w-7 h-7 text-electric-teal" />
                  </div>
                  <h3 className="text-xl font-semibold text-midnight-blue mb-2">{value.title}</h3>
                  <p className="text-gray-600">{value.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* UK Based */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-midnight-blue rounded-2xl p-8 md:p-12">
            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div>
                <div className="flex items-center mb-4">
                  <MapPin className="w-6 h-6 text-electric-teal mr-2" />
                  <span className="text-white font-medium">UK Based & Operated</span>
                </div>
                <h2 className="text-3xl font-bold text-white mb-4">
                  Built for UK Landlords
                </h2>
                <p className="text-gray-300 mb-6">
                  We understand UK property law and compliance requirements because we're based 
                  here. Our platform is designed specifically for the regulations landlords in 
                  England, Wales, Scotland, and Northern Ireland need to meet.
                </p>
                <ul className="space-y-2 text-gray-300">
                  <li className="flex items-center">
                    <Building2 className="w-4 h-4 mr-2 text-electric-teal" />
                    Registered in England and Wales
                  </li>
                  <li className="flex items-center">
                    <Shield className="w-4 h-4 mr-2 text-electric-teal" />
                    GDPR Compliant
                  </li>
                  <li className="flex items-center">
                    <Users className="w-4 h-4 mr-2 text-electric-teal" />
                    UK-based support team
                  </li>
                </ul>
              </div>
              <div className="hidden md:block">
                <div className="bg-white/10 rounded-xl p-8 text-center">
                  <div className="text-6xl font-bold text-electric-teal mb-2">UK</div>
                  <div className="text-white">Proudly British</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-midnight-blue mb-6">
            Join Us on Our Mission
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            Whether you're looking to simplify your compliance or join our team, 
            we'd love to hear from you.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/intake/start">
                Get Started
                <ArrowRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/careers">View Careers</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/contact">Contact Us</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default AboutPage;
