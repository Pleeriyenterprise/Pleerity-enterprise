import React from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Briefcase, ArrowRight } from 'lucide-react';

const CareersPage = () => {
  return (
    <PublicLayout>
      <SEOHead
        title="Careers at Pleerity | Join Our Team"
        description="Join Pleerity Enterprise and help build the future of property compliance technology."
        canonicalUrl="/careers"
      />

      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
          <Briefcase className="w-4 h-4 mr-2" />
          Careers
        </div>
        
        <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
          Join Our Team
        </h1>
        
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
          We're building the future of property compliance technology. 
          Career opportunities coming soon.
        </p>

        <div className="mt-12">
          <Button
            size="lg"
            className="bg-electric-teal hover:bg-electric-teal/90 text-white px-8"
            asChild
          >
            <Link to="/contact">
              Get in Touch
              <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default CareersPage;
