import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Mail, Check } from 'lucide-react';

const NewsletterPage = () => {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const API_URL = process.env.REACT_APP_BACKEND_URL;
    
    try {
      const response = await fetch(`${API_URL}/api/admin/newsletter/subscribe?email=${encodeURIComponent(email)}&source=newsletter_page`, {
        method: 'POST',
      });
      
      if (response.ok) {
        setSubscribed(true);
        setEmail('');
      } else {
        alert('Subscription failed. Please try again.');
      }
    } catch (error) {
      alert('Network error. Please try again.');
    }
  };

  return (
    <PublicLayout>
      <SEOHead
        title="Newsletter Signup | Pleerity"
        description="Subscribe to receive updates on property compliance, new features, and industry insights."
        canonicalUrl="/newsletter"
      />

      <section className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-electric-teal/10 text-electric-teal text-sm font-medium mb-6">
            <Mail className="w-4 h-4 mr-2" />
            Newsletter
          </div>
          
          <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
            Stay Informed
          </h1>
          
          <p className="text-lg text-gray-600 mb-12">
            Get the latest updates on property compliance regulations, platform features, 
            and exclusive insights delivered to your inbox.
          </p>

          {!subscribed ? (
            <form onSubmit={handleSubmit} className="max-w-md mx-auto">
              <div className="flex gap-3">
                <Input
                  type="email"
                  placeholder="your.email@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="flex-1"
                />
                <Button 
                  type="submit" 
                  className="bg-electric-teal hover:bg-electric-teal/90 text-white px-6"
                >
                  Subscribe
                </Button>
              </div>
              <p className="text-xs text-gray-500 mt-4">
                We respect your privacy. Unsubscribe anytime.
              </p>
            </form>
          ) : (
            <div className="bg-green-50 border border-green-200 rounded-lg p-6 max-w-md mx-auto">
              <div className="flex items-center justify-center gap-2 text-green-700 mb-2">
                <Check className="w-5 h-5" />
                <span className="font-semibold">Subscribed Successfully!</span>
              </div>
              <p className="text-sm text-gray-600">
                Thank you for subscribing. You'll receive our next newsletter soon.
              </p>
            </div>
          )}
        </div>
      </section>
    </PublicLayout>
  );
};

export default NewsletterPage;
