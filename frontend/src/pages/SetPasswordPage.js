import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, CheckCircle2, Home } from 'lucide-react';

const SetPasswordPage = () => {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const portalHint = (searchParams.get('portal') || '').toLowerCase();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorIsFromServer, setErrorIsFromServer] = useState(false);
  const [success, setSuccess] = useState(false);
  const [contextLoading, setContextLoading] = useState(Boolean(token));
  const [isTenant, setIsTenant] = useState(portalHint === 'tenant');
  const [redirectPath, setRedirectPath] = useState(portalHint === 'tenant' ? '/tenant' : '/dashboard');

  useEffect(() => {
    if (!token) {
      setContextLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await authAPI.setPasswordContext(token);
        if (cancelled) return;
        setIsTenant(Boolean(data.is_tenant));
        setRedirectPath(data.redirect_path || (data.is_tenant ? '/tenant' : '/dashboard'));
      } catch {
        if (!cancelled && portalHint === 'tenant') {
          setIsTenant(true);
          setRedirectPath('/tenant');
        }
      } finally {
        if (!cancelled) setContextLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, portalHint]);

  const validatePassword = () => {
    if (password.length < 8) {
      return 'Password must be at least 8 characters';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter';
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter';
    }
    if (!/[0-9]/.test(password)) {
      return 'Password must contain at least one number';
    }
    if (password !== confirmPassword) {
      return 'Passwords do not match';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setErrorIsFromServer(false);

    const validationError = validatePassword();
    if (validationError) {
      setError(validationError);
      setErrorIsFromServer(false);
      return;
    }

    if (!token) {
      setError('Invalid password setup link');
      setErrorIsFromServer(false);
      return;
    }

    setLoading(true);

    try {
      const response = await authAPI.setPassword({ token, password });
      const { access_token, user } = response.data;

      loginWithToken(access_token, user);

      const dest =
        user?.role === 'ROLE_TENANT' ? '/tenant' : redirectPath;
      setSuccess(true);
      setTimeout(() => {
        navigate(user?.role === 'ROLE_TENANT' ? '/tenant?first_login=1' : `${dest}?first_login=1`, {
          replace: true,
        });
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to set password');
      setErrorIsFromServer(true);
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
              <AlertDescription>
                This link is not valid. Open your invite email and use the setup link there, or ask your landlord to resend the invite.
              </AlertDescription>
            </Alert>
            <Button 
              onClick={() => navigate('/')} 
              variant="outline"
              className="w-full mt-4"
            >
              Return Home
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (contextLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center text-gray-600">Loading…</CardContent>
        </Card>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-midnight-blue mb-2">Account activated</h3>
            <p className="text-gray-600">
              {isTenant ? 'Opening your tenant portal…' : 'Redirecting to your dashboard…'}
            </p>
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
            {isTenant && <Home className="h-6 w-6 text-electric-teal" />}
            <CardTitle className="text-2xl font-bold text-midnight-blue">Set Your Password</CardTitle>
          </div>
          <CardDescription>
            {isTenant
              ? 'Activate your tenant portal to access your tenancy, documents, rent information, and maintenance reporting.'
              : 'Create a secure password for your Compliance Vault Pro account'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <>
                <Alert variant="destructive" data-testid="password-error">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                {errorIsFromServer && (
                  <p className="text-sm text-gray-600 mt-2">
                    {isTenant ? (
                      <>
                        Need a new link? Ask your landlord to resend the invite from Tenant Management, or contact{' '}
                        <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">
                          info@pleerityenterprise.co.uk
                        </a>
                        .
                      </>
                    ) : (
                      <>
                        Need a new link? <Link to="/onboarding/status" className="text-electric-teal hover:underline">Go to onboarding status</Link> to resend the activation email, or contact support at{' '}
                        <a href="mailto:info@pleerityenterprise.co.uk" className="text-electric-teal hover:underline">info@pleerityenterprise.co.uk</a>.
                      </>
                    )}
                  </p>
                )}
              </>
            )}

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                data-testid="password-input"
              />
              <p className="text-xs text-gray-500">
                Must be at least 8 characters with uppercase, lowercase, and number
              </p>
            </div>

            <div className="space-y-2">
              <label htmlFor="confirm-password" className="text-sm font-medium text-gray-700">
                Confirm Password
              </label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your password"
                required
                data-testid="confirm-password-input"
              />
            </div>

            <Button 
              type="submit" 
              className="w-full btn-primary" 
              disabled={loading}
              data-testid="set-password-submit-btn"
            >
              {loading ? 'Setting password…' : isTenant ? 'Activate portal & continue' : 'Set Password & Continue'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default SetPasswordPage;
