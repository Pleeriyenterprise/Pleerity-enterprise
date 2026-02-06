import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Shield, User } from 'lucide-react';

/**
 * Portal Selector Page - "Welcome Back" selector matching the design
 * Allows users to choose between Client Portal and Staff/Admin Portal
 */
const PortalSelectorPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-midnight-blue mb-4">
            <img src="/pleerity-logo.jpg" alt="Pleerity" className="h-12 w-auto" />
          </div>
          <h1 className="text-3xl font-bold text-midnight-blue mb-2">Welcome Back</h1>
          <p className="text-gray-600">Sign in to access your account</p>
        </div>

        {/* Portal Selection Cards */}
        <div className="space-y-4">
          {/* Client Portal */}
          <Card 
            className="cursor-pointer hover:shadow-lg transition-shadow border-2 hover:border-electric-teal"
            onClick={() => navigate('/login/client')}
          >
            <div className="p-6 flex items-center gap-4 bg-gradient-to-r from-electric-teal to-electric-teal/90 text-white rounded-lg">
              <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <User className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-semibold mb-1">Client Portal</h2>
                <p className="text-white/90 text-sm">Access your dashboard</p>
              </div>
            </div>
          </Card>

          {/* Staff / Admin Portal */}
          <Card 
            className="cursor-pointer hover:shadow-lg transition-shadow border-2 hover:border-midnight-blue"
            onClick={() => navigate('/login/admin')}
          >
            <div className="p-6 flex items-center gap-4 bg-gradient-to-r from-midnight-blue to-gray-800 text-white rounded-lg">
              <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0">
                <Shield className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-semibold mb-1">Staff / Admin Portal</h2>
                <p className="text-white/80 text-sm">Internal staff only</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Divider */}
        <div className="relative my-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-gray-50 text-gray-500">or</span>
          </div>
        </div>

        {/* Back to Website */}
        <div className="text-center">
          <button
            onClick={() => navigate('/')}
            className="text-gray-600 hover:text-electric-teal text-sm font-medium"
          >
            ← Back to Website
          </button>
        </div>
      </div>
    </div>
  );
};

export default PortalSelectorPage;
