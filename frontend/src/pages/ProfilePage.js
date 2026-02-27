import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { ArrowLeft, Save, User, Bell, CheckCircle2, Camera } from 'lucide-react';

const ProfilePage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    full_name: '',
    phone: ''
  });

  useEffect(() => {
    fetchProfile();
  }, []);

  useEffect(() => {
    return () => {
      if (avatarUrl) URL.revokeObjectURL(avatarUrl);
    };
  }, [avatarUrl]);

  const fetchProfile = async () => {
    try {
      const response = await api.get('/profile/me');
      setProfile(response.data);
      setFormData({
        full_name: response.data.full_name,
        phone: response.data.phone || ''
      });
      if (response.data.has_avatar) {
        const avRes = await api.get('/profile/me/avatar', { responseType: 'blob' });
        setAvatarUrl(URL.createObjectURL(avRes.data));
      } else {
        setAvatarUrl(null);
      }
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to load profile';
      setError(typeof message === 'string' ? message : 'Failed to load profile');
      setAvatarUrl(null);
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
      await api.patch('/profile/me', formData);
      setSuccess('Profile updated successfully');
      setTimeout(() => setSuccess(''), 3000);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('profile-updated'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setUploadingAvatar(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post('/profile/me/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchProfile();
      setSuccess('Profile picture updated');
      setTimeout(() => setSuccess(''), 3000);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('profile-updated'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload picture');
    } finally {
      setUploadingAvatar(false);
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
            <div className="flex flex-col sm:flex-row gap-6 mb-6">
              <div className="flex flex-col items-center gap-2">
                <div className="w-24 h-24 rounded-full bg-midnight-blue/10 flex items-center justify-center overflow-hidden border-2 border-gray-200">
                  {avatarUrl ? (
                    <img src={avatarUrl} alt="Profile" className="w-full h-full object-cover" />
                  ) : (
                    <User className="w-12 h-12 text-midnight-blue/50" />
                  )}
                </div>
                <label className="cursor-pointer inline-flex">
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleAvatarChange}
                    disabled={uploadingAvatar}
                  />
                  <span className="inline-flex items-center justify-center rounded-md text-sm font-medium border border-input bg-background px-4 py-2 hover:bg-accent hover:text-accent-foreground disabled:opacity-50">
                    {uploadingAvatar ? 'Uploading...' : <><Camera className="w-4 h-4 mr-1" />Upload photo</>}
                  </span>
                </label>
                <p className="text-xs text-gray-500">JPEG, PNG or WebP, max 5MB</p>
              </div>
              <div className="flex-1">
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
              </div>
            </div>
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
            <p className="text-gray-600">
              Manage your email notification settings, reminder timing, and quiet hours.
            </p>
            
            <Button
              onClick={() => navigate('/app/notifications')}
              variant="outline"
              className="w-full border-electric-teal text-electric-teal hover:bg-teal-50"
              data-testid="manage-notifications-btn"
            >
              <Bell className="w-4 h-4 mr-2" />
              Manage Notification Preferences
            </Button>
            
            <p className="text-xs text-gray-500">
              <strong>Note:</strong> You cannot opt out of critical notifications such as
              password setup, security alerts, and account-related emails.
            </p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default ProfilePage;
