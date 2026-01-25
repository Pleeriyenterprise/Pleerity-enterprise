/**
 * ClearForm Document Creator
 * 
 * Intent-based document generation wizard.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  ArrowLeft, 
  ArrowRight,
  Loader2,
  Mail,
  AlertTriangle,
  FileUser
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { documentsApi, creditsApi } from '../api/clearformApi';
import { toast } from 'sonner';

const DOCUMENT_ICONS = {
  formal_letter: Mail,
  complaint_letter: AlertTriangle,
  cv_resume: FileUser,
};

const ClearFormCreatePage = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useClearFormAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [documentTypes, setDocumentTypes] = useState([]);
  const [selectedType, setSelectedType] = useState(null);
  const [balance, setBalance] = useState(0);
  
  const [formData, setFormData] = useState({
    intent: '',
    // Formal Letter
    recipient_name: '',
    recipient_organization: '',
    sender_name: '',
    subject: '',
    tone: 'formal',
    // Complaint Letter
    company_name: '',
    issue_date: '',
    issue_description: '',
    desired_resolution: '',
    order_reference: '',
    // CV
    full_name: '',
    job_title_target: '',
    years_experience: '',
    skills: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [types, walletData] = await Promise.all([
        documentsApi.getTypes(),
        creditsApi.getBalance(),
      ]);
      setDocumentTypes(types);
      setBalance(walletData.credit_balance);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleTypeSelect = (type) => {
    setSelectedType(type);
    setStep(2);
  };

  const handleGenerate = async () => {
    if (!selectedType) return;
    
    const cost = selectedType.credit_cost;
    if (balance < cost) {
      toast.error(`Insufficient credits. You need ${cost} credits.`);
      navigate('/clearform/credits');
      return;
    }
    
    setLoading(true);
    
    try {
      const payload = {
        document_type: selectedType.type,
        intent: formData.intent,
      };
      
      // Add type-specific fields
      if (selectedType.type === 'formal_letter') {
        Object.assign(payload, {
          recipient_name: formData.recipient_name || undefined,
          recipient_organization: formData.recipient_organization || undefined,
          sender_name: formData.sender_name || undefined,
          subject: formData.subject || undefined,
          tone: formData.tone || undefined,
        });
      } else if (selectedType.type === 'complaint_letter') {
        Object.assign(payload, {
          company_name: formData.company_name || undefined,
          issue_date: formData.issue_date || undefined,
          issue_description: formData.issue_description || undefined,
          desired_resolution: formData.desired_resolution || undefined,
          order_reference: formData.order_reference || undefined,
        });
      } else if (selectedType.type === 'cv_resume') {
        Object.assign(payload, {
          full_name: formData.full_name || undefined,
          job_title_target: formData.job_title_target || undefined,
          years_experience: formData.years_experience ? parseInt(formData.years_experience) : undefined,
          skills: formData.skills ? formData.skills.split(',').map(s => s.trim()) : undefined,
        });
      }
      
      const result = await documentsApi.generate(payload);
      
      toast.success('Document generation started!');
      await refreshUser();
      navigate(`/clearform/document/${result.document_id}`);
      
    } catch (error) {
      toast.error(error.message || 'Failed to generate document');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">Balance:</span>
            <span className="font-medium">{balance} credits</span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="container mx-auto px-4 py-8 max-w-3xl">
        <Button 
          variant="ghost" 
          className="mb-6" 
          onClick={() => step === 1 ? navigate('/clearform/dashboard') : setStep(1)}
        >
          <ArrowLeft className="w-4 h-4 mr-2" /> Back
        </Button>

        {/* Step 1: Select Type */}
        {step === 1 && (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Create New Document</h1>
            <p className="text-slate-600 mb-8">What type of document do you need?</p>
            
            <div className="grid gap-4">
              {documentTypes.map((type) => {
                const Icon = DOCUMENT_ICONS[type.type] || FileText;
                return (
                  <Card 
                    key={type.type} 
                    className="cursor-pointer hover:border-emerald-300 hover:shadow-md transition-all"
                    onClick={() => handleTypeSelect(type)}
                    data-testid={`select-type-${type.type}`}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
                            <Icon className="w-6 h-6 text-emerald-600" />
                          </div>
                          <div>
                            <CardTitle>{type.name}</CardTitle>
                            <CardDescription>{type.description}</CardDescription>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-emerald-600">{type.credit_cost}</span>
                          <span className="text-sm text-slate-500 ml-1">credit{type.credit_cost > 1 ? 's' : ''}</span>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Step 2: Enter Details */}
        {step === 2 && selectedType && (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">{selectedType.name}</h1>
            <p className="text-slate-600 mb-8">Tell us about your document</p>
            
            <Card>
              <CardContent className="pt-6 space-y-6">
                {/* Intent - Always Required */}
                <div className="space-y-2">
                  <Label htmlFor="intent">What do you need this document for? *</Label>
                  <Textarea
                    id="intent"
                    name="intent"
                    value={formData.intent}
                    onChange={handleChange}
                    placeholder="Describe what you want to achieve with this document..."
                    rows={3}
                    required
                    data-testid="intent-input"
                  />
                  <p className="text-xs text-slate-500">Be specific - the more detail you provide, the better the result.</p>
                </div>

                {/* Formal Letter Fields */}
                {selectedType.type === 'formal_letter' && (
                  <>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="recipient_name">Recipient Name</Label>
                        <Input
                          id="recipient_name"
                          name="recipient_name"
                          value={formData.recipient_name}
                          onChange={handleChange}
                          placeholder="John Doe"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="recipient_organization">Organization</Label>
                        <Input
                          id="recipient_organization"
                          name="recipient_organization"
                          value={formData.recipient_organization}
                          onChange={handleChange}
                          placeholder="ABC Company Ltd"
                        />
                      </div>
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="sender_name">Your Name</Label>
                        <Input
                          id="sender_name"
                          name="sender_name"
                          value={formData.sender_name}
                          onChange={handleChange}
                          placeholder="Jane Smith"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="subject">Subject</Label>
                        <Input
                          id="subject"
                          name="subject"
                          value={formData.subject}
                          onChange={handleChange}
                          placeholder="Regarding your inquiry"
                        />
                      </div>
                    </div>
                  </>
                )}

                {/* Complaint Letter Fields */}
                {selectedType.type === 'complaint_letter' && (
                  <>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="company_name">Company Name *</Label>
                        <Input
                          id="company_name"
                          name="company_name"
                          value={formData.company_name}
                          onChange={handleChange}
                          placeholder="TechStore Ltd"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="issue_date">Issue Date</Label>
                        <Input
                          id="issue_date"
                          name="issue_date"
                          value={formData.issue_date}
                          onChange={handleChange}
                          placeholder="January 15, 2026"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="issue_description">Issue Description</Label>
                      <Textarea
                        id="issue_description"
                        name="issue_description"
                        value={formData.issue_description}
                        onChange={handleChange}
                        placeholder="Describe what went wrong..."
                        rows={2}
                      />
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="desired_resolution">Desired Resolution</Label>
                        <Input
                          id="desired_resolution"
                          name="desired_resolution"
                          value={formData.desired_resolution}
                          onChange={handleChange}
                          placeholder="Full refund"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="order_reference">Order/Reference Number</Label>
                        <Input
                          id="order_reference"
                          name="order_reference"
                          value={formData.order_reference}
                          onChange={handleChange}
                          placeholder="ORD-12345"
                        />
                      </div>
                    </div>
                  </>
                )}

                {/* CV Fields */}
                {selectedType.type === 'cv_resume' && (
                  <>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="full_name">Full Name *</Label>
                        <Input
                          id="full_name"
                          name="full_name"
                          value={formData.full_name}
                          onChange={handleChange}
                          placeholder="John Smith"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="job_title_target">Target Role</Label>
                        <Input
                          id="job_title_target"
                          name="job_title_target"
                          value={formData.job_title_target}
                          onChange={handleChange}
                          placeholder="Senior Software Engineer"
                        />
                      </div>
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="years_experience">Years of Experience</Label>
                        <Input
                          id="years_experience"
                          name="years_experience"
                          type="number"
                          value={formData.years_experience}
                          onChange={handleChange}
                          placeholder="5"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="skills">Key Skills (comma-separated)</Label>
                        <Input
                          id="skills"
                          name="skills"
                          value={formData.skills}
                          onChange={handleChange}
                          placeholder="Python, JavaScript, Leadership"
                        />
                      </div>
                    </div>
                  </>
                )}

                {/* Generate Button */}
                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="text-sm">
                    <span className="text-slate-500">Cost:</span>{' '}
                    <span className="font-bold text-emerald-600">{selectedType.credit_cost} credit{selectedType.credit_cost > 1 ? 's' : ''}</span>
                  </div>
                  <Button 
                    onClick={handleGenerate} 
                    disabled={loading || !formData.intent}
                    className="gap-2"
                    data-testid="generate-btn"
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ArrowRight className="w-4 h-4" />
                    )}
                    Generate Document
                  </Button>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </main>
    </div>
  );
};

export default ClearFormCreatePage;
