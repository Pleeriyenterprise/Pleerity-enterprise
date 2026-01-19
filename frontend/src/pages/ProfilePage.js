import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { ArrowLeft, Save, User, Bell, CheckCircle2 } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ProfilePage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    full_name: '',
    phone: ''
  });

  const [preferences, setPreferences] = useState({
    compliance_reminders: true,
    monthly_digest: true,
    product_announcements: true
  });

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.get(
        `${API_URL}/api/profile/me`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setProfile(response.data);
      setFormData({
        full_name: response.data.full_name,
        phone: response.data.phone || ''
      });
      setPreferences(response.data.preferences || {
        compliance_reminders: true,
        monthly_digest: true,
        product_announcements: true
      });
    } catch (err) {
      setError('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      const token = localStorage.getItem('auth_token');
      await axios.patch(
        `${API_URL}/api/profile/me`,
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setSuccess('Profile updated successfully');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      const token = localStorage.getItem('auth_token');
      await axios.patch(
        `${API_URL}/api/profile/preferences`,
        preferences,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setSuccess('Preferences updated successfully');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update preferences');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/app/dashboard')}
                className="text-white hover:text-electric-teal"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="border-l border-gray-600 pl-4">
                <h1 className="text-xl font-bold flex items-center gap-2">
                  <User className="w-5 h-5" />
                  Profile Settings
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
              >
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {success && (
          <Alert className="mb-6 bg-green-50 border-green-200">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">{success}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Profile Information */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <User className="w-5 h-5" />
              Profile Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Full Name</label>
                <Input
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  placeholder="Your full name"
                  data-testid="full-name-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Email</label>
                <Input
                  value={profile?.email}
                  disabled
                  className="bg-gray-100"
                />
                <p className="text-xs text-gray-500">Email cannot be changed for security reasons</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Phone</label>
                <Input
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+44 7700 900000"
                  data-testid="phone-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Account Type</label>
                <Input
                  value={profile?.client_type}
                  disabled
                  className="bg-gray-100"
                />
              </div>

              <Button
                type="submit"
                className="btn-primary"
                disabled={saving}
                data-testid="save-profile-btn"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Saving...' : 'Save Profile'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Notification Preferences */}
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <Bell className="w-5 h-5" />
              Notification Preferences
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-4">
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.compliance_reminders}
                  onChange={(e) => setPreferences({
                    ...preferences,
                    compliance_reminders: e.target.checked
                  })}
                  className="mt-1"
                  data-testid="compliance-reminders-checkbox"
                />
                <div>
                  <p className="font-medium text-gray-900">Compliance Reminders</p>
                  <p className="text-sm text-gray-600">
                    Receive reminders about upcoming deadlines and overdue requirements
                  </p>
                </div>
              </label>

              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.monthly_digest}
                  onChange={(e) => setPreferences({
                    ...preferences,
                    monthly_digest: e.target.checked
                  })}
                  className="mt-1"
                  data-testid="monthly-digest-checkbox"
                />
                <div>
                  <p className="font-medium text-gray-900">Monthly Digest</p>
                  <p className="text-sm text-gray-600">
                    Monthly summary of your compliance status and activities
                  </p>
                </div>
              </label>

              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.product_announcements}
                  onChange={(e) => setPreferences({
                    ...preferences,
                    product_announcements: e.target.checked
                  })}
                  className="mt-1"
                  data-testid="product-announcements-checkbox"
                />
                <div>
                  <p className="font-medium text-gray-900">Product Announcements</p>
                  <p className="text-sm text-gray-600">
                    Updates about new features and improvements
                  </p>
                </div>
              </label>
            </div>

            <div className="pt-4 border-t">
              <p className="text-xs text-gray-500 mb-4">
                <strong>Note:</strong> You cannot opt out of critical notifications such as
                password setup, security alerts, and account-related emails.
              </p>

              <Button
                onClick={handleSavePreferences}
                className="btn-primary"
                disabled={saving}
                data-testid="save-preferences-btn"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Saving...' : 'Save Preferences'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default ProfilePage;
