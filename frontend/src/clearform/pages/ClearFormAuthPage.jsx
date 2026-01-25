/**
 * ClearForm Auth Page
 * 
 * Handles login and registration for ClearForm users.
 */

import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { FileText, ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { toast } from 'sonner';

const ClearFormAuthPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register } = useClearFormAuth();
  
  const isRegister = location.pathname.includes('register');
  const [loading, setLoading] = useState(false);
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    confirmPassword: '',
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      if (isRegister) {
        if (formData.password !== formData.confirmPassword) {
          toast.error('Passwords do not match');
          setLoading(false);
          return;
        }
        await register({
          email: formData.email,
          password: formData.password,
          full_name: formData.full_name,
        });
        toast.success('Account created! Welcome to ClearForm.');
      } else {
        await login(formData.email, formData.password);
        toast.success('Welcome back!');
      }
      navigate('/clearform/dashboard');
    } catch (error) {
      toast.error(error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white flex flex-col">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform" className="flex items-center gap-2">
            <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">ClearForm</span>
          </Link>
          <Link to="/clearform" className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" /> Back to Home
          </Link>
        </div>
      </header>

      {/* Auth Form */}
      <div className="flex-1 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle>{isRegister ? 'Create Account' : 'Welcome Back'}</CardTitle>
            <CardDescription>
              {isRegister 
                ? 'Start creating professional documents in seconds' 
                : 'Sign in to access your documents'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {isRegister && (
                <div className="space-y-2">
                  <Label htmlFor="full_name">Full Name</Label>
                  <Input
                    id="full_name"
                    name="full_name"
                    type="text"
                    required
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="John Smith"
                    data-testid="full-name-input"
                  />
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  data-testid="email-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  data-testid="password-input"
                />
              </div>
              
              {isRegister && (
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type="password"
                    required
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="••••••••"
                    data-testid="confirm-password-input"
                  />
                </div>
              )}
              
              <Button type="submit" className="w-full" disabled={loading} data-testid="auth-submit-btn">
                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                {isRegister ? 'Create Account' : 'Sign In'}
              </Button>
            </form>
            
            <div className="mt-6 text-center text-sm">
              {isRegister ? (
                <>
                  Already have an account?{' '}
                  <Link to="/clearform/login" className="text-emerald-600 hover:underline">
                    Sign in
                  </Link>
                </>
              ) : (
                <>
                  Don't have an account?{' '}
                  <Link to="/clearform/register" className="text-emerald-600 hover:underline">
                    Sign up free
                  </Link>
                </>
              )}
            </div>
            
            {isRegister && (
              <p className="mt-4 text-xs text-center text-slate-500">
                By creating an account, you agree to our Terms of Service and Privacy Policy.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ClearFormAuthPage;
