import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI } from '../../api/client';
import { setContractorAuth } from './ContractorLoginPage';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { AlertCircle, Wrench } from 'lucide-react';

function safeReturnJobPath(raw) {
  const v = (raw || '').trim();
  if (!v.startsWith('/job?token=')) return null;
  if (v.includes('//') || v.includes('..')) return null;
  return v;
}

export default function ContractorSetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const returnTo = safeReturnJobPath(searchParams.get('return_to'));
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (!token) {
      setError('Invalid link');
      return;
    }
    setLoading(true);
    try {
      const { data } = await authAPI.contractorSetPassword({ token, password });
      setContractorAuth(data.access_token, data.user);
      if (typeof window !== 'undefined' && (process.env.NODE_ENV !== 'production' || window.__CVP_CONTRACTOR_DEBUG || window.__CVP_DEBUG)) {
        console.info('[CVP][ContractorPortal] password_set_ok redirect=/contractor');
      }
      setSuccess(true);
      if (returnTo) {
        navigate(returnTo, { replace: true });
      } else {
        navigate('/contractor', { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to set password');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>Link not valid—open your invite email and use the password link there.</AlertDescription>
            </Alert>
            <Button variant="outline" className="w-full mt-4" onClick={() => navigate('/login')}>
              Portal login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2">
            <Wrench className="h-6 w-6 text-electric-teal" />
            <CardTitle className="text-xl font-bold text-midnight-blue">Set your password</CardTitle>
          </div>
          <CardDescription>Create a password to access the contractor portal</CardDescription>
        </CardHeader>
        <CardContent>
          {success ? (
            <p className="text-green-600">
              {returnTo ? 'Password set. Opening your job…' : 'Password set. Opening your portal…'}
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Password</label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Confirm password</label>
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
              </div>
              <Button type="submit" className="w-full bg-electric-teal hover:bg-electric-teal/90" disabled={loading}>
                {loading ? 'Setting…' : 'Set password'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
