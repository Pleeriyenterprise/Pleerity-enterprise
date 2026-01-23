/**
 * Cookie Consent Banner
 * 
 * GDPR/UK-compliant cookie consent with:
 * - Accept All / Reject Non-Essential / Manage Preferences
 * - Server-side consent storage (authoritative)
 * - No scripts beyond Necessary load before consent
 * - Accessible via footer link (Preferences Panel)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Cookie, Shield, BarChart3, Target, Cog, X } from 'lucide-react';
import api from '../api/client';

// Generate or retrieve session ID
const getSessionId = () => {
  let sessionId = localStorage.getItem('pleerity_session_id');
  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('pleerity_session_id', sessionId);
  }
  return sessionId;
};

// Get stored consent state
const getStoredConsent = () => {
  const stored = localStorage.getItem('pleerity_consent');
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return null;
    }
  }
  return null;
};

// Get UTM parameters
const getUTMParams = () => {
  const params = new URLSearchParams(window.location.search);
  return {
    source: params.get('utm_source') || null,
    medium: params.get('utm_medium') || null,
    campaign: params.get('utm_campaign') || null,
    term: params.get('utm_term') || null,
    content: params.get('utm_content') || null,
  };
};

// Cookie categories configuration
const COOKIE_CATEGORIES = [
  {
    id: 'necessary',
    name: 'Necessary',
    description: 'Essential cookies required for the website to function. These cannot be disabled.',
    icon: Shield,
    required: true,
    examples: ['Session cookies', 'Security tokens', 'Load balancing'],
  },
  {
    id: 'functional',
    name: 'Functional',
    description: 'Cookies that enable enhanced functionality like live chat, preferences, and personalization.',
    icon: Cog,
    required: false,
    examples: ['Chat widget preferences', 'Language settings', 'Theme preferences'],
  },
  {
    id: 'analytics',
    name: 'Analytics',
    description: 'Cookies that help us understand how visitors interact with our website.',
    icon: BarChart3,
    required: false,
    examples: ['Page views', 'User journeys', 'Performance metrics'],
  },
  {
    id: 'marketing',
    name: 'Marketing',
    description: 'Cookies used to deliver relevant ads and marketing communications.',
    icon: Target,
    required: false,
    examples: ['Targeted advertising', 'Campaign tracking', 'Conversion tracking'],
  },
];

const CONSENT_VERSION = 'v1';
const BANNER_TEXT_HASH = 'pleerity_banner_v1_2026';

export default function CookieBanner() {
  const [showBanner, setShowBanner] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);
  const [preferences, setPreferences] = useState({
    necessary: true,
    functional: false,
    analytics: false,
    marketing: false,
  });
  const [saving, setSaving] = useState(false);
  const [hasConsented, setHasConsented] = useState(false);

  // Check consent state on mount
  useEffect(() => {
    const checkConsent = async () => {
      const sessionId = getSessionId();
      const storedConsent = getStoredConsent();
      
      if (storedConsent && storedConsent.hasConsented) {
        // User has already consented
        setHasConsented(true);
        setPreferences(storedConsent.preferences);
        return;
      }
      
      // Check server-side state
      try {
        const response = await api.get(`/consent/state/${sessionId}`);
        if (response.data.exists) {
          setHasConsented(true);
          setPreferences(response.data.preferences);
          localStorage.setItem('pleerity_consent', JSON.stringify({
            hasConsented: true,
            preferences: response.data.preferences,
          }));
          return;
        }
      } catch (error) {
        console.error('Failed to check consent state:', error);
      }
      
      // Show banner for first-time visitors
      setShowBanner(true);
      
      // Record banner shown event
      try {
        await api.post('/consent/capture', {
          session_id: sessionId,
          event_type: 'BANNER_SHOWN',
          consent_version: CONSENT_VERSION,
          banner_text_hash: BANNER_TEXT_HASH,
          preferences: { necessary: true, functional: false, analytics: false, marketing: false },
          page_path: window.location.pathname,
          referrer: document.referrer || null,
          utm: getUTMParams(),
          country: null, // Will be detected server-side
          user_agent: navigator.userAgent,
        });
      } catch (error) {
        console.error('Failed to record banner shown:', error);
      }
    };
    
    checkConsent();
  }, []);

  const saveConsent = useCallback(async (eventType, prefs) => {
    setSaving(true);
    const sessionId = getSessionId();
    
    try {
      await api.post('/consent/capture', {
        session_id: sessionId,
        event_type: eventType,
        consent_version: CONSENT_VERSION,
        banner_text_hash: BANNER_TEXT_HASH,
        preferences: prefs,
        page_path: window.location.pathname,
        referrer: document.referrer || null,
        utm: getUTMParams(),
        country: null,
        user_agent: navigator.userAgent,
      });
      
      // Store locally
      localStorage.setItem('pleerity_consent', JSON.stringify({
        hasConsented: true,
        preferences: prefs,
      }));
      
      setHasConsented(true);
      setPreferences(prefs);
      setShowBanner(false);
      setShowPreferences(false);
      
      // Reload page to apply consent (load/unload scripts)
      window.location.reload();
      
    } catch (error) {
      console.error('Failed to save consent:', error);
    } finally {
      setSaving(false);
    }
  }, []);

  const handleAcceptAll = () => {
    const allAccepted = {
      necessary: true,
      functional: true,
      analytics: true,
      marketing: true,
    };
    saveConsent('ACCEPT_ALL', allAccepted);
  };

  const handleRejectNonEssential = () => {
    const onlyNecessary = {
      necessary: true,
      functional: false,
      analytics: false,
      marketing: false,
    };
    saveConsent('REJECT_NON_ESSENTIAL', onlyNecessary);
  };

  const handleSavePreferences = () => {
    saveConsent('CUSTOM', preferences);
  };

  const handleUpdatePreferences = () => {
    // For users updating their preferences after initial consent
    saveConsent('CUSTOM', preferences);
  };

  // Don't render if user has already consented
  if (!showBanner && !showPreferences && hasConsented) {
    return null;
  }

  return (
    <>
      {/* Cookie Banner */}
      {showBanner && (
        <div 
          className="fixed bottom-0 left-0 right-0 z-[9999] bg-white border-t border-gray-200 shadow-2xl animate-slide-up"
          data-testid="cookie-banner"
        >
          <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              {/* Content */}
              <div className="flex items-start gap-3 flex-1">
                <div className="p-2 bg-teal-100 rounded-lg shrink-0">
                  <Cookie className="w-5 h-5 text-teal-600" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">
                    We value your privacy
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    We use cookies to enhance your browsing experience, serve personalized content, and analyze our traffic. 
                    By clicking &quot;Accept All&quot;, you consent to our use of cookies. 
                    Read our{' '}
                    <a href="/privacy-policy" className="text-teal-600 hover:underline">
                      Privacy Policy
                    </a>
                    {' '}and{' '}
                    <a href="/cookie-policy" className="text-teal-600 hover:underline">
                      Cookie Policy
                    </a>
                    .
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowPreferences(true)}
                  data-testid="cookie-manage-btn"
                >
                  Manage Preferences
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRejectNonEssential}
                  data-testid="cookie-reject-btn"
                >
                  Reject Non-Essential
                </Button>
                <Button
                  size="sm"
                  className="bg-teal-600 hover:bg-teal-700"
                  onClick={handleAcceptAll}
                  data-testid="cookie-accept-btn"
                >
                  Accept All
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preferences Modal */}
      <Dialog open={showPreferences} onOpenChange={setShowPreferences}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Cookie className="w-5 h-5 text-teal-600" />
              Cookie Preferences
            </DialogTitle>
            <DialogDescription>
              Manage your cookie preferences. You can enable or disable different types of cookies below.
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="overview" className="mt-4">
            <TabsList className="grid grid-cols-2 w-full">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="details">Cookie Details</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4 mt-4">
              {COOKIE_CATEGORIES.map((category) => {
                const Icon = category.icon;
                const isEnabled = preferences[category.id];
                
                return (
                  <div
                    key={category.id}
                    className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg"
                  >
                    <div className="p-2 bg-gray-100 rounded-lg shrink-0">
                      <Icon className="w-5 h-5 text-gray-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <Label className="font-semibold text-gray-900">
                          {category.name}
                          {category.required && (
                            <span className="ml-2 text-xs text-gray-500">(Required)</span>
                          )}
                        </Label>
                        <Switch
                          checked={isEnabled}
                          onCheckedChange={(checked) => {
                            if (!category.required) {
                              setPreferences(prev => ({
                                ...prev,
                                [category.id]: checked,
                              }));
                            }
                          }}
                          disabled={category.required}
                          data-testid={`cookie-toggle-${category.id}`}
                        />
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {category.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </TabsContent>

            <TabsContent value="details" className="mt-4">
              <div className="space-y-4">
                {COOKIE_CATEGORIES.map((category) => (
                  <div key={category.id} className="border-b border-gray-200 pb-4 last:border-0">
                    <h4 className="font-semibold text-gray-900">{category.name} Cookies</h4>
                    <p className="text-sm text-gray-600 mt-1">{category.description}</p>
                    <div className="mt-2">
                      <span className="text-xs font-medium text-gray-500">Examples:</span>
                      <ul className="text-xs text-gray-500 mt-1 list-disc list-inside">
                        {category.examples.map((example, i) => (
                          <li key={i}>{example}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="mt-6 flex-col sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={handleRejectNonEssential}
              disabled={saving}
            >
              Reject Non-Essential
            </Button>
            <Button
              variant="outline"
              onClick={handleAcceptAll}
              disabled={saving}
            >
              Accept All
            </Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700"
              onClick={hasConsented ? handleUpdatePreferences : handleSavePreferences}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Preferences'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CSS for animation */}
      <style>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
      `}</style>
    </>
  );
}

// Export utility to open preferences from footer link
export const openCookiePreferences = () => {
  window.dispatchEvent(new CustomEvent('open-cookie-preferences'));
};

// Hook to listen for preference open events
export const useCookiePreferences = (onOpen) => {
  useEffect(() => {
    const handler = () => onOpen?.();
    window.addEventListener('open-cookie-preferences', handler);
    return () => window.removeEventListener('open-cookie-preferences', handler);
  }, [onOpen]);
};
