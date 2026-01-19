import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Shield, FileCheck, Bell, BarChart3 } from 'lucide-react';

const LandingPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">Compliance Vault Pro</h1>
            <p className="text-sm text-gray-600">AI-Driven Solutions & Compliance</p>
          </div>
          <div className="flex gap-4">
            <Button variant="ghost" onClick={() => navigate('/login')} data-testid="sign-in-btn">
              Sign In
            </Button>
            <Button 
              className="btn-primary"
              onClick={() => navigate('/intake/start')}
              data-testid="get-started-btn"
            >
              Get Started
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center max-w-3xl mx-auto">
          <h2 className="text-5xl font-bold text-midnight-blue mb-6">
            UK Landlord Compliance Made Simple
          </h2>
          <p className="text-xl text-gray-700 mb-8">
            Manage all your property compliance requirements in one secure platform.
            Stay audit-ready with automated reminders and document tracking.
          </p>
          <Button 
            size="lg" 
            className="btn-secondary text-lg px-8 py-6"
            onClick={() => navigate('/intake/start')}
            data-testid="hero-get-started-btn"
          >
            Get Started Today
          </Button>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h3 className="text-3xl font-bold text-center text-midnight-blue mb-12">
          Everything You Need for Compliance
        </h3>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <Shield className="w-12 h-12 text-electric-teal mb-4" />
              <h4 className="text-xl font-semibold text-midnight-blue mb-2">Compliance Tracking</h4>
              <p className="text-gray-600">
                Monitor all requirements across your property portfolio with real-time status updates.
              </p>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <FileCheck className="w-12 h-12 text-electric-teal mb-4" />
              <h4 className="text-xl font-semibold text-midnight-blue mb-2">Document Vault</h4>
              <p className="text-gray-600">
                Securely store all compliance certificates and documents in one central location.
              </p>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <Bell className="w-12 h-12 text-electric-teal mb-4" />
              <h4 className="text-xl font-semibold text-midnight-blue mb-2">Smart Reminders</h4>
              <p className="text-gray-600">
                Never miss a deadline with automated email and SMS reminders before expiry.
              </p>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <BarChart3 className="w-12 h-12 text-electric-teal mb-4" />
              <h4 className="text-xl font-semibold text-midnight-blue mb-2">Compliance Reports</h4>
              <p className="text-gray-600">
                Generate audit-ready compliance packs and monthly digest reports instantly.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Pricing */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h3 className="text-3xl font-bold text-center text-midnight-blue mb-12">
            Simple, Transparent Pricing
          </h3>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <Card className="enterprise-card">
              <CardContent className="pt-6">
                <h4 className="text-2xl font-bold text-midnight-blue mb-2">1 Property</h4>
                <p className="text-4xl font-bold text-electric-teal mb-4">£29.99<span className="text-lg text-gray-600">/month</span></p>
                <ul className="space-y-2 text-gray-600">
                  <li>✓ Full compliance tracking</li>
                  <li>✓ Document vault</li>
                  <li>✓ Email reminders</li>
                  <li>✓ Monthly reports</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="enterprise-card border-2 border-electric-teal">
              <CardContent className="pt-6">
                <div className="text-sm font-semibold text-electric-teal mb-2">MOST POPULAR</div>
                <h4 className="text-2xl font-bold text-midnight-blue mb-2">2-5 Properties</h4>
                <p className="text-4xl font-bold text-electric-teal mb-4">£49.99<span className="text-lg text-gray-600">/month</span></p>
                <ul className="space-y-2 text-gray-600">
                  <li>✓ Everything in 1 Property</li>
                  <li>✓ Up to 5 properties</li>
                  <li>✓ SMS reminders</li>
                  <li>✓ Priority support</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="enterprise-card">
              <CardContent className="pt-6">
                <h4 className="text-2xl font-bold text-midnight-blue mb-2">6-15 Properties</h4>
                <p className="text-4xl font-bold text-electric-teal mb-4">£79.99<span className="text-lg text-gray-600">/month</span></p>
                <ul className="space-y-2 text-gray-600">
                  <li>✓ Everything in 2-5 Properties</li>
                  <li>✓ Up to 15 properties</li>
                  <li>✓ Compliance packs</li>
                  <li>✓ Dedicated support</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-midnight-blue text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-8">
            <div>
              <h5 className="text-xl font-bold mb-4">Compliance Vault Pro</h5>
              <p className="text-gray-300">AI-Driven Solutions & Compliance</p>
              <p className="text-gray-300 mt-2">Pleerity Enterprise Ltd</p>
            </div>
            <div>
              <h5 className="text-lg font-semibold mb-4">Quick Links</h5>
              <ul className="space-y-2 text-gray-300">
                <li><button onClick={() => navigate('/login')} className="hover:text-electric-teal transition-smooth">Client Sign In</button></li>
                <li><button onClick={() => navigate('/admin/signin')} className="hover:text-electric-teal transition-smooth">Admin Sign In</button></li>
                <li><button onClick={() => navigate('/intake/start')} className="hover:text-electric-teal transition-smooth">Get Started</button></li>
              </ul>
            </div>
            <div>
              <h5 className="text-lg font-semibold mb-4">Support</h5>
              <p className="text-gray-300">Email: support@pleerity.com</p>
              <p className="text-gray-300 mt-2">Monday-Friday, 9am-5pm GMT</p>
            </div>
          </div>
          <div className="border-t border-gray-700 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 Pleerity Enterprise Ltd. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
