import React, { useState, useEffect } from 'react';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Mail, Phone, MapPin, Clock, Send, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

function getUtmAndReferrer() {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);
  return {
    utm_source: params.get('utm_source') || '',
    utm_medium: params.get('utm_medium') || '',
    utm_campaign: params.get('utm_campaign') || '',
    utm_content: params.get('utm_content') || '',
    utm_term: params.get('utm_term') || '',
    referrer: document.referrer || '',
  };
}

const ContactPage = () => {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    phone: '',
    company: '',
    reason: '',
    subject: '',
    message: '',
    privacy_accepted: false,
    marketing_opt_in: false,
    website: '',
    ...getUtmAndReferrer(),
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  useEffect(() => {
    setFormData((prev) => ({ ...prev, ...getUtmAndReferrer() }));
  }, []);

  const contactReasons = [
    { value: 'general', label: 'General Inquiry' },
    { value: 'support', label: 'Technical Support' },
    { value: 'partnership', label: 'Partnership Opportunity' },
    { value: 'press', label: 'Press & Media' },
    { value: 'careers', label: 'Careers' },
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.privacy_accepted) {
      toast.error('Please accept the privacy policy to submit.');
      return;
    }
    setIsSubmitting(true);

    try {
      const API_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${API_URL}/api/public/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: formData.fullName,
          email: formData.email,
          phone: formData.phone || null,
          company_name: formData.company || null,
          contact_reason: formData.reason,
          subject: formData.subject,
          message: formData.message,
          privacy_accepted: formData.privacy_accepted,
          marketing_opt_in: formData.marketing_opt_in,
          website: formData.website || null,
          referrer: formData.referrer || null,
          utm_source: formData.utm_source || null,
          utm_medium: formData.utm_medium || null,
          utm_campaign: formData.utm_campaign || null,
          utm_content: formData.utm_content || null,
          utm_term: formData.utm_term || null,
        }),
      });

      if (response.ok) {
        setIsSubmitted(true);
        toast.success('Message sent successfully!');
      } else {
        const err = await response.json().catch(() => ({}));
        const msg = err.detail || 'Failed to send message';
        toast.error(typeof msg === 'string' ? msg : 'Failed to send message. Please try again.');
      }
    } catch (error) {
      toast.error('Failed to send message. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  if (isSubmitted) {
    return (
      <PublicLayout>
        <SEOHead
          title="Contact Us"
          description="Get in touch with Pleerity Enterprise. Questions about Compliance Vault Pro or our services? We're here to help."
          canonicalUrl="/contact"
        />
        <section className="py-32">
          <div className="max-w-xl mx-auto px-4 text-center">
            <div className="w-20 h-20 bg-electric-teal/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle2 className="w-10 h-10 text-electric-teal" />
            </div>
            <h1 className="text-3xl font-bold text-midnight-blue mb-4">
              Message Sent!
            </h1>
            <p className="text-gray-600 mb-8">
              Thank you for contacting us. We'll get back to you within 1-2 business days.
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setIsSubmitted(false);
                setFormData({
                  fullName: '',
                  email: '',
                  phone: '',
                  company: '',
                  reason: '',
                  subject: '',
                  message: '',
                  privacy_accepted: false,
                  marketing_opt_in: false,
                  website: '',
                  ...getUtmAndReferrer(),
                });
              }}
            >
              Send Another Message
            </Button>
          </div>
        </section>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <SEOHead
        title="Contact Us"
        description="Get in touch with Pleerity Enterprise. Questions about Compliance Vault Pro or our services? We're here to help."
        canonicalUrl="/contact"
      />

      <section className="py-20 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12">
            {/* Left Column - Contact Info */}
            <div>
              <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
                Get in Touch
              </h1>
              <p className="text-xl text-gray-600 mb-8">
                Have questions about Compliance Vault Pro or our services? 
                We're here to help. Send us a message and we'll respond as soon as possible.
              </p>

              <div className="space-y-6 mb-8">
                <div className="flex items-start">
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0 mr-4">
                    <Mail className="w-6 h-6 text-electric-teal" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-midnight-blue mb-1">Email</h3>
                    <a
                      href="mailto:info@pleerityenterprise.co.uk"
                      className="text-gray-600 hover:text-electric-teal"
                    >
                      info@pleerityenterprise.co.uk
                    </a>
                  </div>
                </div>

                <div className="flex items-start">
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0 mr-4">
                    <Clock className="w-6 h-6 text-electric-teal" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-midnight-blue mb-1">Business Hours</h3>
                    <p className="text-gray-600">Monday - Friday, 9am - 5pm GMT</p>
                  </div>
                </div>

                <div className="flex items-start">
                  <div className="w-12 h-12 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0 mr-4">
                    <MapPin className="w-6 h-6 text-electric-teal" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-midnight-blue mb-1">Location</h3>
                    <p className="text-gray-600">United Kingdom</p>
                    <p className="text-sm text-gray-500">Registered in England and Wales</p>
                  </div>
                </div>
              </div>

              <Card className="border-electric-teal/20 bg-electric-teal/5">
                <CardContent className="p-6">
                  <h3 className="font-semibold text-midnight-blue mb-2">
                    Need immediate help?
                  </h3>
                  <p className="text-gray-600 text-sm mb-4">
                    For urgent support issues, existing customers can access help through 
                    the platform's support chat.
                  </p>
                  <Button variant="outline" size="sm" asChild>
                    <a href="/login">Go to Dashboard</a>
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Right Column - Contact Form */}
            <div>
              <Card className="border-0 shadow-xl">
                <CardContent className="p-8">
                  <h2 className="text-2xl font-bold text-midnight-blue mb-6">
                    Send us a message
                  </h2>
                  <form onSubmit={handleSubmit} className="space-y-6 relative">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="fullName">Full Name *</Label>
                        <Input
                          id="fullName"
                          value={formData.fullName}
                          onChange={(e) => handleChange('fullName', e.target.value)}
                          required
                          data-testid="contact-fullname"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="email">Email *</Label>
                        <Input
                          id="email"
                          type="email"
                          value={formData.email}
                          onChange={(e) => handleChange('email', e.target.value)}
                          required
                          data-testid="contact-email"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="phone">Phone (optional)</Label>
                        <Input
                          id="phone"
                          type="tel"
                          value={formData.phone}
                          onChange={(e) => handleChange('phone', e.target.value)}
                          data-testid="contact-phone"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="company">Company (optional)</Label>
                        <Input
                          id="company"
                          value={formData.company}
                          onChange={(e) => handleChange('company', e.target.value)}
                          data-testid="contact-company"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="reason">Reason for Contact *</Label>
                      <Select
                        value={formData.reason}
                        onValueChange={(value) => handleChange('reason', value)}
                        required
                      >
                        <SelectTrigger data-testid="contact-reason">
                          <SelectValue placeholder="Select a reason" />
                        </SelectTrigger>
                        <SelectContent>
                          {contactReasons.map((reason) => (
                            <SelectItem key={reason.value} value={reason.value}>
                              {reason.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="subject">Subject *</Label>
                      <Input
                        id="subject"
                        value={formData.subject}
                        onChange={(e) => handleChange('subject', e.target.value)}
                        required
                        data-testid="contact-subject"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="message">Message *</Label>
                      <Textarea
                        id="message"
                        rows={5}
                        value={formData.message}
                        onChange={(e) => handleChange('message', e.target.value)}
                        required
                        data-testid="contact-message"
                      />
                    </div>

                    {/* Honeypot - hidden from users */}
                    <div className="absolute -left-[9999px] w-1 h-1 overflow-hidden" aria-hidden="true">
                      <Label htmlFor="website">Website</Label>
                      <Input
                        id="website"
                        type="text"
                        tabIndex={-1}
                        autoComplete="off"
                        value={formData.website}
                        onChange={(e) => handleChange('website', e.target.value)}
                      />
                    </div>

                    <div className="flex items-start space-x-2">
                      <Checkbox
                        id="privacy_accepted"
                        checked={formData.privacy_accepted}
                        onCheckedChange={(c) => handleChange('privacy_accepted', !!c)}
                      />
                      <label htmlFor="privacy_accepted" className="text-sm leading-tight">
                        I have read and accept the <a href="/privacy" className="text-electric-teal underline">privacy policy</a>. *
                      </label>
                    </div>
                    <div className="flex items-start space-x-2">
                      <Checkbox
                        id="marketing_opt_in"
                        checked={formData.marketing_opt_in}
                        onCheckedChange={(c) => handleChange('marketing_opt_in', !!c)}
                      />
                      <label htmlFor="marketing_opt_in" className="text-sm text-gray-600">
                        I would like to receive occasional updates and offers from Pleerity (optional).
                      </label>
                    </div>

                    <Button
                      type="submit"
                      className="w-full bg-electric-teal hover:bg-electric-teal/90"
                      disabled={isSubmitting}
                      data-testid="contact-submit"
                    >
                      {isSubmitting ? (
                        'Sending...'
                      ) : (
                        <>
                          Send Message
                          <Send className="w-4 h-4 ml-2" />
                        </>
                      )}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ContactPage;
