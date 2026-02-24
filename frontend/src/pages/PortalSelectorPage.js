import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Shield, User, AlertCircle, Lock, Key, FileCheck } from 'lucide-react';
import { SUPPORT_EMAIL } from '../config';

/**
 * Portal Selector — Compliance Vault Pro Secure Access.
 * Client first, Admin secondary; trust and support copy.
 */
const PortalSelectorPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get('session_expired') === '1';

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {sessionExpired && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="session-expired-alert">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Session expired.</span>
              <span className="block mt-1 text-amber-800">Please sign in again.</span>
            </AlertDescription>
          </Alert>
        )}

        {/* Hero */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-midnight-blue mb-4">
            <img src="/pleerity-logo.jpg" alt="Pleerity" className="h-12 w-auto" />
          </div>
          <h1 className="text-3xl font-bold text-midnight-blue mb-2">
            Compliance Vault Pro Secure Access
          </h1>
          <p className="text-gray-600">
            Sign in to access your compliance dashboard.
          </p>
        </div>

        {/* Primary: Client Portal */}
        <Card
          className="cursor-pointer hover:shadow-lg transition-shadow border-2 border-electric-teal/50 mb-4 overflow-hidden"
          onClick={() => navigate('/login/client')}
        >
          <div className="p-6 bg-gradient-to-r from-electric-teal to-electric-teal/90 text-white">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <User className="w-7 h-7" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-semibold mb-1">Client Portal</h2>
                <p className="text-white/90 text-sm">For landlords and portfolio users.</p>
              </div>
            </div>
          </div>
        </Card>

        {/* Secondary: Staff / Admin */}
        <Card
          className="cursor-pointer hover:shadow transition-shadow border border-gray-200 mb-6 overflow-hidden"
          onClick={() => navigate('/login/admin')}
        >
          <div className="p-4 flex items-center gap-3 bg-gray-50 text-gray-700 hover:bg-gray-100 transition-colors">
            <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
              <Shield className="w-5 h-5 text-gray-600" />
            </div>
            <div className="flex-1">
              <h2 className="text-base font-semibold text-midnight-blue">Staff / Admin</h2>
              <p className="text-gray-500 text-sm">Internal team access only.</p>
            </div>
          </div>
        </Card>

        {/* Trust microcopy */}
        <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-gray-500 mb-8">
          <span className="flex items-center gap-1.5">
            <Lock className="w-4 h-4 text-electric-teal" />
            Secure encrypted access
          </span>
          <span className="flex items-center gap-1.5">
            <Key className="w-4 h-4 text-electric-teal" />
            Role-based authentication
          </span>
          <span className="flex items-center gap-1.5">
            <FileCheck className="w-4 h-4 text-electric-teal" />
            Audit logging enabled
          </span>
        </div>

        {/* Support */}
        <p className="text-center text-sm text-gray-600 mb-6">
          Need help accessing your account?{' '}
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="text-electric-teal font-medium hover:underline"
          >
            Contact support
          </a>
        </p>

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
