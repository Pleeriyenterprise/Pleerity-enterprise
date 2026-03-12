import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { CheckCircle2 } from 'lucide-react';
import { BRAND_LOGO_URL, branding } from '../config/branding';

/**
 * Self-service forgot password for client portal.
 * Submits email; backend sends password-setup link if account exists (no user enumeration).
 */
const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = (email || '').trim().toLowerCase();
    if (!trimmed) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await authAPI.forgotPassword({ email: trimmed });
      setMessage(res.data?.message || 'If an account exists for this email, you will receive a link to set your password. Please check your inbox and spam folder.');
      setSubmitted(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string' && detail.includes('Too many')) {
        setMessage(detail);
      } else {
        setMessage('If an account exists for this email, you will receive a link to set your password. Please check your inbox and spam folder.');
      }
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1">
            <div className="flex justify-center mb-2">
              <img src={BRAND_LOGO_URL} alt={branding.companyName} className="h-10 w-auto" />
            </div>
            <CardTitle className="text-xl font-bold text-midnight-blue text-center">Check your email</CardTitle>
            <CardDescription className="text-center">
              {message}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-center text-green-600">
              <CheckCircle2 className="h-12 w-12" />
            </div>
            <div className="flex flex-col gap-2">
              <Button
                type="button"
                className="w-full bg-electric-teal hover:bg-electric-teal/90"
                onClick={() => navigate('/login/client')}
              >
                Back to sign in
              </Button>
              <p className="text-center text-sm text-gray-600">
                Didn&apos;t receive an email? You can{' '}
                <button type="button" onClick={() => { setSubmitted(false); setMessage(''); }} className="text-electric-teal hover:underline font-medium">
                  try again
                </button>
                {' '}or contact your account administrator for a new setup link.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex justify-center mb-2">
            <img src={BRAND_LOGO_URL} alt={branding.companyName} className="h-10 w-auto" />
          </div>
          <CardTitle className="text-2xl font-bold text-midnight-blue">Forgot password?</CardTitle>
          <CardDescription>
            Enter the email address for your client account. We&apos;ll send you a link to set a new password.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-gray-700">
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-electric-teal hover:bg-electric-teal/90"
              disabled={loading || !(email || '').trim()}
            >
              {loading ? 'Sending...' : 'Send reset link'}
            </Button>
            <p className="text-center text-sm text-gray-600">
              <Link to="/login/client" className="text-electric-teal hover:underline font-medium">
                Back to sign in
              </Link>
            </p>
            <p className="text-xs text-gray-500 text-center">
              You can also contact your account administrator to request a new password setup link.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ForgotPasswordPage;
