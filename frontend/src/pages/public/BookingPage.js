import React, { useState } from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Calendar, Clock, CheckCircle2, Send, Loader2 } from 'lucide-react';
import { capturePricing } from '../../api/leadsApi';
import { toast } from '@/utils/portalNotifications';

const BookingPage = () => {
  const [callbackForm, setCallbackForm] = useState({ name: '', email: '', phone: '', marketing_consent: false });
  const [callbackSubmitting, setCallbackSubmitting] = useState(false);
  const [callbackSubmitted, setCallbackSubmitted] = useState(false);
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

            {/* Right Column - Calendly + Request callback */}
            <div className="space-y-6">
              <Card className="border-electric-teal/20 bg-electric-teal/5">
                <CardContent className="p-4">
                  <h3 className="font-semibold text-midnight-blue mb-2">Can&apos;t find a slot?</h3>
                  <p className="text-sm text-gray-600 mb-3">Request a callback and we&apos;ll arrange a time that works for you.</p>
                  {callbackSubmitted ? (
                    <p className="text-electric-teal font-medium text-sm">Thank you. We&apos;ll be in touch shortly.</p>
                  ) : (
                    <form
                      className="space-y-3"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        if (!callbackForm.email?.trim()) {
                          toast.error('Please enter your email.');
                          return;
                        }
                        setCallbackSubmitting(true);
                        try {
                          await capturePricing({
                            name: callbackForm.name.trim() || null,
                            email: callbackForm.email.trim(),
                            phone: callbackForm.phone.trim() || null,
                            message: 'Consultation request from booking page',
                            marketing_consent: callbackForm.marketing_consent,
                          });
                          setCallbackSubmitted(true);
                          toast.success('Request sent. We\'ll be in touch shortly.');
                        } catch (err) {
                          toast.error(err.message || 'Failed to send request.');
                        } finally {
                          setCallbackSubmitting(false);
                        }
                      }}
                    >
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label htmlFor="callback-name" className="text-sm">Name</Label>
                          <Input
                            id="callback-name"
                            value={callbackForm.name}
                            onChange={(e) => setCallbackForm((p) => ({ ...p, name: e.target.value }))}
                            placeholder="Your name"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="callback-email" className="text-sm">Email *</Label>
                          <Input
                            id="callback-email"
                            type="email"
                            required
                            value={callbackForm.email}
                            onChange={(e) => setCallbackForm((p) => ({ ...p, email: e.target.value }))}
                            placeholder="you@example.com"
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="callback-phone" className="text-sm">Phone</Label>
                        <Input
                          id="callback-phone"
                          type="tel"
                          value={callbackForm.phone}
                          onChange={(e) => setCallbackForm((p) => ({ ...p, phone: e.target.value }))}
                          placeholder="Optional"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id="callback-marketing"
                          checked={callbackForm.marketing_consent}
                          onCheckedChange={(c) => setCallbackForm((p) => ({ ...p, marketing_consent: !!c }))}
                        />
                        <Label htmlFor="callback-marketing" className="text-sm text-gray-600">Send me updates and offers</Label>
                      </div>
                      <Button type="submit" disabled={callbackSubmitting} className="w-full bg-electric-teal hover:bg-electric-teal/90">
                        {callbackSubmitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : <>Request callback <Send className="w-4 h-4 ml-2 inline" /></>}
                      </Button>
                    </form>
                  )}
                </CardContent>
              </Card>
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
