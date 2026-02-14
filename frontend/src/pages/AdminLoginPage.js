import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, getRedirectPathForRole } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Shield } from 'lucide-react';

const AdminLoginPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(email, password, true); // staff portal -> /api/auth/admin/login
      if (result.success) {
        const path = getRedirectPathForRole(result.user?.role);
        navigate(path);
      } else {
        setError(result.error || 'Login failed');
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
            <Shield className="h-6 w-6 text-electric-teal" />
            <CardTitle className="text-2xl font-bold text-midnight-blue">Admin Sign In</CardTitle>
          </div>
          <CardDescription>
            Access the administration panel
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
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
              />
            </div>

            <Button 
              type="submit" 
              className="w-full bg-midnight-blue hover:bg-midnight-blue/90" 
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign In as Admin'}
            </Button>

            <div className="text-center text-sm text-gray-600">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-gray-500 hover:text-gray-700"
              >
                ← Back
              </button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminLoginPage;
