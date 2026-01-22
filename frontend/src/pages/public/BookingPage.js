import React from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Card, CardContent } from '../../components/ui/card';
import { Calendar, Clock, CheckCircle2 } from 'lucide-react';

const BookingPage = () => {
  const benefits = [
    'Learn how Compliance Vault Pro can simplify your compliance',
    'Get personalized recommendations for your portfolio',
    'See a live demo of the platform',
    'Ask questions and get expert answers',
    'No obligation - just helpful guidance',
  ];

  return (
    <PublicLayout>
      <SEOHead
        title="Book a Consultation"
        description="Schedule a free consultation with our compliance experts. Learn how Compliance Vault Pro can simplify your landlord compliance."
        canonicalUrl="/booking"
      />

      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-start">
            {/* Left Column - Info */}
            <div>
              <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
                Book a Consultation
              </h1>
              <p className="text-xl text-gray-600 mb-8">
                Schedule a free 30-minute call with our compliance experts. 
                We'll show you how Compliance Vault Pro can transform your property management.
              </p>

              <Card className="border-0 shadow-lg mb-8">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-midnight-blue mb-4">
                    What to expect:
                  </h3>
                  <ul className="space-y-3">
                    {benefits.map((benefit) => (
                      <li key={benefit} className="flex items-start">
                        <CheckCircle2 className="w-5 h-5 text-electric-teal shrink-0 mr-3 mt-0.5" />
                        <span className="text-gray-700">{benefit}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <div className="flex items-center space-x-6 text-gray-600">
                <div className="flex items-center">
                  <Clock className="w-5 h-5 mr-2 text-electric-teal" />
                  <span>30 minutes</span>
                </div>
                <div className="flex items-center">
                  <Calendar className="w-5 h-5 mr-2 text-electric-teal" />
                  <span>Video call</span>
                </div>
              </div>
            </div>

            {/* Right Column - Calendly Embed */}
            <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
              <div className="p-4 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-midnight-blue text-center">
                  Select a Time
                </h2>
              </div>
              {/* Calendly Embed Placeholder */}
              <div 
                className="calendly-inline-widget" 
                data-url="https://calendly.com/pleerity/consultation"
                style={{ minWidth: '320px', height: '630px' }}
                data-testid="calendly-embed"
              >
                {/* Fallback content while Calendly loads */}
                <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                  <Calendar className="w-16 h-16 text-gray-300 mb-4" />
                  <p className="text-gray-500 mb-4">
                    Loading calendar...
                  </p>
                  <p className="text-sm text-gray-400">
                    If the calendar doesn't load, please{' '}
                    <a 
                      href="https://calendly.com/pleerity/consultation" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-electric-teal hover:underline"
                    >
                      click here to book directly
                    </a>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Calendly Script */}
      <script 
        type="text/javascript" 
        src="https://assets.calendly.com/assets/external/widget.js" 
        async
      />
    </PublicLayout>
  );
};

export default BookingPage;
