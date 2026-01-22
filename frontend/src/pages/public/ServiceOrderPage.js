import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Clock,
  Shield,
  Loader2,
  CreditCard,
  AlertCircle,
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ServiceOrderPage = () => {
  const { serviceCode } = useParams();
  const navigate = useNavigate();
  
  const [service, setService] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(1); // 1: Details, 2: Intake Form, 3: Review
  const [error, setError] = useState(null);
  
  // Customer details
  const [customerData, setCustomerData] = useState({
    full_name: '',
    email: '',
    phone: '',
    company: '',
  });
  
  // Intake form data
  const [intakeData, setIntakeData] = useState({});
  
  // Terms acceptance
  const [acceptTerms, setAcceptTerms] = useState(false);
  
  // Fetch service details
  useEffect(() => {
    const fetchService = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/public/services/${serviceCode}`);
        
        if (!response.ok) {
          throw new Error('Service not found');
        }
        
        const data = await response.json();
        setService(data);
        
        // Initialize intake data with defaults
        const initialIntake = {};
        (data.intake_fields || []).forEach(field => {
          if (field.default_value !== undefined) {
            initialIntake[field.field_id] = field.default_value;
          } else {
            initialIntake[field.field_id] = '';
          }
        });
        setIntakeData(initialIntake);
        
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (serviceCode) {
      fetchService();
    }
  }, [serviceCode]);
  
  // Format price
  const formatPrice = (pence) => {
    if (!pence || pence === 0) return 'Included';
    return `£${(pence / 100).toFixed(2)}`;
  };
  
  // Validate step
  const validateStep = (stepNum) => {
    if (stepNum === 1) {
      if (!customerData.full_name.trim()) {
        toast.error('Please enter your full name');
        return false;
      }
      if (!customerData.email.trim() || !customerData.email.includes('@')) {
        toast.error('Please enter a valid email address');
        return false;
      }
    }
    
    if (stepNum === 2) {
      const requiredFields = (service?.intake_fields || []).filter(f => f.required);
      for (const field of requiredFields) {
        if (!intakeData[field.field_id] || intakeData[field.field_id] === '') {
          toast.error(`Please fill in: ${field.label}`);
          return false;
        }
      }
    }
    
    return true;
  };
  
  // Handle next step
  const handleNextStep = () => {
    if (validateStep(step)) {
      setStep(step + 1);
    }
  };
  
  // Handle submit order
  const handleSubmitOrder = async () => {
    if (!acceptTerms) {
      toast.error('Please accept the terms and conditions');
      return;
    }
    
    setSubmitting(true);
    
    try {
      // Create order
      const orderResponse = await fetch(`${API_URL}/api/orders/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          order_type: 'service_order',
          service_code: service.service_code,
          service_name: service.service_name,
          service_category: service.category,
          customer_email: customerData.email,
          customer_name: customerData.full_name,
          customer_phone: customerData.phone || null,
          customer_company: customerData.company || null,
          parameters: intakeData,
          base_price: service.price_amount,
          vat_amount: Math.round(service.price_amount * 0.2), // 20% VAT
          sla_hours: service.turnaround_hours || 48,
        }),
      });
      
      if (!orderResponse.ok) {
        throw new Error('Failed to create order');
      }
      
      const orderData = await orderResponse.json();
      
      // Create checkout session
      const checkoutResponse = await fetch(`${API_URL}/api/orders/${orderData.order_id}/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          success_url: `${window.location.origin}/order-success?order_id=${orderData.order_id}`,
          cancel_url: `${window.location.origin}/order/${serviceCode}`,
        }),
      });
      
      if (!checkoutResponse.ok) {
        throw new Error('Failed to create checkout session');
      }
      
      const checkoutData = await checkoutResponse.json();
      
      // Redirect to Stripe
      if (checkoutData.checkout_url) {
        window.location.href = checkoutData.checkout_url;
      } else {
        throw new Error('No checkout URL received');
      }
      
    } catch (err) {
      console.error('Order error:', err);
      toast.error('Failed to process order. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };
  
  // Render intake field
  const renderIntakeField = (field) => {
    const value = intakeData[field.field_id] || '';
    
    const handleChange = (newValue) => {
      setIntakeData(prev => ({
        ...prev,
        [field.field_id]: newValue,
      }));
    };
    
    switch (field.field_type) {
      case 'text':
      case 'address':
        return (
          <Input
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.placeholder || ''}
          />
        );
      
      case 'textarea':
        return (
          <Textarea
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.placeholder || ''}
            rows={4}
          />
        );
      
      case 'number':
        return (
          <Input
            type="number"
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.placeholder || ''}
            min={field.min_value}
            max={field.max_value}
          />
        );
      
      case 'date':
        return (
          <Input
            type="date"
            value={value}
            onChange={(e) => handleChange(e.target.value)}
          />
        );
      
      case 'select':
        return (
          <Select value={value} onValueChange={handleChange}>
            <SelectTrigger>
              <SelectValue placeholder={field.placeholder || 'Select an option'} />
            </SelectTrigger>
            <SelectContent>
              {(field.options || []).map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      
      case 'multi_select':
        const selectedValues = value ? value.split(',') : [];
        return (
          <div className="space-y-2">
            {(field.options || []).map((option) => (
              <div key={option} className="flex items-center space-x-2">
                <Checkbox
                  checked={selectedValues.includes(option)}
                  onCheckedChange={(checked) => {
                    const newValues = checked
                      ? [...selectedValues, option]
                      : selectedValues.filter(v => v !== option);
                    handleChange(newValues.join(','));
                  }}
                />
                <label className="text-sm">{option}</label>
              </div>
            ))}
          </div>
        );
      
      case 'checkbox':
        return (
          <div className="flex items-center space-x-2">
            <Checkbox
              checked={value === 'true' || value === true}
              onCheckedChange={(checked) => handleChange(checked ? 'true' : 'false')}
            />
            <label className="text-sm">{field.label}</label>
          </div>
        );
      
      default:
        return (
          <Input
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.placeholder || ''}
          />
        );
    }
  };
  
  if (loading) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-electric-teal" />
        </div>
      </PublicLayout>
    );
  }
  
  if (error || !service) {
    return (
      <PublicLayout>
        <section className="py-32 text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-midnight-blue mb-4">Service Not Found</h1>
          <p className="text-gray-600 mb-8">{error || 'The service you are looking for does not exist.'}</p>
          <Button asChild>
            <Link to="/services/catalogue">View All Services</Link>
          </Button>
        </section>
      </PublicLayout>
    );
  }
  
  const totalPrice = service.price_amount + Math.round(service.price_amount * 0.2);
  const hasIntakeFields = service.intake_fields && service.intake_fields.length > 0;
  const maxSteps = hasIntakeFields ? 3 : 2;
  
  return (
    <PublicLayout>
      <SEOHead
        title={`Order ${service.service_name} - Pleerity Enterprise`}
        description={service.description}
        canonicalUrl={`/order/${serviceCode}`}
      />
      
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Progress Steps */}
          <div className="mb-8">
            <div className="flex items-center justify-center space-x-4">
              {[1, 2, 3].slice(0, maxSteps).map((s) => (
                <React.Fragment key={s}>
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                    step >= s ? 'bg-electric-teal text-white' : 'bg-gray-200 text-gray-500'
                  }`}>
                    {step > s ? <CheckCircle2 className="h-5 w-5" /> : s}
                  </div>
                  {s < maxSteps && (
                    <div className={`w-16 h-1 ${step > s ? 'bg-electric-teal' : 'bg-gray-200'}`} />
                  )}
                </React.Fragment>
              ))}
            </div>
            <div className="flex justify-center mt-2 text-sm text-gray-500">
              <span className={step === 1 ? 'text-electric-teal font-medium' : ''}>Your Details</span>
              {hasIntakeFields && (
                <>
                  <span className="mx-4">→</span>
                  <span className={step === 2 ? 'text-electric-teal font-medium' : ''}>Service Details</span>
                </>
              )}
              <span className="mx-4">→</span>
              <span className={step === maxSteps ? 'text-electric-teal font-medium' : ''}>Review & Pay</span>
            </div>
          </div>
          
          {/* Service Summary Card */}
          <Card className="mb-8 border-0 shadow-lg">
            <CardHeader className="bg-midnight-blue text-white rounded-t-lg">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xl">{service.service_name}</CardTitle>
                  <CardDescription className="text-gray-300">{service.description}</CardDescription>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold">{formatPrice(service.price_amount)}</p>
                  <p className="text-sm text-gray-300">+ VAT</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-4">
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <Clock className="h-4 w-4" />
                  <span>{service.turnaround_hours || 48} hour delivery</span>
                </div>
                <div className="flex items-center gap-1">
                  <FileText className="h-4 w-4" />
                  <span>{(service.documents_generated || []).length} documents</span>
                </div>
                <div className="flex items-center gap-1">
                  <Shield className="h-4 w-4" />
                  <span>Expert reviewed</span>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Step 1: Customer Details */}
          {step === 1 && (
            <Card className="border-0 shadow-lg" data-testid="customer-details-form">
              <CardHeader>
                <CardTitle>Your Details</CardTitle>
                <CardDescription>Tell us a bit about yourself</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full Name *</Label>
                    <Input
                      id="full_name"
                      value={customerData.full_name}
                      onChange={(e) => setCustomerData({...customerData, full_name: e.target.value})}
                      placeholder="John Smith"
                      data-testid="input-full-name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address *</Label>
                    <Input
                      id="email"
                      type="email"
                      value={customerData.email}
                      onChange={(e) => setCustomerData({...customerData, email: e.target.value})}
                      placeholder="john@example.com"
                      data-testid="input-email"
                    />
                  </div>
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number</Label>
                    <Input
                      id="phone"
                      value={customerData.phone}
                      onChange={(e) => setCustomerData({...customerData, phone: e.target.value})}
                      placeholder="+44 7123 456789"
                      data-testid="input-phone"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Company (Optional)</Label>
                    <Input
                      id="company"
                      value={customerData.company}
                      onChange={(e) => setCustomerData({...customerData, company: e.target.value})}
                      placeholder="Your company name"
                      data-testid="input-company"
                    />
                  </div>
                </div>
                
                <div className="pt-4 flex justify-between">
                  <Button variant="outline" asChild>
                    <Link to={`/services/catalogue`}>
                      <ArrowLeft className="h-4 w-4 mr-2" />
                      Back to Services
                    </Link>
                  </Button>
                  <Button 
                    onClick={handleNextStep}
                    className="bg-electric-teal hover:bg-electric-teal/90"
                    data-testid="btn-next-step"
                  >
                    Continue
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Step 2: Intake Form (if has fields) */}
          {step === 2 && hasIntakeFields && (
            <Card className="border-0 shadow-lg" data-testid="intake-form">
              <CardHeader>
                <CardTitle>Service Details</CardTitle>
                <CardDescription>Provide the information we need to complete your order</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {service.intake_fields.map((field) => (
                  <div key={field.field_id} className="space-y-2">
                    <Label htmlFor={field.field_id}>
                      {field.label} {field.required && <span className="text-red-500">*</span>}
                    </Label>
                    {renderIntakeField(field)}
                    {field.help_text && (
                      <p className="text-xs text-gray-500">{field.help_text}</p>
                    )}
                  </div>
                ))}
                
                <div className="pt-4 flex justify-between">
                  <Button variant="outline" onClick={() => setStep(1)}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back
                  </Button>
                  <Button 
                    onClick={handleNextStep}
                    className="bg-electric-teal hover:bg-electric-teal/90"
                    data-testid="btn-next-step"
                  >
                    Continue to Review
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Step 3 (or 2 if no intake): Review & Pay */}
          {step === maxSteps && (
            <Card className="border-0 shadow-lg" data-testid="review-form">
              <CardHeader>
                <CardTitle>Review Your Order</CardTitle>
                <CardDescription>Please review the details before proceeding to payment</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Customer Summary */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-medium mb-2">Customer Details</h4>
                  <div className="grid sm:grid-cols-2 gap-2 text-sm">
                    <div><span className="text-gray-500">Name:</span> {customerData.full_name}</div>
                    <div><span className="text-gray-500">Email:</span> {customerData.email}</div>
                    {customerData.phone && (
                      <div><span className="text-gray-500">Phone:</span> {customerData.phone}</div>
                    )}
                    {customerData.company && (
                      <div><span className="text-gray-500">Company:</span> {customerData.company}</div>
                    )}
                  </div>
                </div>
                
                {/* Intake Summary */}
                {hasIntakeFields && Object.keys(intakeData).some(k => intakeData[k]) && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-medium mb-2">Service Details</h4>
                    <div className="space-y-1 text-sm">
                      {service.intake_fields.map((field) => {
                        const value = intakeData[field.field_id];
                        if (!value) return null;
                        return (
                          <div key={field.field_id}>
                            <span className="text-gray-500">{field.label}:</span> {value}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                
                {/* Documents Included */}
                {service.documents_generated && service.documents_generated.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-medium mb-2">Documents Included</h4>
                    <div className="space-y-1">
                      {service.documents_generated.map((doc) => (
                        <div key={doc.document_code} className="flex items-center text-sm">
                          <FileText className="h-4 w-4 text-electric-teal mr-2" />
                          {doc.document_name}
                          <Badge variant="outline" className="ml-2 text-xs uppercase">
                            {doc.format}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Pricing Summary */}
                <div className="border-t pt-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span>Subtotal</span>
                    <span>{formatPrice(service.price_amount)}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-2">
                    <span>VAT (20%)</span>
                    <span>{formatPrice(Math.round(service.price_amount * 0.2))}</span>
                  </div>
                  <div className="flex justify-between font-bold text-lg">
                    <span>Total</span>
                    <span className="text-electric-teal">{formatPrice(totalPrice)}</span>
                  </div>
                </div>
                
                {/* Terms */}
                <div className="flex items-start space-x-2">
                  <Checkbox
                    id="terms"
                    checked={acceptTerms}
                    onCheckedChange={setAcceptTerms}
                    data-testid="checkbox-terms"
                  />
                  <label htmlFor="terms" className="text-sm text-gray-600 leading-tight">
                    I agree to the{' '}
                    <Link to="/terms" className="text-electric-teal hover:underline" target="_blank">
                      Terms of Service
                    </Link>{' '}
                    and{' '}
                    <Link to="/privacy" className="text-electric-teal hover:underline" target="_blank">
                      Privacy Policy
                    </Link>
                  </label>
                </div>
                
                <div className="pt-4 flex justify-between">
                  <Button variant="outline" onClick={() => setStep(hasIntakeFields ? 2 : 1)}>
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    Back
                  </Button>
                  <Button 
                    onClick={handleSubmitOrder}
                    disabled={submitting || !acceptTerms}
                    className="bg-electric-teal hover:bg-electric-teal/90"
                    data-testid="btn-submit-order"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CreditCard className="h-4 w-4 mr-2" />
                        Proceed to Payment
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </PublicLayout>
  );
};

export default ServiceOrderPage;
