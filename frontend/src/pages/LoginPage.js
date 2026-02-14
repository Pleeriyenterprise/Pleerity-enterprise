import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth, getRedirectPathForRole } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Shield } from 'lucide-react';

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Detect if this is admin login based on route
  const isAdminLogin = location.pathname === '/admin/signin';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(email, password, isAdminLogin);
      if (result.success) {
        const path = getRedirectPathForRole(result.user?.role);
        navigate(path);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2">
            {isAdminLogin && <Shield className="h-6 w-6 text-electric-teal" />}
            <CardTitle className="text-2xl font-bold text-midnight-blue">
              {isAdminLogin ? 'Admin Sign In' : 'Sign In'}
            </CardTitle>
          </div>
          <CardDescription>
            {isAdminLogin 
              ? 'Access the administration panel' 
              : 'Enter your credentials to access your compliance portal'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
            {error && (
              <Alert variant="destructive" data-testid="login-error">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

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
                data-testid="email-input"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                data-testid="password-input"
              />
            </div>

            <Button 
              type="submit" 
              className="w-full btn-primary" 
              disabled={loading}
              data-testid="login-submit-btn"
            >
              {loading ? 'Signing in...' : (isAdminLogin ? 'Sign In as Admin' : 'Sign In')}
            </Button>

            {!isAdminLogin && (
              <div className="text-center text-sm text-gray-600 space-y-2">
                <p>
                  Need an account?{' '}
                  <button
                    type="button"
                    onClick={() => navigate('/intake/start')}
                    className="text-electric-teal hover:underline font-medium"
                  >
                    Get Started
                  </button>
                </p>
                <p>
                  <button
                    type="button"
                    onClick={() => navigate('/')}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    ← Back to Home
                  </button>
                </p>
              </div>
            )}

            {isAdminLogin && (
              <div className="text-center text-sm text-gray-600">
                <button
                  type="button"
                  onClick={() => navigate('/login')}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ← Client Login
                </button>
              </div>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginPage;
