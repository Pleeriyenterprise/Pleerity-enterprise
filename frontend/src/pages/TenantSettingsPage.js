import React, { useEffect, useState } from 'react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { User } from 'lucide-react';

/**
 * Tenant Settings – read-only profile for tenant portal.
 * Minimal view: name and email only (no billing/notifications).
 */
const TenantSettingsPage = () => {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.get('/profile/me')
      .then((r) => { if (!cancelled) setProfile(r.data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center" data-testid="tenant-settings-loading">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
      </div>
    );
  }

  const displayName = profile?.full_name || user?.email || 'Tenant';
  const displayEmail = user?.email || profile?.email || '—';

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="tenant-settings-page">
      <h1 className="text-xl font-bold text-midnight-blue mb-6 flex items-center gap-2">
        <User className="w-6 h-6" />
        Profile
      </h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-midnight-blue">Your details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-500">Name</label>
            <p className="text-midnight-blue font-medium">{displayName}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-500">Email</label>
            <p className="text-midnight-blue">{displayEmail}</p>
          </div>
          <p className="text-sm text-gray-500 pt-2">
            To update your details, contact your landlord or property manager.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default TenantSettingsPage;
