import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Handshake, ArrowRight } from 'lucide-react';

const PartnershipsPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Partnerships | Pleerity Enterprise"
        description="Partner with Pleerity to deliver compliance solutions to your clients."
        canonicalUrl="/partnerships"
      />

      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
          <Handshake className="w-4 h-4 mr-2" />
          Partnerships
        </div>
        
        <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
          Partner With Us
        </h1>
        
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
          Interested in partnering with Pleerity? We're always looking to collaborate 
          with organizations that share our commitment to compliance excellence.
        </p>

        <div className="mt-12">
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/contact">
              Contact Us
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default PartnershipsPage;
