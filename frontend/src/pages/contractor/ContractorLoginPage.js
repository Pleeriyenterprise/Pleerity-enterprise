import React, { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { authAPI } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { AlertCircle, Wrench } from 'lucide-react';

const CONTRACTOR_TOKEN_KEY = 'contractor_token';
const CONTRACTOR_USER_KEY = 'contractor_user';

export function setContractorAuth(accessToken, user) {
  if (typeof window !== 'undefined') {
    if (accessToken) window.localStorage.setItem(CONTRACTOR_TOKEN_KEY, accessToken);
    else window.localStorage.removeItem(CONTRACTOR_TOKEN_KEY);
    if (user) window.localStorage.setItem(CONTRACTOR_USER_KEY, JSON.stringify(user));
    else window.localStorage.removeItem(CONTRACTOR_USER_KEY);
  }
}

export function getContractorToken() {
  return typeof window !== 'undefined' ? window.localStorage.getItem(CONTRACTOR_TOKEN_KEY) : null;
}

export default function ContractorLoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get('session_expired') === '1';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data } = await authAPI.contractorLogin({ email, password });
      setContractorAuth(data.access_token, data.user);
      navigate('/contractor', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2">
            <Wrench className="h-6 w-6 text-electric-teal" />
            <CardTitle className="text-2xl font-bold text-midnight-blue">Contractor Portal</CardTitle>
          </div>
          <CardDescription>Sign in to view your work orders and submit invoices</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {sessionExpired && (
              <Alert className="border-amber-200 bg-amber-50">
                <AlertCircle className="h-4 w-4 text-amber-600" />
                <AlertDescription>
                  <span className="font-medium text-amber-900">Session expired.</span>
                  <span className="block mt-1 text-amber-800">Please sign in again.</span>
                </AlertDescription>
              </Alert>
            )}
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-gray-700">Email</label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">Password</label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full bg-electric-teal hover:bg-electric-teal/90" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
          <p className="text-center text-sm text-gray-500 mt-4">
            <Link to="/contractors/register" className="text-electric-teal hover:underline font-medium">
              New to the network? Apply to join
            </Link>
          </p>
          <p className="text-center text-sm text-gray-500 mt-2">
            <button type="button" className="text-electric-teal hover:underline" onClick={() => navigate('/login')}>
              Client or staff?
            </button>
            <span className="text-gray-400"> · </span>
            <span className="text-gray-500">Use the secure link in your assignment email for a single job (no password).</span>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
