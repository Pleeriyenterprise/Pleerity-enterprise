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
import api, { openBlobApiResponse } from '../api/client';
import UpgradePrompt from '../components/UpgradePrompt';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { cn } from '../lib/utils';

/** Uploaded logos use this path; <img src> cannot send Bearer auth, so we fetch via axios + blob URL. */
function logoUrlRequiresAuthenticatedFetch(url) {
  if (!url || typeof url !== 'string') return false;
  const s = url.trim();
  if (!s) return false;
  try {
    const u = new URL(s, typeof window !== 'undefined' ? window.location.origin : 'https://localhost');
    return u.pathname.replace(/\/$/, '').endsWith('/client/branding/logo');
  } catch {
    return s.includes('/client/branding/logo');
  }
}

const BrandingSettingsPage = () => {
  const navigate = useNavigate();
  const [branding, setBranding] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [logoPreviewSrc, setLogoPreviewSrc] = useState(null);
  const [previewReportLoading, setPreviewReportLoading] = useState(false);
  const logoInputRef = React.useRef(null);

  useEffect(() => {
    fetchBranding();
  }, []);

  useEffect(() => {
    let objectUrlToRevoke = null;
    let cancelled = false;
    const logoUrl = branding?.logo_url;

    if (!logoUrl) {
      setLogoPreviewSrc(null);
      return undefined;
    }

    if (logoUrlRequiresAuthenticatedFetch(logoUrl)) {
      setLogoPreviewSrc(null);
      api
        .get('/client/branding/logo', { responseType: 'blob' })
        .then((res) => {
          const u = URL.createObjectURL(res.data);
          if (cancelled) {
            URL.revokeObjectURL(u);
            return;
          }
          objectUrlToRevoke = u;
          setLogoPreviewSrc(u);
        })
        .catch(() => {
          if (!cancelled) setLogoPreviewSrc(null);
        });
      return () => {
        cancelled = true;
        if (objectUrlToRevoke) URL.revokeObjectURL(objectUrlToRevoke);
      };
    }

    setLogoPreviewSrc(logoUrl);
    return undefined;
  }, [branding?.logo_url]);

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
        setError(
          err.response.data.detail?.message ||
            'White-label branding is included on Professional-tier plans. Billing lists current options for your workspace.',
        );
      } else if (err.response?.status === 400) {
        const d = err.response.data?.detail;
        setError(
          typeof d === 'object' && d?.message ? d.message : (typeof d === 'string' ? d : 'Invalid branding settings'),
        );
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

  const handleLogoUpload = async (e) => {
    const file = e?.target?.files?.[0];
    if (!file || !branding?.feature_enabled) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      setError('Please choose a JPEG, PNG, or WebP image (max 2MB).');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Logo must be 2MB or smaller.');
      return;
    }
    setUploadingLogo(true);
    setError('');
    setSuccess('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/client/branding/logo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const logoUrl = response.data?.logo_url;
      if (logoUrl) {
        setBranding(prev => ({ ...prev, logo_url: logoUrl }));
        setSuccess('Logo uploaded and saved. Save the form to persist any other changes.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload logo');
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handlePreviewReport = async () => {
    if (!branding?.feature_enabled) return;
    setPreviewReportLoading(true);
    setError('');
    try {
      const res = await api.get('/client/branding/preview', { responseType: 'blob' });
      openBlobApiResponse(res, { download: false, fallbackFilename: 'branding_preview.pdf' });
    } catch (err) {
      const d = err.response?.data;
      let msg = 'Failed to load report preview';
      if (d instanceof Blob) {
        try {
          const text = await d.text();
          const j = JSON.parse(text);
          msg = j.detail || msg;
        } catch {
          msg = err.response?.status === 401 ? 'Session expired. Please sign in again.' : msg;
        }
      } else if (typeof d?.detail === 'string') {
        msg = d.detail;
      } else if (d?.detail?.message) {
        msg = d.detail.message;
      }
      setError(msg);
    } finally {
      setPreviewReportLoading(false);
    }
  };

  if (loading) {
    return (
      <div className={cn(portalPageRoot, 'p-4 sm:p-8')}>
        <PortalLoadingPanel message="Loading branding…" />
      </div>
    );
  }

  const isLocked = !branding?.feature_enabled;

  return (
    <div className={cn(portalPageRoot, 'bg-gray-50')} data-testid="branding-settings-page">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 min-w-0">
              <Button 
                variant="ghost" 
                size="sm" 
                className="min-h-11 shrink-0 self-start"
                onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/settings'))}
                data-testid="back-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Settings
              </Button>
              <div className="min-w-0">
                <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  <Palette className="w-5 h-5 text-electric-teal" />
                  Branding Settings
                </h1>
                <p className="text-sm text-gray-500">Customize your reports and emails</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
              <Button
                variant="outline"
                className="min-h-11 w-full sm:w-auto"
                onClick={handleReset}
                disabled={isLocked || saving}
                data-testid="reset-btn"
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                Reset
              </Button>
              <Button
                className="min-h-11 w-full sm:w-auto"
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

      <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
        {/* Upgrade Notice for Locked Feature */}
        {isLocked && (
          <UpgradePrompt
            featureName="White-label reporting & emails"
            featureDescription="Apply your logo, colours, and contact details to client-facing PDFs and emails — suited to larger operations and delegated teams."
            requiredPlan="PLAN_3_PRO"
            requiredPlanName="Professional"
            currentPlan={branding?.current_plan_name}
            variant="card"
            dataTestId="upgrade-notice"
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

        {!isLocked && (
          <Card data-testid="white-label-card">
            <CardHeader>
              <CardTitle>White-label</CardTitle>
              <CardDescription>
                Turn on to use your logo, colours, and contact details on client-facing PDFs and emails.
                The server requires a logo upload, company name, and support email before activation.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="space-y-1">
                <Label htmlFor="white_label_enabled">Use my brand on client-facing materials</Label>
                <p className="text-xs text-muted-foreground">
                  If anything is incomplete, outputs fall back to Pleerity branding (no mixed branding).
                </p>
              </div>
              <Switch
                id="white_label_enabled"
                checked={!!branding?.white_label_enabled}
                onCheckedChange={(v) => handleChange('white_label_enabled', v)}
                data-testid="white-label-switch"
              />
            </CardContent>
            {branding?.resolved_branding && (
              <CardContent className="pt-0 text-xs text-muted-foreground border-t">
                <p>
                  Effective branding:{' '}
                  <strong>
                    {branding.resolved_branding.source === 'client_white_label'
                      ? 'Your brand'
                      : 'Pleerity default'}
                  </strong>
                </p>
                {Array.isArray(branding.resolved_branding.fallback_reasons) &&
                  branding.resolved_branding.fallback_reasons.length > 0 && (
                    <p className="mt-1 font-mono text-[11px]">
                      {branding.resolved_branding.fallback_reasons.join(', ')}
                    </p>
                  )}
              </CardContent>
            )}
          </Card>
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
                <div className="flex gap-2">
                  <Input
                    id="logo_url"
                    type="url"
                    value={branding?.logo_url || ''}
                    onChange={(e) => handleChange('logo_url', e.target.value)}
                    disabled={isLocked}
                    placeholder="https://yoursite.com/logo.png"
                    data-testid="logo-url-input"
                    className="flex-1"
                  />
                  <input
                    ref={logoInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleLogoUpload}
                    data-testid="logo-file-input"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isLocked || uploadingLogo}
                    onClick={() => logoInputRef.current?.click()}
                    data-testid="logo-upload-btn"
                  >
                    {uploadingLogo ? 'Uploading…' : 'Upload'}
                  </Button>
                </div>
                <p className="text-xs text-gray-500">
                  Enter a URL or upload a file (PNG/JPEG/WebP, max 2MB). Recommended: at least 200×200px.
                </p>
              </div>
              <div className="space-y-2">
                <Label>Logo Preview</Label>
                <div className="h-24 border rounded-lg flex items-center justify-center bg-gray-50">
                  {branding?.logo_url ? (
                    logoPreviewSrc ? (
                      <img
                        src={logoPreviewSrc}
                        alt="Logo preview"
                        className="max-h-20 max-w-full object-contain"
                        onError={() => setLogoPreviewSrc(null)}
                      />
                    ) : (
                      <span className="text-gray-400 text-xs text-center px-2">
                        {logoUrlRequiresAuthenticatedFetch(branding.logo_url)
                          ? 'Loading preview…'
                          : 'Could not load image'}
                      </span>
                    )
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
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-gray-600">
                Preview how your report will look with the current branding (company name, logo, colours, header/footer).
              </p>
              <Button
                type="button"
                variant="outline"
                disabled={isLocked || previewReportLoading}
                onClick={handlePreviewReport}
                data-testid="preview-report-btn"
              >
                <Eye className="w-4 h-4 mr-2" />
                {previewReportLoading ? 'Opening…' : 'Preview report'}
              </Button>
            </div>
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
