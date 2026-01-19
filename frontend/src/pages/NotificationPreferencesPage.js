import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Bell,
  BellOff,
  Mail,
  Calendar,
  AlertTriangle,
  FileText,
  Megaphone,
  Clock,
  ArrowLeft,
  Save,
  Loader2,
  CheckCircle,
  Info,
  Smartphone,
  Phone
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import api from '../api/client';

// Feature flag for SMS (can be controlled from environment or API in production)
const SMS_FEATURE_ENABLED = true;

const NotificationPreferencesPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState({
    status_change_alerts: true,
    expiry_reminders: true,
    monthly_digest: true,
    document_updates: true,
    system_announcements: true,
    reminder_days_before: 30,
    quiet_hours_enabled: false,
    quiet_hours_start: '22:00',
    quiet_hours_end: '08:00',
    // SMS preferences
    sms_enabled: false,
    sms_phone_number: '',
    sms_phone_verified: false,
    sms_urgent_alerts_only: true
  });
  const [hasChanges, setHasChanges] = useState(false);
  const [originalPreferences, setOriginalPreferences] = useState(null);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      const response = await api.get('/profile/notifications');
      const data = response.data;
      setPreferences(data);
      setOriginalPreferences(data);
    } catch (error) {
      toast.error('Failed to load notification preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key) => {
    setPreferences(prev => {
      const updated = { ...prev, [key]: !prev[key] };
      setHasChanges(JSON.stringify(updated) !== JSON.stringify(originalPreferences));
      return updated;
    });
  };

  const handleReminderDaysChange = (days) => {
    setPreferences(prev => {
      const updated = { ...prev, reminder_days_before: days };
      setHasChanges(JSON.stringify(updated) !== JSON.stringify(originalPreferences));
      return updated;
    });
  };

  const handleQuietHoursChange = (field, value) => {
    setPreferences(prev => {
      const updated = { ...prev, [field]: value };
      setHasChanges(JSON.stringify(updated) !== JSON.stringify(originalPreferences));
      return updated;
    });
  };

  const savePreferences = async () => {
    setSaving(true);
    try {
      await api.put('/profile/notifications', preferences);
      setOriginalPreferences(preferences);
      setHasChanges(false);
      toast.success('Notification preferences saved successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const notificationTypes = [
    {
      key: 'status_change_alerts',
      icon: AlertTriangle,
      iconColor: 'text-amber-500',
      bgColor: 'bg-amber-50',
      title: 'Compliance Status Alerts',
      description: 'Get notified when your property compliance status changes (GREEN → AMBER → RED)',
      recommended: true
    },
    {
      key: 'expiry_reminders',
      icon: Calendar,
      iconColor: 'text-blue-500',
      bgColor: 'bg-blue-50',
      title: 'Expiry Reminders',
      description: 'Receive reminders before certificates and documents expire',
      recommended: true
    },
    {
      key: 'monthly_digest',
      icon: Mail,
      iconColor: 'text-purple-500',
      bgColor: 'bg-purple-50',
      title: 'Monthly Compliance Digest',
      description: 'A monthly summary of your compliance status and upcoming actions'
    },
    {
      key: 'document_updates',
      icon: FileText,
      iconColor: 'text-green-500',
      bgColor: 'bg-green-50',
      title: 'Document Updates',
      description: 'Notifications when documents are uploaded, verified, or require attention'
    },
    {
      key: 'system_announcements',
      icon: Megaphone,
      iconColor: 'text-gray-500',
      bgColor: 'bg-gray-50',
      title: 'System Announcements',
      description: 'Platform updates, new features, and important service notices'
    }
  ];

  const reminderOptions = [
    { value: 7, label: '1 week' },
    { value: 14, label: '2 weeks' },
    { value: 30, label: '1 month' },
    { value: 60, label: '2 months' },
    { value: 90, label: '3 months' }
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal mx-auto mb-3" />
          <p className="text-gray-600">Loading preferences...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="notification-preferences-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate(-1)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-midnight-blue">Notification Preferences</h1>
                <p className="text-sm text-gray-500">Manage how you receive updates</p>
              </div>
            </div>
            <Button
              onClick={savePreferences}
              disabled={!hasChanges || saving}
              className={`${hasChanges ? 'bg-electric-teal hover:bg-teal-600' : 'bg-gray-300'}`}
              data-testid="save-preferences-btn"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              Save Changes
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Email Notifications Section */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
          <div className="p-4 border-b border-gray-100 bg-gray-50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-electric-teal/10 rounded-lg">
                <Bell className="w-5 h-5 text-electric-teal" />
              </div>
              <div>
                <h2 className="font-semibold text-midnight-blue">Email Notifications</h2>
                <p className="text-sm text-gray-500">Choose which emails you'd like to receive</p>
              </div>
            </div>
          </div>
          
          <div className="divide-y divide-gray-100">
            {notificationTypes.map((notification) => {
              const Icon = notification.icon;
              return (
                <div 
                  key={notification.key}
                  className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                  data-testid={`notification-toggle-${notification.key}`}
                >
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${notification.bgColor}`}>
                      <Icon className={`w-5 h-5 ${notification.iconColor}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-midnight-blue">{notification.title}</h3>
                        {notification.recommended && (
                          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 mt-0.5">{notification.description}</p>
                    </div>
                  </div>
                  <Switch
                    checked={preferences[notification.key]}
                    onCheckedChange={() => handleToggle(notification.key)}
                  />
                </div>
              );
            })}
          </div>
        </section>

        {/* Reminder Timing Section */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
          <div className="p-4 border-b border-gray-100 bg-gray-50">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Clock className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="font-semibold text-midnight-blue">Reminder Timing</h2>
                <p className="text-sm text-gray-500">When should we start sending expiry reminders?</p>
              </div>
            </div>
          </div>
          
          <div className="p-4">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Send reminders before certificates expire:
            </label>
            <div className="grid grid-cols-5 gap-2">
              {reminderOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleReminderDaysChange(option.value)}
                  className={`py-2 px-3 rounded-lg border text-sm font-medium transition-all ${
                    preferences.reminder_days_before === option.value
                      ? 'bg-electric-teal text-white border-electric-teal'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-electric-teal'
                  }`}
                  data-testid={`reminder-days-${option.value}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              <Info className="w-3 h-3 inline mr-1" />
              You'll receive reminders starting {preferences.reminder_days_before} days before each certificate expires.
            </p>
          </div>
        </section>

        {/* Quiet Hours Section */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
          <div className="p-4 border-b border-gray-100 bg-gray-50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <BellOff className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <h2 className="font-semibold text-midnight-blue">Quiet Hours</h2>
                  <p className="text-sm text-gray-500">Pause non-urgent notifications during specific hours</p>
                </div>
              </div>
              <Switch
                checked={preferences.quiet_hours_enabled}
                onCheckedChange={() => handleToggle('quiet_hours_enabled')}
              />
            </div>
          </div>
          
          {preferences.quiet_hours_enabled && (
            <div className="p-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Start time</label>
                  <input
                    type="time"
                    value={preferences.quiet_hours_start}
                    onChange={(e) => handleQuietHoursChange('quiet_hours_start', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    data-testid="quiet-hours-start"
                  />
                </div>
                <div className="text-gray-400 mt-6">to</div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">End time</label>
                  <input
                    type="time"
                    value={preferences.quiet_hours_end}
                    onChange={(e) => handleQuietHoursChange('quiet_hours_end', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    data-testid="quiet-hours-end"
                  />
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                <Info className="w-3 h-3 inline mr-1" />
                Urgent compliance alerts will still be delivered immediately, regardless of quiet hours.
              </p>
            </div>
          )}
        </section>

        {/* SMS Notifications Section (Feature Flagged) */}
        {SMS_FEATURE_ENABLED && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
            <div className="p-4 border-b border-gray-100 bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <Smartphone className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-midnight-blue">SMS Notifications</h2>
                    <p className="text-sm text-gray-500">Receive urgent alerts via text message</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">Beta</span>
                  <Switch
                    checked={preferences.sms_enabled}
                    onCheckedChange={() => handleToggle('sms_enabled')}
                    data-testid="sms-enabled-toggle"
                  />
                </div>
              </div>
            </div>
            
            {preferences.sms_enabled && (
              <div className="p-4 space-y-4">
                {/* Phone Number */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Mobile Number</label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        type="tel"
                        placeholder="+44 7XXX XXXXXX"
                        value={preferences.sms_phone_number || ''}
                        onChange={(e) => {
                          setPreferences(prev => {
                            const updated = { ...prev, sms_phone_number: e.target.value };
                            setHasChanges(JSON.stringify(updated) !== JSON.stringify(originalPreferences));
                            return updated;
                          });
                        }}
                        className="pl-10"
                        data-testid="sms-phone-input"
                      />
                    </div>
                    {preferences.sms_phone_verified ? (
                      <span className="flex items-center gap-1 px-3 py-2 bg-green-100 text-green-700 rounded-lg text-sm">
                        <CheckCircle className="w-4 h-4" />
                        Verified
                      </span>
                    ) : (
                      <Button variant="outline" size="sm" className="text-electric-teal border-electric-teal">
                        Verify
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    We'll send a verification code to confirm your number
                  </p>
                </div>

                {/* Urgent Alerts Only Toggle */}
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-midnight-blue">Urgent Alerts Only</p>
                    <p className="text-sm text-gray-500">Only send SMS when status changes to RED</p>
                  </div>
                  <Switch
                    checked={preferences.sms_urgent_alerts_only}
                    onCheckedChange={() => handleToggle('sms_urgent_alerts_only')}
                    data-testid="sms-urgent-only-toggle"
                  />
                </div>

                <p className="text-xs text-gray-500">
                  <Info className="w-3 h-3 inline mr-1" />
                  SMS charges may apply. We recommend keeping "Urgent Alerts Only" enabled to avoid excessive messages.
                </p>
              </div>
            )}
          </section>
        )}

        {/* Save Confirmation */}
        {hasChanges && (
          <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 bg-midnight-blue text-white px-6 py-3 rounded-full shadow-lg flex items-center gap-3 animate-in slide-in-from-bottom-4">
            <span>You have unsaved changes</span>
            <Button
              size="sm"
              onClick={savePreferences}
              disabled={saving}
              className="bg-electric-teal hover:bg-teal-600"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </div>
        )}
      </main>
    </div>
  );
};

export default NotificationPreferencesPage;
