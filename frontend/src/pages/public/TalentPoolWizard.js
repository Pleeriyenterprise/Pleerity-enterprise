import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { ArrowRight, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';

const TalentPoolWizard = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    country: '',
    linkedin_url: '',
    phone: '',
    interest_areas: [],
    other_interest_text: '',
    professional_summary: '',
    years_experience: '',
    skills_tools: [],
    other_skills_text: '',
    availability: '',
    work_style: [],
    consent_accepted: false,
  });

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const interestOptions = [
    'AI Workflow Automation',
    'Compliance & Documentation',
    'Market Research & Analysis',
    'Operations / Admin',
    'Engineering / Technical',
    'Front End / Back End Development',
    'Other'
  ];

  const skillsOptions = [
    'AI tools',
    'Automation tools',
    'Google Workspace',
    'Microsoft 365',
    'Zoho',
    'Documentation & compliance',
    'Jira / Trello / Asana',
    'Stripe',
    'Other'
  ];

  const handleCheckbox = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].includes(value)
        ? prev[field].filter(item => item !== value)
        : [...prev[field], value]
    }));
  };

  const validateStep = (step) => {
    switch (step) {
      case 1:
        if (!formData.full_name || !formData.email || !formData.country) {
          setError('Please fill in all required fields');
          return false;
        }
        break;
      case 2:
        if (formData.interest_areas.length === 0) {
          setError('Please select at least one interest');
          return false;
        }
        break;
      case 3:
        if (!formData.professional_summary || !formData.years_experience) {
          setError('Please complete all required fields');
          return false;
        }
        break;
      case 4:
        if (!formData.availability || formData.work_style.length === 0 || !formData.consent_accepted) {
          setError('Please complete all required fields and accept consent');
          return false;
        }
        break;
    }
    setError('');
    return true;
  };

  const nextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(prev + 1, 4));
    }
  };

  const prevStep = () => {
    setError('');
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    if (!validateStep(4)) return;
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/talent-pool/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        setSubmitted(true);
      } else {
        const data = await response.json();
        setError(data.detail || 'Submission failed');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center py-20">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
              <h3 className="text-xl font-bold mb-2">Thank You!</h3>
              <p className="mb-4">Your details have been added to our Talent Pool.</p>
              <Button onClick={() => navigate('/careers')}>Back to Careers</Button>
            </CardContent>
          </Card>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <SEOHead title="Join the Talent Pool" canonicalUrl="/careers/talent-pool" />
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            {[1, 2, 3, 4].map(step => (
              <div key={step} className="flex-1 flex items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                  step <= currentStep ? 'bg-electric-teal text-white' : 'bg-gray-200 text-gray-500'
                }`}>
                  {step}
                </div>
                {step < 4 && <div className={`flex-1 h-1 mx-2 ${step < currentStep ? 'bg-electric-teal' : 'bg-gray-200'}`} />}
              </div>
            ))}
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Step {currentStep} of 4</CardTitle>
          </CardHeader>
          <CardContent>
            {currentStep === 1 && (
              <div className="space-y-4">
                <div><Label>Full Name *</Label><Input value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} /></div>
                <div><Label>Email *</Label><Input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} /></div>
                <div><Label>Country *</Label><Input value={formData.country} onChange={(e) => setFormData({...formData, country: e.target.value})} /></div>
                <div><Label>LinkedIn</Label><Input value={formData.linkedin_url} onChange={(e) => setFormData({...formData, linkedin_url: e.target.value})} /></div>
                <div><Label>Phone</Label><Input value={formData.phone} onChange={(e) => setFormData({...formData, phone: e.target.value})} /></div>
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-3">
                <Label>Select areas of interest *</Label>
                {interestOptions.map(opt => (
                  <div key={opt} className="flex items-center space-x-2">
                    <Checkbox checked={formData.interest_areas.includes(opt)} onCheckedChange={() => handleCheckbox('interest_areas', opt)} />
                    <label className="text-sm">{opt}</label>
                  </div>
                ))}
              </div>
            )}

            {currentStep === 3 && (
              <div className="space-y-4">
                <div>
                  <Label>Professional Summary *</Label>
                  <Textarea value={formData.professional_summary} onChange={(e) => setFormData({...formData, professional_summary: e.target.value})} className="min-h-[120px]" />
                </div>
                <div>
                  <Label>Years of Experience *</Label>
                  <Select value={formData.years_experience} onValueChange={(v) => setFormData({...formData, years_experience: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0-1">0-1 years</SelectItem>
                      <SelectItem value="1-2">1-2 years</SelectItem>
                      <SelectItem value="3-5">3-5 years</SelectItem>
                      <SelectItem value="6-10">6-10 years</SelectItem>
                      <SelectItem value="10+">10+ years</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {currentStep === 4 && (
              <div className="space-y-4">
                <div>
                  <Label>Skills</Label>
                  <div className="space-y-2 border rounded p-3 max-h-40 overflow-y-auto">
                    {skillsOptions.map(skill => (
                      <div key={skill} className="flex items-center space-x-2">
                        <Checkbox checked={formData.skills_tools.includes(skill)} onCheckedChange={() => handleCheckbox('skills_tools', skill)} />
                        <label className="text-sm">{skill}</label>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <Label>Availability *</Label>
                  <Select value={formData.availability} onValueChange={(v) => setFormData({...formData, availability: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Immediately">Immediately</SelectItem>
                      <SelectItem value="2 weeks">2 weeks</SelectItem>
                      <SelectItem value="1 month">1 month</SelectItem>
                      <SelectItem value="2+ months">2+ months</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Work Style *</Label>
                  <div className="space-y-2">
                    {['Remote', 'Hybrid', 'Flexible'].map(style => (
                      <div key={style} className="flex items-center space-x-2">
                        <Checkbox checked={formData.work_style.includes(style)} onCheckedChange={() => handleCheckbox('work_style', style)} />
                        <label className="text-sm">{style}</label>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="flex items-start space-x-2 pt-4 border-t">
                  <Checkbox checked={formData.consent_accepted} onCheckedChange={(c) => setFormData({...formData, consent_accepted: c})} />
                  <label className="text-sm">I understand this is not a job application. *</label>
                </div>
              </div>
            )}

            <div className="flex justify-between mt-8 pt-6 border-t">
              <Button onClick={prevStep} disabled={currentStep === 1} variant="outline">
                <ArrowLeft className="w-4 h-4 mr-2" />Back
              </Button>
              {currentStep < 4 ? (
                <Button onClick={nextStep} className="bg-electric-teal hover:bg-electric-teal/90">
                  Next<ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button onClick={handleSubmit} disabled={loading} className="bg-electric-teal hover:bg-electric-teal/90">
                  {loading ? 'Submitting...' : 'Submit'}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </PublicLayout>
  );
};

export default TalentPoolWizard;
