import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { UkPostcodeLookupField } from '../components/address/UkPostcodeLookupField';
import { ArrowLeft, Plus, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../api/client';
import { portalPageRoot } from '../components/client/ClientPortalPatterns';
import { cn } from '../lib/utils';
import { JURISDICTION_OPTIONS, BUILDING_AGE_SCOTLAND_HELPER, showBuildingAgeField } from '../utils/jurisdictionComplianceCopy';
import { useUkPostcodeLookup } from '../hooks/useUkPostcodeLookup';
import { normalizeUkPostcode } from '../utils/ukPostcode';
import {
  getCapabilityDeniedMessage,
  isCapabilityDeniedApiError,
  usePropertyCapabilities,
} from '../utils/propertyCapabilityAccess';

const PropertyCreatePage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { canCreateProperty } = usePropertyCapabilities();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [isPlanLimit, setIsPlanLimit] = useState(false);
  const [defaultJurisdiction, setDefaultJurisdiction] = useState('');
  const submitInFlight = useRef(false);

  const [formData, setFormData] = useState({
    nickname: '',
    address_line_1: '',
    address_line_2: '',
    city: '',
    postcode: '',
    jurisdiction: '',
    property_type: 'residential',
    number_of_units: 1,
    building_age_years: '',
  });

  const postcodeLookup = useUkPostcodeLookup({
    postcode: formData.postcode,
    onPostcodeChange: (postcode) => setFormData((prev) => ({ ...prev, postcode })),
    onLookupComplete: (_data, applied) => {
      if (!applied || !Object.keys(applied).length) return;
      setFormData((prev) => ({
        ...prev,
        ...applied,
        jurisdiction: applied.jurisdiction || prev.jurisdiction,
      }));
    },
  });

  useEffect(() => {
    let cancelled = false;
    api
      .get('/client/settings/jurisdiction')
      .then((res) => {
        if (cancelled) return;
        const d = typeof res.data?.default_jurisdiction === 'string' ? res.data.default_jurisdiction.trim() : '';
        if (d && JURISDICTION_OPTIONS.includes(d)) {
          setDefaultJurisdiction(d);
          setFormData((prev) => (prev.jurisdiction ? prev : { ...prev, jurisdiction: d }));
        }
      })
      .catch(() => {
        if (!cancelled) setDefaultJurisdiction('');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canCreateProperty || submitInFlight.current || loading) return;
    submitInFlight.current = true;
    setError('');
    setIsPlanLimit(false);
    setSuccess(false);
    setLoading(true);

    try {
      const payload = { ...formData };
      if (!payload.nickname?.trim()) delete payload.nickname;
      else payload.nickname = payload.nickname.trim();
      if (!payload.jurisdiction?.trim()) delete payload.jurisdiction;
      else payload.jurisdiction = payload.jurisdiction.trim();
      const ageRaw = String(formData.building_age_years ?? '').trim();
      if (ageRaw === '') {
        delete payload.building_age_years;
      } else {
        const age = parseInt(ageRaw, 10);
        if (Number.isNaN(age) || age < 0 || age > 500) {
          setError('Building age must be a whole number between 0 and 500.');
          setLoading(false);
          submitInFlight.current = false;
          return;
        }
        payload.building_age_years = age;
      }
      payload.postcode = normalizeUkPostcode(payload.postcode);
      await api.post('/properties/create', payload);

      setSuccess(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err) {
      if (isCapabilityDeniedApiError(err)) {
        setError(getCapabilityDeniedMessage(err, 'Failed to create property'));
      } else {
      const detail = err.response?.data?.detail;
      const code = typeof detail === 'object' && detail?.error_code;
      if (err.response?.status === 403 && code === 'PLAN_LIMIT') {
        setIsPlanLimit(true);
        const msg = typeof detail?.message === 'string' ? detail.message : 'You have reached the maximum number of properties for your current plan.';
        setError(msg);
      } else {
        const msg = typeof detail === 'string' ? detail : (detail?.message ?? err.message ?? 'Failed to create property');
        setError(msg);
      }
      }
    } finally {
      setLoading(false);
      submitInFlight.current = false;
    }
  };

  if (success) {
    return (
      <div className={cn(portalPageRoot, 'bg-gray-50 flex items-center justify-center p-4')}>
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-midnight-blue mb-2">Property Added!</h3>
            <p className="text-gray-600">Redirecting to dashboard...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const lookupContext = { city: formData.city, jurisdiction: formData.jurisdiction };
  const effectiveJurisdictionForAge = (formData.jurisdiction || defaultJurisdiction || '').trim();

  return (
    <div className={cn(portalPageRoot, 'bg-gray-50')}>
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
                className="text-white hover:text-electric-teal"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="border-l border-gray-600 pl-4">
                <h1 className="text-xl font-bold flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Add New Property
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

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue">Property Details</CardTitle>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {error}
                  {isPlanLimit && (
                    <div className="mt-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="border-amber-600 text-amber-800 hover:bg-amber-50"
                        onClick={() => navigate('/settings/billing')}
                      >
                        View plan & upgrade
                      </Button>
                    </div>
                  )}
                </AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Property nickname (optional)</label>
                <Input
                  value={formData.nickname}
                  onChange={(e) => setFormData({ ...formData, nickname: e.target.value })}
                  placeholder="e.g. Main Street flat, Deansgate Tower"
                  data-testid="nickname-input"
                />
                <p className="text-xs text-gray-500">If provided, this name will be used to identify the property across the dashboard. Otherwise the address is used.</p>
              </div>

              <UkPostcodeLookupField
                postcodeRef={postcodeLookup.postcodeRef}
                postcodeInput={postcodeLookup.postcodeInput}
                onPostcodeChange={postcodeLookup.handlePostcodeChange}
                onPostcodeFocus={() =>
                  postcodeLookup.postcodeInput.length >= 2 && postcodeLookup.setShowPostcodeDropdown(true)
                }
                onPostcodeBlur={() => postcodeLookup.handlePostcodeBlur(lookupContext)}
                postcodeSuggestions={postcodeLookup.postcodeSuggestions}
                showPostcodeDropdown={postcodeLookup.showPostcodeDropdown}
                loadingPostcodes={postcodeLookup.loadingPostcodes}
                lookingUpPostcode={postcodeLookup.lookingUpPostcode}
                postcodeLookupDone={postcodeLookup.postcodeLookupDone}
                postcodeError={postcodeLookup.postcodeError}
                onSelectSuggestion={(s) => postcodeLookup.selectPostcode(s, lookupContext)}
                testId="postcode-input"
              />

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Address Line 1 *</label>
                <Input
                  value={formData.address_line_1}
                  onChange={(e) => setFormData({ ...formData, address_line_1: e.target.value })}
                  placeholder="123 High Street"
                  required
                  data-testid="address-1-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Address Line 2</label>
                <Input
                  value={formData.address_line_2}
                  onChange={(e) => setFormData({ ...formData, address_line_2: e.target.value })}
                  placeholder="Flat 4B"
                  data-testid="address-2-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">City *</label>
                <Input
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="London"
                  required
                  data-testid="city-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Jurisdiction (optional)</label>
                <select
                  value={formData.jurisdiction}
                  onChange={(e) => setFormData({ ...formData, jurisdiction: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                  data-testid="create-property-jurisdiction-select"
                >
                  <option value="">Use account default</option>
                  {JURISDICTION_OPTIONS.map((j) => (
                    <option key={j} value={j}>
                      {j}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500">
                  Default jurisdiction is used for new properties and any property that does not yet have its own jurisdiction set.
                  {defaultJurisdiction ? ` Current account default: ${defaultJurisdiction}.` : ''}
                  {postcodeLookup.postcodeLookupDone
                    ? ' Postcode lookup may suggest a jurisdiction when country is known; you can still change it here.'
                    : ''}
                </p>
              </div>

              {showBuildingAgeField(effectiveJurisdictionForAge) ? (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">Building age (years, optional)</label>
                  <Input
                    type="number"
                    min="0"
                    max="500"
                    value={formData.building_age_years}
                    onChange={(e) => setFormData({ ...formData, building_age_years: e.target.value })}
                    placeholder="e.g. 75"
                    data-testid="building-age-years-input"
                  />
                  <p className="text-xs text-gray-500">{BUILDING_AGE_SCOTLAND_HELPER}</p>
                </div>
              ) : null}

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Property Type *</label>
                <select
                  value={formData.property_type}
                  onChange={(e) => setFormData({ ...formData, property_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  data-testid="property-type-select"
                >
                  <option value="residential">Residential</option>
                  <option value="hmo">HMO (House in Multiple Occupation)</option>
                  <option value="commercial">Commercial</option>
                  <option value="mixed_use">Mixed Use</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Number of Units</label>
                <Input
                  type="number"
                  min="1"
                  value={formData.number_of_units}
                  onChange={(e) => setFormData({ ...formData, number_of_units: parseInt(e.target.value, 10) })}
                  data-testid="units-input"
                />
              </div>

              <div className="pt-4 border-t">
                <Alert className="mb-4 bg-blue-50 border-blue-200">
                  <AlertDescription className="text-sm text-blue-800">
                    Compliance requirements will be automatically generated based on the property type.
                  </AlertDescription>
                </Alert>

                <Button
                  type="submit"
                  className="btn-primary w-full"
                  disabled={loading}
                  data-testid="create-property-btn"
                >
                  {loading ? 'Creating Property...' : 'Add Property'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default PropertyCreatePage;
