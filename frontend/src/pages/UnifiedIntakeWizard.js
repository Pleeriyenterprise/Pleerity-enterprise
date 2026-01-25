/**
 * Unified Intake Wizard - Multi-step intake form for all non-CVP services.
 * 
 * Steps:
 * 1. Select Service (and pack type/add-ons for document packs)
 * 2. Client Identity (universal fields)
 * 3. Service-Specific Fields (dynamic from schema)
 * 4. Review Summary (all inputs + pricing)
 * 5. Payment (Stripe redirect)
 * 6. Confirmation (order ref after payment)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, Check, CreditCard, FileText,
  User, Briefcase, Building2, Mail, Phone, CheckCircle2,
  AlertCircle, Loader2, Package, Zap, Printer, ChevronDown
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import client from '../api/client';
import { validateCheckout, isDocumentPack, getPackTierName } from '../api/checkoutApi';

// ============================================================================
// STEP COMPONENTS
// ============================================================================

const STEPS = [
  { id: 1, name: 'Select Service', icon: Package },
  { id: 2, name: 'Your Details', icon: User },
  { id: 3, name: 'Service Details', icon: FileText },
  { id: 4, name: 'Review', icon: CheckCircle2 },
  { id: 5, name: 'Payment', icon: CreditCard },
];

function StepIndicator({ currentStep }) {
  return (
    <div className="flex items-center justify-center mb-8">
      {STEPS.map((step, idx) => {
        const isComplete = currentStep > step.id;
        const isCurrent = currentStep === step.id;
        const Icon = step.icon;
        
        return (
          <React.Fragment key={step.id}>
            <div className="flex flex-col items-center">
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors
                ${isComplete ? 'bg-teal-600 border-teal-600 text-white' :
                  isCurrent ? 'border-teal-600 text-teal-600 bg-teal-50' :
                  'border-gray-300 text-gray-400'}
              `}>
                {isComplete ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
              </div>
              <span className={`mt-1 text-xs font-medium ${isCurrent ? 'text-teal-600' : 'text-gray-500'}`}>
                {step.name}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`w-16 h-0.5 mx-2 ${currentStep > step.id ? 'bg-teal-600' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}


// ============================================================================
// STEP 1: SERVICE SELECTION
// ============================================================================

function ServiceSelectionStep({ services, onSelect, selectedService, packs, addons, selectedAddons, onToggleAddon, postalAddress, onPostalChange }) {
  const categories = [
    { code: 'ai_automation', name: 'AI & Automation', icon: Briefcase },
    { code: 'market_research', name: 'Market Research', icon: FileText },
    { code: 'compliance', name: 'Compliance Services', icon: Building2 },
    { code: 'document_pack', name: 'Document Packs', icon: Package },
  ];

  const selectedCategory = selectedService?.category;
  const isDocPack = selectedService?.service_code?.startsWith('DOC_PACK');
  const hasPrintedCopy = selectedAddons.includes('PRINTED_COPY');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Select a Service</h2>
        <p className="text-gray-600">Choose the service that best fits your needs</p>
      </div>

      {categories.map(cat => {
        const catServices = services.filter(s => s.category === cat.code);
        if (catServices.length === 0) return null;
        const CatIcon = cat.icon;
        
        return (
          <div key={cat.code} className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <CatIcon className="h-5 w-5 text-teal-600" />
              <h3 className="font-medium text-gray-800">{cat.name}</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {catServices.map(service => {
                const isSelected = selectedService?.service_code === service.service_code;
                
                return (
                  <Card
                    key={service.service_code}
                    className={`cursor-pointer transition-all hover:shadow-md ${
                      isSelected ? 'ring-2 ring-teal-600 bg-teal-50' : 'hover:border-teal-300'
                    }`}
                    onClick={() => onSelect(service)}
                    data-testid={`service-${service.service_code}`}
                  >
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">{service.name}</h4>
                          <p className="text-sm text-gray-500 mt-1">{service.description}</p>
                        </div>
                        <div className="text-right ml-3">
                          <span className="text-lg font-bold text-teal-600">{service.price_display}</span>
                          {isSelected && <Check className="h-5 w-5 text-teal-600 mt-1 ml-auto" />}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Add-ons section for Document Packs */}
      {isDocPack && addons.length > 0 && (
        <div className="mt-6 p-4 bg-gray-50 rounded-lg border">
          <h3 className="font-medium text-gray-900 mb-3">Optional Add-ons</h3>
          <div className="space-y-3">
            {addons.map(addon => {
              const isSelected = selectedAddons.includes(addon.addon_code);
              
              return (
                <div
                  key={addon.addon_code}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isSelected ? 'bg-teal-50 border-teal-300' : 'bg-white hover:border-teal-300'
                  }`}
                  onClick={() => onToggleAddon(addon.addon_code)}
                >
                  <div className="flex items-center gap-3">
                    <Checkbox checked={isSelected} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {addon.addon_code === 'FAST_TRACK' && <Zap className="h-4 w-4 text-yellow-500" />}
                        {addon.addon_code === 'PRINTED_COPY' && <Printer className="h-4 w-4 text-blue-500" />}
                        <span className="font-medium">{addon.name}</span>
                        <Badge variant="secondary" className="text-xs">{addon.price_display}</Badge>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">{addon.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Postal Address for Printed Copy */}
      {hasPrintedCopy && (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="font-medium text-blue-900 mb-3 flex items-center gap-2">
            <Printer className="h-4 w-4" />
            Postal Delivery Address
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Recipient Name *</Label>
              <Input
                value={postalAddress.postal_recipient_name || ''}
                onChange={(e) => onPostalChange('postal_recipient_name', e.target.value)}
                placeholder="John Smith"
              />
            </div>
            <div>
              <Label>Phone *</Label>
              <Input
                value={postalAddress.postal_phone || ''}
                onChange={(e) => onPostalChange('postal_phone', e.target.value)}
                placeholder="+44 7xxx xxxxxx"
              />
            </div>
            <div className="md:col-span-2">
              <Label>Address Line 1 *</Label>
              <Input
                value={postalAddress.postal_address_line1 || ''}
                onChange={(e) => onPostalChange('postal_address_line1', e.target.value)}
                placeholder="123 High Street"
              />
            </div>
            <div className="md:col-span-2">
              <Label>Address Line 2</Label>
              <Input
                value={postalAddress.postal_address_line2 || ''}
                onChange={(e) => onPostalChange('postal_address_line2', e.target.value)}
                placeholder="Flat 2 (optional)"
              />
            </div>
            <div>
              <Label>City *</Label>
              <Input
                value={postalAddress.postal_city || ''}
                onChange={(e) => onPostalChange('postal_city', e.target.value)}
                placeholder="London"
              />
            </div>
            <div>
              <Label>Postcode *</Label>
              <Input
                value={postalAddress.postal_postcode || ''}
                onChange={(e) => onPostalChange('postal_postcode', e.target.value)}
                placeholder="SW1A 1AA"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================================
// STEP 2: CLIENT IDENTITY
// ============================================================================

function ClientIdentityStep({ data, onChange, errors }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Your Details</h2>
        <p className="text-gray-600">Tell us about yourself</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <Label htmlFor="full_name">Full Name *</Label>
          <Input
            id="full_name"
            value={data.full_name || ''}
            onChange={(e) => onChange('full_name', e.target.value)}
            placeholder="John Smith"
            className={errors.full_name ? 'border-red-500' : ''}
          />
          {errors.full_name && <p className="text-red-500 text-sm mt-1">{errors.full_name}</p>}
        </div>
        
        <div>
          <Label htmlFor="email">Email Address *</Label>
          <Input
            id="email"
            type="email"
            value={data.email || ''}
            onChange={(e) => onChange('email', e.target.value)}
            placeholder="john@example.com"
            className={errors.email ? 'border-red-500' : ''}
          />
          {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
        </div>
        
        <div>
          <Label htmlFor="phone">Phone Number *</Label>
          <Input
            id="phone"
            value={data.phone || ''}
            onChange={(e) => onChange('phone', e.target.value)}
            placeholder="+44 7xxx xxxxxx"
            className={errors.phone ? 'border-red-500' : ''}
          />
          {errors.phone && <p className="text-red-500 text-sm mt-1">{errors.phone}</p>}
        </div>
        
        <div>
          <Label htmlFor="role">Your Role *</Label>
          <Select value={data.role || ''} onValueChange={(v) => onChange('role', v)}>
            <SelectTrigger className={errors.role ? 'border-red-500' : ''}>
              <SelectValue placeholder="Select your role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Landlord">Landlord</SelectItem>
              <SelectItem value="Business Owner">Business Owner</SelectItem>
              <SelectItem value="Manager">Manager</SelectItem>
              <SelectItem value="Other">Other</SelectItem>
            </SelectContent>
          </Select>
          {errors.role && <p className="text-red-500 text-sm mt-1">{errors.role}</p>}
        </div>
        
        {data.role === 'Other' && (
          <div>
            <Label htmlFor="role_other_text">Please specify *</Label>
            <Input
              id="role_other_text"
              value={data.role_other_text || ''}
              onChange={(e) => onChange('role_other_text', e.target.value)}
              placeholder="e.g., Consultant"
              className={errors.role_other_text ? 'border-red-500' : ''}
            />
            {errors.role_other_text && <p className="text-red-500 text-sm mt-1">{errors.role_other_text}</p>}
          </div>
        )}
        
        <div>
          <Label htmlFor="company_name">Company Name</Label>
          <Input
            id="company_name"
            value={data.company_name || ''}
            onChange={(e) => onChange('company_name', e.target.value)}
            placeholder="Acme Ltd (optional)"
          />
        </div>
        
        <div>
          <Label htmlFor="company_website">Company Website</Label>
          <Input
            id="company_website"
            value={data.company_website || ''}
            onChange={(e) => onChange('company_website', e.target.value)}
            placeholder="https://example.com (optional)"
          />
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// STEP 3: SERVICE-SPECIFIC FIELDS (Dynamic)
// ============================================================================

function DynamicField({ field, value, onChange, error }) {
  const renderField = () => {
    switch (field.type) {
      case 'text':
      case 'email':
      case 'phone':
        return (
          <Input
            type={field.type === 'email' ? 'email' : 'text'}
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            className={error ? 'border-red-500' : ''}
          />
        );
      
      case 'textarea':
        return (
          <Textarea
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            rows={4}
            className={error ? 'border-red-500' : ''}
          />
        );
      
      case 'number':
      case 'currency':
        return (
          <Input
            type="number"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            min={field.validation?.min}
            max={field.validation?.max}
            className={error ? 'border-red-500' : ''}
          />
        );
      
      case 'select':
        return (
          <Select value={value || ''} onValueChange={onChange}>
            <SelectTrigger className={error ? 'border-red-500' : ''}>
              <SelectValue placeholder={field.placeholder || 'Select...'} />
            </SelectTrigger>
            <SelectContent>
              {(field.options || []).map(opt => (
                <SelectItem key={opt} value={opt}>{opt}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      
      case 'multi_select':
        return (
          <div className="space-y-2 p-3 border rounded-lg max-h-48 overflow-y-auto">
            {(field.options || []).map(opt => {
              const selected = Array.isArray(value) && value.includes(opt);
              return (
                <div
                  key={opt}
                  className="flex items-center gap-2 cursor-pointer"
                  onClick={() => {
                    const current = Array.isArray(value) ? value : [];
                    if (selected) {
                      onChange(current.filter(v => v !== opt));
                    } else if (!field.max_items || current.length < field.max_items) {
                      onChange([...current, opt]);
                    }
                  }}
                >
                  <Checkbox checked={selected} />
                  <span className="text-sm">{opt}</span>
                </div>
              );
            })}
          </div>
        );
      
      case 'multi_text':
        return (
          <MultiTextInput
            value={value || []}
            onChange={onChange}
            placeholder={field.placeholder}
            maxItems={field.max_items || 10}
          />
        );
      
      case 'date':
        return (
          <Input
            type="date"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            className={error ? 'border-red-500' : ''}
          />
        );
      
      case 'checkbox':
        return (
          <div className="flex items-center gap-2">
            <Checkbox
              checked={value || false}
              onCheckedChange={onChange}
            />
            <span className="text-sm text-gray-700">{field.label}</span>
          </div>
        );
      
      case 'checkbox_group':
        return (
          <div className="space-y-2">
            {(field.options || []).map(opt => {
              const selected = Array.isArray(value) && value.includes(opt);
              return (
                <div
                  key={opt}
                  className="flex items-center gap-2 cursor-pointer"
                  onClick={() => {
                    const current = Array.isArray(value) ? value : [];
                    if (selected) {
                      onChange(current.filter(v => v !== opt));
                    } else {
                      onChange([...current, opt]);
                    }
                  }}
                >
                  <Checkbox checked={selected} />
                  <span className="text-sm">{opt}</span>
                </div>
              );
            })}
          </div>
        );
      
      default:
        return (
          <Input
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
          />
        );
    }
  };

  // Check visibility conditions
  // (This would need access to all form data - simplified here)
  
  return (
    <div className="space-y-1">
      {field.type !== 'checkbox' && (
        <Label className="flex items-center gap-1">
          {field.label}
          {field.required && <span className="text-red-500">*</span>}
        </Label>
      )}
      {field.helper_text && (
        <p className="text-sm text-gray-500 mb-1">{field.helper_text}</p>
      )}
      {renderField()}
      {error && <p className="text-red-500 text-sm">{error}</p>}
    </div>
  );
}

function MultiTextInput({ value, onChange, placeholder, maxItems }) {
  const [inputValue, setInputValue] = useState('');
  const items = Array.isArray(value) ? value : [];

  const addItem = () => {
    if (inputValue.trim() && items.length < maxItems) {
      onChange([...items, inputValue.trim()]);
      setInputValue('');
    }
  };

  const removeItem = (idx) => {
    onChange(items.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={placeholder}
          onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addItem())}
        />
        <Button type="button" variant="outline" onClick={addItem} disabled={items.length >= maxItems}>
          Add
        </Button>
      </div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {items.map((item, idx) => (
            <Badge key={idx} variant="secondary" className="px-2 py-1">
              {item}
              <button
                type="button"
                className="ml-1 text-gray-500 hover:text-red-500"
                onClick={() => removeItem(idx)}
              >
                ×
              </button>
            </Badge>
          ))}
        </div>
      )}
      <p className="text-xs text-gray-500">{items.length} / {maxItems}</p>
    </div>
  );
}

function ServiceFieldsStep({ schema, data, onChange, errors }) {
  // Filter out universal fields (they're in step 2)
  const serviceFields = (schema?.fields || []).filter(
    f => f.group !== 'client_identity' && f.group !== 'delivery' && f.group !== 'consent' && f.type !== 'hidden'
  );

  // Group fields by their group property
  const groups = {};
  serviceFields.forEach(field => {
    const group = field.group || 'general';
    if (!groups[group]) groups[group] = [];
    groups[group].push(field);
  });

  // Sort fields within groups by order
  Object.keys(groups).forEach(key => {
    groups[key].sort((a, b) => (a.order || 0) - (b.order || 0));
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Service Details</h2>
        <p className="text-gray-600">Provide the information needed for your order</p>
      </div>

      {Object.entries(groups).map(([groupName, fields]) => (
        <div key={groupName} className="space-y-4">
          {groupName !== 'general' && (
            <h3 className="font-medium text-gray-700 capitalize">
              {groupName.replace(/_/g, ' ')}
            </h3>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {fields.map(field => (
              <div key={field.field_key} className={field.type === 'textarea' ? 'md:col-span-2' : ''}>
                <DynamicField
                  field={field}
                  value={data[field.field_key]}
                  onChange={(val) => onChange(field.field_key, val)}
                  error={errors[field.field_key]}
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}


// ============================================================================
// STEP 4: REVIEW
// ============================================================================

function ReviewStep({ draft, clientData, intakeData, pricing, onConsentChange, consent }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Review Your Order</h2>
        <p className="text-gray-600">Please review your information before payment</p>
      </div>

      {/* Service */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Selected Service</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between items-center">
            <div>
              <p className="font-medium">{draft?.service_name || draft?.service_code}</p>
              <p className="text-sm text-gray-500">{draft?.category}</p>
            </div>
            <span className="text-lg font-bold text-teal-600">
              £{((pricing?.base_price_pence || 0) / 100).toFixed(2)}
            </span>
          </div>
          
          {pricing?.addons?.length > 0 && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-sm text-gray-500 mb-2">Add-ons:</p>
              {pricing.addons.map(addon => (
                <div key={addon.code} className="flex justify-between text-sm">
                  <span>{addon.name}</span>
                  <span>£{(addon.price_pence / 100).toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
          
          <Separator className="my-3" />
          <div className="flex justify-between font-bold text-lg">
            <span>Total</span>
            <span className="text-teal-600">
              £{((pricing?.total_price_pence || 0) / 100).toFixed(2)}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Client Details */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Your Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-gray-500">Name:</span></div>
            <div>{clientData.full_name}</div>
            <div><span className="text-gray-500">Email:</span></div>
            <div>{clientData.email}</div>
            <div><span className="text-gray-500">Phone:</span></div>
            <div>{clientData.phone}</div>
            <div><span className="text-gray-500">Role:</span></div>
            <div>{clientData.role}{clientData.role === 'Other' && `: ${clientData.role_other_text}`}</div>
          </div>
        </CardContent>
      </Card>

      {/* Consent */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Terms & Consent</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-3">
            <Checkbox
              id="terms"
              checked={consent.consent_terms_privacy || false}
              onCheckedChange={(v) => onConsentChange('consent_terms_privacy', v)}
            />
            <Label htmlFor="terms" className="text-sm leading-relaxed cursor-pointer">
              I agree to the <a href="/terms" className="text-teal-600 underline" target="_blank">Terms of Service</a> and <a href="/privacy" className="text-teal-600 underline" target="_blank">Privacy Policy</a> *
            </Label>
          </div>
          
          <div className="flex items-start gap-3">
            <Checkbox
              id="accuracy"
              checked={consent.accuracy_confirmation || false}
              onCheckedChange={(v) => onConsentChange('accuracy_confirmation', v)}
            />
            <Label htmlFor="accuracy" className="text-sm leading-relaxed cursor-pointer">
              I confirm the information provided is accurate to the best of my knowledge *
            </Label>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


// ============================================================================
// MAIN WIZARD COMPONENT
// ============================================================================

export default function UnifiedIntakeWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Service selection
  const [services, setServices] = useState([]);
  const [packs, setPacks] = useState([]);
  const [addons, setAddons] = useState([]);
  const [selectedService, setSelectedService] = useState(null);
  const [selectedAddons, setSelectedAddons] = useState([]);
  const [postalAddress, setPostalAddress] = useState({});
  
  // Draft
  const [draft, setDraft] = useState(null);
  const [schema, setSchema] = useState(null);
  
  // Form data
  const [clientData, setClientData] = useState({});
  const [intakeData, setIntakeData] = useState({});
  const [consent, setConsent] = useState({});
  const [pricing, setPricing] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});
  
  // =========================================================================
  // AUTO-SAVE: Persist wizard state to localStorage
  // =========================================================================
  const STORAGE_KEY = 'pleerity_intake_wizard_state';
  
  // Load saved state on mount
  useEffect(() => {
    try {
      const savedState = localStorage.getItem(STORAGE_KEY);
      if (savedState) {
        const parsed = JSON.parse(savedState);
        // Only restore if saved within last 24 hours
        const savedTime = parsed.savedAt || 0;
        const isRecent = (Date.now() - savedTime) < 24 * 60 * 60 * 1000;
        
        if (isRecent && parsed.currentStep) {
          // Show recovery prompt
          const shouldRestore = window.confirm(
            'You have an unfinished order. Would you like to continue where you left off?'
          );
          
          if (shouldRestore) {
            setCurrentStep(parsed.currentStep);
            setClientData(parsed.clientData || {});
            setIntakeData(parsed.intakeData || {});
            setConsent(parsed.consent || {});
            setSelectedAddons(parsed.selectedAddons || []);
            setPostalAddress(parsed.postalAddress || {});
            setDraftId(parsed.draftId || null);
            
            // Service will be restored via URL param or saved service code
            if (parsed.selectedServiceCode) {
              setSearchParams({ service: parsed.selectedServiceCode }, { replace: true });
            }
            
            toast.success('Progress restored! You can continue where you left off.');
          } else {
            // User chose not to restore - clear saved state
            localStorage.removeItem(STORAGE_KEY);
          }
        }
      }
    } catch (err) {
      console.error('Failed to restore wizard state:', err);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);
  
  // Save state whenever key fields change
  useEffect(() => {
    // Don't save if on step 1 with no selection, or on payment/confirmation steps
    if (currentStep <= 1 && !selectedService) return;
    if (currentStep >= 5) return; // Don't save during payment/after completion
    
    const stateToSave = {
      currentStep,
      selectedServiceCode: selectedService?.service_code,
      selectedAddons,
      clientData,
      intakeData,
      consent,
      postalAddress,
      draftId,
      savedAt: Date.now(),
    };
    
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
    } catch (err) {
      console.error('Failed to save wizard state:', err);
    }
  }, [currentStep, selectedService, selectedAddons, clientData, intakeData, consent, postalAddress, draftId]);
  
  // Clear saved state after successful order
  const clearSavedState = () => {
    localStorage.removeItem(STORAGE_KEY);
  };

  // Load services on mount
  useEffect(() => {
    const loadServices = async () => {
      try {
        const [servicesRes, packsRes] = await Promise.all([
          client.get('/intake/services'),
          client.get('/intake/packs'),
        ]);
        setServices(servicesRes.data.services || []);
        setPacks(packsRes.data.packs || []);
        setAddons(packsRes.data.addons || []);
      } catch (err) {
        console.error('Failed to load services:', err);
        toast.error('Failed to load services');
      }
    };
    loadServices();
  }, []);
  
  // Handle pre-selection via URL parameter (after services load)
  useEffect(() => {
    const preSelectedServiceCode = searchParams.get('service');
    if (preSelectedServiceCode && services.length > 0 && !selectedService) {
      const serviceMatch = services.find(s => s.service_code === preSelectedServiceCode);
      if (serviceMatch) {
        // Manually set selected service and load schema
        setSelectedService(serviceMatch);
        client.get(`/intake/schema/${serviceMatch.service_code}`)
          .then(res => setSchema(res.data))
          .catch(err => {
            console.error('Failed to load schema:', err);
            toast.error('Failed to load service details');
          });
      }
    }
  }, [services, searchParams, selectedService]);

  // Handle service selection
  const handleServiceSelect = async (service) => {
    setSelectedService(service);
    setSelectedAddons([]);
    setPostalAddress({});
    
    // Update URL with selected service code
    setSearchParams({ service: service.service_code }, { replace: true });
    
    // Load schema for this service
    try {
      const schemaRes = await client.get(`/intake/schema/${service.service_code}`);
      setSchema(schemaRes.data);
    } catch (err) {
      console.error('Failed to load schema:', err);
      toast.error('Failed to load service details');
    }
  };

  // Toggle addon
  const handleToggleAddon = (addonCode) => {
    setSelectedAddons(prev => {
      if (prev.includes(addonCode)) {
        // If removing PRINTED_COPY, clear postal address
        if (addonCode === 'PRINTED_COPY') {
          setPostalAddress({});
        }
        return prev.filter(a => a !== addonCode);
      } else {
        return [...prev, addonCode];
      }
    });
  };

  // Update postal address
  const handlePostalChange = (key, value) => {
    setPostalAddress(prev => ({ ...prev, [key]: value }));
  };

  // Create draft when moving to step 2
  const createDraft = async () => {
    try {
      setLoading(true);
      const res = await client.post('/intake/draft', {
        service_code: selectedService.service_code,
        category: selectedService.category,
      });
      setDraft(res.data);
      
      // Calculate initial pricing
      const priceRes = await client.post('/intake/calculate-price', {
        service_code: selectedService.service_code,
        addons: selectedAddons,
      });
      setPricing(priceRes.data);
      
      return res.data;
    } catch (err) {
      console.error('Failed to create draft:', err);
      toast.error('Failed to start order');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Validate current step
  const validateStep = () => {
    const errors = {};
    
    if (currentStep === 1) {
      if (!selectedService) {
        toast.error('Please select a service');
        return false;
      }
      // Validate postal address if PRINTED_COPY selected
      if (selectedAddons.includes('PRINTED_COPY')) {
        const required = ['postal_recipient_name', 'postal_address_line1', 'postal_city', 'postal_postcode', 'postal_phone'];
        for (const field of required) {
          if (!postalAddress[field]) {
            errors[field] = 'Required';
          }
        }
      }
    }
    
    if (currentStep === 2) {
      if (!clientData.full_name) errors.full_name = 'Required';
      if (!clientData.email) errors.email = 'Required';
      if (!clientData.phone) errors.phone = 'Required';
      if (!clientData.role) errors.role = 'Required';
      if (clientData.role === 'Other' && !clientData.role_other_text) {
        errors.role_other_text = 'Required';
      }
    }
    
    if (currentStep === 4) {
      if (!consent.consent_terms_privacy) {
        toast.error('Please agree to the Terms and Privacy Policy');
        return false;
      }
      if (!consent.accuracy_confirmation) {
        toast.error('Please confirm the accuracy of your information');
        return false;
      }
    }
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Save current step data
  const saveStepData = async () => {
    if (!draft) return;
    
    try {
      setLoading(true);
      
      if (currentStep === 1) {
        // Save addons if doc pack
        if (selectedService?.service_code.startsWith('DOC_PACK')) {
          await client.put(`/intake/draft/${draft.draft_id}/addons`, {
            addons: selectedAddons,
            postal_address: selectedAddons.includes('PRINTED_COPY') ? postalAddress : null,
          });
        }
      } else if (currentStep === 2) {
        await client.put(`/intake/draft/${draft.draft_id}/client-identity`, clientData);
      } else if (currentStep === 3) {
        await client.put(`/intake/draft/${draft.draft_id}/intake`, {
          intake_data: intakeData,
          merge: true,
        });
      } else if (currentStep === 4) {
        await client.put(`/intake/draft/${draft.draft_id}/delivery-consent`, consent);
      }
      
      // Refresh pricing
      const priceRes = await client.post('/intake/calculate-price', {
        service_code: selectedService.service_code,
        addons: selectedAddons,
      });
      setPricing(priceRes.data);
      
    } catch (err) {
      console.error('Failed to save step:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Navigate to next step
  const nextStep = async () => {
    if (!validateStep()) return;
    
    try {
      if (currentStep === 1 && !draft) {
        await createDraft();
      } else if (draft) {
        await saveStepData();
      }
      
      setCurrentStep(prev => Math.min(prev + 1, 5));
    } catch (err) {
      console.error('Navigation error:', err);
    }
  };

  // Navigate to previous step
  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  // Proceed to payment
  const proceedToPayment = async () => {
    if (!validateStep()) return;
    
    try {
      setLoading(true);
      
      // Save consent
      await client.put(`/intake/draft/${draft.draft_id}/delivery-consent`, consent);
      
      // Pre-checkout validation for document packs
      if (isDocumentPack(selectedService?.service_code)) {
        const validation = await validateCheckout({
          service_code: selectedService.service_code,
          selected_documents: draft?.selected_documents || [],
          variant_code: selectedAddons.includes('FAST_TRACK') ? 'fast_track' : 
                       selectedAddons.includes('PRINTED_COPY') ? 'printed' : 'standard',
        });
        
        if (!validation.valid) {
          console.error('Checkout validation failed:', validation.errors);
          toast.error(validation.errors?.[0] || 'Checkout validation failed');
          return;
        }
        
        // Log validation warnings
        if (validation.warnings?.length > 0) {
          console.warn('Checkout validation warnings:', validation.warnings);
          validation.warnings.forEach(w => toast.warning(w, { duration: 5000 }));
        }
        
        console.log('Checkout validated:', {
          service: validation.service_code,
          pack_tier: validation.pack_tier,
          documents_selected: validation.documents_selected,
        });
      }
      
      // Create checkout session
      const res = await client.post(`/intake/draft/${draft.draft_id}/checkout`, {});
      
      // Clear saved state before redirecting to payment
      clearSavedState();
      
      // Redirect to Stripe
      window.location.href = res.data.checkout_url;
      
    } catch (err) {
      console.error('Payment error:', err);
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || 'Payment failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // Render current step
  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <ServiceSelectionStep
            services={services}
            packs={packs}
            addons={addons}
            selectedService={selectedService}
            selectedAddons={selectedAddons}
            postalAddress={postalAddress}
            onSelect={handleServiceSelect}
            onToggleAddon={handleToggleAddon}
            onPostalChange={handlePostalChange}
          />
        );
      case 2:
        return (
          <ClientIdentityStep
            data={clientData}
            onChange={(key, val) => setClientData(prev => ({ ...prev, [key]: val }))}
            errors={validationErrors}
          />
        );
      case 3:
        return (
          <ServiceFieldsStep
            schema={schema}
            data={intakeData}
            onChange={(key, val) => setIntakeData(prev => ({ ...prev, [key]: val }))}
            errors={validationErrors}
          />
        );
      case 4:
        return (
          <ReviewStep
            draft={{ ...draft, service_name: selectedService?.name }}
            clientData={clientData}
            intakeData={intakeData}
            pricing={pricing}
            consent={consent}
            onConsentChange={(key, val) => setConsent(prev => ({ ...prev, [key]: val }))}
          />
        );
      case 5:
        return (
          <div className="text-center py-12">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-teal-600" />
            <p className="mt-4 text-lg text-gray-600">Redirecting to payment...</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8" data-testid="unified-intake-wizard">
      <div className="max-w-3xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Order Service</h1>
          <p className="text-gray-600 mt-1">Complete the form to place your order</p>
        </div>

        {/* Step Indicator */}
        <StepIndicator currentStep={currentStep} />

        {/* Step Content */}
        <Card className="mb-6">
          <CardContent className="p-6">
            {renderStep()}
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between">
          <Button
            variant="outline"
            onClick={prevStep}
            disabled={currentStep === 1 || loading}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          
          {currentStep < 4 ? (
            <Button
              onClick={nextStep}
              disabled={loading || (currentStep === 1 && !selectedService)}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Continue
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : currentStep === 4 ? (
            <Button
              onClick={proceedToPayment}
              disabled={loading}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CreditCard className="h-4 w-4 mr-2" />}
              Proceed to Payment
            </Button>
          ) : null}
        </div>

        {/* Draft Reference */}
        {draft && (
          <p className="text-center text-sm text-gray-500 mt-4">
            Reference: {draft.draft_ref}
          </p>
        )}
      </div>
    </div>
  );
}
