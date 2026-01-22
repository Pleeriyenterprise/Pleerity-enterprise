import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead } from '../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Briefcase, MapPin, ArrowRight } from 'lucide-react';

const CareersPage = () => {
  // Placeholder - no open positions initially
  const openPositions = [];

  return (
    <PublicLayout>
      <SEOHead
        title="Careers"
        description="Join Pleerity Enterprise. We're building the future of property compliance. View open positions and apply."
        canonicalUrl="/careers"
      />

      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
            Join Our Team
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            We're building the future of property compliance. Join us in making landlords' lives easier.
          </p>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-midnight-blue mb-8">Open Positions</h2>

          {openPositions.length === 0 ? (
            <Card className="border-gray-200">
              <CardContent className="p-8 text-center">
                <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-midnight-blue mb-2">
                  No Open Positions
                </h3>
                <p className="text-gray-600 mb-6">
                  We don't have any open positions right now, but we're always interested in 
                  hearing from talented people.
                </p>
                <Button variant="outline" asChild>
                  <Link to="/contact">Get in Touch</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {openPositions.map((position) => (
                <Card key={position.id} className="hover:shadow-lg transition-shadow">
                  <CardContent className="p-6">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-lg font-semibold text-midnight-blue mb-2">
                          {position.title}
                        </h3>
                        <div className="flex items-center text-gray-500 text-sm space-x-4">
                          <span className="flex items-center">
                            <Briefcase className="w-4 h-4 mr-1" />
                            {position.type}
                          </span>
                          <span className="flex items-center">
                            <MapPin className="w-4 h-4 mr-1" />
                            {position.location}
                          </span>
                        </div>
                      </div>
                      <Button size="sm" asChild>
                        <Link to={`/careers/${position.id}`}>
                          View
                          <ArrowRight className="w-4 h-4 ml-1" />
                        </Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="py-16 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-bold text-midnight-blue mb-4">
            Why Work With Us?
          </h2>
          <div className="grid md:grid-cols-3 gap-6 mt-8">
            {[
              { title: 'Remote First', description: 'Work from anywhere in the UK' },
              { title: 'Growth', description: 'Join an early-stage company with big ambitions' },
              { title: 'Impact', description: 'Help thousands of landlords stay compliant' },
            ].map((item) => (
              <Card key={item.title} className="border-0 shadow-lg">
                <CardContent className="p-6 text-center">
                  <h3 className="font-semibold text-midnight-blue mb-2">{item.title}</h3>
                  <p className="text-gray-600 text-sm">{item.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CareersPage;
