import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { intakeAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Switch } from '../components/ui/switch';
import { 
  AlertCircle, 
  User, 
  Building2, 
  Users, 
  Check, 
  ChevronRight,
  ChevronLeft,
  Home,
  Plus,
  Trash2,
  Upload,
  Mail,
  FileText,
  Shield,
  CreditCard,
  Loader2,
  Search,
  X,
  Info,
  AlertTriangle,
  CheckCircle,
  Lock,
  ArrowUpRight
} from 'lucide-react';
import { toast } from 'sonner';
import { v4 as uuidv4 } from 'uuid';
import { PropertyLimitPrompt } from '../components/UpgradePrompt';

// Plan limits - NEW PLAN STRUCTURE (must match backend plan_registry.py)
const PLAN_LIMITS = {
  // New plan codes
  PLAN_1_SOLO: 2,
  PLAN_2_PORTFOLIO: 10,
  PLAN_3_PRO: 25,
  // Legacy codes (for backward compatibility)
  PLAN_1: 2,
  PLAN_2_5: 10,
  PLAN_6_15: 25
};

// Plan names for display
const PLAN_NAMES = {
  PLAN_1_SOLO: 'Solo Landlord',
  PLAN_2_PORTFOLIO: 'Portfolio',
  PLAN_3_PRO: 'Professional',
  // Legacy
  PLAN_1: 'Solo Landlord',
  PLAN_2_5: 'Portfolio',
  PLAN_6_15: 'Professional'
};

// Property types
const PROPERTY_TYPES = [
  { value: 'flat', label: 'Flat/Apartment' },
  { value: 'house', label: 'House' },
  { value: 'bungalow', label: 'Bungalow' },
  { value: 'terraced', label: 'Terraced House' },
  { value: 'semi-detached', label: 'Semi-Detached' },
  { value: 'detached', label: 'Detached' },
  { value: 'commercial', label: 'Commercial' }
];

// Occupancy types
const OCCUPANCY_TYPES = [
  { value: 'single_family', label: 'Single Family' },
  { value: 'multi_family', label: 'Multi Family' },
  { value: 'student', label: 'Student Let' },
  { value: 'professional', label: 'Professional Let' },
  { value: 'mixed', label: 'Mixed Use' }
];

// Licence types
const LICENCE_TYPES = [
  { value: 'selective', label: 'Selective Licensing' },
  { value: 'additional', label: 'Additional Licensing' },
  { value: 'mandatory_hmo', label: 'Mandatory HMO Licence' }
];

// Licence statuses
const LICENCE_STATUSES = [
  { value: 'applied', label: 'Applied' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'expired', label: 'Expired' },
  { value: 'unknown', label: 'Unknown' }
];

// Certificate availability options
const CERT_OPTIONS = [
  { value: 'YES', label: 'Yes, I have it' },
  { value: 'NO', label: "No, I don't have it" },
  { value: 'UNSURE', label: 'Unsure' }
];

const IntakePage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [plans, setPlans] = useState([]);
  const [intakeSessionId] = useState(() => uuidv4());

  // Form data state
  const [formData, setFormData] = useState({
    // Step 1: Your Details
    full_name: '',
    email: '',
    client_type: '',
    company_name: '',
    preferred_contact: 'EMAIL',
    phone: '',
    
    // Step 2: Plan - NEW DEFAULT
    billing_plan: 'PLAN_1_SOLO',
    
    // Step 3: Properties
    properties: [{
      nickname: '',
      postcode: '',
      address_line_1: '',
      address_line_2: '',
      city: '',
      property_type: 'house',
      is_hmo: false,
      bedrooms: '',
      occupancy: 'single_family',
      council_name: '',
      council_code: '',
      licence_required: '',
      licence_type: '',
      licence_status: '',
      managed_by: 'LANDLORD',
      send_reminders_to: 'LANDLORD',
      agent_name: '',
      agent_email: '',
      agent_phone: '',
      cert_gas_safety: '',
      cert_eicr: '',
      cert_epc: '',
      cert_licence: ''
    }],
    
    // Step 4: Preferences & Consents
    document_submission_method: '',
    email_upload_consent: false,
    consent_data_processing: false,
    consent_service_boundary: false
  });

  // Property limit state for upgrade prompts
  const [propertyLimitError, setPropertyLimitError] = useState(null);

  // Load plans on mount
  useEffect(() => {
    const loadPlans = async () => {
      try {
        const response = await intakeAPI.getPlans();
        setPlans(response.data.plans);
      } catch (err) {
        console.error('Failed to load plans:', err);
      }
    };
    loadPlans();
  }, []);

  // Step validation
  const validateStep = (stepNum) => {
    setError('');
    
    switch (stepNum) {
      case 1:
        if (!formData.full_name.trim()) {
          setError('Full name is required');
          return false;
        }
        if (!formData.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
          setError('Valid email is required');
          return false;
        }
        if (!formData.client_type) {
          setError('Please select your client type');
          return false;
        }
        if ((formData.client_type === 'COMPANY' || formData.client_type === 'AGENT') && !formData.company_name.trim()) {
          setError('Company name is required');
          return false;
        }
        if ((formData.preferred_contact === 'SMS' || formData.preferred_contact === 'BOTH') && !formData.phone.trim()) {
          setError('Phone number is required when SMS is enabled');
          return false;
        }
        return true;
        
      case 2:
        if (!formData.billing_plan) {
          setError('Please select a plan');
          return false;
        }
        return true;
        
      case 3:
        const maxProps = PLAN_LIMITS[formData.billing_plan] || 1;
        if (formData.properties.length === 0) {
          setError('At least one property is required');
          return false;
        }
        if (formData.properties.length > maxProps) {
          setError(`Maximum ${maxProps} properties allowed for your plan`);
          return false;
        }
        for (let i = 0; i < formData.properties.length; i++) {
          const prop = formData.properties[i];
          if (!prop.postcode.trim()) {
            setError(`Property ${i + 1}: Postcode is required`);
            return false;
          }
          if (!prop.address_line_1.trim()) {
            setError(`Property ${i + 1}: Address line 1 is required`);
            return false;
          }
          if (!prop.city.trim()) {
            setError(`Property ${i + 1}: City is required`);
            return false;
          }
          if ((prop.send_reminders_to === 'AGENT' || prop.send_reminders_to === 'BOTH')) {
            if (!prop.agent_name.trim() || !prop.agent_email.trim()) {
              setError(`Property ${i + 1}: Agent name and email are required`);
              return false;
            }
          }
        }
        return true;
        
      case 4:
        if (!formData.document_submission_method) {
          setError('Please select a document submission method');
          return false;
        }
        if (formData.document_submission_method === 'EMAIL' && !formData.email_upload_consent) {
          setError('Please accept the email upload consent');
          return false;
        }
        if (!formData.consent_data_processing) {
          setError('GDPR consent is required');
          return false;
        }
        if (!formData.consent_service_boundary) {
          setError('Service boundary acknowledgment is required');
          return false;
        }
        return true;
        
      default:
        return true;
    }
  };

  const nextStep = () => {
    if (validateStep(step)) {
      setStep(step + 1);
      window.scrollTo(0, 0);
    }
  };

  const prevStep = () => {
    setStep(step - 1);
    window.scrollTo(0, 0);
  };

  const goToStep = (stepNum) => {
    // Only allow going back or staying on current step
    if (stepNum <= step) {
      setStep(stepNum);
      window.scrollTo(0, 0);
    }
  };

  // Property management with server-side validation
  const addProperty = async () => {
    const maxProps = PLAN_LIMITS[formData.billing_plan] || 2;
    const newCount = formData.properties.length + 1;
    
    // Clear previous error
    setPropertyLimitError(null);
    
    // First check local limit
    if (newCount > maxProps) {
      // Find upgrade plan
      let upgradePlan = null;
      let upgradePlanName = null;
      let upgradeLimit = null;
      
      if (formData.billing_plan === 'PLAN_1_SOLO' || formData.billing_plan === 'PLAN_1') {
        upgradePlan = 'PLAN_2_PORTFOLIO';
        upgradePlanName = 'Portfolio';
        upgradeLimit = 10;
      } else if (formData.billing_plan === 'PLAN_2_PORTFOLIO' || formData.billing_plan === 'PLAN_2_5') {
        upgradePlan = 'PLAN_3_PRO';
        upgradePlanName = 'Professional';
        upgradeLimit = 25;
      }
      
      setPropertyLimitError({
        currentLimit: maxProps,
        requestedCount: newCount,
        currentPlan: PLAN_NAMES[formData.billing_plan] || formData.billing_plan,
        upgradePlan,
        upgradePlanName,
        upgradeLimit
      });
      
      toast.error(`You've reached the maximum of ${maxProps} properties for the ${PLAN_NAMES[formData.billing_plan] || 'current'} plan.`);
      return;
    }
    
    // Optionally validate with backend (belt and suspenders)
    try {
      const response = await intakeAPI.validatePropertyCount(formData.billing_plan, newCount);
      if (!response.data.allowed) {
        setPropertyLimitError({
          currentLimit: response.data.current_limit,
          requestedCount: newCount,
          currentPlan: PLAN_NAMES[formData.billing_plan] || formData.billing_plan,
          upgradePlan: response.data.upgrade_to,
          upgradePlanName: response.data.upgrade_to_name,
          upgradeLimit: response.data.upgrade_to_limit
        });
        toast.error(response.data.error || 'Property limit exceeded');
        return;
      }
    } catch (err) {
      // If validation fails, still allow (UI already checked)
      console.warn('Backend validation failed, using frontend check:', err);
    }
    
    setFormData({
      ...formData,
      properties: [...formData.properties, {
        nickname: '',
        postcode: '',
        address_line_1: '',
        address_line_2: '',
        city: '',
        property_type: 'house',
        is_hmo: false,
        bedrooms: '',
        occupancy: 'single_family',
        council_name: '',
        council_code: '',
        licence_required: '',
        licence_type: '',
        licence_status: '',
        managed_by: 'LANDLORD',
        send_reminders_to: 'LANDLORD',
        agent_name: '',
        agent_email: '',
        agent_phone: '',
        cert_gas_safety: '',
        cert_eicr: '',
        cert_epc: '',
        cert_licence: ''
      }]
    });
  };

  const removeProperty = (index) => {
    if (formData.properties.length > 1) {
      setFormData({
        ...formData,
        properties: formData.properties.filter((_, i) => i !== index)
      });
      // Clear property limit error when removing
      setPropertyLimitError(null);
    }
  };

  const updateProperty = (index, field, value) => {
    const updated = [...formData.properties];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, properties: updated });
  };

  // Submit intake
  const handleSubmit = async () => {
    if (!validateStep(4)) return;
    
    setLoading(true);
    setError('');

    try {
      const submitData = {
        ...formData,
        intake_session_id: intakeSessionId
      };
      
      const response = await intakeAPI.submit(submitData);
      const { client_id, customer_reference } = response.data;
      
      // Store for post-checkout
      localStorage.setItem('pending_client_id', client_id);
      localStorage.setItem('customer_reference', customer_reference);
      
      toast.success(`Registration successful! Reference: ${customer_reference}`);
      
      // Create checkout session and redirect
      const checkoutResponse = await intakeAPI.createCheckout(client_id);
      window.location.href = checkoutResponse.data.checkout_url;
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit intake form');
      setLoading(false);
    }
  };

  // Progress indicator
  const steps = [
    { num: 1, name: 'Your Details', icon: User },
    { num: 2, name: 'Select Plan', icon: CreditCard },
    { num: 3, name: 'Properties', icon: Home },
    { num: 4, name: 'Preferences', icon: FileText },
    { num: 5, name: 'Review', icon: Shield }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" data-testid="intake-wizard">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-electric-teal to-teal-600 rounded-lg flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-midnight-blue">Compliance Vault Pro</h1>
                <p className="text-xs text-gray-500">Premium UK Landlord Compliance</p>
              </div>
            </div>
            <button 
              onClick={() => navigate('/')}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      </header>

      {/* Progress Steps */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {steps.map((s, idx) => (
              <React.Fragment key={s.num}>
                <button
                  onClick={() => goToStep(s.num)}
                  disabled={s.num > step}
                  className={`flex flex-col items-center gap-1 transition-all ${
                    s.num <= step ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
                  }`}
                  data-testid={`step-indicator-${s.num}`}
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                    s.num < step 
                      ? 'bg-green-500 text-white' 
                      : s.num === step 
                        ? 'bg-electric-teal text-white ring-4 ring-electric-teal/20' 
                        : 'bg-gray-200 text-gray-500'
                  }`}>
                    {s.num < step ? <Check className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
                  </div>
                  <span className={`text-xs font-medium ${
                    s.num === step ? 'text-electric-teal' : s.num < step ? 'text-green-600' : 'text-gray-500'
                  }`}>
                    {s.name}
                  </span>
                </button>
                {idx < steps.length - 1 && (
                  <div className={`flex-1 h-1 mx-2 rounded ${
                    s.num < step ? 'bg-green-500' : 'bg-gray-200'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step 1: Your Details */}
        {step === 1 && (
          <Step1YourDetails 
            formData={formData} 
            setFormData={setFormData}
            onNext={nextStep}
          />
        )}

        {/* Step 2: Select Plan */}
        {step === 2 && (
          <Step2SelectPlan
            formData={formData}
            setFormData={setFormData}
            plans={plans}
            onNext={nextStep}
            onBack={prevStep}
          />
        )}

        {/* Step 3: Properties */}
        {step === 3 && (
          <Step3Properties
            formData={formData}
            setFormData={setFormData}
            updateProperty={updateProperty}
            addProperty={addProperty}
            removeProperty={removeProperty}
            propertyLimitError={propertyLimitError}
            setPropertyLimitError={setPropertyLimitError}
            onNext={nextStep}
            onBack={prevStep}
          />
        )}

        {/* Step 4: Preferences & Consents */}
        {step === 4 && (
          <Step4Preferences
            formData={formData}
            setFormData={setFormData}
            onNext={nextStep}
            onBack={prevStep}
          />
        )}

        {/* Step 5: Review & Payment */}
        {step === 5 && (
          <Step5Review
            formData={formData}
            plans={plans}
            goToStep={goToStep}
            onSubmit={handleSubmit}
            onBack={prevStep}
            loading={loading}
          />
        )}
      </main>
    </div>
  );
};

// ============================================================================
// STEP 1: YOUR DETAILS
// ============================================================================
const Step1YourDetails = ({ formData, setFormData, onNext }) => {
  const clientTypes = [
    { value: 'INDIVIDUAL', label: 'Individual Landlord', icon: User, desc: 'Managing your own properties' },
    { value: 'COMPANY', label: 'Property Company', icon: Building2, desc: 'Corporate property management' },
    { value: 'AGENT', label: 'Letting Agent', icon: Users, desc: 'Managing properties for others' }
  ];

  const showCompanyName = formData.client_type === 'COMPANY' || formData.client_type === 'AGENT';
  const showPhone = formData.preferred_contact === 'SMS' || formData.preferred_contact === 'BOTH';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl text-midnight-blue">Your Details</CardTitle>
        <CardDescription>Tell us about yourself to personalize your experience</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Full Name */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">Full Name *</label>
          <Input
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            placeholder="John Smith"
            data-testid="full-name-input"
          />
        </div>

        {/* Email */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">Email Address *</label>
          <Input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            placeholder="john@example.com"
            data-testid="email-input"
          />
        </div>

        {/* Client Type - Card Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">I am a... *</label>
          <div className="grid grid-cols-3 gap-3">
            {clientTypes.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setFormData({ ...formData, client_type: type.value })}
                className={`p-4 rounded-lg border-2 text-left transition-all ${
                  formData.client_type === type.value
                    ? 'border-electric-teal bg-electric-teal/5 ring-2 ring-electric-teal/20'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                data-testid={`client-type-${type.value.toLowerCase()}`}
              >
                <type.icon className={`w-6 h-6 mb-2 ${
                  formData.client_type === type.value ? 'text-electric-teal' : 'text-gray-400'
                }`} />
                <p className="font-medium text-sm text-midnight-blue">{type.label}</p>
                <p className="text-xs text-gray-500 mt-1">{type.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Company Name (Conditional) */}
        {showCompanyName && (
          <div className="space-y-2 animate-fadeIn">
            <label className="text-sm font-medium text-gray-700">Company Name *</label>
            <Input
              value={formData.company_name}
              onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              placeholder="ABC Properties Ltd"
              data-testid="company-name-input"
            />
          </div>
        )}

        {/* Preferred Contact Method */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">Preferred Contact Method *</label>
          <div className="grid grid-cols-3 gap-3">
            {[
              { value: 'EMAIL', label: 'Email Only' },
              { value: 'SMS', label: 'SMS Only' },
              { value: 'BOTH', label: 'Both Email & SMS' }
            ].map((method) => (
              <button
                key={method.value}
                type="button"
                onClick={() => setFormData({ ...formData, preferred_contact: method.value })}
                className={`py-2 px-4 rounded-lg border-2 text-sm font-medium transition-all ${
                  formData.preferred_contact === method.value
                    ? 'border-electric-teal bg-electric-teal/5 text-electric-teal'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
                data-testid={`contact-${method.value.toLowerCase()}`}
              >
                {method.label}
              </button>
            ))}
          </div>
        </div>

        {/* Phone Number (Conditional) */}
        {showPhone && (
          <div className="space-y-2 animate-fadeIn">
            <label className="text-sm font-medium text-gray-700">Phone Number *</label>
            <Input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="+44 7700 900000"
              data-testid="phone-input"
            />
            <p className="text-xs text-gray-500">Required for SMS notifications</p>
          </div>
        )}

        <div className="pt-4">
          <Button 
            onClick={onNext} 
            className="w-full bg-electric-teal hover:bg-teal-600"
            data-testid="step1-next"
          >
            Next: Select Plan
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// STEP 2: SELECT PLAN
// ============================================================================
const Step2SelectPlan = ({ formData, setFormData, plans, onNext, onBack }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl text-midnight-blue">Select Your Plan</CardTitle>
        <CardDescription>Choose the plan that fits your portfolio size</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4">
          {plans.map((plan) => (
            <button
              key={plan.plan_id}
              type="button"
              onClick={() => setFormData({ ...formData, billing_plan: plan.plan_id })}
              className={`p-6 rounded-xl border-2 text-left transition-all ${
                formData.billing_plan === plan.plan_id
                  ? 'border-electric-teal bg-electric-teal/5 ring-2 ring-electric-teal/20'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              data-testid={`plan-${plan.plan_id.toLowerCase()}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-midnight-blue">{plan.name}</h3>
                    {plan.plan_id === 'PLAN_2_5' && (
                      <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">
                        Popular
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1">Up to {plan.max_properties} {plan.max_properties === 1 ? 'property' : 'properties'}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-electric-teal">£{plan.monthly_price.toFixed(2)}</p>
                  <p className="text-xs text-gray-500">/month</p>
                </div>
              </div>
              
              <div className="mt-4 pt-4 border-t border-gray-100">
                <ul className="grid grid-cols-2 gap-2">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-center gap-2 text-sm text-gray-600">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
              
              <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
                <span className="text-sm text-gray-500">First payment:</span>
                <span className="font-semibold text-midnight-blue">
                  £{(plan.monthly_price + plan.setup_fee).toFixed(2)}
                  <span className="text-xs text-gray-500 ml-1">(incl. £{plan.setup_fee.toFixed(2)} setup)</span>
                </span>
              </div>
            </button>
          ))}
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={onBack} className="flex-1" data-testid="step2-back">
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <Button 
            onClick={onNext} 
            className="flex-1 bg-electric-teal hover:bg-teal-600"
            data-testid="step2-next"
          >
            Next: Add Properties
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// STEP 3: PROPERTIES
// ============================================================================
const Step3Properties = ({ formData, setFormData, updateProperty, addProperty, removeProperty, propertyLimitError, setPropertyLimitError, onNext, onBack }) => {
  const maxProperties = PLAN_LIMITS[formData.billing_plan] || 2;
  const canAddMore = formData.properties.length < maxProperties;

  // Get upgrade plan info
  const getUpgradePlan = () => {
    const plan = formData.billing_plan;
    if (plan === 'PLAN_1_SOLO' || plan === 'PLAN_1') {
      return { code: 'PLAN_2_PORTFOLIO', name: 'Portfolio', limit: 10 };
    } else if (plan === 'PLAN_2_PORTFOLIO' || plan === 'PLAN_2_5') {
      return { code: 'PLAN_3_PRO', name: 'Professional', limit: 25 };
    }
    return null;
  };

  const upgradePlan = getUpgradePlan();

  const handleUpgrade = () => {
    if (upgradePlan) {
      setFormData({ ...formData, billing_plan: upgradePlan.code });
      setPropertyLimitError(null);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl text-midnight-blue">Your Properties</CardTitle>
              <CardDescription>
                Add up to {maxProperties} {maxProperties === 1 ? 'property' : 'properties'} with the {PLAN_NAMES[formData.billing_plan] || 'current'} plan
              </CardDescription>
            </div>
            <span className={`text-sm font-medium px-3 py-1 rounded-full ${
              formData.properties.length >= maxProperties 
                ? 'bg-amber-100 text-amber-800' 
                : 'bg-gray-100 text-gray-700'
            }`}>
              {formData.properties.length}/{maxProperties}
            </span>
          </div>
        </CardHeader>
      </Card>

      {/* Property Limit Error with Upgrade Prompt */}
      {propertyLimitError && (
        <PropertyLimitPrompt
          currentLimit={propertyLimitError.currentLimit}
          requestedCount={propertyLimitError.requestedCount}
          currentPlan={propertyLimitError.currentPlan}
          upgradePlan={propertyLimitError.upgradePlan}
          upgradePlanName={propertyLimitError.upgradePlanName}
          upgradeLimit={propertyLimitError.upgradeLimit}
          onUpgrade={handleUpgrade}
        />
      )}

      {formData.properties.map((property, index) => (
        <PropertyCard
          key={index}
          property={property}
          index={index}
          total={formData.properties.length}
          updateProperty={updateProperty}
          removeProperty={removeProperty}
          showLicenceFields={property.licence_required === 'YES'}
          showAgentFields={property.send_reminders_to === 'AGENT' || property.send_reminders_to === 'BOTH'}
        />
      ))}

      {/* Add Property Button */}
      {canAddMore ? (
        <button
          type="button"
          onClick={addProperty}
          className="w-full py-4 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:border-electric-teal hover:text-electric-teal transition-colors flex items-center justify-center gap-2"
          data-testid="add-property-btn"
        >
          <Plus className="w-5 h-5" />
          Add Another Property ({formData.properties.length + 1}/{maxProperties})
        </button>
      ) : (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3" data-testid="property-limit-warning">
          <Lock className="w-5 h-5 text-amber-600 mt-0.5" />
          <div>
            <p className="font-medium text-amber-800">Property limit reached</p>
            <p className="text-sm text-amber-700">
              You've added the maximum {maxProperties} {maxProperties === 1 ? 'property' : 'properties'} for the {PLAN_NAMES[formData.billing_plan] || 'current'} plan.
              {upgradePlan && (
                <>
                  {' '}
                  <button 
                    onClick={handleUpgrade}
                    className="underline font-medium hover:text-amber-900"
                    data-testid="upgrade-plan-link"
                  >
                    Upgrade to {upgradePlan.name} (up to {upgradePlan.limit} properties)
                  </button>
                </>
              )}
            </p>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1" data-testid="step3-back">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button 
          onClick={onNext} 
          className="flex-1 bg-electric-teal hover:bg-teal-600"
          data-testid="step3-next"
        >
          Next: Preferences
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
};

// Property Card Component
const PropertyCard = ({ property, index, total, updateProperty, removeProperty, showLicenceFields, showAgentFields }) => {
  const [councilSearch, setCouncilSearch] = useState('');
  const [councilResults, setCouncilResults] = useState([]);
  const [showCouncilDropdown, setShowCouncilDropdown] = useState(false);
  const [loadingCouncils, setLoadingCouncils] = useState(false);
  const [lookingUpPostcode, setLookingUpPostcode] = useState(false);
  const [postcodeError, setPostcodeError] = useState('');
  const [postcodeLookupDone, setPostcodeLookupDone] = useState(false);
  
  // Postcode autocomplete state
  const [postcodeInput, setPostcodeInput] = useState(property.postcode || '');
  const [postcodeSuggestions, setPostcodeSuggestions] = useState([]);
  const [showPostcodeDropdown, setShowPostcodeDropdown] = useState(false);
  const [loadingPostcodes, setLoadingPostcodes] = useState(false);
  
  const councilRef = useRef(null);
  const postcodeRef = useRef(null);

  // Postcode autocomplete - fetch suggestions as user types
  const fetchPostcodeSuggestions = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setPostcodeSuggestions([]);
      return;
    }
    
    setLoadingPostcodes(true);
    try {
      const response = await intakeAPI.autocompletePostcode(query);
      setPostcodeSuggestions(response.data.postcodes || []);
    } catch (err) {
      console.error('Postcode autocomplete error:', err);
      setPostcodeSuggestions([]);
    } finally {
      setLoadingPostcodes(false);
    }
  }, []);

  // Debounced postcode autocomplete
  useEffect(() => {
    const timer = setTimeout(() => {
      if (postcodeInput && postcodeInput.length >= 2 && !postcodeLookupDone) {
        fetchPostcodeSuggestions(postcodeInput);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [postcodeInput, postcodeLookupDone, fetchPostcodeSuggestions]);

  // Select a postcode from dropdown and trigger full lookup
  const selectPostcode = async (suggestion) => {
    const postcode = suggestion.postcode;
    setPostcodeInput(postcode);
    updateProperty(index, 'postcode', postcode);
    setShowPostcodeDropdown(false);
    setPostcodeSuggestions([]);
    
    // Trigger full lookup
    await lookupPostcode(postcode);
  };

  // Lookup postcode and auto-fill fields
  const lookupPostcode = useCallback(async (postcode) => {
    if (!postcode || postcode.length < 5) return;
    
    // Clean postcode
    const cleanPostcode = postcode.trim().toUpperCase().replace(/\s+/g, '');
    
    // Basic UK postcode validation
    if (!/^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i.test(cleanPostcode)) {
      return;
    }
    
    setLookingUpPostcode(true);
    setPostcodeError('');
    
    try {
      const response = await intakeAPI.lookupPostcode(postcode);
      const data = response.data;
      
      // Auto-fill city
      if (data.suggested_city && !property.city) {
        updateProperty(index, 'city', data.suggested_city);
      }
      
      // Auto-fill council
      if (data.council_name && !property.council_name) {
        updateProperty(index, 'council_name', data.council_name);
        updateProperty(index, 'council_code', data.council_code);
        setCouncilSearch(data.council_name);
      }
      
      setPostcodeLookupDone(true);
      toast.success('Address details found! Please enter your street address.');
    } catch (err) {
      if (err.response?.status === 404) {
        setPostcodeError('Postcode not found');
      } else {
        setPostcodeError('Could not lookup postcode');
      }
    } finally {
      setLookingUpPostcode(false);
    }
  }, [index, property.city, property.council_name, updateProperty]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (councilRef.current && !councilRef.current.contains(e.target)) {
        setShowCouncilDropdown(false);
      }
      if (postcodeRef.current && !postcodeRef.current.contains(e.target)) {
        setShowPostcodeDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search councils
  const searchCouncils = useCallback(async (query) => {
    if (query.length < 2) {
      setCouncilResults([]);
      return;
    }
    
    setLoadingCouncils(true);
    try {
      const response = await intakeAPI.searchCouncils(query);
      setCouncilResults(response.data.councils);
    } catch (err) {
      console.error('Council search error:', err);
    } finally {
      setLoadingCouncils(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (councilSearch) {
        searchCouncils(councilSearch);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [councilSearch, searchCouncils]);

  const selectCouncil = (council) => {
    updateProperty(index, 'council_name', council.name);
    updateProperty(index, 'council_code', council.code);
    setCouncilSearch(council.name);
    setShowCouncilDropdown(false);
  };

  // Handle postcode input change
  const handlePostcodeChange = (value) => {
    const upperValue = value.toUpperCase();
    setPostcodeInput(upperValue);
    updateProperty(index, 'postcode', upperValue);
    setPostcodeLookupDone(false);
    setPostcodeError('');
    setShowPostcodeDropdown(true);
  };

  // Handle postcode blur - trigger lookup if valid
  const handlePostcodeBlur = () => {
    // Small delay to allow dropdown click to register
    setTimeout(() => {
      setShowPostcodeDropdown(false);
      if (postcodeInput && postcodeInput.length >= 5 && !postcodeLookupDone) {
        lookupPostcode(postcodeInput);
      }
    }, 200);
  };

  return (
    <Card className="overflow-hidden" data-testid={`property-card-${index}`}>
      <div className="bg-gray-50 px-6 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Home className="w-4 h-4 text-gray-500" />
          <span className="font-medium text-midnight-blue">Property {index + 1}</span>
          {property.nickname && <span className="text-gray-500">- {property.nickname}</span>}
        </div>
        {total > 1 && (
          <button
            type="button"
            onClick={() => removeProperty(index)}
            className="text-red-500 hover:text-red-600 p-1"
            data-testid={`remove-property-${index}`}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
      
      <CardContent className="pt-6 space-y-6">
        {/* Basic Info */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Property Nickname</label>
            <Input
              value={property.nickname}
              onChange={(e) => updateProperty(index, 'nickname', e.target.value)}
              placeholder="e.g., Main Street Flat"
              data-testid={`property-${index}-nickname`}
            />
          </div>
          <div className="space-y-2" ref={postcodeRef}>
            <label className="text-sm font-medium text-gray-700">Postcode *</label>
            <div className="relative">
              <Input
                value={postcodeInput}
                onChange={(e) => handlePostcodeChange(e.target.value)}
                onFocus={() => postcodeInput.length >= 2 && setShowPostcodeDropdown(true)}
                onBlur={handlePostcodeBlur}
                placeholder="Start typing... e.g., SW1A"
                className={postcodeError ? 'border-red-300' : ''}
                data-testid={`property-${index}-postcode`}
              />
              {(lookingUpPostcode || loadingPostcodes) && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <Loader2 className="w-4 h-4 animate-spin text-electric-teal" />
                </div>
              )}
              {postcodeLookupDone && !lookingUpPostcode && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                </div>
              )}
              
              {/* Postcode Autocomplete Dropdown */}
              {showPostcodeDropdown && postcodeSuggestions.length > 0 && (
                <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                  {postcodeSuggestions.map((suggestion, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        selectPostcode(suggestion);
                      }}
                      className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                    >
                      <div>
                        <span className="font-medium text-midnight-blue">{suggestion.postcode}</span>
                        <span className="text-sm text-gray-500 ml-2">
                          {suggestion.post_town || suggestion.admin_district}
                        </span>
                      </div>
                      <span className="text-xs text-gray-400">{suggestion.region}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {postcodeError && (
              <p className="text-xs text-red-500">{postcodeError}</p>
            )}
            {postcodeLookupDone && (
              <p className="text-xs text-green-600">City and council auto-filled ✓</p>
            )}
            {!postcodeLookupDone && !postcodeError && postcodeInput.length >= 2 && (
              <p className="text-xs text-gray-500">Select from suggestions or type full postcode</p>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">Address Line 1 *</label>
          <Input
            value={property.address_line_1}
            onChange={(e) => updateProperty(index, 'address_line_1', e.target.value)}
            placeholder="123 Example Street"
            data-testid={`property-${index}-address1`}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Address Line 2</label>
            <Input
              value={property.address_line_2}
              onChange={(e) => updateProperty(index, 'address_line_2', e.target.value)}
              placeholder="Flat 4, Building Name"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">City *</label>
            <Input
              value={property.city}
              onChange={(e) => updateProperty(index, 'city', e.target.value)}
              placeholder="London"
              data-testid={`property-${index}-city`}
            />
          </div>
        </div>

        {/* Property Type & Details */}
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Property Type</label>
            <select
              value={property.property_type}
              onChange={(e) => updateProperty(index, 'property_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              data-testid={`property-${index}-type`}
            >
              {PROPERTY_TYPES.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Bedrooms</label>
            <Input
              type="number"
              min="1"
              max="20"
              value={property.bedrooms}
              onChange={(e) => updateProperty(index, 'bedrooms', e.target.value)}
              placeholder="3"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Occupancy</label>
            <select
              value={property.occupancy}
              onChange={(e) => updateProperty(index, 'occupancy', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              {OCCUPANCY_TYPES.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* HMO Toggle */}
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div>
            <p className="font-medium text-sm text-midnight-blue">Is this an HMO?</p>
            <p className="text-xs text-gray-500">House in Multiple Occupation</p>
          </div>
          <Switch
            checked={property.is_hmo}
            onCheckedChange={(checked) => updateProperty(index, 'is_hmo', checked)}
            data-testid={`property-${index}-hmo`}
          />
        </div>

        {/* Council Search */}
        <div className="space-y-2" ref={councilRef}>
          <label className="text-sm font-medium text-gray-700">Local Council</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              value={councilSearch || property.council_name}
              onChange={(e) => {
                setCouncilSearch(e.target.value);
                setShowCouncilDropdown(true);
              }}
              onFocus={() => setShowCouncilDropdown(true)}
              placeholder="Search councils..."
              className="pl-10"
              data-testid={`property-${index}-council`}
            />
            {property.council_name && (
              <button
                type="button"
                onClick={() => {
                  updateProperty(index, 'council_name', '');
                  updateProperty(index, 'council_code', '');
                  setCouncilSearch('');
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            )}
          </div>
          
          {showCouncilDropdown && councilResults.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {councilResults.map((council) => (
                <button
                  key={council.code}
                  type="button"
                  onClick={() => selectCouncil(council)}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                >
                  <span className="font-medium text-sm">{council.name}</span>
                  <span className="text-xs text-gray-500">{council.region}</span>
                </button>
              ))}
            </div>
          )}
          {loadingCouncils && (
            <p className="text-xs text-gray-500">Searching...</p>
          )}
        </div>

        {/* Licensing */}
        <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Is a licence required?</label>
            <div className="flex gap-2">
              {['YES', 'NO', 'UNSURE'].map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => updateProperty(index, 'licence_required', opt)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    property.licence_required === opt
                      ? 'bg-electric-teal text-white'
                      : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {opt === 'YES' ? 'Yes' : opt === 'NO' ? 'No' : 'Unsure'}
                </button>
              ))}
            </div>
          </div>

          {showLicenceFields && (
            <div className="grid grid-cols-2 gap-4 pt-2 animate-fadeIn">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Licence Type</label>
                <select
                  value={property.licence_type}
                  onChange={(e) => updateProperty(index, 'licence_type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">Select type...</option>
                  {LICENCE_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Licence Status</label>
                <select
                  value={property.licence_status}
                  onChange={(e) => updateProperty(index, 'licence_status', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">Select status...</option>
                  {LICENCE_STATUSES.map(status => (
                    <option key={status.value} value={status.value}>{status.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Management & Reminders */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Who manages this property?</label>
            <select
              value={property.managed_by}
              onChange={(e) => updateProperty(index, 'managed_by', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="LANDLORD">Landlord</option>
              <option value="AGENT">Agent</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Send reminders to</label>
            <select
              value={property.send_reminders_to}
              onChange={(e) => updateProperty(index, 'send_reminders_to', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="LANDLORD">Landlord</option>
              <option value="AGENT">Agent</option>
              <option value="BOTH">Both</option>
            </select>
          </div>
        </div>

        {/* Agent Details (Conditional) */}
        {showAgentFields && (
          <div className="p-4 bg-blue-50 rounded-lg space-y-4 animate-fadeIn">
            <p className="text-sm font-medium text-blue-800">Agent Details</p>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Agent Name *</label>
                <Input
                  value={property.agent_name}
                  onChange={(e) => updateProperty(index, 'agent_name', e.target.value)}
                  placeholder="Jane Doe"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Agent Email *</label>
                <Input
                  type="email"
                  value={property.agent_email}
                  onChange={(e) => updateProperty(index, 'agent_email', e.target.value)}
                  placeholder="agent@example.com"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Agent Phone</label>
                <Input
                  type="tel"
                  value={property.agent_phone}
                  onChange={(e) => updateProperty(index, 'agent_phone', e.target.value)}
                  placeholder="+44 7700 900000"
                />
              </div>
            </div>
          </div>
        )}

        {/* Current Compliance Status */}
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg space-y-4">
          <div className="flex items-start gap-2">
            <Info className="w-5 h-5 text-amber-600 mt-0.5" />
            <div>
              <p className="font-medium text-amber-800">Current Compliance Status</p>
              <p className="text-sm text-amber-700">Do you currently have these certificates?</p>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            {[
              { key: 'cert_gas_safety', label: 'Gas Safety Certificate' },
              { key: 'cert_eicr', label: 'EICR (Electrical)' },
              { key: 'cert_epc', label: 'EPC' },
              ...(property.licence_required === 'YES' ? [{ key: 'cert_licence', label: 'Licence' }] : [])
            ].map(cert => (
              <div key={cert.key} className="space-y-2">
                <label className="text-sm font-medium text-gray-700">{cert.label}</label>
                <select
                  value={property[cert.key]}
                  onChange={(e) => updateProperty(index, cert.key, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                >
                  <option value="">Select...</option>
                  {CERT_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// STEP 4: PREFERENCES & CONSENTS
// ============================================================================
const Step4Preferences = ({ formData, setFormData, onNext, onBack }) => {
  const PLEERITY_EMAIL = 'info@pleerityenterprise.co.uk';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl text-midnight-blue">Preferences & Consents</CardTitle>
        <CardDescription>Choose how you'd like to submit documents and accept required terms</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Document Submission Method */}
        <div className="space-y-4">
          <label className="text-sm font-medium text-gray-700">How would you like to submit documents? *</label>
          
          <div className="grid grid-cols-2 gap-4">
            {/* Option A: Upload */}
            <button
              type="button"
              onClick={() => setFormData({ ...formData, document_submission_method: 'UPLOAD', email_upload_consent: false })}
              className={`p-6 rounded-xl border-2 text-left transition-all ${
                formData.document_submission_method === 'UPLOAD'
                  ? 'border-electric-teal bg-electric-teal/5 ring-2 ring-electric-teal/20'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              data-testid="doc-method-upload"
            >
              <Upload className={`w-8 h-8 mb-3 ${
                formData.document_submission_method === 'UPLOAD' ? 'text-electric-teal' : 'text-gray-400'
              }`} />
              <h3 className="font-semibold text-midnight-blue">Upload Here</h3>
              <p className="text-sm text-gray-500 mt-1">
                Upload your compliance documents directly through the portal
              </p>
            </button>
            
            {/* Option B: Email */}
            <button
              type="button"
              onClick={() => setFormData({ ...formData, document_submission_method: 'EMAIL' })}
              className={`p-6 rounded-xl border-2 text-left transition-all ${
                formData.document_submission_method === 'EMAIL'
                  ? 'border-electric-teal bg-electric-teal/5 ring-2 ring-electric-teal/20'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              data-testid="doc-method-email"
            >
              <Mail className={`w-8 h-8 mb-3 ${
                formData.document_submission_method === 'EMAIL' ? 'text-electric-teal' : 'text-gray-400'
              }`} />
              <h3 className="font-semibold text-midnight-blue">Email to Pleerity</h3>
              <p className="text-sm text-gray-500 mt-1">
                Email your documents and we'll upload them for you
              </p>
            </button>
          </div>
        </div>

        {/* Email Upload Section */}
        {formData.document_submission_method === 'EMAIL' && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-4 animate-fadeIn">
            <div>
              <p className="text-sm font-medium text-blue-800 mb-2">Send your documents to:</p>
              <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-blue-200">
                <Mail className="w-5 h-5 text-blue-600" />
                <span className="font-mono font-medium text-blue-900">{PLEERITY_EMAIL}</span>
              </div>
              <p className="text-xs text-blue-700 mt-2">
                After payment, please email your compliance documents to this address and include your customer reference number.
              </p>
            </div>
            
            <label className="flex items-start gap-3 p-4 bg-white rounded-lg border border-blue-200 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.email_upload_consent}
                onChange={(e) => setFormData({ ...formData, email_upload_consent: e.target.checked })}
                className="mt-1 rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
                data-testid="email-consent-checkbox"
              />
              <div>
                <span className="text-sm font-medium text-gray-900">
                  I consent to Pleerity uploading documents on my behalf *
                </span>
                <p className="text-xs text-gray-600 mt-1">
                  By checking this box, you authorise Pleerity Enterprise Ltd to upload compliance documents you email to {PLEERITY_EMAIL} into your portal.
                </p>
              </div>
            </label>
          </div>
        )}

        {/* Mandatory Consents */}
        <div className="space-y-4 pt-4 border-t">
          <h3 className="font-semibold text-midnight-blue">Required Consents</h3>
          
          {/* GDPR Consent */}
          <label className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="checkbox"
              checked={formData.consent_data_processing}
              onChange={(e) => setFormData({ ...formData, consent_data_processing: e.target.checked })}
              className="mt-1 rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
              data-testid="gdpr-consent-checkbox"
            />
            <div>
              <span className="text-sm font-medium text-gray-900">
                Data Processing Consent (GDPR) *
              </span>
              <p className="text-xs text-gray-600 mt-1">
                I consent to Pleerity Enterprise Ltd processing my personal data for compliance management purposes in accordance with their Privacy Policy.
              </p>
            </div>
          </label>

          {/* Service Boundary Acknowledgment */}
          <label className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="checkbox"
              checked={formData.consent_service_boundary}
              onChange={(e) => setFormData({ ...formData, consent_service_boundary: e.target.checked })}
              className="mt-1 rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
              data-testid="service-consent-checkbox"
            />
            <div>
              <span className="text-sm font-medium text-gray-900">
                Service Acknowledgment *
              </span>
              <p className="text-xs text-gray-600 mt-1">
                I understand that Compliance Vault Pro does not provide legal advice or guarantee regulatory compliance. The service is a compliance tracking tool and the responsibility for ensuring regulatory compliance remains with the property owner/manager.
              </p>
            </div>
          </label>
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="outline" onClick={onBack} className="flex-1" data-testid="step4-back">
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <Button 
            onClick={onNext} 
            className="flex-1 bg-electric-teal hover:bg-teal-600"
            data-testid="step4-next"
          >
            Review & Pay
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// STEP 5: REVIEW & PAYMENT
// ============================================================================
const Step5Review = ({ formData, plans, goToStep, onSubmit, onBack, loading }) => {
  const selectedPlan = plans.find(p => p.plan_id === formData.billing_plan);

  const clientTypeLabels = {
    INDIVIDUAL: 'Individual Landlord',
    COMPANY: 'Property Company',
    AGENT: 'Letting Agent'
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl text-midnight-blue">Review Your Details</CardTitle>
          <CardDescription>Please review your information before proceeding to payment</CardDescription>
        </CardHeader>
      </Card>

      {/* Your Details Summary */}
      <Card>
        <div className="px-6 py-3 bg-gray-50 border-b flex items-center justify-between">
          <h3 className="font-semibold text-midnight-blue">Your Details</h3>
          <button 
            onClick={() => goToStep(1)} 
            className="text-sm text-electric-teal hover:underline"
            data-testid="edit-details"
          >
            Edit
          </button>
        </div>
        <CardContent className="pt-4">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Full Name</dt>
              <dd className="font-medium text-midnight-blue">{formData.full_name}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Email</dt>
              <dd className="font-medium text-midnight-blue">{formData.email}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Account Type</dt>
              <dd className="font-medium text-midnight-blue">{clientTypeLabels[formData.client_type]}</dd>
            </div>
            {formData.company_name && (
              <div>
                <dt className="text-gray-500">Company</dt>
                <dd className="font-medium text-midnight-blue">{formData.company_name}</dd>
              </div>
            )}
            <div>
              <dt className="text-gray-500">Contact Preference</dt>
              <dd className="font-medium text-midnight-blue">{formData.preferred_contact}</dd>
            </div>
            {formData.phone && (
              <div>
                <dt className="text-gray-500">Phone</dt>
                <dd className="font-medium text-midnight-blue">{formData.phone}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Plan Summary */}
      {selectedPlan && (
        <Card>
          <div className="px-6 py-3 bg-gray-50 border-b flex items-center justify-between">
            <h3 className="font-semibold text-midnight-blue">Selected Plan</h3>
            <button 
              onClick={() => goToStep(2)} 
              className="text-sm text-electric-teal hover:underline"
              data-testid="edit-plan"
            >
              Edit
            </button>
          </div>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-midnight-blue">{selectedPlan.name}</p>
                <p className="text-sm text-gray-500">Up to {selectedPlan.max_properties} properties</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-electric-teal">£{selectedPlan.monthly_price.toFixed(2)}/month</p>
                <p className="text-xs text-gray-500">+ £{selectedPlan.setup_fee.toFixed(2)} setup fee</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Properties Summary */}
      <Card>
        <div className="px-6 py-3 bg-gray-50 border-b flex items-center justify-between">
          <h3 className="font-semibold text-midnight-blue">Properties ({formData.properties.length})</h3>
          <button 
            onClick={() => goToStep(3)} 
            className="text-sm text-electric-teal hover:underline"
            data-testid="edit-properties"
          >
            Edit
          </button>
        </div>
        <CardContent className="pt-4 divide-y">
          {formData.properties.map((prop, index) => (
            <div key={index} className={`py-3 ${index > 0 ? 'pt-3' : ''}`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-midnight-blue">
                    {prop.nickname || `Property ${index + 1}`}
                  </p>
                  <p className="text-sm text-gray-600">{prop.address_line_1}, {prop.city}, {prop.postcode}</p>
                </div>
                <div className="flex gap-2">
                  {prop.is_hmo && (
                    <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">HMO</span>
                  )}
                  {prop.licence_required === 'YES' && (
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">Licensed</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Preferences Summary */}
      <Card>
        <div className="px-6 py-3 bg-gray-50 border-b flex items-center justify-between">
          <h3 className="font-semibold text-midnight-blue">Preferences</h3>
          <button 
            onClick={() => goToStep(4)} 
            className="text-sm text-electric-teal hover:underline"
            data-testid="edit-preferences"
          >
            Edit
          </button>
        </div>
        <CardContent className="pt-4">
          <div className="flex items-center gap-2">
            {formData.document_submission_method === 'UPLOAD' ? (
              <>
                <Upload className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-700">Documents will be uploaded through the portal</span>
              </>
            ) : (
              <>
                <Mail className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-700">Documents will be emailed to Pleerity</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 mt-2">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span className="text-sm text-gray-700">GDPR and service terms accepted</span>
          </div>
        </CardContent>
      </Card>

      {/* Payment Summary */}
      {selectedPlan && (
        <Card className="border-2 border-electric-teal">
          <CardContent className="pt-6">
            <h3 className="font-semibold text-midnight-blue mb-4">Payment Summary</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Monthly subscription</span>
                <span className="font-medium">£{selectedPlan.monthly_price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">One-time setup fee</span>
                <span className="font-medium">£{selectedPlan.setup_fee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t text-base">
                <span className="font-semibold text-midnight-blue">Total due today</span>
                <span className="font-bold text-electric-teal">
                  £{(selectedPlan.monthly_price + selectedPlan.setup_fee).toFixed(2)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={onBack} className="flex-1" data-testid="step5-back">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button 
          onClick={onSubmit} 
          disabled={loading}
          className="flex-1 bg-electric-teal hover:bg-teal-600"
          data-testid="submit-payment"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <CreditCard className="w-4 h-4 mr-2" />
              Proceed to Payment
            </>
          )}
        </Button>
      </div>

      {/* Cancel Link */}
      <div className="text-center">
        <button 
          onClick={() => window.location.href = '/'}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel and return to homepage
        </button>
      </div>
    </div>
  );
};

export default IntakePage;
