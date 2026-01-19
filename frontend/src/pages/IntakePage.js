import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { intakeAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle } from 'lucide-react';

const IntakePage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    company_name: '',
    client_type: 'INDIVIDUAL',
    preferred_contact: 'EMAIL',
    billing_plan: 'PLAN_1',
    properties: [{ address_line_1: '', address_line_2: '', city: '', postcode: '', property_type: 'residential', number_of_units: 1 }],
    consent_data_processing: false,
    consent_communications: false
  });

  const addProperty = () => {
    setFormData({
      ...formData,
      properties: [...formData.properties, { address_line_1: '', address_line_2: '', city: '', postcode: '', property_type: 'residential', number_of_units: 1 }]
    });
  };

  const updateProperty = (index, field, value) => {
    const updatedProperties = [...formData.properties];
    updatedProperties[index][field] = value;
    setFormData({ ...formData, properties: updatedProperties });
  };

  const removeProperty = (index) => {
    if (formData.properties.length > 1) {
      const updatedProperties = formData.properties.filter((_, i) => i !== index);
      setFormData({ ...formData, properties: updatedProperties });
    }
  };

  const handleSubmit = async () => {
    setError('');
    
    if (!formData.consent_data_processing || !formData.consent_communications) {
      setError('Please accept all required consents');
      return;
    }

    setLoading(true);

    try {
      const response = await intakeAPI.submit(formData);
      const { client_id } = response.data;
      
      // Store client_id for post-checkout redirect
      localStorage.setItem('pending_client_id', client_id);
      
      // Create checkout session
      const checkoutResponse = await intakeAPI.createCheckout(client_id);
      window.location.href = checkoutResponse.data.checkout_url;
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit intake form');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-midnight-blue">Get Started with Compliance Vault Pro</CardTitle>
            <p className="text-gray-600">Step {step} of 3</p>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {step === 1 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-midnight-blue mb-4">Your Details</h3>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium">Full Name *</label>
                  <Input
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    placeholder="John Smith"
                    required
                    data-testid="full-name-input"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Email *</label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="john@example.com"
                    required
                    data-testid="email-input"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Phone</label>
                  <Input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    placeholder="+44 7700 900000"
                    data-testid="phone-input"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">I am a... *</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    value={formData.client_type}
                    onChange={(e) => setFormData({ ...formData, client_type: e.target.value })}
                    data-testid="client-type-select"
                  >
                    <option value="INDIVIDUAL">Individual Landlord</option>
                    <option value="COMPANY">Property Company</option>
                    <option value="AGENT">Letting Agent</option>
                  </select>
                </div>

                {(formData.client_type === 'COMPANY' || formData.client_type === 'AGENT') && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Company Name</label>
                    <Input
                      value={formData.company_name}
                      onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                      placeholder="ABC Properties Ltd"
                      data-testid="company-name-input"
                    />
                  </div>
                )}

                <Button onClick={() => setStep(2)} className="btn-primary w-full" data-testid="next-btn-step1">
                  Next: Add Properties
                </Button>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-midnight-blue mb-4">Your Properties</h3>
                
                {formData.properties.map((property, index) => (
                  <Card key={index} className="border border-gray-200">
                    <CardContent className="pt-6 space-y-3">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="font-medium">Property {index + 1}</h4>
                        {formData.properties.length > 1 && (
                          <Button variant="ghost" size="sm" onClick={() => removeProperty(index)}>
                            Remove
                          </Button>
                        )}
                      </div>

                      <Input
                        value={property.address_line_1}
                        onChange={(e) => updateProperty(index, 'address_line_1', e.target.value)}
                        placeholder="Address Line 1 *"
                        required
                        data-testid={`property-${index}-address1`}
                      />

                      <Input
                        value={property.address_line_2}
                        onChange={(e) => updateProperty(index, 'address_line_2', e.target.value)}
                        placeholder="Address Line 2"
                        data-testid={`property-${index}-address2`}
                      />

                      <div className="grid grid-cols-2 gap-3">
                        <Input
                          value={property.city}
                          onChange={(e) => updateProperty(index, 'city', e.target.value)}
                          placeholder="City *"
                          required
                          data-testid={`property-${index}-city`}
                        />

                        <Input
                          value={property.postcode}
                          onChange={(e) => updateProperty(index, 'postcode', e.target.value)}
                          placeholder="Postcode *"
                          required
                          data-testid={`property-${index}-postcode`}
                        />
                      </div>
                    </CardContent>
                  </Card>
                ))}

                <Button variant="outline" onClick={addProperty} className="w-full" data-testid="add-property-btn">
                  + Add Another Property
                </Button>

                <div className="flex gap-3">
                  <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                    Back
                  </Button>
                  <Button onClick={() => setStep(3)} className="btn-primary flex-1" data-testid="next-btn-step2">
                    Next: Choose Plan
                  </Button>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-midnight-blue mb-4">Choose Your Plan</h3>

                <div className="space-y-3">
                  <label className="flex items-start p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-electric-teal transition-smooth">
                    <input
                      type="radio"
                      name="billing_plan"
                      value="PLAN_1"
                      checked={formData.billing_plan === 'PLAN_1'}
                      onChange={(e) => setFormData({ ...formData, billing_plan: e.target.value })}
                      className="mt-1"
                      data-testid="plan-1-radio"
                    />
                    <div className="ml-3 flex-1">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold">1 Property</span>
                        <span className="text-lg font-bold text-electric-teal">£29.99/month</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">Perfect for individual landlords</p>
                    </div>
                  </label>

                  <label className="flex items-start p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-electric-teal transition-smooth">
                    <input
                      type="radio"
                      name="billing_plan"
                      value="PLAN_2_5"
                      checked={formData.billing_plan === 'PLAN_2_5'}
                      onChange={(e) => setFormData({ ...formData, billing_plan: e.target.value })}
                      className="mt-1"
                      data-testid="plan-2-5-radio"
                    />
                    <div className="ml-3 flex-1">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold">2-5 Properties</span>
                        <span className="text-lg font-bold text-electric-teal">£49.99/month</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">Most popular - includes SMS reminders</p>
                    </div>
                  </label>

                  <label className="flex items-start p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-electric-teal transition-smooth">
                    <input
                      type="radio"
                      name="billing_plan"
                      value="PLAN_6_15"
                      checked={formData.billing_plan === 'PLAN_6_15'}
                      onChange={(e) => setFormData({ ...formData, billing_plan: e.target.value })}
                      className="mt-1"
                      data-testid="plan-6-15-radio"
                    />
                    <div className="ml-3 flex-1">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold">6-15 Properties</span>
                        <span className="text-lg font-bold text-electric-teal">£79.99/month</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">For larger portfolios with compliance packs</p>
                    </div>
                  </label>
                </div>

                <div className="space-y-3 pt-4 border-t">
                  <label className="flex items-start">
                    <input
                      type="checkbox"
                      checked={formData.consent_data_processing}
                      onChange={(e) => setFormData({ ...formData, consent_data_processing: e.target.checked })}
                      className="mt-1"
                      data-testid="consent-data-checkbox"
                    />
                    <span className="ml-3 text-sm text-gray-700">
                      I consent to Pleerity Enterprise Ltd processing my data for compliance management purposes *
                    </span>
                  </label>

                  <label className="flex items-start">
                    <input
                      type="checkbox"
                      checked={formData.consent_communications}
                      onChange={(e) => setFormData({ ...formData, consent_communications: e.target.checked })}
                      className="mt-1"
                      data-testid="consent-comms-checkbox"
                    />
                    <span className="ml-3 text-sm text-gray-700">
                      I consent to receiving compliance reminders and notifications *
                    </span>
                  </label>
                </div>

                <div className="flex gap-3">
                  <Button variant="outline" onClick={() => setStep(2)} className="flex-1">
                    Back
                  </Button>
                  <Button 
                    onClick={handleSubmit} 
                    className="btn-primary flex-1" 
                    disabled={loading || !formData.consent_data_processing || !formData.consent_communications}
                    data-testid="submit-btn"
                  >
                    {loading ? 'Processing...' : 'Proceed to Payment'}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default IntakePage;
