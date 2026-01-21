import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Palette, Upload, Mail, Phone, Globe, Building2, 
  RefreshCcw, Save, Lock, AlertTriangle, CheckCircle,
  ArrowLeft, Eye
} from 'lucide-react';
import api from '../api/client';
import UpgradePrompt from '../components/UpgradePrompt';

const BrandingSettingsPage = () => {
  const navigate = useNavigate();
  const [branding, setBranding] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    fetchBranding();
  }, []);

  const fetchBranding = async () => {
    try {
      const response = await api.get('/client/branding');
      setBranding(response.data);
    } catch (err) {
      setError('Failed to load branding settings');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, value) => {
    setBranding(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
    setSuccess('');
  };

  const handleSave = async () => {
    if (!branding.feature_enabled) return;
    
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const response = await api.put('/client/branding', branding);
      setBranding(response.data);
      setHasChanges(false);
      setSuccess('Branding settings saved successfully');
    } catch (err) {
      if (err.response?.status === 403) {
        setError(err.response.data.detail?.message || 'Upgrade required to use this feature');
      } else {
        setError('Failed to save branding settings');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!branding.feature_enabled) return;
    
    if (!window.confirm('Are you sure you want to reset all branding settings to defaults?')) {
      return;
    }

    setSaving(true);
    setError('');

    try {
      await api.post('/client/branding/reset');
      await fetchBranding();
      setHasChanges(false);
      setSuccess('Branding settings reset to defaults');
    } catch (err) {
      setError('Failed to reset branding settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200 rounded w-1/3"></div>
            <div className="h-64 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  const isLocked = !branding?.feature_enabled;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="branding-settings-page">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate('/app/settings')}
                data-testid="back-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Settings
              </Button>
              <div>
                <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Palette className="w-5 h-5 text-electric-teal" />
                  Branding Settings
                </h1>
                <p className="text-sm text-gray-500">Customize your reports and emails</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={handleReset}
                disabled={isLocked || saving}
                data-testid="reset-btn"
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                Reset
              </Button>
              <Button
                onClick={handleSave}
                disabled={isLocked || saving || !hasChanges}
                data-testid="save-btn"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Upgrade Notice for Locked Feature */}
        {isLocked && (
          <UpgradePrompt
            featureName="White-Label Branding"
            featureDescription="Customize your compliance reports and emails with your company logo, colors, and contact information. Create a professional, branded experience for your clients."
            requiredPlan="PLAN_3_PRO"
            requiredPlanName="Professional"
            currentPlan={branding?.current_plan_name}
            variant="card"
            data-testid="upgrade-notice"
          />
        )}

        {error && (
          <Alert variant="destructive" data-testid="error-alert">
            <AlertTriangle className="w-4 h-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="border-green-200 bg-green-50" data-testid="success-alert">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <AlertDescription className="text-green-800">{success}</AlertDescription>
          </Alert>
        )}

        {/* Company Information */}
        <Card className={isLocked ? 'opacity-60' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              Company Information
            </CardTitle>
            <CardDescription>
              Basic company details shown in reports and compliance packs
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name</Label>
                <Input
                  id="company_name"
                  value={branding?.company_name || ''}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                  disabled={isLocked}
                  placeholder="Your Company Ltd"
                  data-testid="company-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="website_url">Website URL</Label>
                <Input
                  id="website_url"
                  type="url"
                  value={branding?.website_url || ''}
                  onChange={(e) => handleChange('website_url', e.target.value)}
                  disabled={isLocked}
                  placeholder="https://www.yourcompany.com"
                  data-testid="website-input"
                />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="contact_email">Contact Email</Label>
                <Input
                  id="contact_email"
                  type="email"
                  value={branding?.contact_email || ''}
                  onChange={(e) => handleChange('contact_email', e.target.value)}
                  disabled={isLocked}
                  placeholder="contact@yourcompany.com"
                  data-testid="contact-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact_phone">Contact Phone</Label>
                <Input
                  id="contact_phone"
                  type="tel"
                  value={branding?.contact_phone || ''}
                  onChange={(e) => handleChange('contact_phone', e.target.value)}
                  disabled={isLocked}
                  placeholder="+44 123 456 7890"
                  data-testid="contact-phone-input"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Color Scheme */}
        <Card className={isLocked ? 'opacity-60' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="w-5 h-5" />
              Color Scheme
            </CardTitle>
            <CardDescription>
              Customize colors used in reports and compliance packs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="primary_color">Primary Color</Label>
                <div className="flex gap-2">
                  <Input
                    id="primary_color"
                    type="color"
                    value={branding?.primary_color || '#0B1D3A'}
                    onChange={(e) => handleChange('primary_color', e.target.value)}
                    disabled={isLocked}
                    className="w-12 h-10 p-1 cursor-pointer"
                    data-testid="primary-color-picker"
                  />
                  <Input
                    value={branding?.primary_color || '#0B1D3A'}
                    onChange={(e) => handleChange('primary_color', e.target.value)}
                    disabled={isLocked}
                    className="flex-1 font-mono text-sm"
                    placeholder="#0B1D3A"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="secondary_color">Secondary Color</Label>
                <div className="flex gap-2">
                  <Input
                    id="secondary_color"
                    type="color"
                    value={branding?.secondary_color || '#00B8A9'}
                    onChange={(e) => handleChange('secondary_color', e.target.value)}
                    disabled={isLocked}
                    className="w-12 h-10 p-1 cursor-pointer"
                    data-testid="secondary-color-picker"
                  />
                  <Input
                    value={branding?.secondary_color || '#00B8A9'}
                    onChange={(e) => handleChange('secondary_color', e.target.value)}
                    disabled={isLocked}
                    className="flex-1 font-mono text-sm"
                    placeholder="#00B8A9"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="accent_color">Accent Color</Label>
                <div className="flex gap-2">
                  <Input
                    id="accent_color"
                    type="color"
                    value={branding?.accent_color || '#FFB800'}
                    onChange={(e) => handleChange('accent_color', e.target.value)}
                    disabled={isLocked}
                    className="w-12 h-10 p-1 cursor-pointer"
                    data-testid="accent-color-picker"
                  />
                  <Input
                    value={branding?.accent_color || '#FFB800'}
                    onChange={(e) => handleChange('accent_color', e.target.value)}
                    disabled={isLocked}
                    className="flex-1 font-mono text-sm"
                    placeholder="#FFB800"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="text_color">Text Color</Label>
                <div className="flex gap-2">
                  <Input
                    id="text_color"
                    type="color"
                    value={branding?.text_color || '#1F2937'}
                    onChange={(e) => handleChange('text_color', e.target.value)}
                    disabled={isLocked}
                    className="w-12 h-10 p-1 cursor-pointer"
                    data-testid="text-color-picker"
                  />
                  <Input
                    value={branding?.text_color || '#1F2937'}
                    onChange={(e) => handleChange('text_color', e.target.value)}
                    disabled={isLocked}
                    className="flex-1 font-mono text-sm"
                    placeholder="#1F2937"
                  />
                </div>
              </div>
            </div>

            {/* Color Preview */}
            <div className="mt-4 p-4 rounded-lg border" style={{ backgroundColor: branding?.primary_color || '#0B1D3A' }}>
              <div className="flex items-center justify-between">
                <span className="text-white font-medium">Color Preview</span>
                <div className="flex gap-2">
                  <span 
                    className="px-3 py-1 rounded text-sm font-medium"
                    style={{ backgroundColor: branding?.secondary_color || '#00B8A9', color: 'white' }}
                  >
                    Secondary
                  </span>
                  <span 
                    className="px-3 py-1 rounded text-sm font-medium"
                    style={{ backgroundColor: branding?.accent_color || '#FFB800', color: '#1F2937' }}
                  >
                    Accent
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Logo & Assets */}
        <Card className={isLocked ? 'opacity-60' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-5 h-5" />
              Logo & Assets
            </CardTitle>
            <CardDescription>
              Upload your logo to appear in reports and compliance packs
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="logo_url">Logo URL</Label>
                <Input
                  id="logo_url"
                  type="url"
                  value={branding?.logo_url || ''}
                  onChange={(e) => handleChange('logo_url', e.target.value)}
                  disabled={isLocked}
                  placeholder="https://yoursite.com/logo.png"
                  data-testid="logo-url-input"
                />
                <p className="text-xs text-gray-500">
                  Recommended: PNG or SVG, at least 200x200px
                </p>
              </div>
              <div className="space-y-2">
                <Label>Logo Preview</Label>
                <div className="h-24 border rounded-lg flex items-center justify-center bg-gray-50">
                  {branding?.logo_url ? (
                    <img 
                      src={branding.logo_url} 
                      alt="Logo preview" 
                      className="max-h-20 max-w-full object-contain"
                      onError={(e) => e.target.style.display = 'none'}
                    />
                  ) : (
                    <span className="text-gray-400 text-sm">No logo set</span>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Report Customization */}
        <Card className={isLocked ? 'opacity-60' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Eye className="w-5 h-5" />
              Report Customization
            </CardTitle>
            <CardDescription>
              Customize the appearance of generated compliance packs and reports
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="report_header_text">Report Header Text</Label>
              <Input
                id="report_header_text"
                value={branding?.report_header_text || ''}
                onChange={(e) => handleChange('report_header_text', e.target.value)}
                disabled={isLocked}
                placeholder="Custom header text for reports"
                data-testid="header-text-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="report_footer_text">Report Footer Text</Label>
              <Input
                id="report_footer_text"
                value={branding?.report_footer_text || ''}
                onChange={(e) => handleChange('report_footer_text', e.target.value)}
                disabled={isLocked}
                placeholder="Custom disclaimer or footer text"
                data-testid="footer-text-input"
              />
            </div>
            <div className="flex items-center justify-between pt-2">
              <div>
                <Label htmlFor="include_pleerity_branding">Show "Powered by Pleerity"</Label>
                <p className="text-sm text-gray-500">
                  Include Pleerity branding in reports
                </p>
              </div>
              <Switch
                id="include_pleerity_branding"
                checked={branding?.include_pleerity_branding !== false}
                onCheckedChange={(checked) => handleChange('include_pleerity_branding', checked)}
                disabled={isLocked}
                data-testid="pleerity-branding-toggle"
              />
            </div>
          </CardContent>
        </Card>

        {/* Email Customization */}
        <Card className={isLocked ? 'opacity-60' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5" />
              Email Customization
            </CardTitle>
            <CardDescription>
              Customize how compliance emails appear to recipients
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email_from_name">Email "From" Name</Label>
                <Input
                  id="email_from_name"
                  value={branding?.email_from_name || ''}
                  onChange={(e) => handleChange('email_from_name', e.target.value)}
                  disabled={isLocked}
                  placeholder="Your Company Compliance"
                  data-testid="email-from-input"
                />
                <p className="text-xs text-gray-500">
                  Emails still sent from @pleerity.com domain
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email_reply_to">Reply-To Address</Label>
                <Input
                  id="email_reply_to"
                  type="email"
                  value={branding?.email_reply_to || ''}
                  onChange={(e) => handleChange('email_reply_to', e.target.value)}
                  disabled={isLocked}
                  placeholder="compliance@yourcompany.com"
                  data-testid="email-reply-to-input"
                />
                <p className="text-xs text-gray-500">
                  Where replies to compliance emails will be sent
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BrandingSettingsPage;
