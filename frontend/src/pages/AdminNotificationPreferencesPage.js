/**
 * Admin Notification Preferences Page
 * Allows admins to configure their notification settings for order events.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, Mail, Phone, MessageSquare, Save,
  ArrowLeft, Check, Settings, AlertCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import client from '../api/client';

const NOTIFICATION_EVENTS = [
  {
    id: 'new_order',
    label: 'New Orders',
    description: 'When a new paid order enters the queue',
    icon: Bell,
    defaultEnabled: true,
  },
  {
    id: 'document_ready',
    label: 'Document Ready for Review',
    description: 'When a document draft is generated and awaits approval',
    icon: Settings,
    defaultEnabled: true,
  },
  {
    id: 'client_response',
    label: 'Client Information Received',
    description: 'When a client submits requested information',
    icon: MessageSquare,
    defaultEnabled: true,
  },
  {
    id: 'sla_warning',
    label: 'SLA Warning',
    description: 'When an order is approaching its SLA deadline',
    icon: AlertCircle,
    defaultEnabled: true,
  },
  {
    id: 'sla_breach',
    label: 'SLA Breach',
    description: 'When an order has exceeded its SLA deadline',
    icon: AlertCircle,
    defaultEnabled: true,
  },
  {
    id: 'order_delivered',
    label: 'Order Delivered',
    description: 'When an order is successfully delivered to the client',
    icon: Check,
    defaultEnabled: false,
  },
  {
    id: 'delivery_failed',
    label: 'Delivery Failed',
    description: 'When order delivery encounters an error',
    icon: AlertCircle,
    defaultEnabled: true,
  },
];

export default function AdminNotificationPreferencesPage() {
  const [preferences, setPreferences] = useState({
    email_enabled: true,
    sms_enabled: false,
    in_app_enabled: true,
    notification_email: '',
    notification_phone: '',
  });
  const [profile, setProfile] = useState({ name: '', email: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const fetchPreferences = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch both preferences and profile
      const [prefsResponse, profileResponse] = await Promise.all([
        client.get('/api/admin/notifications/preferences'),
        client.get('/api/admin/notifications/profile'),
      ]);
      
      if (prefsResponse.data) {
        setPreferences({
          email_enabled: prefsResponse.data.email_enabled ?? true,
          sms_enabled: prefsResponse.data.sms_enabled ?? false,
          in_app_enabled: prefsResponse.data.in_app_enabled ?? true,
          notification_email: prefsResponse.data.notification_email || '',
          notification_phone: prefsResponse.data.notification_phone || '',
        });
      }
      
      if (profileResponse.data) {
        setProfile({
          name: profileResponse.data.name || '',
          email: profileResponse.data.auth_email || profileResponse.data.email || '',
        });
      }
    } catch (error) {
      console.error('Failed to fetch preferences:', error);
      toast.error('Failed to load notification preferences');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  const handleSave = async () => {
    try {
      setSaving(true);
      
      await client.put('/api/admin/notifications/preferences', {
        email_enabled: preferences.email_enabled,
        sms_enabled: preferences.sms_enabled,
        in_app_enabled: preferences.in_app_enabled,
        notification_email: preferences.notification_email || null,
        notification_phone: preferences.notification_phone || null,
      });
      
      toast.success('Notification preferences saved');
    } catch (error) {
      console.error('Failed to save preferences:', error);
      toast.error('Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const toggleChannel = (channel) => {
    setPreferences(prev => ({
      ...prev,
      [channel]: !prev[channel],
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Bell className="h-8 w-8 animate-pulse mx-auto text-gray-400" />
          <p className="mt-2 text-gray-500">Loading preferences...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8" data-testid="admin-notification-prefs-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <Button 
            variant="ghost" 
            className="mb-4"
            onClick={() => navigate('/admin/dashboard')}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Button>
          
          <div className="flex items-center gap-3">
            <div className="p-2 bg-teal-100 rounded-lg">
              <Bell className="h-6 w-6 text-teal-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Notification Preferences</h1>
              <p className="text-gray-500">
                Configure how you receive notifications for order events
              </p>
            </div>
          </div>
        </div>

        {/* Profile Summary */}
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Your Account</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-teal-100 flex items-center justify-center">
                <span className="text-teal-700 font-semibold text-lg">
                  {profile.name?.[0]?.toUpperCase() || 'A'}
                </span>
              </div>
              <div>
                <p className="font-medium text-gray-900">{profile.name || 'Admin'}</p>
                <p className="text-sm text-gray-500">{profile.email}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Notification Channels */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Notification Channels</CardTitle>
            <CardDescription>
              Choose how you want to receive notifications
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Email */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 rounded-lg">
                  <Mail className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">Email Notifications</p>
                  <p className="text-sm text-gray-500">Receive notifications via email</p>
                </div>
              </div>
              <Switch
                checked={preferences.email_enabled}
                onCheckedChange={() => toggleChannel('email_enabled')}
                data-testid="toggle-email"
              />
            </div>
            
            {preferences.email_enabled && (
              <div className="ml-14">
                <Label htmlFor="notification_email" className="text-sm text-gray-600">
                  Email Address (leave blank to use account email)
                </Label>
                <Input
                  id="notification_email"
                  type="email"
                  placeholder={profile.email || 'your@email.com'}
                  value={preferences.notification_email}
                  onChange={(e) => setPreferences(prev => ({ ...prev, notification_email: e.target.value }))}
                  className="mt-1 max-w-sm"
                  data-testid="notification-email-input"
                />
              </div>
            )}

            <Separator />

            {/* SMS */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-50 rounded-lg">
                  <Phone className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">SMS Notifications</p>
                  <p className="text-sm text-gray-500">Receive urgent notifications via SMS</p>
                </div>
              </div>
              <Switch
                checked={preferences.sms_enabled}
                onCheckedChange={() => toggleChannel('sms_enabled')}
                data-testid="toggle-sms"
              />
            </div>
            
            {preferences.sms_enabled && (
              <div className="ml-14">
                <Label htmlFor="notification_phone" className="text-sm text-gray-600">
                  Phone Number (UK mobile)
                </Label>
                <Input
                  id="notification_phone"
                  type="tel"
                  placeholder="+44 7xxx xxxxxx"
                  value={preferences.notification_phone}
                  onChange={(e) => setPreferences(prev => ({ ...prev, notification_phone: e.target.value }))}
                  className="mt-1 max-w-sm"
                  data-testid="notification-phone-input"
                />
              </div>
            )}

            <Separator />

            {/* In-App */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 rounded-lg">
                  <Bell className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">In-App Notifications</p>
                  <p className="text-sm text-gray-500">Show notifications in the admin dashboard</p>
                </div>
              </div>
              <Switch
                checked={preferences.in_app_enabled}
                onCheckedChange={() => toggleChannel('in_app_enabled')}
                data-testid="toggle-in-app"
              />
            </div>
          </CardContent>
        </Card>

        {/* Notification Events */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Event Types</CardTitle>
            <CardDescription>
              These events will trigger notifications through your enabled channels
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {NOTIFICATION_EVENTS.map((event) => {
                const Icon = event.icon;
                return (
                  <div
                    key={event.id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                  >
                    <Icon className="h-5 w-5 text-gray-500 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{event.label}</p>
                      <p className="text-sm text-gray-500">{event.description}</p>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {event.defaultEnabled ? 'Active' : 'Optional'}
                    </Badge>
                  </div>
                );
              })}
            </div>
            <p className="text-sm text-gray-500 mt-4">
              Note: Event-level toggles will be available in a future update.
              Currently, all events are enabled for your selected channels.
            </p>
          </CardContent>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => navigate('/admin/dashboard')}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-teal-600 hover:bg-teal-700"
            data-testid="save-preferences-btn"
          >
            {saving ? (
              <>
                <span className="animate-spin mr-2">⟳</span>
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save Preferences
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
